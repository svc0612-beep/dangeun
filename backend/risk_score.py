"""
위험도 채점 — 에이전트가 모은 자료를 규칙으로 점수 매기기

왜 LLM 에게 맡기지 않는가

    같은 자료를 두 번 보여줘도 다르게 답할 수 있다.
    관리자는 "왜 높음인지" 를 검증할 방법이 없다.
    "AI가 그랬대요" 는 계정을 정지시킬 근거가 못 된다.

그래서 나눴다

    자료 모으기   ← 에이전트 (무엇을 볼지 스스로 정하는 것, 잘하는 일)
    점수 계산     ← 이 파일 (규칙. 같은 자료면 늘 같은 점수)
    설명 쓰기     ← 에이전트 (숫자를 사람 말로 풀어주기만)

점수는 확률이 아니다. "이런 신호가 이만큼 겹쳤다" 를 세는 눈금일 뿐이고,
최종 판단은 사람이 한다
"""

from typing import Optional


# ---------------------------------------------------------------
# 채점표
#
# 점수를 정한 기준
#   3점 — 그것만으로도 거래를 말릴 만한 것
#   2점 — 겹치면 위험해지는 것
#   1점 — 참고만 할 것
# ---------------------------------------------------------------
RULES = [
    # --- 매물에서 ---
    {
        "이름": "직거래 원칙 위반 문구",
        "점수": 3,
        "설명": "택배·선입금·비대면을 유도하는 말이 있음",
    },
    {
        "이름": "사진 도용",
        "점수": 3,
        "설명": "먼저 올라온 남의 매물과 같은 사진을 씀",
    },
    {
        "이름": "시세보다 크게 낮음",
        "점수": 2,
        "설명": "같은 분류 중간값의 절반 이하",
    },
    {
        "이름": "사진 없음",
        "점수": 1,
        "설명": "물건을 보여주지 않음",
    },

    # --- 판매자에서 ---
    {
        "이름": "거래 이력 없음",
        "점수": 2,
        "설명": "판매·구매 완료가 한 건도 없음",
    },
    {
        "이름": "취소가 잦음",
        "점수": 2,
        "설명": "거래 취소가 3회 이상",
    },
    {
        "이름": "가입한 지 얼마 안 됨",
        "점수": 1,
        "설명": "가입 7일 이내",
    },
    {
        "이름": "신고를 여러 번 받음",
        "점수": 2,
        "설명": "이 건 말고도 신고가 2회 이상",
    },
    {
        "이름": "매너온도가 낮음",
        "점수": 1,
        "설명": "36.5도 미만",
    },

    # --- 대화에서 ---
    {
        "이름": "대화에 위험 문구",
        "점수": 3,
        "설명": "채팅에서 선입금·택배 등을 요구함",
    },

    # --- 관계에서 ---
    {
        "이름": "무리로 움직임",
        "점수": 3,
        "설명": "특정 상대와만 거래하거나 후기를 주고받음",
    },
]

RULE_BY_NAME = {r["이름"]: r for r in RULES}


# 점수 합계로 위험도를 정하는 문턱
HIGH = 6      # 이상이면 높음
MEDIUM = 3    # 이상이면 보통


