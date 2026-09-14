"""
의미 검색이 제대로 갈리는지 확인 + 벡터 다시 만들기

만드는 방식(제목만 쓰기)이 바뀌었으므로 기존 벡터를 새로 계산해야 함.

실행:  python check_search.py            벡터를 새로 만들고 점수를 보여줌
       python check_search.py --check    다시 만들지 않고 점수만 확인
"""


# --- 이 파일은 scripts/ 안에 있지만 backend 의 파일들을 씁니다 ---
# 파이썬은 실행한 파일이 있는 폴더만 찾아보므로, 한 칸 위(backend)도
# 찾도록 알려줍니다. 이 세 줄이 없으면 "No module named 'database'" 가 납니다
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ------------------------------------------------------------------

import json
import sys

from database import SessionLocal, Post
import ai_search


def rebuild(db):
    """만드는 방식이 바뀌었으니 전부 다시 계산"""
    posts = db.query(Post).all()
    print(f"매물 {len(posts)}개의 벡터를 다시 만듭니다…")

    done = 0
    for i, post in enumerate(posts, 1):
        vec = ai_search.embed_post(post)
        if vec:
            post.embedding = vec
            done += 1
        if i % 50 == 0:
            db.commit()
            print(f"  {i}/{len(posts)}")

    db.commit()
    print(f"완료 — {done}개\n")


def score_table(db, query: str):
    """검색어 하나에 대해 점수가 어떻게 갈리는지"""
    posts = db.query(Post).filter(Post.embedding.isnot(None)).all()

    q_vec = ai_search.embed_text(query)
    if q_vec is None:
        print("모델을 쓸 수 없습니다.")
        return

    scored = []
    for p in posts:
        try:
            scored.append((ai_search.cosine(q_vec, json.loads(p.embedding)), p.title))
        except Exception:
            continue

    scored.sort(reverse=True)

    print(f'  "{query}"')
    print(f"     제목점수 {ai_search.MIN_SCORE} 이상 + 낱말점수 "
          f"{ai_search.WORD_SCORE} 이상 + 1등의 "
          f"{int(ai_search.RELATIVE_RATIO * 100)}% 이상\n")

    cache = {}
    rows = []

    for score, title in scored[:14]:
        wscore = ai_search.word_match(q_vec, title, cache)
        rows.append((score, wscore, title))

    # 실제로 통과하는 것 계산
    ok_first = [r for r in rows if r[0] >= ai_search.MIN_SCORE
                and r[1] >= ai_search.WORD_SCORE]
    top = ok_first[0][0] if ok_first else 0

    shown = 0
    for score, wscore, title in rows:
        passed = (score >= ai_search.MIN_SCORE
                  and wscore >= ai_search.WORD_SCORE
                  and score >= top * ai_search.RELATIVE_RATIO)
        if passed:
            shown += 1
        mark = "O" if passed else "  "
        print(f"     {mark} 제목 {score:.3f} · 낱말 {wscore:.3f}   {title}")

    print(f"     → 화면에 나오는 것 {shown}개\n")


def main():
    db = SessionLocal()
    try:
        if not ai_search.is_ready():
            print("의미 검색 모델을 쓸 수 없습니다.")
            return

        if "--check" not in sys.argv:
            rebuild(db)

        print("=" * 56)
        print("검색어별 점수 — O 표시가 화면에 나오는 것")
        print("=" * 56 + "\n")

        for q in ["노트북", "스마트폰", "냉장고", "세탁기", "자전거", "겨울옷", "캠핑", "의자"]:
            score_table(db, q)

    finally:
        db.close()


if __name__ == "__main__":
    main()
