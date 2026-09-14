"""
관리 도구 — 다시 계산하기

대화 분석, 의미 검색 벡터, 사진 지문을 다시 만드는 것들.
지금은 로그인만 하면 되지만, 나중에 is_admin 검사를 넣을 자리
"""

import json
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import User, Post, PostImage, Report
from deps import get_db, get_admin_user
import ai_search
import image_check
import chat_tips
import agent
from routers.reports import reporter_trust

router = APIRouter(tags=["관리"])


class InvestigateOptions(BaseModel):
    """조사 방식.

    solo   — 조사관 한 명이 도구 7개를 다 씀 (기본)
    team   — 매물·이력·관계 조사관 셋이 나눠 보고 모음. 두 배쯤 빠름
    debate — 검사가 모으고, 변호인이 반박하고, 정리 담당이 정리
    """
    mode: str = "solo"
    # 관리자가 남기는 지시. "무리부터 봐줘" 같은 것
    note: Optional[str] = None




@router.post("/admin/rebuild-tips")
def admin_rebuild_tips(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """대화를 다시 분석해 추천 문구를 갱신.
    지금은 로그인만 하면 되지만, 3층에서 관리자 전용으로 좁힐 자리"""
    return chat_tips.rebuild_tips(db)




@router.get("/admin/tips")
def admin_tips():
    """지금 학습된 추천 문구를 그대로 보여줌 (확인용).

    메시지가 오갈 때마다 바로 반영되므로 서버를 껐다 켤 필요가 없다
    """
    counted = sum(len(v) for v in chat_tips.COUNTS.values())
    return {
        "learned_at": chat_tips.LEARNED_AT,
        "묶음": len(chat_tips.LEARNED_TIPS),
        "세고있는문장": counted,
        "최소횟수": chat_tips.MIN_COUNT,
        "묶음당최대": chat_tips.MAX_TIPS,
        "tips": {f"{k[0]}/{k[1]}": v for k, v in chat_tips.LEARNED_TIPS.items()},
    }




@router.post("/admin/rebuild-embeddings")
def rebuild_embeddings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """벡터가 없는 매물에 채워 넣음.
    모델을 나중에 깔았거나, 가짜 데이터를 넣은 뒤에 한 번 돌리면 됨"""
    if not ai_search.is_ready():
        raise HTTPException(status_code=400, detail="의미 검색 모델을 쓸 수 없습니다")

    posts = db.query(Post).filter(Post.embedding.is_(None)).all()
    done = 0
    for post in posts:
        vec = ai_search.embed_post(post)
        if vec:
            post.embedding = vec
            done += 1

    db.commit()
    total = db.query(Post).filter(Post.embedding.isnot(None)).count()
    return {"new": done, "total_with_embedding": total}




@router.post("/admin/rebuild-image-hashes")
def rebuild_image_hashes(
    force: bool = Query(False, description="이미 있는 지문도 다시 만들기"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """지문이 없는 사진에 채워 넣음. 기능을 나중에 켰을 때 한 번 돌리면 됨"""
    if not image_check.is_ready():
        raise HTTPException(status_code=400, detail="사진 검사 기능을 쓸 수 없습니다")

    q = db.query(PostImage)
    if not force:
        q = q.filter(PostImage.image_hash.is_(None))

    done = 0
    for image in q.all():
        path = image.image_url.lstrip("/")
        if not os.path.exists(path):
            continue
        h = image_check.make_hash(path)
        if h:
            image.image_hash = h
            done += 1

    db.commit()
    total = db.query(PostImage).filter(PostImage.image_hash.isnot(None)).count()
    return {"new": done, "total_with_hash": total}


# ---------------------------------------------------------------
# 신고 목록
# ---------------------------------------------------------------
@router.get("/admin/reports")
def list_reports(
    status: str = Query("접수", description="접수 / 처리완료 / 기각"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    rows = (
        db.query(Report)
        .filter(Report.status == status)
        .order_by(Report.created_at.desc())
        .limit(50)
        .all()
    )

    out = []
    for r in rows:
        item = {
            "id": r.id,
            "대상종류": r.target_type,
            "대상번호": r.target_id,
            "사유": r.reason,
            "내용": r.detail,
            "신고자": r.reporter.nickname if r.reporter else "?",
            "신고자번호": r.reporter_id,
            # 이 사람의 지난 신고가 얼마나 맞았는지.
            # 거짓 신고가 잦으면 관리자가 걸러 들을 수 있어야 함
            "신고자신뢰도": reporter_trust(r.reporter_id, db) if r.reporter_id else None,
            "접수": r.created_at,
            "상태": r.status,
            # 에이전트가 조사한 결과. 아직 안 됐으면 비어 있음
            "조사": {
                "위험도": r.ai_risk,
                "권고": r.ai_action,
                "요약": r.ai_summary,
                "근거": json.loads(r.ai_grounds) if r.ai_grounds else [],
                # 도구가 돌려준 자료 전부. 관리자가 펼쳐서 원본을 볼 수 있음
                "단계": json.loads(r.ai_steps) if r.ai_steps else [],
                # 무엇을 봤고 무엇을 못 봤는지
                "점검": json.loads(r.ai_coverage) if r.ai_coverage else None,
                # 항목별 채점. 관리자가 "왜 이 점수인지" 를 볼 수 있게
                "채점": json.loads(r.ai_score) if r.ai_score else None,
                "방식": r.ai_mode or "혼자 조사",
                # 조사 전에 관리자가 남긴 지시
                "관리자지시": r.ai_note,
                "재판": json.loads(r.ai_debate) if r.ai_debate else None,
                "조사시각": r.ai_checked_at,
            } if r.ai_checked_at else None,
        }
        # 신고당한 쪽이 누구인지. 이게 없으면 무엇을 판단할지 알 수 없음
        if r.target_type == "post":
            post = db.get(Post, r.target_id)
            item["매물번호"] = r.target_id

            if post:
                item["대상이름"] = post.title
                item["대상"] = {
                    "종류": "매물",
                    "제목": post.title,
                    "가격": post.price,
                    "카테고리": post.category,
                    "지역": post.region,
                    "본문": (post.content or "")[:300],
                    "상태": post.status,
                    "숨김": post.is_hidden,
                    # 그 매물을 올린 사람 — 실제로 조치할 대상
                    "판매자": {
                        "번호": post.seller_id,
                        "아이디": post.seller.username if post.seller else "?",
                        "닉네임": post.seller.nickname if post.seller else "?",
                        "매너온도": post.seller.manner_temp if post.seller else None,
                        "판매": post.seller.completed_deals if post.seller else 0,
                        "취소": post.seller.cancel_count if post.seller else 0,
                        "정지": post.seller.is_blocked if post.seller else False,
                    },
                }
            else:
                item["대상이름"] = "(삭제된 매물)"
                item["대상"] = None
        else:
            user = db.get(User, r.target_id)
            item["매물번호"] = None

            if user:
                item["대상이름"] = user.nickname
                item["대상"] = {
                    "종류": "회원",
                    "판매자": {
                        "번호": user.id,
                        "아이디": user.username,
                        "닉네임": user.nickname,
                        "매너온도": user.manner_temp,
                        "판매": user.completed_deals,
                        "취소": user.cancel_count,
                        "정지": user.is_blocked,
                    },
                }
            else:
                item["대상이름"] = "(탈퇴한 회원)"
                item["대상"] = None

        # 이 대상이 지금까지 몇 번 신고당했는지
        if item["대상"]:
            uid = item["대상"]["판매자"]["번호"]
            item["대상"]["신고당한횟수"] = (
                db.query(Report)
                .filter(Report.target_type == "user", Report.target_id == uid)
                .count()
                + db.query(Report)
                .join(Post, Report.target_id == Post.id)
                .filter(Report.target_type == "post", Post.seller_id == uid)
                .count()
            )

        out.append(item)

    return {"count": len(out), "reports": out}


# ---------------------------------------------------------------
# 에이전트에게 조사 시키기
#
# 15~40초 걸림. 도구를 여러 번 부르기 때문
# ---------------------------------------------------------------
@router.post("/admin/reports/{report_id}/investigate")
def investigate_report(
    report_id: int,
    options: InvestigateOptions = InvestigateOptions(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="신고를 찾을 수 없습니다")

    # 에이전트에게 건넬 상황 설명.
    # 신고 사유를 그대로 믿지 말라고 프롬프트에 적어뒀음
    if report.target_type == "post":
        target = f"{report.target_id}번 매물"
        post = db.get(Post, report.target_id)
        extra = f" (판매자는 {post.seller_id}번 회원)" if post else ""
    else:
        target = f"{report.target_id}번 회원"
        extra = ""

    question = (
        f"{target}{extra} 이(가) '{report.reason}' 사유로 신고됐습니다. "
        f"신고자는 {report.reporter_id}번 회원입니다."
    )
    if report.detail:
        question += f" 신고자가 적은 내용: {report.detail[:200]}"

    # 조사 방식 — 혼자 다 보거나, 조사관 셋이 나눠 보거나
    note = (options.note or "").strip() or None

    if options.mode == "team":
        import agent_team
        result = agent_team.investigate(question, db, note=note)
    elif options.mode == "debate":
        import agent_debate
        result = agent_debate.investigate(question, db, note=note)
    else:
        result = agent.investigate(question, db, note=note)

    if "오류" in result:
        raise HTTPException(status_code=400, detail=result["오류"])

    # 다시 조사한 결과도 저장해둠
    c = result["결론"]
    report.ai_risk = c["위험도"]
    report.ai_action = c["권고"]
    report.ai_summary = c["요약"]
    report.ai_grounds = json.dumps(c["근거"], ensure_ascii=False)
    # 도구 결과까지 통째로. 관리자가 원본을 직접 볼 수 있게
    report.ai_steps = json.dumps(result["단계"], ensure_ascii=False, default=str)
    report.ai_coverage = json.dumps(result.get("점검", {}), ensure_ascii=False)
    report.ai_score = json.dumps(result.get("채점", {}), ensure_ascii=False)
    report.ai_mode = result.get("방식", "혼자 조사")
    report.ai_note = note
    # 검사·변호인·정리 방식이면 양쪽 말도 남긴다
    report.ai_debate = (
        json.dumps(result["재판"], ensure_ascii=False) if result.get("재판") else None
    )
    report.ai_checked_at = datetime.utcnow()
    db.commit()

    return {"신고번호": report_id, "질문": question, **result}


# ---------------------------------------------------------------
# 신고 처리 — 사람이 결정
# ---------------------------------------------------------------
class ReportDecision(BaseModel):
    status: str      # 처리완료 / 기각


@router.patch("/admin/reports/{report_id}")
def decide_report(
    report_id: int,
    data: ReportDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """에이전트는 권고만 하고, 실제 처리는 여기서 사람이 함"""
    if data.status not in ("처리완료", "기각"):
        raise HTTPException(status_code=400, detail="처리완료 또는 기각만 가능합니다")

    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="신고를 찾을 수 없습니다")

    report.status = data.status
    db.commit()

    return {"id": report.id, "상태": report.status}


class FollowUpOptions(BaseModel):
    """보충 조사 — 이미 조사한 건에 도구 몇 개를 더 돌린다"""
    tools: list = []
    note: Optional[str] = None


@router.post("/admin/reports/{report_id}/follow-up")
def follow_up_report(
    report_id: int,
    options: FollowUpOptions,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """관리자가 "이것도 봐줘" 할 때.

    처음부터 다시 조사하면 오래 걸리고 이미 본 것을 또 본다.
    앞서 모은 자료는 그대로 두고 새로 본 것만 얹은 뒤 전체를 다시 채점한다
    """
    import follow_up

    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="신고를 찾을 수 없습니다")
    if not report.ai_checked_at:
        raise HTTPException(status_code=400, detail="아직 조사하지 않은 신고입니다")

    result = follow_up.run(
        report, options.tools, db,
        note=(options.note or "").strip() or None,
    )
    if "오류" in result:
        raise HTTPException(status_code=503, detail=result["오류"])

    follow_up.save(report, result, db)
    return result
