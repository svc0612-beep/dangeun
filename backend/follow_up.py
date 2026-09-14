"""
보충 조사 — 관리자가 "이것도 봐줘" 할 때

조사가 끝난 뒤 화면에 이렇게 나온다.

    확인함    매물_보기 · 판매자_이력 · 시세_견주기
    확인못함  무리_확인 · 채팅_기록

관리자가 "무리_확인" 을 누르면 그것만 더 돌린다.
처음부터 다시 조사하면 40초가 또 걸리고, 이미 본 것을 다시 보게 된다.

앞서 모은 자료는 그대로 두고 새로 본 것만 얹은 다음
전체를 다시 채점한다 — 신호가 하나 늘면 위험도가 바뀔 수 있기 때문
"""

import json
import time

from sqlalchemy.orm import Session

import agent
import agent_tools
import prompts
import query_ai
import risk_score
from database import Report


def run(report: Report, tools: list, db: Session, note: str = None) -> dict:
    """이미 조사한 신고에 도구 몇 개를 더 돌린다.

    tools — 더 볼 도구 이름들. 예: ["무리_확인", "채팅_기록"]
    note  — 관리자가 남긴 지시 (없어도 됨)
    """
    if not query_ai.is_ready():
        return {"오류": "이 기기에서는 조사 기능을 쓸 수 없습니다"}

    # 목록에 없는 도구는 걸러냄
    valid = [t for t in tools if t in agent_tools.TOOLS]
    if not valid:
        return {"오류": "더 볼 수 있는 도구가 없습니다"}

    prior = json.loads(report.ai_steps) if report.ai_steps else []

    started = time.time()
    result = agent.investigate(
        agent.build_question(report, db),
        db,
        tools=valid,
        role=prompts.build("follow_up", tools=", ".join(valid)),
        max_steps=len(valid) + 2,
        note=note,
        prior_steps=prior,
    )

    if "오류" in result:
        return result

    result["방식"] = (report.ai_mode or "혼자 조사") + " + 보충"
    result["보충"] = {
        "더본것": valid,
        "앞선걸음": len(prior),
        "지금걸음": len(result["단계"]) - len(prior),
        "걸린시간": round(time.time() - started, 1),
    }
    return result


def save(report: Report, result: dict, db: Session):
    """보충 조사 결과를 신고 기록에 덮어씀"""
    from datetime import datetime

    conclusion = result["결론"]
    report.ai_risk = conclusion["위험도"]
    report.ai_action = conclusion["권고"]
    report.ai_summary = conclusion["요약"]
    report.ai_grounds = json.dumps(conclusion["근거"], ensure_ascii=False)
    report.ai_steps = json.dumps(result["단계"], ensure_ascii=False, default=str)
    report.ai_coverage = json.dumps(result.get("점검", {}), ensure_ascii=False)
    report.ai_score = json.dumps(result.get("채점", {}), ensure_ascii=False)
    report.ai_mode = result.get("방식", "보충 조사")
    report.ai_checked_at = datetime.utcnow()
    db.commit()
