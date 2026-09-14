"""
매물 — 등록 · 목록 · 상세 · 수정 · 삭제 · 상태 · 끌올 · 사진 · 찜
"""

import base64
import json
import os
import shutil    # 업로드된 파일을 디스크에 복사
import uuid      # 겹치지 않는 파일 이름 생성
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import User, Post, PostImage, Favorite
from pydantic import BaseModel

from schemas import (
    PostCreate, PostUpdate, PostResponse, PostDetailResponse,
    PostImageResponse, StatusUpdate,
)
from deps import (
    get_db, get_current_user, get_current_user_optional,
    get_active_user, check_region,
)
from config import (
    UPLOAD_DIR, ALLOWED_EXT, MAX_IMAGE_BYTES, MAX_IMAGES_PER_POST,
    ALLOWED_STATUS, BUMP_COOLDOWN_HOURS, expand_query,
)
from korean import to_chosung, is_chosung_only
import ai_search
import image_check
import vision
import query_ai
import risk_watch
import threading
from scam import check_post_risks

router = APIRouter(tags=["매물"])




# ---------------------------------------------------------------
# 매물 등록 (로그인 필요)
# current_user 한 줄로 로그인 검사가 끝남
# ---------------------------------------------------------------
@router.post("/posts", status_code=201, response_model=PostResponse)
def create_post(
    data: PostCreate,
    db: Session = Depends(get_db),
    # 정지된 회원은 글을 못 올림
    current_user: User = Depends(get_active_user),
):
    check_region(data.region)

    # 지금 시각. 작성시각과 끌올시각을 같은 값으로 시작시킴
    now = datetime.utcnow()

    post = Post(
        seller_id=current_user.id,  # 판매자는 입력받지 않음. 토큰에서 가져옴
        title=data.title,
        content=data.content,
        price=data.price,
        category=data.category,
        region=data.region,
        place_name=data.place_name,
        # AI가 쓴 설명. 판매자 글과 섞지 않고 따로 보관
        ai_description=data.ai_description,
        # status="판매중", view_count=0 은 DB 기본값이 알아서 채움
        created_at=now,
        bumped_at=now,
    )

    # 누적 카운터 +1. 나중에 이 매물을 삭제해도 이 숫자는 안 줄어듦
    current_user.total_posts += 1

    db.add(post)
    db.commit()
    db.refresh(post)

    # 위험 신호가 겹치면 관리자에게 알림.
    # 신고를 기다리면 누군가 당한 뒤에야 알게 되므로 올라올 때 본다.
    # 별도 흐름이라 등록하는 사람은 기다리지 않음
    threading.Thread(
        target=risk_watch.check_post, args=(post.id,), daemon=True
    ).start()  # DB가 매긴 id 를 받아옴

    # 의미 검색용 벡터 만들기. 모델이 없으면 None 이 들어가고 그냥 넘어감
    post.embedding = ai_search.embed_post(post)
    db.commit()

    return post




