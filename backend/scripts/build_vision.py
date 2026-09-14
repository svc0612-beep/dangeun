"""
사진 벡터 만들기

서버가 켜질 때 자동으로 만들지만, 그때 모델을 아직 내려받는 중이었다면
건너뛰게 됨. 그럴 때 이걸 직접 돌리면 됨.

실행:  python build_vision.py
"""


# --- 이 파일은 scripts/ 안에 있지만 backend 의 파일들을 씁니다 ---
# 파이썬은 실행한 파일이 있는 폴더만 찾아보므로, 한 칸 위(backend)도
# 찾도록 알려줍니다. 이 세 줄이 없으면 "No module named 'database'" 가 납니다
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ------------------------------------------------------------------

import json
import os

from database import SessionLocal, PostImage
import vision


def main():
    if not vision.is_ready():
        print("사진 이해 모델을 쓸 수 없습니다. 위 메시지를 확인하세요.")
        return

    db = SessionLocal()
    try:
        todo = db.query(PostImage).filter(PostImage.image_vec.is_(None)).all()
        total = db.query(PostImage).count()

        if not todo:
            print(f"이미 다 만들어져 있습니다. (사진 {total}장)")
            return

        print(f"사진 {len(todo)}장의 벡터를 만듭니다. 1~3분 걸립니다.\n")

        done = missing = 0
        for i, image in enumerate(todo, 1):
            path = image.image_url.lstrip("/")

            if not os.path.exists(path):
                missing += 1
                continue

            vec = vision.embed_image(path)
            if vec:
                image.image_vec = json.dumps(vec)
                done += 1

            # 20장마다 중간 저장 — 도중에 멈춰도 한 것까지는 남게
            if i % 20 == 0:
                db.commit()
                print(f"  {i}/{len(todo)} 장 처리")

        db.commit()

        print(f"\n완료 — {done}장 생성", end="")
        if missing:
            print(f", 파일이 없어 건너뜀 {missing}장", end="")
        print()
        print("이제 python check_vision.py 로 확인해보세요.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
