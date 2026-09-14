"""
사기 조사 에이전트

신고가 들어오면 스스로 자료를 찾아보고 정리해줌.

    "신고 #12 확인해봐"
        ↓
    매물_보기(3)     → "선입금 후 택배거래만" 발견
        ↓  수상하네, 판매자는?
    판매자_이력(7)   → 거래 0건, 취소 3회, 가입 2일
        ↓  이력도 없네, 사진은?
    사진_도용검사(3) → 남의 매물과 같은 사진
        ↓
    "위험 신호 3개 — 계정 정지 검토 필요"

무엇을 볼지는 에이전트가 정하고, 볼 수 있는 것은 우리가 정함(agent_tools).
읽기 도구만 주기 때문에 스스로 지우거나 정지시킬 수 없음 — 결정은 사람이 함
"""

import json
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from config import OLLAMA_MODEL, AGENT_MAX_STEPS, AGENT_TIMEOUT
import agent_tools
import prompts
import query_ai
import risk_score


# 지시서는 agents/조사원.md 에 있다.
# 코드를 안 고치고 다듬을 수 있게 밖으로 뺐음


def _extract_json(raw: str) -> Optional[dict]:
    """모델이 말을 덧붙여도 JSON 부분만 뽑아냄"""
    if not raw:
        return None

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    text = fenced.group(1) if fenced else None

    if text is None:
        brace = re.search(r"\{.*\}", raw, re.S)
        if not brace:
            return None
        text = brace.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def investigate(
    question: str,
    db: Session,
    on_step=None,
    tools: list = None,
    role: str = None,
    max_steps: int = None,
    finish: bool = True,
    note: str = None,
    prior_steps: list = None,
) -> dict:
    """조사를 시작함.

    question — "3번 매물이 사기 의심으로 신고됐습니다. 신고자는 7번 회원입니다."
    on_step  — 한 걸음마다 부를 함수 (화면에 진행 상황을 보여주려고)

    아래 넷은 여러 조사관을 나눠 쓸 때만 준다. 안 주면 지금까지처럼 혼자 다 본다.
    tools     — 이번 조사에서 쓸 수 있는 도구. 안 주면 전부
    role      — 이 조사관이 맡은 몫. 프롬프트 앞에 붙는다
    max_steps — 걸음 수. 맡은 몫이 좁으면 적게 줘도 된다
    finish    — False 면 채점하지 않고 모은 자료만 돌려준다.
                여럿이 나눠 볼 때는 마지막에 한 번만 채점해야 하므로

    아래 둘은 사람이 끼어들 때 쓴다.
    note        — 관리자가 남긴 지시. "무리부터 봐줘" 같은 것
    prior_steps — 앞선 조사에서 이미 본 자료. 같은 도구를 다시 부르지 않게 하고
                  마지막 채점에도 함께 넣는다

    돌려주는 값 — {"단계": [...], "결론": {...}}
    """
    if not query_ai.is_ready():
        return {"오류": "이 기기에서는 조사 기능을 쓸 수 없습니다"}

    limit = max_steps or AGENT_MAX_STEPS
    system = prompts.build("solo", tools=agent_tools.tool_list_text(tools))

    # 맡은 몫이 있으면 맨 앞에 붙인다.
    # "당신은 매물만 본다" 를 분명히 해야 남의 몫까지 뒤지지 않는다
    if role:
        system = f"{role}\n\n{system}"

    # 관리자가 남긴 지시. 규칙보다 위는 아니지만 어디부터 볼지는 정할 수 있음
    if note:
        system += (
            "\n\n## 관리자가 남긴 지시\n\n"
            f"{note}\n\n"
            "이 지시를 먼저 따르십시오. 다만 지시에 없는 것도 필요하면 살펴보고,\n"
            "지시가 자료와 어긋나면 자료를 따르십시오."
        )

    # 앞선 조사에서 이미 본 것. 같은 도구를 또 부르지 않게
    if prior_steps:
        seen = ", ".join(f"{p['도구']}({p['인자']})" for p in prior_steps)
        system += (
            "\n\n## 이미 확인한 것\n\n"
            f"{seen}\n\n"
            "위 도구들은 앞선 조사에서 이미 불렀습니다. 다시 부르지 마십시오.\n"
            "아직 안 본 것을 살펴보십시오."
        )

    # 지금까지의 대화. 모델은 기억이 없어서 매번 전부 다시 보내야 함
    history = [f"조사할 건: {question}"]
    steps = []

    for turn in range(limit):
        prompt = system + "\n\n" + "\n\n".join(history) + "\n\n다음 행동(JSON):"

        data = query_ai._post_json("/api/generate", {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2, "num_predict": 400},
        }, AGENT_TIMEOUT)

        if data is None:
            break

        parsed = _extract_json(data.get("response", ""))
        if parsed is None:
            history.append("(형식이 잘못됐습니다. JSON만 출력하세요)")
            continue

        # 결론을 냈으면 끝.
        # 위험도와 권고는 모델 말이 아니라 규칙으로 계산한다 —
        # 같은 자료면 늘 같은 답이 나와야 관리자가 검증할 수 있다
        if "결론" in parsed:
            merged = _merge_steps(prior_steps, steps)
            if not finish:
                return {"단계": merged, "메모": parsed["결론"]}
            return _finish(merged, parsed["결론"])

        # 도구를 부르는 경우
        name = parsed.get("도구")
        arg = parsed.get("인자")
        why = parsed.get("이유", "")

        if not name or arg is None:
            history.append("(도구와 인자를 모두 적어야 합니다)")
            continue

        result = agent_tools.run_tool(name, arg, db, only=tools)

        # 없거나 쓸 수 없는 도구를 불렀으면 걸음으로 세지 않고 다시 알려준다.
        # 거절당한 것까지 기록에 남으면 관리자가 볼 때 어수선하다
        # 이미 부른 도구를 또 부르면 걸음을 낭비한다.
        # 같은 자료가 여러 번 쌓이면 채점에서도 같은 신호가 겹쳐 세일 수 있다
        already = any(
            st["도구"] == name and str(st["인자"]) == str(arg) for st in steps
        )
        if already:
            history.append(
                f'{{"도구": "{name}", "인자": {arg}}}\n'
                f"이미 확인했습니다. 같은 것을 다시 부르지 말고 "
                f"아직 안 본 것을 살펴보거나 결론을 내십시오."
            )
            continue

        # "오류" 와 "결과" 를 가른다.
        #   오류 — 도구를 잘못 불렀다. 자료를 아예 못 봤으므로 걸음에서 뺀다
        #   결과 — 봤는데 자료가 없었다. "채팅을 봤지만 대화가 없다" 는
        #          관리자가 알아야 하므로 걸음에 남긴다
        error = result.get("오류", "") if isinstance(result, dict) else ""

        if error:
            allowed = tools or list(agent_tools.TOOLS)
            history.append(
                f'{{"도구": "{name}"}}\n'
                f"거절: {error}\n"
                f"쓸 수 있는 도구는 다음뿐입니다 — {', '.join(allowed)}"
            )
            continue

        step = {"순서": len(steps) + 1, "도구": name, "인자": arg,
                "이유": why, "결과": result}
        steps.append(step)

        if on_step:
            on_step(step)

        history.append(
            f'{{"도구": "{name}", "인자": {arg}}}\n'
            f"결과: {json.dumps(result, ensure_ascii=False)[:600]}"
        )

    merged = _merge_steps(prior_steps, steps)

    if not finish:
        return {"단계": merged, "메모": None}

    # 정해진 걸음 안에 결론을 못 냈을 때에도 점수는 낼 수 있다.
    # 모은 자료만으로 채점하고, 조사가 덜 끝났다고 밝힌다
    return _finish(merged, {
        "근거": [f"{len(merged)}가지를 확인했으나 조사를 마치지 못했습니다"],
        "요약": "조사가 끝나지 않았습니다. 관리자가 직접 봐주세요.",
    }, unfinished=True)