# ---------------------------------------------------------------
# 매물 목록 조회 (로그인 불필요 - 누구나 구경 가능)
# Query(...) = 주소 뒤에 ?region=역삼동 처럼 붙는 값
# ---------------------------------------------------------------
@router.get("/posts", response_model=list[PostResponse])
def list_posts(
    region: Optional[str] = Query(None, description="동네로 거르기"),
    category: Optional[str] = Query(None, description="카테고리로 거르기"),
    keyword: Optional[str] = Query(None, description="제목·본문에서 검색"),
    skip: int = Query(0, ge=0, description="건너뛸 개수"),
    limit: int = Query(20, ge=1, le=100, description="가져올 개수"),
    db: Session = Depends(get_db),
):
    # query() 는 아직 DB에 안 감. 조건을 쌓아두기만 함
    q = db.query(Post)

    # 값이 들어온 것만 조건으로 추가
    # like("서울%") = 앞부분이 서울로 시작하는 것 전부.
    # "서울"만 오면 서울 전체, "서울 강남구"가 오면 그 구만 걸림
    if region:
        q = q.filter(Post.region.like(region + "%"))
    if category:
        q = q.filter(Post.category == category)

    # 검색어
    # 자음만 친 경우(ㅇㅇㅍ)는 SQL로 못 거름 — DB에 그런 글자가 없으니까.
    # 그래서 결과를 파이썬으로 가져와 초성을 만들어 비교함
    word = (keyword or "").strip()
    chosung_search = is_chosung_only(word)

    if word and not chosung_search:
        # 같은 말 사전으로 검색어를 넓힘.
        #   "폰"   → 폰·스마트폰·갤럭시·아이폰·S24 …
        #   "티비" → 티비·TV·텔레비전 …
        # 모델은 글자가 다르면 관계를 못 알아채는 일이 있어서,
        # 사람이 아는 관계를 사전으로 메워줌
        words = expand_query(word)

        # contains("에어") → SQL의 LIKE %에어%
        # or_ = 여러 조건 중 하나만 맞아도 통과
        conditions = []
        for w in words:
            conditions.append(Post.title.contains(w))
            conditions.append(Post.content.contains(w))

        q = q.filter(or_(*conditions))

    # 거래완료된 것과 관리자가 숨긴 것은 목록에서 뺌
    q = q.filter(Post.status != "거래완료", Post.is_hidden == False)

    # desc() = 내림차순. 최근에 끌올된 것이 위로
    q = q.order_by(Post.bumped_at.desc())

    if chosung_search:
        # 초성 검색은 SQL로 못 하므로, 조건에 맞는 것을 가져와 파이썬에서 거름.
        # 매물이 아주 많아지면 posts에 초성 칸을 따로 두는 방식으로 바꿔야 함
        rows = q.all()
        hit = [p for p in rows if to_chosung(p.title).startswith(word)]
        return hit[skip:skip + limit]

    # offset/limit = 페이징. 20개씩 끊어서 가져오기
    # .all() 이 실행되는 순간 실제로 DB에 SQL 이 날아감
    return q.offset(skip).limit(limit).all()




# ---------------------------------------------------------------
# 매물 상세 조회 (로그인 불필요)
# /posts/1 처럼 주소 뒤에 번호를 붙여서 하나만 가져옴
# ---------------------------------------------------------------
@router.get("/posts/{post_id}", response_model=PostDetailResponse)
def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    # 로그인은 선택. 안 했으면 None이 들어옴
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    # db.get(테이블, 번호) = 기본키로 한 줄 가져오기. 없으면 None
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")

    # 숨긴 매물은 판매자 본인과 관리자만 볼 수 있음
    if post.is_hidden:
        is_owner = current_user and current_user.id == post.seller_id
        is_admin = current_user and current_user.is_admin
        if not (is_owner or is_admin):
            raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")

    # 상세 화면을 열 때만 조회수를 올림 (목록에서 스쳐간 건 안 셈)
    post.view_count += 1
    db.commit()
    db.refresh(post)

    # 응답에 실을 값을 객체에 직접 붙여줌.
    # DB 칸은 아니지만 파이썬 객체라 이렇게 얹으면 그대로 응답에 나감
    post.favorite_count = len(post.favorites)
    post.is_favorited = (
        any(f.user_id == current_user.id for f in post.favorites)
        if current_user else False   # 비로그인이면 무조건 False
    )
    # 위험 신호 계산 (파일 아래쪽 사기 예방 구역에 정의됨)
    post.risk_flags = check_post_risks(post, db)

    return post




