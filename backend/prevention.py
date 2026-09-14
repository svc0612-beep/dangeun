"""
사전 예방 — 채팅 규칙 위반 누진 처리

채팅에서 위험 신호(선입금·택배 등)가 잡히면:
  1) 위반을 '증거'와 함께 violations 에 기록
  2) 최근 STRIKE_WINDOW_HOURS 안의 위반 수(활성 카운트)를 셈
  3) 카운트에 따라 단계별 조치 (매너온도 하락 → 매물 숨김 → 관리자 상정)

원칙 (지금까지 정한 설계 그대로)
  · 판정은 규칙(이 파일), 최종 정지 같은 무거운 결정은 사람(관리자)
  · 사람이 아니라 '행동'을 겨냥 — 경고 안내는 chats.py 가 양쪽에게 보여줌
  · 처벌은 시간이 지나면 풀림 — 활성 카운트가 '시간 창' 기준이라 자연히 해방
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

import badwords
from config import (
    PREVENTION_ON,        # 기능 on/off
    STRIKE_WINDOW_HOURS,  # 활성 카운트 유지 시간
    MANNER_PENALTY,       # 위반 1회당 매너온도 하락(도)
    STRIKE_STEPS,         # {2:"manner", 3:"hide", 4:"report"}
    COUNT_KINDS,          # 카운트에 셀 위반 종류 (기본 scam 만)
)
from database import Violation, User, AdminNotice


# STRIKE_STEPS 에서 각 조치가 시작되는 '문턱 횟수'를 뽑아둔다.
# config 의 숫자만 바꾸면 정책이 바뀌고, 이 코드는 그대로 둬도 된다.
def _threshold(action: str):
    for count, act in STRIKE_STEPS.items():
        if act == action:
            return count
    return None


MANNER_AT = _threshold("manner")   # 이 횟수부터 매너온도 하락
HIDE_AT = _threshold("hide")       # 이 횟수에 도달하면 매물 숨김
REPORT_AT = _threshold("report")   # 이 횟수 이상이면 관리자에게 상정


def active_strike_count(db: Session, user_id: int) -> int:
    """이 사람의 '활성' 위반 수.

    최근 STRIKE_WINDOW_HOURS 안에 있고, 아직 '무혐의(cleared)' 처리가
    안 된 위반만 센다.
      · 시각(created_at)만 보므로 로그아웃/재로그인으로는 못 피한다
      · 시간이 지난 위반은 자연히 빠져서 '해방' 된다
      · 관리자가 무혐의 처리한 것(cleared=True)은 빠진다 (되돌리기)
    """
    since = datetime.utcnow() - timedelta(hours=STRIKE_WINDOW_HOURS)
    return (
        db.query(Violation)
        .filter(
            Violation.user_id == user_id,
            Violation.cleared == False,   # noqa: E712 (SQLAlchemy 는 == False 를 씀)
            Violation.created_at >= since,
        )
        .count()
    )


def check(db: Session, room, sender: User, content: str):
    """메시지 하나를 검사해, 위반이면 기록하고 단계별 조치를 한다.

    room    — 이 메시지가 오간 채팅방 (ChatRoom)
    sender  — 이 메시지를 보낸 사람 (= 위반자)
    content — 메시지 내용

    돌려주는 값 — 무슨 조치를 했는지 요약 dict, 위반이 아니면 None.
    (DB 저장은 여기서 add/flush 만 하고, 최종 commit 은 부르는 쪽(chats.py)이 한다)
    """
    # 0) 기능이 꺼져 있거나 빈 메시지면 아무것도 안 함
    if not PREVENTION_ON or not content:
        return None

    # 1) 무엇이 걸렸는지 판정 (badwords 재사용)
    kind, hits = badwords.classify(content)

    # 사기 신호(scam)만 누진 카운트에 센다.
    # 욕설(curse) 같은 건 경고만 하고(그건 chats.py 담당) 여기선 세지 않는다.
    # → 오탐이 잦은 종류로 사람을 처벌하지 않기 위함 (낙인 방지)
    if kind not in COUNT_KINDS:
        return None

    # 2) 위반 1건을 '증거'와 함께 기록
    v = Violation(
        user_id=sender.id,
        rule=(hits[0] if hits else kind),   # 어긴 규칙 (첫 번째로 걸린 말)
        snippet=content[:200],              # 실제 문장 일부 = 관리자가 볼 증거
        room_id=room.id,
        kind=kind,
    )
    db.add(v)
    db.flush()   # 방금 기록을 아래 카운트에 포함시키려고 먼저 반영

    # 3) 활성 카운트 (방금 것 포함)
    count = active_strike_count(db, sender.id)

    actions = []   # 이번에 실제로 취한 조치들

    # 4-a) 매너온도 하락 — MANNER_AT 회부터 '매 위반마다' 조금씩 깎는다.
    #      1회는 봐준다(누구나 실수). 0도 밑으로는 안 내려가게 막는다.
    if MANNER_AT and count >= MANNER_AT:
        now_temp = sender.manner_temp if sender.manner_temp is not None else 36.5
        sender.manner_temp = round(max(0.0, now_temp - MANNER_PENALTY), 1)
        actions.append("manner")

    # 4-b) 매물 숨김 — HIDE_AT 회에 '도달한 순간' 한 번.
    #      단, 위반자가 '그 매물의 판매자' 일 때만 숨긴다.
    #      (구매자가 사기꾼인데 판매자 매물을 숨기면 애먼 사람이 피해 보니까)
    if HIDE_AT and count == HIDE_AT:
        post = getattr(room, "post", None)
        if post is not None and post.seller_id == sender.id and not post.is_hidden:
            post.is_hidden = True
            post.hidden_reason = "채팅 규칙 반복 위반"
            actions.append("hide")

    # 4-c) 관리자 상정 — REPORT_AT 회 이상이면 알림을 만든다.
    #      단, 같은 사람에 대한 '안 읽은' 상정 알림이 이미 있으면 또 만들지 않는다.
    #      (메시지마다 알림이 쌓여 관리자를 도배하는 걸 막음)
    if REPORT_AT and count >= REPORT_AT:
        dup = (
            db.query(AdminNotice)
            .filter(
                AdminNotice.kind == "risk_user",
                AdminNotice.link_type == "user",
                AdminNotice.link_id == sender.id,
                AdminNotice.is_read == False,
            )
            .first()
        )
        if dup is None:
            who = sender.nickname or sender.username
            db.add(AdminNotice(
                kind="risk_user",
                title=f"{who} 님, 채팅 규칙 {count}회 위반 — 확인 필요",
                body=_evidence_text(db, sender.id),   # 근거(위반 문장) 몇 줄
                link_type="user",
                link_id=sender.id,
                level="높음",
            ))
            actions.append("report")

    # commit 은 부르는 쪽에서 (한 트랜잭션으로 묶기 위해)
    return {"count": count, "kind": kind, "rule": v.rule, "actions": actions}


def _evidence_text(db: Session, user_id: int, limit: int = 5) -> str:
    """관리자 알림에 넣을 근거 — 이 사람의 최근 위반 문장 몇 줄"""
    rows = (
        db.query(Violation)
        .filter(Violation.user_id == user_id, Violation.cleared == False)
        .order_by(Violation.created_at.desc())
        .limit(limit)
        .all()
    )
    lines = [f'· [{v.rule}] "{v.snippet}"' for v in rows]
    return "\n".join(lines) if lines else "(근거 없음)"
