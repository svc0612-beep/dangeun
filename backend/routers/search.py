"""
검색 — 추천어 · 오타 보정 · 초성 · 의미 검색 · 인기 검색어 · 지역 목록
"""

import difflib   # 비슷한 낱말 찾기 (파이썬 기본 제공)
import re        # 글자에서 단어만 뽑아낼 때
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import User, Post, PostImage, SearchLog
from schemas import PostResponse, SearchLogCreate
from deps import get_db, get_current_user_optional
from config import (
    CATEGORIES, REGION_TREE, expand_query,
    RANK_DAYS, RANK_SIZE, RANK_MIN_COUNT, RANK_STOPWORDS,
)
from korean import to_jamo, to_chosung, is_chosung_only
import ai_search
import query_ai
import vision

router = APIRouter(tags=["검색"])




# ---------------------------------------------------------------
# 지역 목록 조회 (로그인 불필요)
# 프론트의 드롭다운이 이걸 받아서 채움.
# 목록이 서버 한 곳에만 있어서 나중에 지역을 늘려도 화면 코드는 그대로
# ---------------------------------------------------------------
@router.get("/regions")
def list_regions():
    # 프론트는 이 트리를 받아 드롭다운 두 개를 채움
    return {"regions": REGION_TREE}



    # 204는 본문이 없어야 해서 아무것도 return 하지 않음


# ---------------------------------------------------------------
# 검색어 추천 / 오타 보정
#
# 한글은 "애어푸라이키" 처럼 오타가 나면 글자가 하나도 안 겹침.
# 자모로 쪼개면 ㅇㅐㅇㅓㅍㅜㄹㅏㅇㅣㅋㅣ vs ㅇㅔㅇㅓㅍㅡㄹㅏㅇㅣㅇㅓ 로
# 절반 넘게 겹쳐서 비슷한 낱말을 찾아낼 수 있음
# (한글 도구 함수들은 파일 위쪽에 모아뒀음)
# ---------------------------------------------------------------
def collect_words(db: Session) -> list[str]:
    """등록된 매물 제목에서 검색에 쓸 만한 낱말을 모음.
    나중에 매물이 아주 많아지면 이 결과를 캐시하거나
    검색 기록을 따로 저장하는 방식으로 바꾸면 됨"""
    titles = [t[0] for t in db.query(Post.title).all()]

    words = set()
    for title in titles:
        # 한글·영문·숫자만 남기고 나머지는 공백으로. 그다음 공백으로 쪼갬
        for w in re.sub(r"[^가-힣a-zA-Z0-9]", " ", title).split():
            if len(w) >= 2:            # 한 글자짜리는 추천해봐야 의미 없음
                words.add(w)

    # 카테고리도 후보에 넣음. 매물 제목에 안 나와도 "디지털기기"를 찾을 수 있게
    words.update(CATEGORIES)

    return sorted(words)




@router.get("/suggest")
def suggest(
    q: str = Query(min_length=1, max_length=30),
    db: Session = Depends(get_db),
):
    word = q.strip()
    words = collect_words(db)

    # 0) 자음만 쳤으면 초성 검색. "ㅇㅇㅍ" → "에어프라이어"
    # 완성된 글자와는 비교 방식이 아예 달라서 여기서 갈라짐.
    # 자음만 친 건 오타가 아니라 줄임말이라 오타 보정도 하지 않음
    if is_chosung_only(word):
        hits = [w for w in words if to_chosung(w).startswith(word)]
        return {"query": word, "suggestions": hits[:8], "similar": []}

    # 같은 말 사전으로 넓힘 — "폰" 을 쳤을 때 "갤럭시" 도 추천되게
    related = expand_query(word)

    # 1) 앞글자가 같은 것 — "에어" → "에어프라이어", "에어컨"
    starts = [w for w in words if w.startswith(word) and w != word]

    # 2) 어디든 포함된 것 — "프라이" → "에어프라이어"
    contains = [w for w in words if word in w and w not in starts and w != word]

    # 3) 사전에 적힌 같은 말 중 실제 매물에 있는 것.
    #    앞부분이 맞을 때만 — "폰" 의 같은 말 "갤럭시" 로 찾을 때
    #    "갤럭시북3"(노트북)까지 딸려오지 않게 함
    for alt in related[1:]:
        low = alt.lower()
        for w in words:
            if w.lower().startswith(low) and w not in starts and w not in contains:
                contains.append(w)

    # 3) 비슷한 것 (오타 보정). 자모로 풀어서 비교
    # cutoff = 얼마나 비슷해야 통과할지. 낮추면 많이 걸리고 엉뚱한 것도 섞임
    jamo_map = {to_jamo(w): w for w in words}
    close_jamo = difflib.get_close_matches(to_jamo(word), list(jamo_map), n=5, cutoff=0.55)
    similar = [
        jamo_map[j] for j in close_jamo
        if jamo_map[j] not in starts and jamo_map[j] not in contains and jamo_map[j] != word
    ]

    return {
        "query": word,
        # 추천 목록. 앞글자 일치를 먼저, 그다음 포함
        "suggestions": (starts + contains)[:8],
        # "이걸 찾으셨나요?" 에 쓸 후보
        "similar": similar[:3],
    }




