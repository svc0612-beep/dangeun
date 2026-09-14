"""
위험 매물 지키기 — 신고를 기다리지 않는다

신고가 들어와야 도는 구조는 누군가 당한 뒤에야 안다.
매물이 올라올 때 위험 신호를 세어, 심하면 관리자에게 바로 알린다.

여기서 알림만 보내고 숨기거나 지우지는 않는다.
잘못 걸린 매물을 자동으로 내리면 멀쩡한 판매자가 피해를 본다
"""

from datetime import datetime

from sqlalchemy.orm import Session

from database import Post, AdminNotice
from scam import check_post_risks


# 이 점수 이상이면 관리자에게 알림.
# danger 2점 · warn 1점으로 세고, 사진 없음(info)은 세지 않음
NOTIFY_SCORE = 3


def grade(post, db: Session) -> tuple:
    """매물의 위험 점수와 걸린 신호들"""
    flags = check_post_risks(post, db)
    serious = [f for f in flags if f.level in ("danger", "warn")]
    score = sum(2 if f.level == "danger" else 1 for f in serious)
    return score, serious


def check_post(post_id: int):
    """매물 하나를 살펴보고 위험하면 알림을 남긴다.

    매물을 올리거나 고칠 때 별도 흐름에서 부른다 —
    사용자는 기다리지 않는다
    """
    from database import SessionLocal

    db = SessionLocal()
    try:
        post = db.get(Post, post_id)
        if post is None or post.risk_notified:
            return

        score, serious = grade(post, db)
        if score < NOTIFY_SCORE:
            return

        reasons = " / ".join(f.message[:60] for f in serious[:3])
        seller = post.seller.nickname if post.seller else "?"

        db.add(AdminNotice(
            kind="risk_post",
            title=f"[위험 {score}점] {post.title} — {seller}",
            body=f"신고 없이 걸러낸 매물입니다.\n{reasons}",
            link_type="post",
            link_id=post.id,
            level="높음" if score >= 5 else "보통",
        ))

        # 같은 매물로 알림이 되풀이되지 않게
        post.risk_notified = True
        db.commit()

        print(f"[위험 매물] #{post.id} '{post.title}' {score}점 — 관리자에게 알림")

    except Exception as e:
        db.rollback()
        print(f"[위험 매물] #{post_id} 확인 실패 — {e}")
    finally:
        db.close()


def scan_all(db: Session, limit: int = 300) -> int:
    """아직 안 알린 매물을 훑어 위험한 것을 알린다.

    서버가 켜질 때 한 번 돌린다. 앱을 껐다 켜는 사이에 올라온 것도
    놓치지 않기 위해서
    """
    posts = (
        db.query(Post)
        .filter(
            Post.risk_notified == False,
            Post.status != "거래완료",
            Post.is_hidden == False,
        )
        .order_by(Post.created_at.desc())
        .limit(limit)
        .all()
    )

    found = 0
    for post in posts:
        try:
            score, serious = grade(post, db)
        except Exception:
            continue

        # 점수가 낮아도 한 번 봤으면 다시 안 보게 표시
        post.risk_notified = True

        if score < NOTIFY_SCORE:
            continue

        reasons = " / ".join(f.message[:60] for f in serious[:3])
        seller = post.seller.nickname if post.seller else "?"

        db.add(AdminNotice(
            kind="risk_post",
            title=f"[위험 {score}점] {post.title} — {seller}",
            body=f"신고 없이 걸러낸 매물입니다.\n{reasons}",
            link_type="post",
            link_id=post.id,
            level="높음" if score >= 5 else "보통",
        ))
        found += 1

    db.commit()
    return found