def _merge_steps(prior: list, fresh: list) -> list:
    """앞선 조사와 이번 조사를 합침.

    같은 도구를 같은 인자로 불렀으면 하나만 남긴다 —
    채점할 때 같은 신호가 두 번 세어지면 안 되므로
    """
    if not prior:
        return fresh

    out = []
    seen = set()
    for step in list(prior) + list(fresh):
        key = (step.get("도구"), str(step.get("인자")))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(step))

    for i, step in enumerate(out, 1):
        step["순서"] = i
    return out


def _finish(steps: list, raw: dict, unfinished: bool = False) -> dict:
    """조사를 마무리한다.

    위험도·권고는 risk_score 가 규칙으로 계산하고,
    모델은 근거와 요약만 쓴다
    """
    graded = risk_score.score(steps)

    grounds = raw.get("근거", []) if isinstance(raw, dict) else []
    if isinstance(grounds, str):
        grounds = [grounds]
    grounds = [str(g)[:200] for g in grounds][:6]

    summary = str(raw.get("요약", "") if isinstance(raw, dict) else "")[:200]

    return {
        "단계": steps,
        "점검": coverage(steps),
        "채점": graded,
        "결론": {
            "위험도": graded["위험도"],
            "총점": graded["총점"],
            "권고": "직접 확인 필요" if unfinished else graded["권고"],
            "근거": grounds,
            "요약": summary,
        },
    }


