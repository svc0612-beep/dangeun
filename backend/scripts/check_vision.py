"""
CLIP(사진 이해)이 제대로 도는지 확인

세 가지를 봄
  1) 모델이 올라왔는지, 사진 벡터가 몇 개나 준비됐는지
  2) 말로 사진 찾기 — 검색어와 사진의 점수가 제대로 갈리는지
  3) 카테고리 추천 — 실제 매물 사진으로 짐작이 맞는지

실행:  python check_vision.py
       python check_vision.py 내사진.jpg      직접 찍은 사진으로 확인
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

from database import SessionLocal, Post, PostImage
import vision


def show_ready(db):
    print("=" * 52)
    if not vision.is_ready():
        print("사진 이해 모델을 쓸 수 없습니다.")
        print("서버 로그에 [사진 이해] 로 시작하는 줄을 확인하세요.")
        return False

    total = db.query(PostImage).count()
    done = db.query(PostImage).filter(PostImage.image_vec.isnot(None)).count()
    print(f"모델 준비됨 · 사진 {total}장 중 {done}장 벡터 완료")
    if done < total:
        print("아직 만드는 중일 수 있습니다. 잠시 뒤 다시 실행해보세요.")
    print("=" * 52)
    return done > 0


def test_search(db):
    """말로 사진 찾기 — 점수가 어떻게 나오는지 눈으로 확인"""
    images = db.query(PostImage).filter(PostImage.image_vec.isnot(None)).all()

    queries = [
        "노트북", "자전거", "옷", "냉장고",
        "파란색 물건", "동그란 물건", "나무로 된 가구",
    ]

    print("\n[말로 사진 찾기]")
    print("점수는 코사인 유사도 — 절대값보다 위아래 간격이 중요합니다\n")

    for q in queries:
        hits = vision.search_images(q, images, top=3)
        print(f'  "{q}"')
        if not hits:
            print(f"     걸린 사진 없음 (문턱 {vision.MIN_SEARCH_SCORE})")
        for image, score in hits:
            post = db.get(Post, image.post_id)
            title = post.title if post else "?"
            print(f"     {score:.3f}  {title}")
        print()


def test_category(db, path=None):
    """카테고리 추천 — 정답을 아는 매물 사진으로 맞는지 확인"""
    print("[사진 보고 카테고리 짐작]")

    if path:
        print(f"\n  파일: {path}")
        for g in vision.guess_category(path):
            print(f"     {g['score']:.3f}  {g['category']}")
        return

    # 매물 사진 몇 장을 뽑아 실제 카테고리와 견줌
    rows = (
        db.query(PostImage, Post)
        .join(Post, PostImage.post_id == Post.id)
        .filter(PostImage.image_vec.isnot(None))
        .limit(60)
        .all()
    )

    seen = set()
    checked = hit = 0

    for image, post in rows:
        # 카테고리마다 한 장씩만
        if post.category in seen:
            continue
        seen.add(post.category)

        guesses = vision.guess_category(image.image_url.lstrip("/"))
        if not guesses:
            continue

        names = [g["category"] for g in guesses]
        ok = post.category in names
        checked += 1
        hit += 1 if ok else 0

        mark = "O" if ok else "  "
        print(f"\n  {mark} {post.title}")
        print(f"       실제: {post.category}")
        print(f"       짐작: " + ", ".join(
            f"{g['category']}({g['score']:.2f})" for g in guesses
        ))

    if checked:
        print(f"\n  상위 3개 안에 실제 카테고리가 든 경우: {hit}/{checked}")
        print("  ※ 더미 사진은 도형이라 낮게 나옵니다.")
        print("     실제 물건 사진으로 해보려면:  python check_vision.py 사진.jpg")


def main():
    db = SessionLocal()
    try:
        if not show_ready(db):
            return

        path = sys.argv[1] if len(sys.argv) > 1 else None
        if path:
            test_category(db, path)
        else:
            test_search(db)
            test_category(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
