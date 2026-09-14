"""
거래 후기 · 공개 프로필 · 내 거래 내역
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import User, Post, ChatRoom, Review
from schemas import ReviewCreate
from deps import get_db, get_current_user
from config import (
    REVIEW_OPEN_DAYS, RATING_LABELS, GOOD_TAGS, BAD_TAGS, TEMP_DELTA,
)
from chat_core import get_room_or_404, add_system_message, notify_room

router = APIRouter(tags=["후기"])




def review_to_dict(rv: Review) -> dict:
    return {
        "id": rv.id,
        "rating": rv.rating,
        "rating_label": RATING_LABELS.get(rv.rating, ""),
        # 저장할 땐 쉼표로 이어붙였으니 꺼낼 땐 다시 쪼갬
        "tags": [t for t in (rv.tags or "").split(",") if t],
        "comment": rv.comment,
        "reviewer_nickname": rv.reviewer.nickname,
        "created_at": rv.created_at,
    }




def is_review_open(rv: Review, db: Session) -> bool:
    """공개해도 되는 후기인지.
    상대도 썼거나, 쓴 지 7일이 지났으면 공개"""
    other = (
        db.query(Review)
        .filter(Review.room_id == rv.room_id, Review.reviewer_id != rv.reviewer_id)
        .first()
    )
    if other is not None:
        return True
    return datetime.utcnow() - rv.created_at > timedelta(days=REVIEW_OPEN_DAYS)




@router.get("/review-options")
def review_options():
    """후기 화면이 별점 문구와 태그 목록을 받아감.
    서버에 두면 문구를 바꿔도 화면 코드는 안 고쳐도 됨"""
    return {
        "rating_labels": RATING_LABELS,
        "good_tags": GOOD_TAGS,
        "bad_tags": BAD_TAGS,
        "open_days": REVIEW_OPEN_DAYS,
    }




@router.post("/chats/{room_id}/review", status_code=201)
async def write_review(
    room_id: int,
    data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = get_room_or_404(room_id, db, current_user)

    # 거래가 확정된 뒤에만 쓸 수 있음
    if not (room.buyer_decided_at and room.seller_confirmed_at):
        raise HTTPException(status_code=400, detail="거래가 확정된 뒤에 후기를 남길 수 있습니다")

    dup = (
        db.query(Review)
        .filter(Review.room_id == room_id, Review.reviewer_id == current_user.id)
        .first()
    )
    if dup:
        raise HTTPException(status_code=409, detail="이미 후기를 남겼습니다")

    # 상대가 누구인지는 방에서 알 수 있음
    is_buyer = current_user.id == room.buyer_id
    partner = room.post.seller if is_buyer else room.buyer

    # 목록에 없는 태그는 버림 (화면을 고쳐서 아무 글자나 보내는 걸 막음)
    allowed = set(GOOD_TAGS + BAD_TAGS)
    tags = [t for t in data.tags if t in allowed][:5]

    review = Review(
        room_id=room_id,
        reviewer_id=current_user.id,
        reviewee_id=partner.id,
        rating=data.rating,
        tags=",".join(tags),
        comment=(data.comment or "").strip() or None,
    )
    db.add(review)

    # 매너온도 반영. 0~99 범위를 벗어나지 않게 잘라줌
    delta = TEMP_DELTA.get(data.rating, 0.0)
    partner.manner_temp = round(min(99.0, max(0.0, partner.manner_temp + delta)), 1)

    add_system_message(db, room, f"{current_user.nickname}님이 거래 후기를 남겼어요")
    db.commit()

    await notify_room(room.id, db)

    return {"message": "후기를 남겼습니다. 상대도 작성하면 서로에게 공개됩니다."}




@router.get("/users/{user_id}/reviews")
def user_reviews(
    user_id: int,
    db: Session = Depends(get_db),
):
    """그 사람이 받은 후기 중 공개된 것만"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다")

    rows = (
        db.query(Review)
        .filter(Review.reviewee_id == user_id)
        .order_by(Review.created_at.desc())
        .all()
    )
    opened = [r for r in rows if is_review_open(r, db)]

    # 평균 별점은 공개된 것만으로 계산
    avg = round(sum(r.rating for r in opened) / len(opened), 1) if opened else None

    return {
        "nickname": user.nickname,
        "manner_temp": user.manner_temp,
        "review_count": len(opened),
        "average_rating": avg,
        "reviews": [review_to_dict(r) for r in opened[:20]],
    }