# 조사에서 꼭 확인해야 할 것들.
# 이걸 안 봤으면 조사가 끝난 게 아니라 "덜 본 것"
MUST_CHECK = ["매물_보기", "판매자_이력"]
SHOULD_CHECK = ["사진_도용검사", "시세_견주기", "채팅_기록", "신고자_이력", "무리_확인"]


def coverage(steps: list) -> dict:
    """무엇을 봤고 무엇을 못 봤는지.

    "못 본 것" 을 숨기면 관리자가 조사를 완전한 것으로 오해함.
    안 본 것은 안 봤다고 분명히 말해야 판단할 수 있다
    """
    used = {s["도구"] for s in steps}

    # 도구를 불렀는데 자료가 없어서 못 본 경우도 구분함
    empty = []
    for s in steps:
        result = s.get("결과", {})
        if isinstance(result, dict):
            text = str(result.get("결과", "")) + str(result.get("오류", ""))
            if "없" in text or "모자" in text or "쓸 수 없" in text:
                empty.append({"도구": s["도구"], "이유": text[:60]})

    missing_must = [t for t in MUST_CHECK if t not in used]
    missing_should = [t for t in SHOULD_CHECK if t not in used]

    return {
        "확인함": sorted(used),
        "확인못함": missing_must + missing_should,
        "필수누락": missing_must,          # 이게 있으면 조사가 덜 된 것
        "자료없음": empty,                 # 봤지만 자료가 없던 것
        "완료": len(missing_must) == 0,
    }


def _clean_conclusion(raw) -> dict:
    """모델이 엉뚱한 값을 줄 수 있으니 정해진 것만 남김"""
    if not isinstance(raw, dict):
        return {"위험도": "보통", "근거": [], "권고": "직접 확인 필요", "요약": str(raw)[:100]}

    level = str(raw.get("위험도", "")).strip()
    if level not in ("높음", "보통", "낮음"):
        level = "보통"

    action = str(raw.get("권고", "")).strip()
    if action not in ("계정 정지 검토", "경고 발송", "매물 숨김", "문제없음"):
        action = "직접 확인 필요"

    grounds = raw.get("근거", [])
    if isinstance(grounds, str):
        grounds = [grounds]
    grounds = [str(g)[:200] for g in grounds][:6]

    return {
        "위험도": level,
        "근거": grounds,
        "권고": action,
        "요약": str(raw.get("요약", ""))[:200],
    }


