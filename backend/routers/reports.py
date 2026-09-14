"""
신고 — 접수만 하고 처리는 관리자 대시보드에서
"""

import threading
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import User, Post, Report
from schemas import ReportCreate
from deps import get_db, get_current_user
from config import REPORT_REASONS, REPORT_DAILY_LIMIT
import agent
import query_ai

router = APIRouter(tags=["신고"])




@router.post("/reports", status_code=201)
def create_report(
    data: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.target_type not in ("post", "user"):
        raise HTTPException(status_code=400, detail="신고 대상이 올바르지 않습니다")
    if data.reason not in REPORT_REASONS:
        raise HTTPException(status_code=400, detail="신고 사유를 골라주세요")

    # 대상이 실제로 있는지 확인
    if data.target_type == "post":
        target = db.get(Post, data.target_id)
        if target is None:
            raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")
        if target.seller_id == current_user.id:
            raise HTTPException(status_code=400, detail="본인 매물은 신고할 수 없습니다")
    else:
        target = db.get(User, data.target_id)
        if target is None:
            raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다")
        if target.id == current_user.id:
            raise HTTPException(status_code=400, detail="본인은 신고할 수 없습니다")

    # 하루 신고 횟수 제한. 한 사람이 무더기로 넣는 것을 막음
    since = datetime.utcnow() - timedelta(days=1)
    today = (
        db.query(Report)
        .filter(Report.reporter_id == current_user.id, Report.created_at >= since)
        .count()
    )
    if today >= REPORT_DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"하루에 {REPORT_DAILY_LIMIT}건까지 신고할 수 있습니다",
        )

    # 같은 대상을 두 번 신고하는 건 막음
    dup = (
        db.query(Report)
        .filter(
            Report.reporter_id == current_user.id,
            Report.target_type == data.target_type,
            Report.target_id == data.target_id,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=409, detail="이미 신고한 대상입니다")

    report = Report(
        reporter_id=current_user.id,
        target_type=data.target_type,
        target_id=data.target_id,
        reason=data.reason,
        detail=data.detail,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # 에이전트가 알아서 조사하게 함.
    # 15~40초 걸리므로 별도 흐름에서 돌림 — 신고한 사람은 기다리지 않음.
    #
    # 다만 거짓 신고를 되풀이하는 사람의 신고는 뒤로 미룬다.
    # 열 번 넣어 다 기각된 사람 때문에 진짜 신고가 밀리면 안 되므로
    if query_ai.is_ready():
        trust = reporter_trust(current_user.id, db)
        delay = 0

        # 판정된 신고가 3건 이상인데 인정률이 30% 미만이면 미룸
        judged = trust["accepted"] + trust["rejected"]
        if judged >= 3 and trust["score"] < 0.3:
            delay = 300      # 5분 뒤에 조사
            print(f"[신고] #{report.id} — 신고자 인정률 {int(trust['score']*100)}%, "
                  f"조사를 {delay}초 미룹니다")

        threading.Thread(
            target=_investigate_later,
            args=(report.id, delay),
            daemon=True,
        ).start()

    return {"message": "신고가 접수되었습니다. 확인 후 조치하겠습니다."}




@router.get("/report-reasons")
def report_reasons():
    """신고 화면의 사유 목록. 서버에 두면 화면을 안 고치고 늘릴 수 있음"""
    return {"reasons": REPORT_REASONS}


def _investigate_later(report_id: int, delay: int = 0):
    """조사를 시작함. delay 초만큼 기다렸다가 돌림"""
    import time
    if delay:
        time.sleep(delay)
    agent.investigate_report_now(report_id)


# ---------------------------------------------------------------
# 신고자가 얼마나 믿을 만한지
#
# 지금까지 낸 신고 중 몇 건이 실제로 문제였는지 셈.
# 열 번 넣어 다 기각된 사람의 신고는 나중에 조사 순서를 뒤로 미룸
# ---------------------------------------------------------------
def reporter_trust(user_id: int, db: Session) -> dict:
    rows = db.query(Report).filter(Report.reporter_id == user_id).all()

    total = len(rows)
    if total == 0:
        # 처음 신고하는 사람. 의심할 이유가 없으니 보통으로 봄
        return {"total": 0, "accepted": 0, "rejected": 0, "score": 0.5}

    accepted = sum(1 for r in rows if r.status == "처리완료")
    rejected = sum(1 for r in rows if r.status == "기각")
    judged = accepted + rejected

    # 아직 판정된 게 없으면 보통
    score = 0.5 if judged == 0 else accepted / judged

    return {
        "total": total,
        "accepted": accepted,
        "rejected": rejected,
        "score": round(score, 2),
    }
