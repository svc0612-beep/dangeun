"""
채팅 자동완성 — 실제 대화를 분석해 추천 문구 만들기

messages 테이블에 쌓인 대화를 읽어 "어느 단계에서 어떤 말이 자주 나오는지"
를 세고, 그 결과를 채팅창 추천 문구로 씀.

사람이 목록을 고치지 않아도 대화가 쌓일수록 실제 말투에 가까워짐.
config.CHAT_SUGGESTIONS 는 자료가 모자랄 때 쓰는 기본값

메시지가 오갈 때마다 learn_one() 이 그 한 줄만 셈에 더한다.
서버를 껐다 켜지 않아도 새 대화가 바로 반영됨
"""

import json
import os
import threading
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database import ChatRoom, Message
import badwords
from config import MIN_COUNT


# 단계별로 최대 몇 개까지 보여줄지
MAX_TIPS = 6


# 분석 결과를 담아두는 곳. 매 요청마다 다시 세면 느려짐
LEARNED_TIPS: dict[tuple, list[str]] = {}


LEARNED_AT: Optional[datetime] = None


# (역할, 단계) → {문장: 나온 횟수}
#
# 전에는 대화 전체를 매번 다시 셌다. 대화가 몇 만 줄이 되면 몇 초씩 걸려서
# 서버를 켤 때 한 번만 돌렸고, 그래서 새 대화가 바로 반영되지 않았다.
#
# 이제는 횟수를 여기 기억해두고, 새 말이 오면 그 한 줄만 더한다.
# 대화가 아무리 쌓여도 한 줄 더하는 값은 같다
COUNTS: dict[tuple, dict[str, int]] = {}

# 여러 사람이 동시에 말할 수 있으므로 셈이 어긋나지 않게 잠금
_lock = threading.Lock()

# 파일에 쓰는 것은 잦으면 느려진다. 몇 번 바뀌면 한 번씩 저장
_dirty = 0
SAVE_EVERY = 20




def message_stage(msg: Message, room: ChatRoom, order: int) -> str:
    """이 말이 대화의 어느 단계에서 나왔는지 판단"""
    decided = room.buyer_decided_at
    confirmed = room.seller_confirmed_at

    if confirmed and msg.created_at >= confirmed:
        return "done"
    if decided and msg.created_at >= decided:
        return "reserved"
    # 각자 처음 두 마디까지는 "첫 인사"로 봄
    return "first" if order < 2 else "talking"




def rebuild_tips(db: Session) -> dict:
    """대화를 다시 세어 추천 문구를 만듦"""
    global LEARNED_TIPS, LEARNED_AT

    # (역할, 단계) → {문장: 횟수}
    counter: dict[tuple, dict[str, int]] = {}

    rooms = db.query(ChatRoom).all()
    for room in rooms:
        seller_id = room.post.seller_id
        # 사람이 쓴 말만. 시스템 안내와 사진은 뺌
        texts = [m for m in room.messages if m.kind == "text"]

        # 사람별로 몇 번째 말인지 세기 위해
        seen = {room.buyer_id: 0, seller_id: 0}

        for msg in texts:
            if msg.sender_id is None:
                continue
            role = "buyer" if msg.sender_id == room.buyer_id else "seller"
            order = seen.get(msg.sender_id, 0)
            seen[msg.sender_id] = order + 1

            stage = message_stage(msg, room, order)
            # 예약중·거래완료 단계는 역할을 나누지 않음 (둘 다 비슷한 말을 씀)
            key = ("both", stage) if stage in ("reserved", "done") else (role, stage)

            text = msg.content.strip()
            # 너무 짧거나 긴 말은 추천으로 쓸 수 없음
            if not (4 <= len(text) <= 40):
                continue

            # 욕설·사기 문구는 추천에서 뺌.
            # 사기꾼이 "선입금 부탁드려요" 를 여러 번 쓰면 그게 추천이 되어
            # 앱이 사기를 거드는 꼴이 됨
            if not badwords.is_clean(text):
                continue

            counter.setdefault(key, {})
            counter[key][text] = counter[key].get(text, 0) + 1

    # 많이 나온 순으로 추리기
    learned = {}
    for key, freq in counter.items():
        picked = [t for t, c in sorted(freq.items(), key=lambda x: -x[1]) if c >= MIN_COUNT]
        if picked:
            learned[key] = picked[:MAX_TIPS]

    # 나중에 한 줄씩 더할 수 있게 횟수도 기억해둔다
    global COUNTS
    COUNTS = counter

    LEARNED_TIPS = learned
    LEARNED_AT = datetime.utcnow()

    return {
        "rooms": len(rooms),
        "groups": len(learned),
        "learned_at": LEARNED_AT,
        # 어떤 말이 뽑혔는지 눈으로 확인할 수 있게
        "tips": {f"{k[0]}/{k[1]}": v for k, v in learned.items()},
    }