# ---------------------------------------------------------------
# 신고 하나를 조사해 결과를 DB에 적어둠
#
# 신고가 들어오는 즉시 별도 흐름에서 부름.
# 사용자는 기다리지 않고, 관리자는 나중에 정리된 결과를 봄
# ---------------------------------------------------------------
def build_question(report, db: Session) -> str:
    """신고 내용을 에이전트에게 건넬 문장으로.

    신고 사유를 그대로 믿지 말라고 프롬프트에 적어뒀으므로
    여기서는 있는 그대로 전달만 함
    """
    from database import Post

    if report.target_type == "post":
        post = db.get(Post, report.target_id)
        extra = f" (판매자는 {post.seller_id}번 회원)" if post else ""
        target = f"{report.target_id}번 매물{extra}"
    else:
        target = f"{report.target_id}번 회원"

    text = (f"{target} 이(가) '{report.reason}' 사유로 신고됐습니다. "
            f"신고자는 {report.reporter_id}번 회원입니다.")
    if report.detail:
        text += f" 신고자가 적은 내용: {report.detail[:200]}"
    return text


def investigate_report_now(report_id: int, mode: str = "solo"):
    """신고 하나를 조사해 결과를 저장. 별도 흐름에서 부르는 것을 전제로
    DB 창구를 직접 열고 닫음

    mode — solo: 혼자 다 봄 (기본) / team: 조사관 셋이 나눠 봄
           debate: 검사·변호인·정리
    """
    from database import SessionLocal, Report

    db = SessionLocal()
    try:
        report = db.get(Report, report_id)
        if report is None:
            return

        question = build_question(report, db)

        if mode == "team":
            import agent_team
            result = agent_team.investigate(question, db)
        elif mode == "debate":
            import agent_debate
            result = agent_debate.investigate(question, db)
        else:
            result = investigate(question, db)

        if "오류" in result:
            print(f"[조사] 신고 #{report_id} 건너뜀 — {result['오류']}")
            return

        conclusion = result["결론"]
        report.ai_risk = conclusion["위험도"]
        report.ai_action = conclusion["권고"]
        report.ai_summary = conclusion["요약"]
        report.ai_grounds = json.dumps(conclusion["근거"], ensure_ascii=False)
        # 도구가 돌려준 자료를 통째로 남김.
        # 요약만 남기면 관리자가 "정말 그런가" 를 확인할 방법이 없음.
        # 에이전트를 못 믿더라도 원본을 직접 볼 수 있어야 판단할 수 있다
        report.ai_steps = json.dumps(result["단계"], ensure_ascii=False, default=str)
        report.ai_coverage = json.dumps(result.get("점검", {}), ensure_ascii=False)
        report.ai_score = json.dumps(result.get("채점", {}), ensure_ascii=False)
        report.ai_mode = result.get("방식", "혼자 조사")
        report.ai_debate = (
            json.dumps(result["재판"], ensure_ascii=False) if result.get("재판") else None
        )
        report.ai_checked_at = datetime.utcnow()

        # 관리자에게 알림. 위험도가 높을수록 눈에 띄게
        _notify_admin(db, report, conclusion)

        db.commit()

        print(f"[조사] 신고 #{report_id} 완료 — "
              f"{conclusion['위험도']} / {conclusion['권고']} "
              f"({len(result['단계'])}단계)")

    except Exception as e:
        db.rollback()
        print(f"[조사] 신고 #{report_id} 실패 — {e}")
    finally:
        db.close()


def _notify_admin(db: Session, report, conclusion: dict):
    """조사가 끝났음을 관리자에게 알림.

    관리자가 대시보드를 계속 보고 있을 리 없으니,
    쌓아두었다가 들어왔을 때 보게 함
    """
    from database import AdminNotice, Post

    if report.target_type == "post":
        post = db.get(Post, report.target_id)
        target = post.title if post else f"{report.target_id}번 매물"
    else:
        target = f"{report.target_id}번 회원"

    level = conclusion["위험도"]
    grounds = conclusion.get("근거", [])

    db.add(AdminNotice(
        kind="report_done",
        title=f"[{level}] {target} — {conclusion['권고']}",
        body=conclusion["요약"] + (
            "\n근거: " + " / ".join(grounds[:3]) if grounds else ""
        ),
        link_type="report",
        link_id=report.id,
        level=level,
    ))
