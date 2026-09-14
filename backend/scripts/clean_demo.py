"""
시험용 데이터 지우기

seed_chats.py / seed_searches.py 로 만든 가짜 자료를 치웁니다.
직접 만든 계정(svc933 등)과 그 매물은 건드리지 않습니다.

지우기 전에 대화에서 배운 추천 문구를 learned_tips.json 으로 남깁니다.
대화가 사라져도 채팅창 자동완성은 계속 나옵니다.

실행:
    python clean_demo.py            무엇이 지워지는지 보여주기만 함
    python clean_demo.py --yes      실제로 지움
"""


# --- 이 파일은 scripts/ 안에 있지만 backend 의 파일들을 씁니다 ---
# 파이썬은 실행한 파일이 있는 폴더만 찾아보므로, 한 칸 위(backend)도
# 찾도록 알려줍니다. 이 세 줄이 없으면 "No module named 'database'" 가 납니다
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ------------------------------------------------------------------

import os
import sys

from database import (
    SessionLocal, init_db,
    User, Post, PostImage, Favorite, ChatRoom, Message, Review, Report, SearchLog,
)
import chat_tips

# 가짜 회원의 아이디 앞부분. seed_chats.py 가 demo00 ~ demo09 로 만듦
DEMO_PREFIX = "demo"


def count_all(db):
    """지금 DB에 뭐가 얼마나 있는지"""
    return {
        "회원": db.query(User).count(),
        "매물": db.query(Post).count(),
        "사진": db.query(PostImage).count(),
        "찜": db.query(Favorite).count(),
        "채팅방": db.query(ChatRoom).count(),
        "메시지": db.query(Message).count(),
        "후기": db.query(Review).count(),
        "신고": db.query(Report).count(),
        "검색기록": db.query(SearchLog).count(),
    }


def main():
    do_it = "--yes" in sys.argv
    init_db()
    db = SessionLocal()

    try:
        before = count_all(db)

        demo_users = db.query(User).filter(User.username.like(DEMO_PREFIX + "%")).all()
        demo_ids = [u.id for u in demo_users]

        # 가짜 회원이 올린 매물
        demo_posts = (
            db.query(Post).filter(Post.seller_id.in_(demo_ids)).all()
            if demo_ids else []
        )

        # 가짜 회원이 참여한 채팅방 (구매자로 들어간 것)
        demo_rooms = (
            db.query(ChatRoom).filter(ChatRoom.buyer_id.in_(demo_ids)).all()
            if demo_ids else []
        )

        print("=" * 46)
        print("지금 DB")
        for k, v in before.items():
            print(f"  {k:6} {v:5}개")

        print()
        print("지울 것")
        print(f"  가짜 회원   {len(demo_users):5}명  ({DEMO_PREFIX}00 ~)")
        print(f"  그 매물     {len(demo_posts):5}개  (딸린 사진·찜·채팅 포함)")
        print(f"  그 채팅방   {len(demo_rooms):5}개  (구매자로 참여한 것)")
        print(f"  검색 기록   {before['검색기록']:5}건  (전부)")
        print("=" * 46)

        if not demo_users and before["검색기록"] == 0:
            print("지울 시험용 자료가 없습니다.")
            return

        if not do_it:
            print()
            print("실제로 지우려면:  python clean_demo.py --yes")
            return

        # 1) 지우기 전에 추천 문구를 파일로 남김
        print()
        print("추천 문구를 먼저 저장합니다…")
        chat_tips.rebuild_tips(db)
        chat_tips.save_tips()

        # 2) 매물 삭제 — 사진 파일도 디스크에서 지움
        for post in demo_posts:
            for image in post.images:
                path = image.image_url.lstrip("/")
                if os.path.exists(path):
                    os.remove(path)
            # 사진·찜·채팅방은 cascade 설정으로 함께 사라짐
            db.delete(post)

        # 3) 구매자로 참여한 채팅방 (매물은 남의 것이라 위에서 안 지워짐)
        for room in demo_rooms:
            db.delete(room)

        # 4) 가짜 회원이 쓴 후기·신고·찜
        if demo_ids:
            db.query(Review).filter(
                (Review.reviewer_id.in_(demo_ids)) | (Review.reviewee_id.in_(demo_ids))
            ).delete(synchronize_session=False)
            db.query(Report).filter(
                Report.reporter_id.in_(demo_ids)
            ).delete(synchronize_session=False)
            db.query(Favorite).filter(
                Favorite.user_id.in_(demo_ids)
            ).delete(synchronize_session=False)

        # 5) 검색 기록은 전부 (실제 검색도 몇 건뿐이고 곧 다시 쌓임)
        db.query(SearchLog).delete()

        db.commit()

        # 6) 마지막에 회원 삭제 — 위에서 참조를 다 끊어둠
        for user in demo_users:
            db.delete(user)
        db.commit()

        after = count_all(db)
        print()
        print("=" * 46)
        print("정리 끝")
        for k in before:
            print(f"  {k:6} {before[k]:5} → {after[k]:5}")
        print("=" * 46)
        print()
        print("추천 문구는 learned_tips.json 에 남아 있어 채팅창에 계속 나옵니다.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
