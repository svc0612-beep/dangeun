"""
사진 주소(image_url) 고치기 — 한 번만 돌리는 정리 스크립트

배경
  예전 코드가 사진 주소를 웹 경로(/uploads/xxx.jpg)가 아니라
  윈도우 절대경로(/C:\\danggeun\\backend\\uploads/xxx.jpg)로 저장해서
  브라우저가 사진을 못 찾는 문제가 있었음.
  코드는 이미 고쳤고, 이 스크립트는 '이미 잘못 저장된 옛날 행'만 바로잡음.

쓰는 법
  1) 백엔드 서버를 먼저 끈다 (DB를 동시에 건드리지 않기 위해)
  2) backend 폴더에서:  python scripts/fix_image_urls.py
  3) 서버를 다시 켠다

안전장치
  · /uploads/ 로 잘 시작하는 행은 건드리지 않음
  · 실제로 뭘 바꿀지 먼저 보여주고, 물어본 뒤에 저장함
"""

import os
import sqlite3

# 이 스크립트가 있는 곳(scripts/) 기준으로 backend/danggeun.db 를 찾음
HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "..", "danggeun.db")   # scripts/ 의 한 단계 위 = backend/


def to_web_url(bad: str) -> str:
    """잘못된 주소에서 파일 이름만 뽑아 /uploads/파일명 으로 바꿈.

    예) /C:\\danggeun\\backend\\uploads/ed2c33.jpg  →  /uploads/ed2c33.jpg
    슬래시(/)든 역슬래시(\\)든 마지막 조각(파일 이름)만 취한다.
    """
    name = bad.replace("\\", "/").rstrip("/")   # 역슬래시를 슬래시로 통일
    name = name.split("/")[-1]                  # 맨 뒤 = 파일 이름
    return f"/uploads/{name}"


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # /uploads/ 로 시작하지 '않는' 행만 문제 대상
    cur.execute(
        "SELECT id, post_id, image_url FROM post_images "
        "WHERE image_url NOT LIKE '/uploads/%'"
    )
    rows = cur.fetchall()

    if not rows:
        print("고칠 게 없습니다. 모든 사진 주소가 이미 정상입니다.")
        conn.close()
        return

    # 무엇을 어떻게 바꿀지 먼저 보여줌
    print(f"바로잡을 사진 {len(rows)}개:")
    plans = []
    for img_id, post_id, old in rows:
        new = to_web_url(old)
        plans.append((img_id, new))
        print(f"  [id {img_id}, 매물 {post_id}]")
        print(f"      전: {old}")
        print(f"      후: {new}")

    # 정말 바꿀지 물어봄 (엔터=취소, 실수 방지)
    answer = input("\n이대로 저장할까요? (y/N) ").strip().lower()
    if answer != "y":
        print("취소했습니다. 아무것도 바꾸지 않았습니다.")
        conn.close()
        return

    # 저장
    for img_id, new in plans:
        cur.execute(
            "UPDATE post_images SET image_url = ? WHERE id = ?",
            (new, img_id),
        )
    conn.commit()
    conn.close()
    print(f"완료 — {len(plans)}개를 고쳤습니다. 이제 서버를 다시 켜세요.")


if __name__ == "__main__":
    main()