# ---------------------------------------------------------------
# 공개 프로필 — 남이 볼 수 있는 정보만
#
# 후기를 매물 상세 구석에 작게 붙이면 아무도 안 봄.
# "이 사람과 거래해도 될까"를 판단할 수 있게 한 화면에 모아줌
# ---------------------------------------------------------------
@router.get("/users/{user_id}/profile")
def user_profile(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다")

    # 공개된 후기만
    rows = (
        db.query(Review)
        .filter(Review.reviewee_id == user_id)
        .order_by(Review.created_at.desc())
        .all()
    )
    opened = [r for r in rows if is_review_open(r, db)]
    avg = round(sum(r.rating for r in opened) / len(opened), 1) if opened else None

    # 별점이 몇 개씩 있는지. 막대그래프로 보여주려고
    dist = {n: 0 for n in range(1, 6)}
    for r in opened:
        dist[r.rating] += 1

    # 어떤 태그를 많이 받았는지. 많은 순으로
    tag_count: dict[str, int] = {}
    for r in opened:
        for t in (r.tags or "").split(","):
            if t:
                tag_count[t] = tag_count.get(t, 0) + 1
    top_tags = sorted(tag_count.items(), key=lambda x: -x[1])[:5]

    # 지금 팔고 있는 매물
    selling = (
        db.query(Post)
        .filter(Post.seller_id == user_id, Post.status != "거래완료")
        .order_by(Post.bumped_at.desc())
        .limit(8)
        .all()
    )

    return {
        # 실명·이메일·전화번호·집주소는 절대 넣지 않음
        "id": user.id,
        "nickname": user.nickname,
        "region": user.region,
        "manner_temp": user.manner_temp,
        "completed_deals": user.completed_deals,
        "completed_purchases": user.completed_purchases,
        "cancel_count": user.cancel_count,
        "joined_at": user.created_at,

        "average_rating": avg,
        "review_count": len(opened),
        "rating_dist": dist,
        "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
        "reviews": [review_to_dict(r) for r in opened[:20]],

        "selling": [
            {
                "id": p.id,
                "title": p.title,
                "price": p.price,
                "status": p.status,
                "thumbnail": p.images[0].image_url if p.images else None,
            }
            for p in selling
        ],
    }




# ---------------------------------------------------------------
# 내 후기 — 받은 것과 쓴 것
#
# 받은 후기도 블라인드 규칙을 따름.
# 내가 아직 안 썼으면 상대 후기를 못 봄 —
# 먼저 읽고 나서 맞대응하는 걸 막기 위함
# ---------------------------------------------------------------
@router.get("/me/reviews")
def my_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    received = (
        db.query(Review)
        .filter(Review.reviewee_id == current_user.id)
        .order_by(Review.created_at.desc())
        .all()
    )
    written = (
        db.query(Review)
        .filter(Review.reviewer_id == current_user.id)
        .order_by(Review.created_at.desc())
        .all()
    )

    opened = [r for r in received if is_review_open(r, db)]
    hidden = len(received) - len(opened)   # 아직 못 보는 개수

    avg = round(sum(r.rating for r in opened) / len(opened), 1) if opened else None

    def with_post(rv: Review) -> dict:
        d = review_to_dict(rv)
        # 어떤 물건 거래였는지 같이 보여줌
        d["post_title"] = rv.room.post.title if rv.room else None
        d["partner_nickname"] = rv.reviewee.nickname   # 쓴 후기에서는 상대가 대상자
        return d

    return {
        "average_rating": avg,
        "received_count": len(opened),
        # 상대는 썼는데 내가 안 써서 아직 못 보는 후기 수
        "hidden_count": hidden,
        "received": [with_post(r) for r in opened],
        "written": [with_post(r) for r in written],
    }




# ---------------------------------------------------------------
# 내 거래 내역 — 확정된 거래만
#
# "무엇을 누구와 거래했고, 후기를 주고받았는지"를 한 화면에서 봄.
# 판매 내역(매물 기준)과 달리 여기는 거래(상대 포함) 기준
# ---------------------------------------------------------------
@router.get("/me/deals")
def my_deals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    as_buyer = db.query(ChatRoom).filter(ChatRoom.buyer_id == current_user.id).all()
    as_seller = (
        db.query(ChatRoom)
        .join(Post, ChatRoom.post_id == Post.id)
        .filter(Post.seller_id == current_user.id)
        .all()
    )

    rooms = [
        r for r in (as_buyer + as_seller)
        # 양쪽이 다 눌러 확정된 것만
        if r.buyer_decided_at and r.seller_confirmed_at
    ]
    rooms.sort(key=lambda r: r.seller_confirmed_at or r.created_at, reverse=True)

    out = []
    for room in rooms:
        is_buyer = current_user.id == room.buyer_id
        partner = room.post.seller if is_buyer else room.buyer

        mine = (
            db.query(Review)
            .filter(Review.room_id == room.id, Review.reviewer_id == current_user.id)
            .first()
        )
        theirs = (
            db.query(Review)
            .filter(Review.room_id == room.id, Review.reviewer_id == partner.id)
            .first()
        )

        out.append({
            "room_id": room.id,
            "my_role": "buyer" if is_buyer else "seller",
            "post": {
                "id": room.post.id,
                "title": room.post.title,
                "price": room.post.price,
                "status": room.post.status,
                "thumbnail": room.post.images[0].image_url if room.post.images else None,
            },
            "partner_id": partner.id,
            "partner_nickname": partner.nickname,
            "done_at": room.seller_confirmed_at,

            # 내가 쓴 후기는 언제든 볼 수 있음
            "my_review": review_to_dict(mine) if mine else None,
            # 상대 후기는 내가 써야 보임 (블라인드)
            "their_review": (
                review_to_dict(theirs) if (theirs and mine) else None
            ),
            "their_review_waiting": bool(theirs and not mine),
        })

    return {"deals": out}




# ---------------------------------------------------------------
# 아직 후기를 안 남긴 거래
#
# 홈 화면 위쪽 배너에 씀. 거래 목록 전체를 받으면 무거워서
# 필요한 것만 추려 가볍게 돌려줌
# ---------------------------------------------------------------
@router.get("/me/pending-reviews")
def pending_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    as_buyer = db.query(ChatRoom).filter(ChatRoom.buyer_id == current_user.id).all()
    as_seller = (
        db.query(ChatRoom)
        .join(Post, ChatRoom.post_id == Post.id)
        .filter(Post.seller_id == current_user.id)
        .all()
    )

    out = []
    for room in as_buyer + as_seller:
        # 확정된 거래만
        if not (room.buyer_decided_at and room.seller_confirmed_at):
            continue
        # 이미 쓴 것은 뺌
        wrote = (
            db.query(Review)
            .filter(Review.room_id == room.id, Review.reviewer_id == current_user.id)
            .first()
        )
        if wrote:
            continue

        is_buyer = current_user.id == room.buyer_id
        partner = room.post.seller if is_buyer else room.buyer
        out.append({
            "room_id": room.id,
            "post_title": room.post.title,
            "partner_nickname": partner.nickname,
            "done_at": room.seller_confirmed_at,
        })

    # 최근 거래부터
    out.sort(key=lambda x: x["done_at"], reverse=True)
    return {"count": len(out), "pending": out}