# ===============================================================
# 의미 검색
#
# 글자 검색(/posts?keyword=)은 "노트북"으로 "랩탑"을 못 찾음.
# 여기는 뜻으로 찾아서 글자가 안 겹쳐도 걸림.
#
# 기존 검색을 대체하지 않고 아래에 덧붙이는 자리 —
# 정확한 것이 위, 비슷한 것이 아래
# ===============================================================
# 주소를 /posts/similar 로 두면 /posts/{post_id} 와 부딪힘 —
# FastAPI가 "similar"를 매물 번호로 읽어버림. 그래서 /search/ 아래로 뺐음
@router.get("/search/similar", response_model=list[PostResponse])
def similar_posts(
    keyword: str = Query(min_length=1, max_length=50),
    region: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    exclude: Optional[str] = Query(None, description="이미 보여준 매물 번호들, 쉼표로 구분"),
    db: Session = Depends(get_db),
):
    if not ai_search.is_ready():
        return []          # 모델이 없는 기기에서는 조용히 빈 결과

    # 지역·카테고리는 그대로 지킴. 뜻이 비슷해도 부산 매물을 보여주면 안 되니까
    q = db.query(Post).filter(Post.status != "거래완료", Post.embedding.isnot(None))
    if region:
        q = q.filter(Post.region.like(region + "%"))
    if category:
        q = q.filter(Post.category == category)

    # 글자 검색으로 이미 나온 것은 빼서 중복을 막음
    exclude_ids = set()
    if exclude:
        for part in exclude.split(","):
            if part.strip().isdigit():
                exclude_ids.add(int(part.strip()))

    ranked = ai_search.rank_posts(keyword.strip(), q.all(), exclude_ids)
    return [post for post, _ in ranked]




