"""
조사관 여럿이 한꺼번에 — 나눠 보고 모으기

혼자 다 보면 차례로 도느라 오래 걸린다.
    매물 → 판매자 → 사진 → 시세 → 관계 → 결론    40초

셋으로 나눠 한꺼번에 돌리면
    매물 조사관 ┐
    판매자 조사관├→ 동시에 →  모아서 채점        15초
    관계 조사관 ┘

빨라지는 것 말고도 얻는 게 있다.
맡은 몫이 좁으면 프롬프트가 짧아져서 12B 모델이 덜 헤맨다.
"매물만 보세요" 라고 하면 매물에 집중한다

판정은 여전히 규칙이 한다. 조사관들은 자료를 모을 뿐이고,
마지막에 한 번만 risk_score 가 채점한다
"""

import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

import agent
import prompts
import query_ai
import risk_score
from database import SessionLocal


# ---------------------------------------------------------------
# 조사관 셋
#
# 서로 겹치지 않게 몫을 나눴다. 겹치면 같은 도구를 두 번 부르게 된다
# ---------------------------------------------------------------
INVESTIGATORS = [
    {
        "이름": "매물 조사관",
        "몫": "매물 자체",
        "지시서": "post_inspector",
        "도구": ["매물_보기", "시세_견주기", "사진_도용검사"],
        "걸음": 4,
    },
    {
        "이름": "이력 조사관",
        "몫": "판매자와 대화",
        "지시서": "history_inspector",
        "도구": ["판매자_이력", "채팅_기록", "신고자_이력"],
        "걸음": 4,
    },
    {
        "이름": "관계 조사관",
        "몫": "함께 움직이는 사람",
        "지시서": "network_inspector",
        "도구": ["무리_확인", "판매자_이력"],
        "걸음": 3,
    },
]


def _run_one(spec: dict, question: str, on_step=None, note: str = None) -> dict:
    """조사관 하나를 돌린다.

    각자 자기 DB 연결을 쓴다 — 여러 흐름이 한 연결을 나눠 쓰면 어긋난다
    """
    db = SessionLocal()
    started = time.time()

    try:
        def wrapped(step):
            # 어느 조사관이 부른 것인지 표시
            step["조사관"] = spec["이름"]
            if on_step:
                on_step(step)

        # finish=False — 채점은 마지막에 한 번만
        result = agent.investigate(
            question, db,
            on_step=wrapped,
            tools=spec["도구"],
            role=prompts.build(spec["지시서"]),
            max_steps=spec["걸음"],
            finish=False,
            note=note,
        )

        steps = result.get("단계", [])
        for s in steps:
            s["조사관"] = spec["이름"]

        return {
            "이름": spec["이름"],
            "몫": spec["몫"],
            "단계": steps,
            "메모": result.get("메모"),
            "걸린시간": round(time.time() - started, 1),
        }

    except Exception as e:
        return {
            "이름": spec["이름"],
            "몫": spec["몫"],
            "단계": [],
            "메모": None,
            "오류": str(e),
            "걸린시간": round(time.time() - started, 1),
        }
    finally:
        db.close()


def investigate(question: str, db: Session, on_step=None, note: str = None) -> dict:
    """조사관 셋을 한꺼번에 돌리고 모은다.

    db 는 채점과 마무리에만 쓴다. 조사관들은 각자 연결을 연다
    """
    if not query_ai.is_ready():
        return {"오류": "이 기기에서는 조사 기능을 쓸 수 없습니다"}

    started = time.time()

    # 셋을 동시에. 순서대로 돌면 나눈 뜻이 없다
    with ThreadPoolExecutor(max_workers=len(INVESTIGATORS)) as pool:
        futures = [
            pool.submit(_run_one, spec, question, on_step, note)
            for spec in INVESTIGATORS
        ]
        reports = [f.result() for f in futures]

    # 모든 걸음을 한 줄로 모아 채점한다.
    # 같은 도구를 둘이 불렀으면 하나만 남긴다 — 점수가 두 번 매겨지면 안 됨
    merged = []
    seen = set()
    for rep in reports:
        for step in rep["단계"]:
            key = (step["도구"], str(step["인자"]))
            if key in seen:
                continue
            seen.add(key)
            merged.append(step)

    for i, step in enumerate(merged, 1):
        step["순서"] = i

    graded = risk_score.score(merged)

    # 조사관들이 남긴 메모를 근거로 모은다
    grounds = []
    for rep in reports:
        memo = rep.get("메모") or {}
        for g in (memo.get("근거") or []):
            text = str(g)[:200]
            if text and text not in grounds:
                grounds.append(text)

    # 아무도 근거를 안 남겼으면 채점 내용을 대신 쓴다.
    # 근거 줄이 비어 있으면 관리자가 무엇을 보고 판단할지 알 수 없다
    if not grounds:
        grounds = [f"{h['신호']} — {h['설명']}" for h in graded.get("신호", [])]

    return {
        "방식": "여럿이 나눠 조사",
        "조사관": [
            {
                "이름": r["이름"],
                "몫": r["몫"],
                "걸음": len(r["단계"]),
                "걸린시간": r["걸린시간"],
                "요약": (r.get("메모") or {}).get("요약", ""),
                "오류": r.get("오류"),
            }
            for r in reports
        ],
        "단계": merged,
        "점검": agent.coverage(merged),
        "채점": graded,
        "걸린시간": round(time.time() - started, 1),
        "결론": {
            "위험도": graded["위험도"],
            "총점": graded["총점"],
            "권고": graded["권고"],
            "근거": grounds[:6],
            "요약": _summary(reports, graded),
        },
    }


def _summary(reports: list, graded: dict) -> str:
    """조사관들의 말을 한 줄로.

    아무도 요약을 안 남겼으면 채점 결과로 대신 만든다 —
    "위험 신호 3가지" 보다 무엇이 걸렸는지를 적는 편이 쓸모 있다
    """
    parts = []
    for r in reports:
        memo = r.get("메모") or {}
        text = str(memo.get("요약", "")).strip()
        if text:
            parts.append(f"{r['이름']}: {text}")

    if parts:
        return " / ".join(parts)[:300]

    signals = graded.get("신호", [])
    if not signals:
        return "조사관 셋이 나눠 살펴봤으나 걸린 위험 신호가 없습니다."

    names = " · ".join(h["신호"] for h in signals[:3])
    return f"조사관 셋이 나눠 살펴봤습니다. {names} 가 걸렸습니다."
