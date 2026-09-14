"""
관계 분석 — 여럿이 짜고 하는 사기 찾기

혼자 하는 사기는 매물·이력만 봐도 잡힌다.
그런데 여럿이 나눠서 하면 각자는 깨끗해 보인다.

    A가 매물을 올린다        → 겉보기엔 정상
    B가 사서 5점 후기를 쓴다  → 겉보기엔 정상
    C가 그 후기를 믿고 산다   → 당한다

A만 조사하면 아무 문제가 없다. **관계를 봐야 보이는 것**이다.

무엇으로 이어져 있는지는 DB에 남아 있다
  · 누구와 거래했나        chat_rooms
  · 누구에게 후기를 썼나    reviews
  · 언제 가입했나          users.created_at
  · 같은 사진을 썼나       post_images.image_hash

완벽하지 않다. "서로만 거래" 같은 강한 신호는 잡히지만,
조심스럽게 활동하는 무리는 놓칠 수 있다.
목표는 "확실히 잡기" 가 아니라 "관리자가 볼 만한 것을 올려주기"
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from database import User, Post, PostImage, ChatRoom, Review


# ---------------------------------------------------------------
# 판단 기준
# ---------------------------------------------------------------

# 두 사람이 이만큼 거래했으면 "자주" 로 봄
CLOSE_DEALS = 3

# 전체 거래 중 한 사람과의 거래가 이 비율을 넘으면 "그 사람하고만" 으로 봄
ONLY_RATIO = 0.7

# 가입 시각이 이 안에 몰려 있으면 함께 만든 계정일 수 있음
SAME_SIGNUP_MINUTES = 30

# 후기 점수가 이 이상만 오갔으면 서로 띄워주기로 봄
HIGH_RATING = 5


def _deal_partners(user_id: int, db: Session) -> Counter:
    """이 사람이 거래를 마친 상대들. 상대 번호 → 횟수"""
    partners = Counter()

    # 내가 판 것
    rooms = (
        db.query(ChatRoom)
        .join(Post, ChatRoom.post_id == Post.id)
        .filter(Post.seller_id == user_id, ChatRoom.seller_confirmed_at.isnot(None))
        .all()
    )
    for r in rooms:
        partners[r.buyer_id] += 1

    # 내가 산 것
    rooms = (
        db.query(ChatRoom)
        .filter(ChatRoom.buyer_id == user_id, ChatRoom.seller_confirmed_at.isnot(None))
        .all()
    )
    for r in rooms:
        if r.post:
            partners[r.post.seller_id] += 1

    partners.pop(user_id, None)      # 혹시 모를 자기 자신 제외
    return partners


def _review_pairs(user_id: int, db: Session) -> dict:
    """이 사람과 후기를 주고받은 상대들.
    상대 번호 → {"준것": [별점들], "받은것": [별점들]}"""
    out = defaultdict(lambda: {"준것": [], "받은것": []})

    for r in db.query(Review).filter(Review.reviewer_id == user_id).all():
        out[r.reviewee_id]["준것"].append(r.rating)

    for r in db.query(Review).filter(Review.reviewee_id == user_id).all():
        out[r.reviewer_id]["받은것"].append(r.rating)

    out.pop(user_id, None)
    return dict(out)


def _shared_images(user_id: int, db: Session) -> list:
    """이 사람의 사진을 다른 사람도 쓰고 있는지"""
    my_hashes = {
        img.image_hash
        for img in (
            db.query(PostImage)
            .join(Post, PostImage.post_id == Post.id)
            .filter(Post.seller_id == user_id, PostImage.image_hash.isnot(None))
            .all()
        )
    }
    if not my_hashes:
        return []

    found = defaultdict(list)
    rows = (
        db.query(PostImage, Post)
        .join(Post, PostImage.post_id == Post.id)
        .filter(
            PostImage.image_hash.in_(my_hashes),
            Post.seller_id != user_id,
        )
        .all()
    )
    for img, post in rows:
        found[post.seller_id].append(post.title)

    return [
        {"상대번호": uid, "겹친매물": titles[:3], "건수": len(titles)}
        for uid, titles in found.items()
    ]


def find_group(user_id: int, db: Session) -> dict:
    """이 사람이 누구와 어떻게 이어져 있는지 훑어본다"""
    me = db.get(User, user_id)
    if me is None:
        return {"오류": "그런 회원이 없습니다"}

    partners = _deal_partners(user_id, db)
    total_deals = sum(partners.values())
    reviews = _review_pairs(user_id, db)
    images = _shared_images(user_id, db)

    # 사진이 겹치는 상대는 거래가 없어도 살펴봐야 함
    candidates = set(partners) | set(reviews) | {x["상대번호"] for x in images}

    linked = []
    for other_id in candidates:
        other = db.get(User, other_id)
        if other is None:
            continue

        deals = partners.get(other_id, 0)
        rv = reviews.get(other_id, {"준것": [], "받은것": []})
        img = next((x for x in images if x["상대번호"] == other_id), None)

        signs = []
        score = 0

        # ① 자주 거래
        if deals >= CLOSE_DEALS:
            signs.append(f"{deals}회 거래")
            score += 2

        # ② 그 사람하고만 거래 — 가장 강한 신호.
        # 정상 거래는 상대가 흩어지는데, 짜고 하면 자기들끼리만 돈다
        if total_deals >= 3 and deals / total_deals >= ONLY_RATIO:
            ratio = int(deals / total_deals * 100)
            signs.append(f"전체 거래의 {ratio}%가 이 사람과")
            score += 3

        # ③ 후기를 주고받음.
        # 한 번씩 주고받는 것은 정상 거래에서도 늘 일어나므로 점수를 안 준다.
        # 여러 번 오갔을 때만 의미가 있다
        given, got = len(rv["준것"]), len(rv["받은것"])
        if given and got:
            signs.append(f"후기를 서로 주고받음 (준 것 {given} · 받은 것 {got})")
            if given + got >= 4:
                score += 2

            # 여러 번 오갔는데 전부 최고점이면 서로 띄워주는 것일 수 있음
            all_high = all(x >= HIGH_RATING for x in rv["준것"] + rv["받은것"])
            if all_high and given + got >= 4:
                signs.append("여러 번 오갔는데 전부 최고점")
                score += 2

        # ④ 같은 사진
        if img:
            signs.append(f"같은 사진을 쓴 매물 {img['건수']}건")
            score += 3

        # ⑤ 비슷한 때 가입.
        # 다만 이것만으로는 약하다 — 같은 날 가입한 사람이야 많다.
        # 다른 신호가 이미 있을 때만 보태서 센다
        gap_min = None
        if me.created_at and other.created_at:
            gap_min = abs((me.created_at - other.created_at).total_seconds()) / 60

        if gap_min is not None and gap_min <= SAME_SIGNUP_MINUTES and score > 0:
            signs.append(f"가입 시각 차이 {int(gap_min)}분")
            score += 2

        # ⑥ 같은 동네. 이것도 혼자서는 아무 뜻이 없다
        if me.region and me.region == other.region and score > 0:
            signs.append("같은 동네")
            score += 1

        if not signs:
            continue

        linked.append({
            "번호": other.id,
            "아이디": other.username,
            "닉네임": other.nickname,
            "거래횟수": deals,
            "신호": signs,
            "점수": score,
            "정지됨": other.is_blocked,
        })

    linked.sort(key=lambda x: -x["점수"])

    # 점수가 높은 상대가 있으면 무리로 의심
    strong = [x for x in linked if x["점수"] >= 5]

    return {
        "회원": {"번호": me.id, "아이디": me.username, "닉네임": me.nickname},
        "거래총횟수": total_deals,
        "이어진사람수": len(linked),
        "의심되는상대": len(strong),
        "관계": linked[:10],
        "판단": _verdict(strong, total_deals),
    }


def _verdict(strong: list, total_deals: int) -> str:
    """사람이 읽을 한 줄"""
    if not strong:
        return "함께 움직이는 것으로 보이는 상대는 없습니다"

    names = ", ".join(f"{x['닉네임']}({x['아이디']})" for x in strong[:3])
    if len(strong) == 1:
        return f"{names} 과(와) 함께 움직이는 것으로 보입니다"
    return f"{names} 등 {len(strong)}명과 함께 움직이는 것으로 보입니다"


# ---------------------------------------------------------------
# 전체에서 의심스러운 무리 찾기 (신고 없이도)
# ---------------------------------------------------------------
def scan_groups(db: Session, limit: int = 10) -> list:
    """모든 회원을 훑어 서로만 거래하는 무리를 찾는다.

    회원이 많아지면 오래 걸리므로 관리자가 눌렀을 때만 돌린다
    """
    users = db.query(User).filter(User.is_blocked == False).all()

    # 같은 무리를 여러 번 보고하지 않게, 이미 묶인 사람은 건너뜀
    seen = set()
    groups = []

    for u in users:
        if u.id in seen:
            continue

        result = find_group(u.id, db)
        strong = [x for x in result.get("관계", []) if x["점수"] >= 5]
        if not strong:
            continue

        members = [u.id] + [x["번호"] for x in strong]
        seen.update(members)

        groups.append({
            "대표": {"번호": u.id, "아이디": u.username, "닉네임": u.nickname},
            "인원": len(members),
            "구성원": [
                {"번호": x["번호"], "닉네임": x["닉네임"], "점수": x["점수"], "신호": x["신호"]}
                for x in strong
            ],
            "총점": sum(x["점수"] for x in strong),
        })

    groups.sort(key=lambda g: -g["총점"])
    return groups[:limit]