# ---------------------------------------------------------------
# 새 말 하나를 바로 배우기
#
# 메시지가 오갈 때마다 부른다. 대화 전체를 다시 세지 않고
# 그 한 줄만 횟수에 더한 뒤, 그 묶음의 추천 목록만 다시 고른다.
#
# 대화가 몇 만 줄이 되어도 한 줄 더하는 값은 같다
# ---------------------------------------------------------------
def learn_one(msg: Message, room: ChatRoom, db: Session = None) -> bool:
    """메시지 하나를 추천 문구 셈에 반영.

    배웠으면 True. 걸러졌으면 False
    """
    if msg is None or room is None:
        return False
    if msg.kind != "text" or msg.sender_id is None:
        return False

    text = (msg.content or "").strip()

    # 너무 짧거나 긴 말은 추천으로 쓸 수 없음
    if not (4 <= len(text) <= 40):
        return False

    # 욕설·사기 문구는 배우지 않음.
    # 사기꾼이 "선입금 부탁드려요" 를 여러 번 쓰면 그게 추천이 되어
    # 앱이 사기를 거드는 꼴이 됨
    if not badwords.is_clean(text):
        return False

    try:
        seller_id = room.post.seller_id
    except Exception:
        return False

    role = "buyer" if msg.sender_id == room.buyer_id else "seller"

    # 이 사람이 이 방에서 몇 번째로 말했는지 —
    # "첫 인사" 인지 아닌지를 가르는 데 필요함
    order = sum(
        1 for m in room.messages
        if m.kind == "text"
        and m.sender_id == msg.sender_id
        and m.id != msg.id
        and m.created_at <= msg.created_at
    )

    stage = message_stage(msg, room, order)
    # 예약중·거래완료 단계는 역할을 나누지 않음 (둘 다 비슷한 말을 씀)
    key = ("both", stage) if stage in ("reserved", "done") else (role, stage)

    global _dirty

    with _lock:
        COUNTS.setdefault(key, {})
        COUNTS[key][text] = COUNTS[key].get(text, 0) + 1

        # 이 묶음만 다시 고름. 다른 묶음은 건드리지 않음
        freq = COUNTS[key]
        picked = [
            t for t, c in sorted(freq.items(), key=lambda x: -x[1])
            if c >= MIN_COUNT
        ][:MAX_TIPS]

        if picked:
            LEARNED_TIPS[key] = picked
        else:
            LEARNED_TIPS.pop(key, None)

        _dirty += 1
        need_save = _dirty >= SAVE_EVERY

    # 파일 쓰기는 잠금 밖에서. 느린 일을 잠근 채로 하면 다른 사람이 기다림
    if need_save:
        save_tips()
        with _lock:
            _dirty = 0

    return True


def learn_later(message_id: int, room_id: int):
    """별도 흐름에서 배우게 함.

    메시지를 보내는 사람이 기다리지 않도록.
    DB 연결을 새로 여는 이유 — 다른 흐름의 연결을 나눠 쓰면 어긋남
    """
    from database import SessionLocal

    db = SessionLocal()
    try:
        msg = db.get(Message, message_id)
        room = db.get(ChatRoom, room_id)
        if msg and room:
            learn_one(msg, room, db)
    except Exception as e:
        print(f"[추천 문구] 배우기 실패 — {e}")
    finally:
        db.close()


# ---------------------------------------------------------------
# 분석 결과를 파일로 남기기
#
# 대화를 지워도 추천 문구는 남게 하기 위함.
# 시험용 대화로 한 번 배워두면, 그 대화를 다 지워도
# 실제 사용자에게는 계속 추천이 나감
# ---------------------------------------------------------------
# 어디서 실행하든 backend 폴더의 파일을 쓰게 함
TIPS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "learned_tips.json"
)


def save_tips() -> bool:
    """지금 배운 문구를 파일로 저장"""
    if not LEARNED_TIPS:
        return False
    try:
        # 키가 ("buyer","first") 같은 묶음이라 파일에 그대로 못 넣음.
        # "buyer|first" 형태의 글자로 바꿔서 저장
        data = {f"{k[0]}|{k[1]}": v for k, v in LEARNED_TIPS.items()}
        with open(TIPS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[추천 문구] {len(data)}개 묶음을 {TIPS_FILE} 에 저장")
        return True
    except Exception as e:
        print(f"[추천 문구] 저장 실패 — {e}")
        return False


def load_tips() -> bool:
    """파일에 저장해둔 문구를 불러옴"""
    global LEARNED_TIPS
    if not os.path.exists(TIPS_FILE):
        return False
    try:
        with open(TIPS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        LEARNED_TIPS = {tuple(k.split("|")): v for k, v in data.items()}
        print(f"[추천 문구] {len(LEARNED_TIPS)}개 묶음을 파일에서 불러옴")
        return True
    except Exception as e:
        print(f"[추천 문구] 불러오기 실패 — {e}")
        return False


def prepare(db: Session):
    """서버 시작 때 부름.

    대화가 넉넉하면 그걸로 배우고 파일에 남김.
    대화가 없거나 적으면 예전에 저장해둔 파일을 씀 —
    시험용 대화를 지운 뒤에도 추천이 이어지도록
    """
    rooms = db.query(ChatRoom).count()

    if rooms >= 5:
        rebuild_tips(db)
        if LEARNED_TIPS:
            save_tips()
            return

    load_tips()
