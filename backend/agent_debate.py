"""
검사 · 변호인 · 정리 담당 — 서로 견줘 보기

한 사람이 조사하면 처음 본 신호에 끌려간다.
"선입금" 을 발견하면 그 뒤로는 사기라는 눈으로만 자료를 읽는다.

그래서 둘로 나눴다.

    검사     — 같은 자료에서 위험한 쪽을 짚는다
    변호인   — 같은 자료에서 억울할 만한 쪽을 짚는다
    정리 담당 — 양쪽 말을 듣고 정리한다 (판결하지 않는다)

위험도는 여전히 risk_score 가 규칙으로 계산한다.
정리 담당도 점수를 정하지 않는다 — 양쪽 주장을 관리자가 읽을 수 있게 정리할 뿐이다.

이 방식의 값어치는 속도가 아니라 **억울한 사람을 걸러내는 것** 이다.
초보 판매자가 사기꾼처럼 보이는 일이 흔하기 때문에
"가입 7일차" 를 위험으로만 읽으면 새 사용자가 계속 정지된다
"""

import json
import time

from sqlalchemy.orm import Session

import agent
import agent_tools
import prompts
import query_ai
import risk_score
from config import OLLAMA_MODEL
from database import SessionLocal


AGENT_TIMEOUT = 120








def _ask(prompt: str) -> dict:
    """모델에게 한 번 묻고 JSON 을 받아온다"""
    data = query_ai._post_json("/api/generate", {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2, "num_predict": 500},
    }, AGENT_TIMEOUT)

    if data is None:
        return {}

    parsed = agent._extract_json(data.get("response", ""))
    return parsed or {}


def _evidence_text(steps: list) -> str:
    """검사가 모은 자료를 변호인이 읽을 수 있게 펼침"""
    lines = []
    for s in steps:
        result = json.dumps(s.get("결과", {}), ensure_ascii=False)[:500]
        lines.append(f"[{s['도구']}] {result}")
    return "\n".join(lines) if lines else "(모은 자료가 없습니다)"


def investigate(question: str, db: Session, on_step=None, note: str = None) -> dict:
    """검사 → 변호인 → 정리 담당 순으로 돌린다"""
    if not query_ai.is_ready():
        return {"오류": "이 기기에서는 조사 기능을 쓸 수 없습니다"}

    started = time.time()

    # ── 1. 검사가 자료를 모으고 주장을 편다 ──────────
    t = time.time()
    result = agent.investigate(
        question, db,
        on_step=on_step,
        role=prompts.build("prosecutor"),
        finish=False,
        note=note,
    )
    steps = result.get("단계", [])
    claim = result.get("메모") or {}
    prosecutor_time = round(time.time() - t, 1)

    claim_text = "\n".join(f"- {g}" for g in (claim.get("근거") or [])) or "(주장 없음)"
    if claim.get("요약"):
        claim_text += f"\n요약: {claim['요약']}"

    # ── 2. 변호인이 같은 자료를 다르게 읽는다 ────────
    t = time.time()
    defense = _ask(prompts.build(
        "defender",
        evidence=_evidence_text(steps),
        claim=claim_text,
    ))
    defender_time = round(time.time() - t, 1)

    # ── 3. 규칙이 채점한다. 양쪽 말과 무관하게 ───────
    graded = risk_score.score(steps)

    defense_text = "\n".join(f"- {r}" for r in (defense.get("반론") or [])) or "(반론 없음)"
    if defense.get("인정"):
        defense_text += "\n인정한 것: " + ", ".join(defense["인정"])

    # ── 4. 정리 담당이 양쪽 말을 정리한다 ───────────────────────────
    t = time.time()
    verdict = _ask(prompts.build(
        "summarizer",
        claim=claim_text,
        defense=defense_text,
        level=graded["위험도"],
        score=graded["총점"],
        signals=", ".join(h["신호"] for h in graded["신호"]) or "없음",
    ))
    summary_time = round(time.time() - t, 1)

    return {
        "방식": "검사·변호인·정리",
        "재판": {
            "검사": {
                "주장": claim.get("근거") or [],
                "요약": claim.get("요약", ""),
                "걸린시간": prosecutor_time,
            },
            "변호인": {
                "반론": defense.get("반론") or [],
                "인정": defense.get("인정") or [],
                "요약": defense.get("요약", ""),
                "걸린시간": defender_time,
            },
            "정리": {
                "정리": verdict.get("정리", ""),
                "남은의문": verdict.get("남은의문") or [],
                "걸린시간": summary_time,
            },
        },
        "단계": steps,
        "점검": agent.coverage(steps),
        "채점": graded,
        "걸린시간": round(time.time() - started, 1),
        "결론": {
            "위험도": graded["위험도"],
            "총점": graded["총점"],
            "권고": graded["권고"],
            # 근거는 검사의 주장 + 변호인이 인정한 것
            "근거": _merge_grounds(claim, defense, graded),
            "요약": verdict.get("정리") or _fallback(graded),
        },
    }


def _merge_grounds(claim: dict, defense: dict, graded: dict) -> list:
    """양쪽 말을 근거로 모은다.

    변호인의 반론도 함께 남긴다 — 관리자가 한쪽 말만 보고
    정지시키는 일이 없도록
    """
    out = []

    for g in (claim.get("근거") or [])[:4]:
        out.append(f"[검사] {str(g)[:150]}")

    for r in (defense.get("반론") or [])[:3]:
        out.append(f"[변호] {str(r)[:150]}")

    if not out:
        out = [f"{h['신호']} — {h['설명']}" for h in graded.get("신호", [])]

    return out[:8]


def _fallback(graded: dict) -> str:
    signals = graded.get("신호", [])
    if not signals:
        return "양쪽 말을 들었으나 걸린 위험 신호가 없습니다."
    names = " · ".join(h["신호"] for h in signals[:3])
    return f"검사와 변호인의 말을 들었습니다. {names} 가 걸렸습니다."