@router.patch("/posts/{post_id}", response_model=PostResponse)
def update_post(
    post_id: int,
    data: PostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")

    if post.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인 매물만 수정할 수 있습니다")

    if data.region is not None:
        check_region(data.region)

    # 보낸 칸만 골라서 덮어씀
    # place_name은 None(지우기)도 유효한 값이라 따로 처리
    changes = data.model_dump(exclude_unset=True)
    # 장소 관련 칸은 None(지우기)도 정상적인 값이라 그대로 반영함
    clearable = {"place_name", "ai_description"}
    for key, value in changes.items():
        if key in clearable or value is not None:
            setattr(post, key, value)

    # 제목·본문·카테고리가 바뀌면 뜻도 달라지므로 벡터를 다시 만듦.
    # 가격이나 장소만 고쳤으면 그대로 둠 (계산이 헛되니까)
    if any(k in changes for k in ("title", "content", "category")):
        post.embedding = ai_search.embed_post(post)

    db.commit()
    db.refresh(post)
    return post




# ---------------------------------------------------------------
# 매물 삭제 (로그인 필요 + 본인 매물만)
# 나중에 관리자 기능을 붙일 때는 users에 is_admin 칸을 추가하고
# 아래 권한 검사 한 줄에 "or current_user.is_admin" 만 더하면 됨
# ---------------------------------------------------------------
@router.delete("/posts/{post_id}", status_code=204)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")

    # 권한 검사. 나중에 관리자를 허용하려면 이 조건만 넓히면 됨
    if post.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인 매물만 삭제할 수 있습니다")

    # 1) 사진 파일을 디스크에서 먼저 지움
    # DB 행만 지우면 uploads 폴더에 주인 없는 파일이 계속 쌓임
    for image in post.images:
        file_path = image.image_url.lstrip("/")   # "/uploads/a.jpg" → "uploads/a.jpg"
        if os.path.exists(file_path):
            os.remove(file_path)

    # 2) 매물 삭제.
    # post_images와 favorites 행은 cascade 설정 덕분에 같이 지워짐
    db.delete(post)
    db.commit()




@router.patch("/posts/{post_id}/status", response_model=PostResponse)
def update_post_status(
    post_id: int,
    data: StatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")

    # 내 매물만 상태를 바꿀 수 있음
    if post.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인 매물만 변경할 수 있습니다")

    # 정해진 값만 허용. 오타로 이상한 상태가 들어가는 걸 막음
    if data.status not in ALLOWED_STATUS:
        raise HTTPException(
            status_code=400,
            detail=f"상태는 {', '.join(ALLOWED_STATUS)} 중 하나여야 합니다",
        )

    before = post.status
    after = data.status

    # 같은 값이면 아무것도 안 함 (카운터가 중복으로 오르는 걸 막음)
    if before != after:
        if after == "거래완료":
            current_user.completed_deals += 1   # 완료로 바뀔 때만 +1
        elif before == "거래완료":
            current_user.completed_deals -= 1   # 완료를 취소하면 -1

        post.status = after
        db.commit()
        db.refresh(post)

    return post




@router.post("/posts/{post_id}/bump", response_model=PostResponse)
def bump_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")

    if post.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인 매물만 끌어올릴 수 있습니다")

    if post.status == "거래완료":
        raise HTTPException(status_code=400, detail="거래완료된 매물은 끌어올릴 수 없습니다")

    now = datetime.utcnow()
    next_ok = post.bumped_at + timedelta(hours=BUMP_COOLDOWN_HOURS)

    if now < next_ok:
        # 남은 시간을 시간 단위로 올림해서 알려줌
        left = next_ok - now
        hours = int(left.total_seconds() // 3600) + 1
        # 429 = "너무 자주 요청했다"
        raise HTTPException(
            status_code=429,
            detail=f"{hours}시간 뒤에 다시 끌어올릴 수 있습니다",
        )

    post.bumped_at = now
    db.commit()
    db.refresh(post)
    return post




# ---------------------------------------------------------------
# 매물 사진 업로드 (로그인 필요 + 본인 매물만)
# UploadFile = 업로드된 파일을 다루는 FastAPI 타입
# File(...) = "이건 파일로 받겠다"는 표시. ... 은 필수라는 뜻
# ---------------------------------------------------------------
@router.post("/posts/{post_id}/images", status_code=201, response_model=PostImageResponse)
def upload_post_image(
    post_id: int,                     # 주소에 들어있는 값. /posts/1/images 면 1
    file: UploadFile = File(...),     # 업로드된 파일
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1) 매물이 있는지 확인
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")

    # 2) 내 매물인지 확인 — 남의 글에 사진을 넣으면 안 되니까
    # 403 = "누구인지는 알겠는데 권한이 없다"
    if post.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인 매물에만 사진을 올릴 수 있습니다")

    # 3) 사진 개수 제한
    if len(post.images) >= MAX_IMAGES_PER_POST:
        raise HTTPException(
            status_code=400,
            detail=f"사진은 최대 {MAX_IMAGES_PER_POST}장까지 가능합니다",
        )

    # 4) 확장자 검사
    # splitext("사진.JPG") → ("사진", ".JPG") 로 나눠줌. lower()로 소문자 통일
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"이미지 파일만 올릴 수 있습니다 ({', '.join(sorted(ALLOWED_EXT))})",
        )

    # 5) 겹치지 않는 파일 이름 만들기
    # 원본 이름을 그대로 쓰면 "사진.jpg"끼리 덮어써버림.
    # uuid4()는 매번 다른 무작위 문자열이라 충돌하지 않음
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, saved_name)

    # 6) 실제로 디스크에 저장
    # copyfileobj = 업로드된 내용을 통째로 파일에 흘려보냄
    with open(saved_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    # 7) 용량 검사 — 저장한 뒤에 크기를 재고, 너무 크면 지움
    if os.path.getsize(saved_path) > MAX_IMAGE_BYTES:
        os.remove(saved_path)
        raise HTTPException(status_code=400, detail="사진은 5MB 이하만 가능합니다")

    # 8) DB에는 경로만 기록. 파일 자체는 uploads 폴더에 있음
    image = PostImage(
        post_id=post.id,
        image_url=f"/uploads/{saved_name}",  # 웹 주소는 static 마운트(/uploads)에 맞춤. 예: /uploads/a1b2c3.jpg
        sort_order=len(post.images),              # 기존 개수 = 다음 순번 (첫 장이 0)
        # 사진의 지문. 나중에 같은 사진을 쓴 매물을 찾는 데 씀
        image_hash=image_check.make_hash(saved_path),
        # 사진에 무엇이 찍혔는지. 말로 사진을 찾을 때 씀
        image_vec=(lambda v: json.dumps(v) if v else None)(
            vision.embed_image(saved_path)
        ),
    )

    db.add(image)
    db.commit()
    db.refresh(image)

    return image




# ---------------------------------------------------------------
# 매물 사진 삭제 (로그인 필요 + 본인 매물만)
# status_code=204 : "성공했고 돌려줄 내용은 없다"
# ---------------------------------------------------------------
@router.delete("/posts/{post_id}/images/{image_id}", status_code=204)
def delete_post_image(
    post_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image = db.get(PostImage, image_id)

    # 사진이 없거나, 그 사진이 이 매물 것이 아닌 경우
    if image is None or image.post_id != post_id:
        raise HTTPException(status_code=404, detail="사진을 찾을 수 없습니다")

    post = db.get(Post, post_id)
    if post is None or post.seller_id != current_user.id:
        raise HTTPException(status_code=403, detail="본인 매물의 사진만 삭제할 수 있습니다")

    # 디스크에서도 파일을 지움. DB만 지우면 쓰레기 파일이 계속 쌓임
    # lstrip("/") : "/uploads/abc.jpg" → "uploads/abc.jpg" 로 앞의 슬래시 제거
    file_path = image.image_url.lstrip("/")
    if os.path.exists(file_path):
        os.remove(file_path)

    db.delete(image)
    db.commit()




# ===============================================================
# 사진 도용 탐지
#
# 남의 매물 사진을 그대로 가져다 쓰는 건 중고 사기의 흔한 수법.
# 사진마다 지문을 만들어두고 겹치는 것을 찾음.
#
# 같은 판매자가 자기 사진을 다시 쓰는 건 정상이라 제외함 —
# "누가 올렸는지"가 사진이 같은 것보다 중요한 판단 기준
# ===============================================================
@router.get("/posts/{post_id}/image-check")
def check_post_images(
    post_id: int,
    db: Session = Depends(get_db),
):
    """이 매물의 사진이 다른 사람 매물에도 쓰였는지 확인"""
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")

    if not image_check.is_ready():
        return {"available": False, "duplicates": []}

    found = []
    for image in post.images:
        for hit in image_check.find_duplicates(
            image.image_hash, post.id, post.seller_id, db
        ):
            found.append({"image_url": image.image_url, **hit})

    return {"available": True, "duplicates": found}



    # total_posts / completed_deals 는 일부러 줄이지 않음.
    # "누적 기록"이라 매물을 지워도 판매 이력은 남아야 함

    # 204는 본문이 없어야 해서 아무것도 return 하지 않음


# ---------------------------------------------------------------
# 찜하기 (로그인 필요)
# 이미 찜한 상태에서 또 눌러도 에러 없이 성공 처리함.
# 버튼 연타나 화면 어긋남으로 두 번 눌릴 수 있어서
# ---------------------------------------------------------------
@router.post("/posts/{post_id}/favorite", status_code=201)
def add_favorite(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")

    # 이미 찜했는지 확인
    exists = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id, Favorite.post_id == post_id)
        .first()
    )

    if exists is None:
        db.add(Favorite(user_id=current_user.id, post_id=post_id))
        db.commit()

    # 화면이 바로 반영할 수 있게 현재 상태를 돌려줌
    count = db.query(Favorite).filter(Favorite.post_id == post_id).count()
    return {"post_id": post_id, "is_favorited": True, "favorite_count": count}




# ---------------------------------------------------------------
# 찜 취소 (로그인 필요)
# 찜한 적 없는데 눌러도 에러 없이 성공 처리 (위와 같은 이유)
# ---------------------------------------------------------------
@router.delete("/posts/{post_id}/favorite")
def remove_favorite(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fav = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user.id, Favorite.post_id == post_id)
        .first()
    )

    if fav is not None:
        db.delete(fav)
        db.commit()

    count = db.query(Favorite).filter(Favorite.post_id == post_id).count()
    return {"post_id": post_id, "is_favorited": False, "favorite_count": count}




# ---------------------------------------------------------------
# 내가 올린 매물 목록 (로그인 필요)
# 주소를 /me/... 로 둔 이유:
# seller_id를 파라미터로 받으면 아무 번호나 넣어 남의 판매내역을 볼 수 있음.
# 토큰에서 "누구"를 꺼내면 남의 것을 조회할 방법 자체가 없어짐
# ---------------------------------------------------------------
@router.get("/me/posts", response_model=list[PostResponse])
def my_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 목록(/posts)과 달리 거래완료된 것도 포함함.
    # 내 판매내역에서는 팔린 물건도 보여야 하니까
    return (
        db.query(Post)
        .filter(Post.seller_id == current_user.id)
        .order_by(Post.bumped_at.desc())
        .all()
    )




# ---------------------------------------------------------------
# 내가 찜한 매물 목록 (로그인 필요)
# ---------------------------------------------------------------
@router.get("/me/favorites", response_model=list[PostResponse])
def my_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # join = 두 테이블을 이어붙임.
    # "favorites에서 내 것만 고르고, 거기 딸린 posts를 가져와라"
    return (
        db.query(Post)
        .join(Favorite, Favorite.post_id == Post.id)
        .filter(Favorite.user_id == current_user.id)
        .order_by(Favorite.created_at.desc())   # 최근에 찜한 것이 위로
        .all()
    )


# ---------------------------------------------------------------
# 사진 보고 카테고리 짐작하기
#
# 등록 화면에서 사진을 고르면 바로 불러서 카테고리를 채워줌.
# 확신이 아니라 제안이라, 사용자가 다른 걸 고르면 그게 우선
# ---------------------------------------------------------------
@router.post("/vision/guess-category")
async def guess_category(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    # 파일 검사를 먼저 — 모델이 없더라도 잘못된 파일은 같은 이유로 막아야
    # 화면이 어느 기기에서든 같은 반응을 받음
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="이미지 파일만 올릴 수 있습니다")

    if not vision.is_ready():
        return {"available": False, "guesses": []}

    # 임시 파일로 저장했다가 확인 후 지움.
    # 등록 전 미리보기 단계라 계속 갖고 있을 이유가 없음
    tmp_name = f"tmp_{uuid.uuid4().hex}{ext}"
    tmp_path = os.path.join(UPLOAD_DIR, tmp_name)

    try:
        with open(tmp_path, "wb") as out:
            shutil.copyfileobj(file.file, out)

        if os.path.getsize(tmp_path) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=400, detail="사진은 5MB 이하만 올릴 수 있습니다")

        return {"available": True, "guesses": vision.guess_category(tmp_path)}
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ---------------------------------------------------------------
# 사진 보고 설명 초안 쓰기
#
# 등록 화면의 "사진 보고 설명 써주기" 버튼이 부름.
# 5~15초 걸려서 사진을 고르는 즉시가 아니라 눌렀을 때만 돌아감
# ---------------------------------------------------------------
class DescribeResponse(BaseModel):
    available: bool
    description: Optional[str] = None


@router.post("/vision/describe", response_model=DescribeResponse)
async def describe_photo(
    file: UploadFile = File(...),
    title: str = Form("", description="판매자가 적은 제목"),
    category: str = Form("", description="고른 카테고리"),
    current_user: User = Depends(get_current_user),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="이미지 파일만 올릴 수 있습니다")

    raw = await file.read()
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="사진은 5MB 이하만 올릴 수 있습니다")

    if not query_ai.is_ready():
        return DescribeResponse(available=False)

    # Ollama 는 사진을 base64 글자로 받음
    encoded = base64.b64encode(raw).decode("ascii")

    text = query_ai.describe_image(encoded, title, category)
    if not text:
        # 모델이 답을 못 준 경우. 등록 자체는 막지 않음
        return DescribeResponse(available=True, description=None)

    return DescribeResponse(available=True, description=text)