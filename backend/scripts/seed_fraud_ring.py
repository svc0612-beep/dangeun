"""
가짜 사기 무리 만들기 — 관계 분석이 진짜로 잡는지 확인용

혼자 하는 사기와 달리, 여럿이 짜고 하면 각자는 깨끗해 보인다.
그래서 일부러 이런 무리를 만들어 본다

    ring01 · ring02 · ring03   세 계정을 몇 분 사이에 만듦
    서로에게만 물건을 팔고 사면서 5점 후기를 주고받음
    같은 사진을 돌려 씀

정상 회원(clean01)도 하나 만들어서, 그 사람은 안 걸리는지 함께 본다

실행:  python seed_fraud_ring.py
지우기: python seed_fraud_ring.py --clean
"""


# --- 이 파일은 scripts/ 안에 있지만 backend 의 파일들을 씁니다 ---
# 파이썬은 실행한 파일이 있는 폴더만 찾아보므로, 한 칸 위(backend)도
# 찾도록 알려줍니다. 이 세 줄이 없으면 "No module named 'database'" 가 납니다
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ------------------------------------------------------------------

import os
import random
import sys
import uuid
from datetime import datetime, timedelta

import bcrypt

from database import (
    SessionLocal, init_db,
    User, Post, PostImage, ChatRoom, Message, Review,
)

PREFIX = "ring"
CLEAN = "clean01"
UPLOAD_DIR = "uploads"


def make_user(db, username, nickname, region, when):
    u = User(
        username=username,
        password_hash=bcrypt.hashpw(b"pass1234", bcrypt.gensalt()).decode(),
        nickname=nickname,
        region=region,
        name="시험",
        email=f"{username}@test.local",
        phone=f"010-9{random.randint(1000000, 9999999)}",
        address="서울시 어딘가",
        created_at=when,
    )
    db.add(u)
    db.flush()
    return u


def make_post(db, seller, title, price, when, image_hash=None):
    p = Post(
        seller_id=seller.id,
        title=title,
        content="상태 좋습니다. 직거래로 만나요.",
        price=price,
        category="디지털기기",
        region=seller.region,
        created_at=when,
        bumped_at=when,
    )
    db.add(p)
    db.flush()

    if image_hash:
        # 같은 사진을 돌려 쓰는 것을 흉내냄 (지문만 같게)
        db.add(PostImage(
            post_id=p.id,
            image_url=f"/{UPLOAD_DIR}/ring_{uuid.uuid4().hex[:8]}.png",
            image_hash=image_hash,
            sort_order=0,
        ))

    seller.total_posts += 1
    return p


def make_deal(db, post, buyer, when):
    """거래를 성사시키고 서로 5점 후기를 남김"""
    room = ChatRoom(
        post_id=post.id,
        buyer_id=buyer.id,
        created_at=when,
        last_message_at=when,
        buyer_decided_at=when,
        seller_confirmed_at=when + timedelta(minutes=5),
    )
    db.add(room)
    db.flush()

    db.add(Message(room_id=room.id, sender_id=buyer.id,
                   content="구매하고 싶습니다", created_at=when))

    post.status = "거래완료"
    post.seller.completed_deals += 1
    buyer.completed_purchases += 1

    # 서로 최고점 후기
    db.add(Review(room_id=room.id, reviewer_id=buyer.id, reviewee_id=post.seller_id,
                  rating=5, tags='["친절해요"]', comment="좋은 거래였습니다",
                  created_at=when + timedelta(minutes=10)))
    db.add(Review(room_id=room.id, reviewer_id=post.seller_id, reviewee_id=buyer.id,
                  rating=5, tags='["시간 약속을 잘 지켜요"]', comment="감사합니다",
                  created_at=when + timedelta(minutes=11)))
    return room


def build(db):
    now = datetime.utcnow()
    base = now - timedelta(days=10)

    # --- 사기 무리 세 명. 몇 분 사이에 가입 ---
    ring = [
        make_user(db, "ring01", "무리하나", "서울 강남구", base),
        make_user(db, "ring02", "무리둘", "서울 강남구", base + timedelta(minutes=4)),
        make_user(db, "ring03", "무리셋", "서울 강남구", base + timedelta(minutes=9)),
    ]

    # --- 정상 회원. 따로 가입하고 여러 사람과 거래 ---
    clean = make_user(db, CLEAN, "정상회원", "서울 마포구", base - timedelta(days=40))

    db.flush()

    # 무리끼리 같은 사진을 돌려 씀
    shared = "a1b2c3d4e5f60718"

    # 서로에게만 팔고 사면서 후기를 쌓음
    plan = [
        (ring[0], ring[1], "아이폰 14 팝니다", 700000),
        (ring[1], ring[0], "갤럭시 S23 팝니다", 500000),
        (ring[0], ring[2], "맥북 에어 M2", 900000),
        (ring[2], ring[0], "아이패드 에어", 450000),
        (ring[1], ring[2], "에어팟 프로", 180000),
        (ring[2], ring[1], "갤럭시워치6", 170000),
    ]

    for i, (seller, buyer, title, price) in enumerate(plan):
        when = base + timedelta(days=i + 1)
        post = make_post(db, seller, title, price, when,
                         image_hash=shared if i % 2 == 0 else None)
        make_deal(db, post, buyer, when + timedelta(hours=2))

    # 무리 중 하나가 지금 미끼 매물을 올려둠
    make_post(db, ring[0], "아이폰 15 프로 급처분", 300000, now - timedelta(hours=3))

    # --- 정상 회원은 여러 사람과 골고루 거래 ---
    others = db.query(User).filter(User.username.like("demo%")).limit(4).all()
    for i, other in enumerate(others):
        when = base + timedelta(days=i * 3)
        post = make_post(db, clean, f"정상 매물 {i + 1}", 50000 + i * 10000, when)
        make_deal(db, post, other, when + timedelta(hours=3))

    db.commit()

    print("사기 무리 3명 (ring01~03) — 서로만 거래 · 5점 후기 교환 · 같은 사진")
    print("정상 회원 1명 (clean01) — 여러 사람과 골고루 거래")
    print("비밀번호는 모두 pass1234")


def clean_up(db):
    users = db.query(User).filter(
        (User.username.like(PREFIX + "%")) | (User.username == CLEAN)
    ).all()

    for u in users:
        # 이 사람이 올린 매물과 딸린 것들
        for p in db.query(Post).filter(Post.seller_id == u.id).all():
            db.delete(p)
        # 구매자로 참여한 방
        for r in db.query(ChatRoom).filter(ChatRoom.buyer_id == u.id).all():
            db.delete(r)
        db.query(Review).filter(
            (Review.reviewer_id == u.id) | (Review.reviewee_id == u.id)
        ).delete(synchronize_session=False)

    db.commit()

    for u in users:
        db.delete(u)
    db.commit()

    print(f"{len(users)}명과 딸린 자료를 지웠습니다.")


def main():
    init_db()
    db = SessionLocal()
    try:
        if "--clean" in sys.argv:
            clean_up(db)
            return

        if db.query(User).filter(User.username == "ring01").first():
            print("이미 있습니다. 다시 만들려면:  python seed_fraud_ring.py --clean")
            return

        build(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