@router.post("/search-logs", status_code=201)
def log_search(
    data: SearchLogCreate,
    db: Session = Depends(get_db),
    # 로그인 안 해도 기록함. 누구인지는 중복을 거르는 데만 씀
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    # 앞뒤 공백을 없애고 소문자로 통일 — "노트북 "과 "노트북"이 따로 세지 않게
    word = data.keyword.strip().lower()

    # 자음만 친 것(ㅇㅇㅍ)이나 한 글자는 순위에 의미가 없음
    if len(word) < 2 or is_chosung_only(word) or word in RANK_STOPWORDS:
        return {"logged": False}

    # 같은 사람이 같은 말을 하루에 여러 번 쳐도 한 번만 셈.
    # 이게 없으면 혼자 연타해서 1위를 만들 수 있음
    if current_user:
        since = datetime.utcnow() - timedelta(days=1)
        dup = (
            db.query(SearchLog)
            .filter(
                SearchLog.keyword == word,
                SearchLog.user_id == current_user.id,
                SearchLog.created_at >= since,
            )
            .first()
        )
        if dup:
            return {"logged": False}

    db.add(SearchLog(keyword=word, user_id=current_user.id if current_user else None))
    db.commit()
    return {"logged": True}




def count_keywords(db: Session, start: datetime, end: datetime) -> dict[str, int]:
    """어느 기간 동안 각 검색어가 몇 번 나왔는지 세어 돌려줌"""
    rows = (
        db.query(SearchLog.keyword)
        .filter(SearchLog.created_at >= start, SearchLog.created_at < end)
        .all()
    )
    counter: dict[str, int] = {}
    for (word,) in rows:
        counter[word] = counter.get(word, 0) + 1
    return counter




@router.get("/search-ranking")
def search_ranking(db: Session = Depends(get_db)):
    """인기 검색어 순위.

    change 의 뜻
      "new"  이번 주에 처음 순위에 든 말
      숫자   지난주보다 오른 계단 수 (양수면 상승, 음수면 하락, 0이면 그대로)
    """
    now = datetime.utcnow()
    this_start = now - timedelta(days=RANK_DAYS)
    prev_start = now - timedelta(days=RANK_DAYS * 2)

    this_week = count_keywords(db, this_start, now)
    prev_week = count_keywords(db, prev_start, this_start)

    def to_rank(counter: dict[str, int]) -> dict[str, int]:
        """횟수 목록을 "검색어 → 등수" 로 바꿈"""
        ordered = sorted(counter.items(), key=lambda x: (-x[1], x[0]))
        return {word: i + 1 for i, (word, _) in enumerate(ordered)}

    prev_rank = to_rank(prev_week)

    # 횟수가 같으면 가나다순 — 순위가 매번 뒤바뀌지 않게
    ranked = sorted(
        [(w, c) for w, c in this_week.items() if c >= RANK_MIN_COUNT],
        key=lambda x: (-x[1], x[0]),
    )[:RANK_SIZE]

    out = []
    for i, (word, count) in enumerate(ranked):
        rank = i + 1
        before = prev_rank.get(word)
        # 지난주에 없던 말이면 new, 있었으면 등수 차이
        change = "new" if before is None else before - rank

        out.append({
            "rank": rank,
            "keyword": word,
            "count": count,
            "change": change,
        })

    return {"period_days": RANK_DAYS, "ranking": out, "updated_at": now}


# ---------------------------------------------------------------
# 질의 해석 — 문장을 카테고리·키워드로 번역
#
#   "캠핑장 가야하는데 초보 캠퍼한테 맞는 의자랑 테이블 추천해줘"
#     → 카테고리 스포츠/레저 / 키워드 캠핑 의자, 캠핑 테이블
#
# 모델이 없는 기기에서는 available=false 만 돌려주고 끝남.
# 화면은 그때 이 구역을 아예 안 보여줌
# ---------------------------------------------------------------
@router.get("/search/interpret")
def interpret_query(
    q: str = Query(min_length=1, max_length=200, description="사용자가 친 문장"),
):
    if not query_ai.is_ready():
        return {"available": False, "result": None}

    result = query_ai.interpret(q)
    return {"available": True, "result": result}


# ---------------------------------------------------------------
# 말로 사진 찾기
#
# 제목에 없는 말로도 찾을 수 있음 —
# "파란색 자전거" 처럼 사진에 보이는 것을 적으면 그런 사진이 달린 매물이 나옴
# ---------------------------------------------------------------
@router.get("/search/by-photo", response_model=list[PostResponse])
def search_by_photo(
    q: str = Query(min_length=2, max_length=50),
    region: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    if not vision.is_ready():
        return []

    # 벡터가 있는 사진만. 지역을 골랐으면 그 지역 매물의 사진만
    rows = (
        db.query(PostImage)
        .join(Post, PostImage.post_id == Post.id)
        .filter(PostImage.image_vec.isnot(None), Post.status != "거래완료")
    )
    if region:
        rows = rows.filter(Post.region.like(region + "%"))

    hits = vision.search_images(q.strip(), rows.all())

    # 한 매물에 사진이 여러 장이면 가장 잘 맞는 것만 남기고 매물 단위로 묶음
    best: dict[int, float] = {}
    for image, score in hits:
        if score > best.get(image.post_id, 0):
            best[image.post_id] = score

    order = sorted(best, key=lambda pid: -best[pid])[:20]
    if not order:
        return []

    found = db.query(Post).filter(Post.id.in_(order)).all()
    # 점수 순서를 유지해서 돌려줌
    by_id = {p.id: p for p in found}
    return [by_id[pid] for pid in order if pid in by_id]
