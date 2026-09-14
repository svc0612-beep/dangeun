"""
관리자 대시보드 자료

관리자만 볼 수 있음. deps.get_admin_user 가
is_admin 과 아이디를 둘 다 확인함
"""

import json
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import (
    User, Post, PostImage, Favorite, ChatRoom, Message,
    Review, Report, SearchLog, Withdrawal, AdminNotice, AdminAction, Warning_,
)
from deps import get_db, get_admin_user
from config import CATEGORIES, WITHDRAW_REASONS

router = APIRouter(prefix="/admin", tags=["관리자 대시보드"])


def day_range(days: int) -> list[str]:
    """오늘부터 거슬러 올라가는 날짜 목록. 그래프의 가로축"""
    today = datetime.utcnow().date()
    return [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


def count_by_day(rows, days: int, field: str = "created_at") -> list[dict]:
    """날짜별 개수를 셈. 자료가 없는 날은 0으로 채움 —
    빈 날을 빼면 그래프가 거짓말을 함"""
    labels = day_range(days)
    counter = Counter()

    for row in rows:
        when = getattr(row, field, None)
        if when:
            counter[when.date().isoformat()] += 1

    return [{"날짜": d, "수": counter.get(d, 0)} for d in labels]


# ---------------------------------------------------------------
# 오늘 한눈에
# ---------------------------------------------------------------
@router.get("/summary")
def summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = now - timedelta(days=7)

    return {
        "전체": {
            "회원": db.query(User).count(),
            "매물": db.query(Post).count(),
            "거래완료": db.query(Post).filter(Post.status == "거래완료").count(),
            "판매중": db.query(Post).filter(
                Post.status == "판매중", Post.is_hidden == False
            ).count(),
        },
        "오늘": {
            "새회원": db.query(User).filter(User.created_at >= today).count(),
            "새매물": db.query(Post).filter(Post.created_at >= today).count(),
            "거래완료": db.query(ChatRoom).filter(
                ChatRoom.seller_confirmed_at >= today
            ).count(),
            "새신고": db.query(Report).filter(Report.created_at >= today).count(),
            "탈퇴": db.query(Withdrawal).filter(Withdrawal.created_at >= today).count(),
        },
        "이번주": {
            "새회원": db.query(User).filter(User.created_at >= week).count(),
            "새매물": db.query(Post).filter(Post.created_at >= week).count(),
            "거래완료": db.query(ChatRoom).filter(
                ChatRoom.seller_confirmed_at >= week
            ).count(),
            "새신고": db.query(Report).filter(Report.created_at >= week).count(),
            "탈퇴": db.query(Withdrawal).filter(Withdrawal.created_at >= week).count(),
        },
        "처리할것": {
            "안읽은알림": db.query(AdminNotice).filter(
                AdminNotice.is_read == False
            ).count(),
            "미처리신고": db.query(Report).filter(Report.status == "접수").count(),
            "정지된회원": db.query(User).filter(User.is_blocked == True).count(),
            "숨긴매물": db.query(Post).filter(Post.is_hidden == True).count(),
        },
    }


# ---------------------------------------------------------------
# 매물 현황 그래프
# ---------------------------------------------------------------
@router.get("/stats/posts")
def stats_posts(
    days: int = Query(14, ge=7, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    since = datetime.utcnow() - timedelta(days=days)
    posts = db.query(Post).filter(Post.created_at >= since).all()

    # 거래는 판매 확인 시각을 기준으로
    deals = db.query(ChatRoom).filter(
        ChatRoom.seller_confirmed_at.isnot(None),
        ChatRoom.seller_confirmed_at >= since,
    ).all()

    all_posts = db.query(Post).all()

    return {
        "기간": days,
        "등록": count_by_day(posts, days),
        "거래": count_by_day(deals, days, "seller_confirmed_at"),
        "카테고리별": [
            {"이름": c, "수": sum(1 for p in all_posts if p.category == c)}
            for c in CATEGORIES
        ],
        "상태별": [
            {"이름": s, "수": sum(1 for p in all_posts if p.status == s)}
            for s in ("판매중", "예약중", "거래완료")
        ],
        # 시·군·구 단위 — 몇 개만 자르지 않고 전부. 화면에서 골라 보게 함
        "지역별": sorted(
            [{"이름": r, "수": n} for r, n in Counter(p.region for p in all_posts).items()],
            key=lambda x: -x["수"],
        ),
        # 시·도 단위로 묶은 것. "서울 강남구" 에서 앞부분만 떼어 셈
        "시도별": sorted(
            [
                {"이름": r, "수": n}
                for r, n in Counter(
                    (p.region or "").split()[0] for p in all_posts if p.region
                ).items()
            ],
            key=lambda x: -x["수"],
        ),
    }


# ---------------------------------------------------------------
# 가입·탈퇴 그래프
# ---------------------------------------------------------------
@router.get("/stats/users")
def stats_users(
    days: int = Query(14, ge=7, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    since = datetime.utcnow() - timedelta(days=days)

    joined = db.query(User).filter(User.created_at >= since).all()
    left = db.query(Withdrawal).filter(Withdrawal.created_at >= since).all()
    all_left = db.query(Withdrawal).all()

    # 얼마나 쓰다가 떠났는지
    spans = {"1주 이내": 0, "1개월 이내": 0, "3개월 이내": 0, "그 이상": 0}
    for w in all_left:
        d = w.days_used or 0
        if d <= 7:
            spans["1주 이내"] += 1
        elif d <= 30:
            spans["1개월 이내"] += 1
        elif d <= 90:
            spans["3개월 이내"] += 1
        else:
            spans["그 이상"] += 1

    return {
        "기간": days,
        "가입": count_by_day(joined, days),
        "탈퇴": count_by_day(left, days),
        "탈퇴사유": [
            {"이름": r, "수": sum(1 for w in all_left if w.reason == r)}
            for r in WITHDRAW_REASONS
        ],
        "사용기간": [{"이름": k, "수": v} for k, v in spans.items()],
        "총탈퇴": len(all_left),
    }


# ---------------------------------------------------------------
# 탈퇴한 사람들이 남긴 말
# ---------------------------------------------------------------
@router.get("/withdrawals")
def list_withdrawals(
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    rows = (
        db.query(Withdrawal)
        .order_by(Withdrawal.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "count": len(rows),
        "목록": [
            {
                "사유": w.reason,
                "내용": w.detail,
                "지역": w.region,
                "쓴기간": f"{w.days_used}일" if w.days_used is not None else "-",
                "올린매물": w.total_posts,
                "거래완료": w.completed_deals,
                "떠난날": w.created_at,
            }
            for w in rows
        ],
    }


# ---------------------------------------------------------------
# 기간별 판매 내역
# ---------------------------------------------------------------
@router.get("/sold")
def sold_items(
    period: str = Query("today", description="today / yesterday / week"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        start, end = today, now
    elif period == "yesterday":
        start, end = today - timedelta(days=1), today
    else:
        start, end = today - timedelta(days=7), now

    rooms = (
        db.query(ChatRoom)
        .filter(
            ChatRoom.seller_confirmed_at.isnot(None),
            ChatRoom.seller_confirmed_at >= start,
            ChatRoom.seller_confirmed_at < end,
        )
        .order_by(ChatRoom.seller_confirmed_at.desc())
        .all()
    )

    items = []
    for room in rooms:
        post = room.post
        if post is None:
            continue
        items.append({
            "매물번호": post.id,
            "제목": post.title,
            "카테고리": post.category,
            "가격": post.price,
            "지역": post.region,
            "판매자": post.seller.nickname if post.seller else "?",
            "구매자": room.buyer.nickname if room.buyer else "?",
            "거래시각": room.seller_confirmed_at,
        })

    # 지역별 — 어느 동네에서 거래가 활발한지 한눈에
    by_region = Counter(i["지역"] for i in items)
    by_sido = Counter((i["지역"] or "").split()[0] for i in items if i["지역"])

    # 지역별 거래 금액도 함께. 건수는 적어도 금액이 큰 동네가 있음
    money_by_region = {}
    for i in items:
        money_by_region[i["지역"]] = money_by_region.get(i["지역"], 0) + i["가격"]

    return {
        "기간": period,
        "count": len(items),
        "지역별": sorted(
            [{"이름": r, "수": n} for r, n in by_region.items()],
            key=lambda x: -x["수"],
        ),
        "시도별": sorted(
            [{"이름": r, "수": n} for r, n in by_sido.items()],
            key=lambda x: -x["수"],
        ),
        "지역별금액": sorted(
            [{"이름": r, "수": m} for r, m in money_by_region.items()],
            key=lambda x: -x["수"],
        ),
        "카테고리별": sorted(
            [{"이름": c, "수": n} for c, n in Counter(i["카테고리"] for i in items).items()],
            key=lambda x: -x["수"],
        ),
        "합계금액": sum(i["가격"] for i in items),
        "목록": items[:100],
    }


# ---------------------------------------------------------------
# 전체 매물 목록
# ---------------------------------------------------------------
@router.get("/posts")
def list_posts(
    keyword: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    region: Optional[str] = Query(None, description="시/도 또는 시/군/구"),
    status: Optional[str] = Query(None),
    hidden: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    q = db.query(Post)

    if keyword:
        q = q.filter(Post.title.contains(keyword))
    if category:
        q = q.filter(Post.category == category)
    if region:
        # "서울" 이면 서울 전체, "서울 강남구" 면 그 구만
        q = q.filter(Post.region.like(region + "%"))
    if status:
        q = q.filter(Post.status == status)
    if hidden is not None:
        q = q.filter(Post.is_hidden == hidden)

    total = q.count()
    rows = q.order_by(Post.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "목록": [
            {
                "번호": p.id,
                "제목": p.title,
                "가격": p.price,
                "카테고리": p.category,
                "지역": p.region,
                "상태": p.status,
                "숨김": p.is_hidden,
                "숨긴이유": p.hidden_reason,
                "판매자": p.seller.nickname if p.seller else "?",
                "판매자번호": p.seller_id,
                "조회수": p.view_count,
                "사진수": len(p.images),
                "등록일": p.created_at,
            }
            for p in rows
        ],
    }


# ---------------------------------------------------------------
# 회원 목록
# ---------------------------------------------------------------
@router.get("/users")
def list_users(
    keyword: Optional[str] = Query(None, description="아이디·닉네임으로 찾기"),
    blocked: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    q = db.query(User)

    if keyword:
        q = q.filter(
            (User.username.contains(keyword)) | (User.nickname.contains(keyword))
        )
    if blocked is not None:
        q = q.filter(User.is_blocked == blocked)

    total = q.count()
    rows = q.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    out = []
    for u in rows:
        # 이 사람이 신고당한 횟수
        reported = (
            db.query(Report)
            .filter(Report.target_type == "user", Report.target_id == u.id)
            .count()
        )
        out.append({
            "번호": u.id,
            "아이디": u.username,
            "닉네임": u.nickname,
            "동네": u.region,
            "매너온도": u.manner_temp,
            "매물": u.total_posts,
            "판매": u.completed_deals,
            "구매": u.completed_purchases,
            "취소": u.cancel_count,
            "신고당함": reported,
            "정지": u.is_blocked,
            "정지사유": u.blocked_reason,
            "가입일": u.created_at,
        })

    return {"total": total, "목록": out}


# ---------------------------------------------------------------
# 관리자 알림
#
# 에이전트가 조사를 마치면 여기에 쌓임
# ---------------------------------------------------------------
@router.get("/notices")
def list_notices(
    unread_only: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    q = db.query(AdminNotice)
    if unread_only:
        q = q.filter(AdminNotice.is_read == False)

    rows = q.order_by(AdminNotice.created_at.desc()).limit(limit).all()
    unread = db.query(AdminNotice).filter(AdminNotice.is_read == False).count()

    return {
        "안읽음": unread,
        "목록": [
            {
                "id": n.id,
                "종류": n.kind,
                "제목": n.title,
                "내용": n.body,
                "위험도": n.level,
                "연결": {"종류": n.link_type, "번호": n.link_id},
                "읽음": n.is_read,
                "시각": n.created_at,
            }
            for n in rows
        ],
    }


@router.patch("/notices/{notice_id}/read")
def read_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    notice = db.get(AdminNotice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")
    notice.is_read = True
    db.commit()
    return {"id": notice.id, "읽음": True}


@router.post("/notices/read-all")
def read_all_notices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    n = (
        db.query(AdminNotice)
        .filter(AdminNotice.is_read == False)
        .update({"is_read": True})
    )
    db.commit()
    return {"읽음처리": n}


# ---------------------------------------------------------------
# 조치 — 계정 정지 / 매물 숨김
#
# 에이전트는 권고만 하고, 실제로 손대는 것은 여기서 사람이 함.
# 무엇을 했는지 admin_actions 에 남겨서 나중에 근거로 씀
# ---------------------------------------------------------------
class BlockRequest(BaseModel):
    reason: str


def log_action(db: Session, admin_id: int, action: str,
               target_type: str, target_id: int, reason: str = ""):
    """관리자가 한 일을 남김"""
    db.add(AdminAction(
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason[:200],
    ))


@router.post("/users/{user_id}/block")
def block_user(
    user_id: int,
    data: BlockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """계정 정지. 지우지 않고 막기만 함 —
    지우면 거래 기록과 후기가 함께 사라져 상대방 이력까지 망가짐"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="본인은 정지할 수 없습니다")

    user.is_blocked = True
    user.blocked_reason = data.reason[:200]
    user.blocked_at = datetime.utcnow()

    log_action(db, current_user.id, "계정정지", "user", user_id, data.reason)
    db.commit()

    return {"번호": user.id, "아이디": user.username, "정지": True,
            "사유": user.blocked_reason}


@router.post("/users/{user_id}/unblock")
def unblock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다")

    user.is_blocked = False
    user.blocked_reason = None
    user.blocked_at = None

    log_action(db, current_user.id, "정지해제", "user", user_id)
    db.commit()

    return {"번호": user.id, "아이디": user.username, "정지": False}


@router.post("/posts/{post_id}/hide")
def hide_post(
    post_id: int,
    data: BlockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """매물 숨김. 목록·검색에서 빠지지만 지워지지는 않음"""
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")

    post.is_hidden = True
    post.hidden_reason = data.reason[:200]

    log_action(db, current_user.id, "매물숨김", "post", post_id, data.reason)
    db.commit()

    return {"번호": post.id, "제목": post.title, "숨김": True}


@router.post("/posts/{post_id}/unhide")
def unhide_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")

    post.is_hidden = False
    post.hidden_reason = None

    log_action(db, current_user.id, "숨김해제", "post", post_id)
    db.commit()

    return {"번호": post.id, "제목": post.title, "숨김": False}


# ---------------------------------------------------------------
# 조치 기록
# ---------------------------------------------------------------
@router.get("/actions")
def list_actions(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """관리자가 무엇을 했는지. "왜 정지됐냐" 는 물음에 답하려면 기록이 있어야 함"""
    rows = (
        db.query(AdminAction)
        .order_by(AdminAction.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "count": len(rows),
        "목록": [
            {
                "한일": a.action,
                "대상종류": a.target_type,
                "대상번호": a.target_id,
                "사유": a.reason,
                "관리자": a.admin.nickname if a.admin else "?",
                "시각": a.created_at,
            }
            for a in rows
        ],
    }


# ---------------------------------------------------------------
# 관리자 비밀번호 변경
#
# 일반 회원과 같은 방식이지만, 관리자는 이 화면에서 바로 바꿀 수 있게 함.
# 현재 비밀번호를 다시 묻는 이유 — 자리를 비운 사이 남이 바꾸는 것을 막음
# ---------------------------------------------------------------
class AdminPasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.patch("/password")
def change_admin_password(
    data: AdminPasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    from deps import verify_password, hash_password

    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다")

    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="새 비밀번호는 8자 이상이어야 합니다")

    if verify_password(data.new_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="현재 비밀번호와 다른 것으로 정해주세요")

    current_user.password_hash = hash_password(data.new_password)
    log_action(db, current_user.id, "비밀번호변경", "user", current_user.id)
    db.commit()

    return {"message": "비밀번호가 변경되었습니다"}


# ---------------------------------------------------------------
# 위험해 보이는 매물 — 신고가 없어도 걸러냄
#
# 신고를 기다리면 누군가 당한 뒤에야 알게 됨.
# 위험 신호가 겹치는 매물을 먼저 찾아 보여줌
# ---------------------------------------------------------------
@router.get("/risky-posts")
def risky_posts(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    from scam import check_post_risks

    # 최근 매물부터 살펴봄. 오래된 것까지 다 보면 느려짐
    posts = (
        db.query(Post)
        .filter(Post.status != "거래완료", Post.is_hidden == False)
        .order_by(Post.created_at.desc())
        .limit(200)
        .all()
    )

    found = []
    for post in posts:
        flags = check_post_risks(post, db)
        # 심각한 것만. 사진 없음 같은 안내는 세지 않음
        serious = [f for f in flags if f.level in ("danger", "warn")]
        if not serious:
            continue

        found.append({
            "번호": post.id,
            "제목": post.title,
            "가격": post.price,
            "판매자": post.seller.nickname if post.seller else "?",
            "판매자번호": post.seller_id,
            "등록일": post.created_at,
            "위험": [{"단계": f.level, "내용": f.message} for f in serious],
            "점수": sum(2 if f.level == "danger" else 1 for f in serious),
        })

    # 위험한 순으로
    found.sort(key=lambda x: -x["점수"])
    return {"count": len(found), "목록": found[:limit]}


# ---------------------------------------------------------------
# 지역 목록 — 드롭다운에 채울 것
#
# 매물이 실제로 있는 지역만 돌려줌. 229개 시군구를 다 보여주면
# 대부분 0건이라 고르기 어려움
# ---------------------------------------------------------------
@router.get("/regions")
def region_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    rows = db.query(Post.region).all()
    counter = Counter(r[0] for r in rows if r[0])

    # 시·도 → 시·군·구 로 묶음
    tree: dict[str, list] = {}
    for full, n in counter.items():
        parts = full.split()
        sido = parts[0]
        tree.setdefault(sido, []).append({"이름": full, "수": n})

    for sido in tree:
        tree[sido].sort(key=lambda x: -x["수"])

    return {
        "시도": sorted(
            [{"이름": s, "수": sum(x["수"] for x in v)} for s, v in tree.items()],
            key=lambda x: -x["수"],
        ),
        "시군구": tree,
    }


# ---------------------------------------------------------------
# 카테고리별로 정리한 매물
# ---------------------------------------------------------------
@router.get("/posts/by-category")
def posts_by_category(
    region: Optional[str] = Query(None, description="비우면 전국"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    q = db.query(Post).filter(Post.status != "거래완료", Post.is_hidden == False)
    if region:
        q = q.filter(Post.region.like(region + "%"))

    posts = q.order_by(Post.created_at.desc()).all()

    # 카테고리마다 묶고, 각 묶음에서 최근 것 몇 개만 보여줌
    groups: dict[str, list] = {}
    for p in posts:
        groups.setdefault(p.category, []).append(p)

    out = []
    for name in CATEGORIES:
        rows = groups.get(name, [])
        if not rows:
            continue
        out.append({
            "카테고리": name,
            "수": len(rows),
            "평균가": int(sum(r.price for r in rows) / len(rows)) if rows else 0,
            "매물": [
                {
                    "번호": r.id,
                    "제목": r.title,
                    "가격": r.price,
                    "지역": r.region,
                    "판매자": r.seller.nickname if r.seller else "?",
                    "상태": r.status,
                    "등록일": r.created_at,
                }
                for r in rows[:10]
            ],
        })

    return {"지역": region or "전국", "총매물": len(posts), "묶음": out}


# ---------------------------------------------------------------
# 경고 보내기
#
# 정지는 너무 무겁고 그냥 두기는 곤란할 때.
# 사용자는 다음에 앱을 열 때 경고를 보고 확인을 눌러야 넘어감
# ---------------------------------------------------------------
class WarnRequest(BaseModel):
    reason: str
    detail: Optional[str] = None
    report_id: Optional[int] = None


@router.post("/users/{user_id}/warn")
def warn_user(
    user_id: int,
    data: WarnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="본인에게는 보낼 수 없습니다")

    warn = Warning_(
        user_id=user_id,
        reason=data.reason[:200],
        detail=(data.detail or "").strip() or None,
        report_id=data.report_id,
    )
    db.add(warn)

    log_action(db, current_user.id, "경고발송", "user", user_id, data.reason)
    db.commit()
    db.refresh(warn)

    # 이 사람이 지금까지 몇 번 경고받았는지 함께 알려줌
    total = db.query(Warning_).filter(Warning_.user_id == user_id).count()

    return {
        "id": warn.id,
        "회원": user.nickname,
        "아이디": user.username,
        "사유": warn.reason,
        "누적경고": total,
    }


@router.get("/users/{user_id}/warnings")
def user_warnings(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """이 회원이 받은 경고 이력. 정지를 결정할 때 참고"""
    rows = (
        db.query(Warning_)
        .filter(Warning_.user_id == user_id)
        .order_by(Warning_.created_at.desc())
        .all()
    )
    return {
        "count": len(rows),
        "목록": [
            {
                "id": w.id,
                "사유": w.reason,
                "내용": w.detail,
                "읽음": w.is_read,
                "보낸때": w.created_at,
            }
            for w in rows
        ],
    }


# ---------------------------------------------------------------
# 함께 움직이는 무리 찾기
#
# 신고를 기다리지 않고 전체를 훑는다.
# 회원이 많아지면 오래 걸리므로 관리자가 눌렀을 때만 돌린다
# ---------------------------------------------------------------
@router.get("/groups")
def find_groups(
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    import network
    return {"목록": network.scan_groups(db, limit=limit)}


@router.get("/users/{user_id}/group")
def user_group(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """한 사람이 누구와 어떻게 이어져 있는지"""
    import network
    result = network.find_group(user_id, db)
    if "오류" in result:
        raise HTTPException(status_code=404, detail=result["오류"])
    return result


# ---------------------------------------------------------------
# 에이전트 지시서
#
# 조사관에게 주는 지시가 agents/ 폴더의 .md 파일에 들어 있다.
# 관리자가 무엇이 적혀 있는지 볼 수 있어야 조사 결과를 판단할 수 있다
# ---------------------------------------------------------------
@router.get("/prompts")
def list_prompts(
    current_user: User = Depends(get_admin_user),
):
    import prompts
    return {"목록": prompts.list_all()}


@router.get("/prompts/{name:path}")
def read_prompt(
    name: str,
    current_user: User = Depends(get_admin_user),
):
    """지시서 하나의 내용. 공용 조각까지 끼워 넣은 완성본도 함께"""
    import prompts

    raw = prompts.load(name)
    if not raw:
        raise HTTPException(status_code=404, detail="그런 지시서가 없습니다")

    return {
        "이름": name,
        "원본": raw,
        # 실제로 모델이 받는 글. 공용 조각이 끼워진 상태
        "완성본": prompts.build(name, tools="(도구 목록이 들어갈 자리)"),
    }


@router.post("/prompts/reload")
def reload_prompts(
    current_user: User = Depends(get_admin_user),
):
    """지시서를 고친 뒤 서버를 껐다 켜지 않아도 되게"""
    import prompts
    prompts.reload()
    return {"message": "지시서를 다시 읽었습니다", "목록": prompts.list_all()}


# ---------------------------------------------------------------
# 사전 예방 — 제재 대기 목록 & 무혐의 처리
#
# 채팅 규칙을 반복해서 어긴 사람을 관리자가 보고 판단하는 창구.
# 자동으로 정지시키지 않는다 — 근거(증거)를 보여주고, 결정은 사람이 한다.
# ---------------------------------------------------------------
@router.get("/penalties")
def penalty_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """제재 대기 목록.

    최근 STRIKE_WINDOW_HOURS 안에 '활성' 위반(무혐의 처리 안 됨)이 있는
    사람들을, 위반이 많은 순으로 돌려준다. 각자에 대해 '증거'(어긴 규칙·
    실제 문장·시각)를 함께 담아, 관리자가 근거를 보고 판단하게 한다.
    """
    from database import Violation
    from config import STRIKE_WINDOW_HOURS

    since = datetime.utcnow() - timedelta(hours=STRIKE_WINDOW_HOURS)

    # 활성 위반만 (무혐의 처리 안 됐고, 시간 창 안)
    rows = (
        db.query(Violation)
        .filter(Violation.cleared == False, Violation.created_at >= since)  # noqa: E712
        .order_by(Violation.created_at.desc())
        .all()
    )

    # 사람별로 묶기
    groups: dict[int, list] = {}
    for v in rows:
        groups.setdefault(v.user_id, []).append(v)

    out = []
    for user_id, vs in groups.items():
        u = db.get(User, user_id)
        if u is None:
            continue
        out.append({
            "회원번호": user_id,
            "닉네임": u.nickname,
            "아이디": u.username,
            "지역": u.region,
            "매너온도": u.manner_temp,
            "정지": u.is_blocked,
            "위반수": len(vs),
            # 증거 — 최근 10건까지. 관리자가 이걸 보고 진짜 사기인지 판단
            "증거": [
                {"규칙": v.rule, "문장": v.snippet,
                 "시각": v.created_at, "방번호": v.room_id}
                for v in vs[:10]
            ],
        })

    # 위반 많은 순
    out.sort(key=lambda x: -x["위반수"])
    return {"count": len(out), "목록": out}


@router.post("/users/{user_id}/clear-violations")
def clear_violations(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """무혐의 처리 — 오탐이었거나 봐줄 만하면 활성 위반을 '없던 일'로.

    기록을 지우지는 않고 cleared=True 로 표시만 한다.
    그러면 활성 카운트에서 빠져(되돌리기), 이력은 남아 나중에 참고할 수 있다.
    """
    from database import Violation

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다")

    updated = (
        db.query(Violation)
        .filter(Violation.user_id == user_id, Violation.cleared == False)  # noqa: E712
        .update({Violation.cleared: True}, synchronize_session=False)
    )

    log_action(db, current_user.id, "무혐의", "user", user_id, "채팅 위반 무혐의 처리")
    db.commit()

    return {"회원번호": user_id, "무혐의처리건수": updated}