def _num(text) -> Optional[float]:
    """'720,000원' 같은 글자에서 숫자만 꺼냄"""
    if isinstance(text, (int, float)):
        return float(text)
    if not isinstance(text, str):
        return None

    digits = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def score(steps: list) -> dict:
    """에이전트가 모은 자료를 보고 점수를 매긴다.

    steps — agent.investigate 가 돌려준 "단계" 목록.
            각 항목에 도구 이름과 그 도구가 돌려준 결과가 들어 있다
    """
    hits = []          # 걸린 신호들
    seen = {}          # 도구 이름 → 결과

    for s in steps:
        name = s.get("도구")
        result = s.get("결과")
        if isinstance(result, dict):
            seen[name] = result

    def add(rule_name: str, detail: str = ""):
        rule = RULE_BY_NAME.get(rule_name)
        if rule is None:
            return
        hits.append({
            "신호": rule_name,
            "점수": rule["점수"],
            "설명": detail or rule["설명"],
        })

    # ── 매물 ─────────────────────────────────────────
    post = seen.get("매물_보기", {})
    if post:
        bad = post.get("위험문구")
        if isinstance(bad, list) and bad:
            add("직거래 원칙 위반 문구", f"본문·제목에 {', '.join(bad[:3])}")

        if post.get("사진수") == 0:
            add("사진 없음")

    # ── 사진 도용 ────────────────────────────────────
    img = seen.get("사진_도용검사", {})
    if img and img.get("겹친것"):
        first = img["겹친것"][0]
        add("사진 도용",
            f"{first.get('그판매자','다른 회원')}님의 '{first.get('겹친매물','')}' 와 같은 사진")

    # ── 시세 ─────────────────────────────────────────
    price = seen.get("시세_견주기", {})
    ratio_text = price.get("비율", "")
    if "%" in str(ratio_text):
        pct = _num(str(ratio_text).split("%")[0].split()[-1])
        if pct is not None and pct <= 50:
            add("시세보다 크게 낮음", f"같은 분류 중간값의 {int(pct)}%")

    # ── 판매자 ───────────────────────────────────────
    seller = seen.get("판매자_이력", {})
    if seller:
        sold = seller.get("판매완료", 0) or 0
        bought = seller.get("구매완료", 0) or 0
        if sold + bought == 0:
            add("거래 이력 없음", "판매·구매 완료 0건")

        cancels = seller.get("거래취소", 0) or 0
        if cancels >= 3:
            add("취소가 잦음", f"거래 취소 {cancels}회")

        joined = str(seller.get("가입", ""))
        if "오늘" in joined:
            add("가입한 지 얼마 안 됨", "오늘 가입")
        elif "일 전" in joined:
            days = _num(joined)
            if days is not None and days <= 7:
                add("가입한 지 얼마 안 됨", f"가입 {int(days)}일 전")

        reported = seller.get("신고당한횟수", 0) or 0
        if reported >= 2:
            add("신고를 여러 번 받음", f"신고 {reported}회")

        temp = seller.get("매너온도")
        if isinstance(temp, (int, float)) and temp < 36.5:
            add("매너온도가 낮음", f"매너온도 {temp}도")

    # ── 대화 ─────────────────────────────────────────
    chat = seen.get("채팅_기록", {})
    chat_bad = chat.get("위험문구")
    if isinstance(chat_bad, list) and chat_bad:
        add("대화에 위험 문구", f"채팅에서 {', '.join(chat_bad[:3])}")

    # ── 관계 ─────────────────────────────────────────
    group = seen.get("무리_확인", {})
    if group and (group.get("의심되는상대") or 0) > 0:
        add("무리로 움직임", group.get("판단", ""))

    total = sum(h["점수"] for h in hits)

    if total >= HIGH:
        level = "높음"
    elif total >= MEDIUM:
        level = "보통"
    else:
        level = "낮음"

    return {
        "위험도": level,
        "총점": total,
        "신호": sorted(hits, key=lambda h: -h["점수"]),
        "기준": f"{HIGH}점 이상 높음 · {MEDIUM}점 이상 보통 · 그 아래 낮음",
        "권고": recommend(level, hits),
        # 점수보다 무거운 권고가 나온 까닭. 없으면 빈 글
        "권고사유": override_reason(hits),
    }


def override_reason(hits: list) -> str:
    """점수와 상관없이 무거운 권고가 나온 까닭.

    "보통 5점" 인데 "계정 정지 검토" 가 나오면 관리자가 헷갈린다.
    왜 그런지 한 줄로 알려준다
    """
    names = {h["신호"] for h in hits}

    if "사진 도용" in names:
        return "남의 사진을 퍼왔습니다 — 점수와 상관없이 정지를 검토합니다"
    if "무리로 움직임" in names:
        return "여럿이 짜고 하는 정황이 있습니다 — 점수와 상관없이 정지를 검토합니다"
    return ""


def recommend(level: str, hits: list) -> str:
    """점수와 신호로 권고를 정한다. 이것도 규칙이지 판단이 아니다"""
    names = {h["신호"] for h in hits}

    # 사진 도용이나 무리 활동은 다른 사람에게 계속 피해를 준다
    if "사진 도용" in names or "무리로 움직임" in names:
        return "계정 정지 검토"

    if level == "높음":
        return "계정 정지 검토"
    if level == "보통":
        return "경고 발송"

    # 낮음이어도 매물 자체에 문제가 있으면 그 매물만 내린다.
    # 사람에게는 손대지 않는다 — 초보가 서툴게 쓴 것일 수 있으므로
    post_problems = {"직거래 원칙 위반 문구", "시세보다 크게 낮음", "사진 없음"}
    if names & post_problems:
        return "매물 숨김"

    # "가입 7일차" 처럼 사람에 대한 신호만 있으면 아무것도 하지 않는다.
    # 새 사용자는 다 그렇기 때문
    return "문제없음"
