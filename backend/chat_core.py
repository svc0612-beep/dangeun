"""
채팅의 공통 부분

채팅방을 꺼내오고 화면에 보낼 형태로 만드는 일, 그리고 WebSocket 연결 관리.
채팅 화면(routers/chats.py)과 후기(routers/reviews.py)가 함께 씀
"""

from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import HTTPException, WebSocket
from sqlalchemy.orm import Session

from database import User, Post, ChatRoom, Message, Review
from config import SECRET_KEY, ALGORITHM




# ---------------------------------------------------------------
# 채팅 - 공통 도구
# ---------------------------------------------------------------
def get_room_or_404(room_id: int, db: Session, user: User) -> ChatRoom:
    """방을 가져오면서 내가 그 방의 당사자인지도 확인.
    구매자도 판매자도 아니면 남의 대화를 훔쳐보는 것이므로 막음"""
    room = db.get(ChatRoom, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다")

    if user.id != room.buyer_id and user.id != room.post.seller_id:
        raise HTTPException(status_code=403, detail="참여 중인 대화가 아닙니다")

    return room




def build_room(room: ChatRoom, user: User, db: Session) -> dict:
    """채팅방 하나를 화면에 보낼 형태로 만듦"""
    is_buyer = user.id == room.buyer_id

    # 내가 마지막으로 읽은 시각 이후에 온, 내가 안 보낸 메시지 수
    read_at = room.buyer_read_at if is_buyer else room.seller_read_at
    q = db.query(Message).filter(
        Message.room_id == room.id,
        Message.sender_id != user.id,
    )
    if read_at is not None:
        q = q.filter(Message.created_at > read_at)
    unread = q.count()

    # 목록에 보여줄 마지막 대화 한 줄
    last = (
        db.query(Message)
        .filter(Message.room_id == room.id)
        .order_by(Message.created_at.desc())
        .first()
    )

    partner = room.post.seller if is_buyer else room.buyer

    # 후기 상태 (거래 확정 후에만 쓸 수 있음)
    both_decided = room.buyer_decided_at is not None and room.seller_confirmed_at is not None
    wrote = (
        db.query(Review)
        .filter(Review.room_id == room.id, Review.reviewer_id == user.id)
        .first()
        is not None
    )

    return {
        "id": room.id,
        "partner_id": partner.id,
        "can_review": both_decided and not wrote,
        "my_review_done": wrote,
        "partner": {
            "nickname": partner.nickname,
            "region": partner.region,
            "manner_temp": partner.manner_temp,
            "completed_deals": partner.completed_deals,
            "completed_purchases": partner.completed_purchases,
            "cancel_count": partner.cancel_count,
        },
        "post": {
            "id": room.post.id,
            "title": room.post.title,
            "price": room.post.price,
            "status": room.post.status,
            "thumbnail": room.post.images[0].image_url if room.post.images else None,
            "place_name": room.post.place_name,
        },
        "partner_nickname": room.post.seller.nickname if is_buyer else room.buyer.nickname,
        "my_role": "buyer" if is_buyer else "seller",
        "buyer_decided": room.buyer_decided_at is not None,
        "seller_confirmed": room.seller_confirmed_at is not None,
        "unread_count": unread,
        "last_message": last.content if last else None,
        "last_message_at": room.last_message_at,
    }




def add_system_message(db: Session, room: ChatRoom, text: str):
    """서버가 남기는 안내. 보낸 사람이 없어서 화면에서 가운데 정렬로 그려짐"""
    msg = Message(room_id=room.id, sender_id=None, content=text, kind="system")
    db.add(msg)
    room.last_message_at = datetime.utcnow()
    return msg




# ===============================================================
# 실시간 채팅 (WebSocket)
#
# 일반 API는 "물어보면 답한다"라서 새 메시지가 왔는지 알려면
# 계속 물어봐야 함(폴링). WebSocket은 연결을 열어두고
# 서버가 먼저 밀어줄 수 있어서 즉시 도착함
# ===============================================================
class ConnectionManager:
    """방 번호별로 열려 있는 연결을 모아둠.
    한 사람이 여러 탭을 열 수도 있어서 방마다 목록으로 관리함"""

    def __init__(self):
        self.rooms: dict[int, list[WebSocket]] = {}

    async def connect(self, room_id: int, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(room_id, []).append(ws)

    def disconnect(self, room_id: int, ws: WebSocket):
        conns = self.rooms.get(room_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self.rooms.pop(room_id, None)   # 아무도 없으면 방 자체를 지움

    async def broadcast(self, room_id: int, payload: dict):
        """그 방에 연결된 모두에게 보냄. 보낸 사람도 포함 —
        화면이 서버가 저장한 값을 그대로 받아 그리게 하려고"""
        dead = []
        for ws in list(self.rooms.get(room_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)     # 이미 끊긴 연결
        for ws in dead:
            self.disconnect(room_id, ws)




manager = ConnectionManager()




def user_from_token(token: str, db: Session) -> Optional[User]:
    """WebSocket은 Authorization 헤더를 붙이기 번거로워서
    토큰을 주소 뒤(?token=...)로 받음"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return db.get(User, int(payload["sub"]))
    except jwt.InvalidTokenError:
        return None




def message_payload(msg: Message) -> dict:
    """화면에 보낼 메시지 한 줄의 형태. REST 응답과 같은 모양으로 맞춤"""
    return {
        "type": "message",
        "id": msg.id,
        "sender_id": msg.sender_id,
        "content": msg.content,
        "kind": msg.kind,
        "image_url": msg.image_url,
        "created_at": msg.created_at.isoformat(),
    }




async def notify_room(room_id: int, db: Session):
    """거래 확정·취소처럼 일반 API에서 일어난 일을 채팅창에 바로 알림.
    방금 남긴 시스템 메시지를 밀어주고, 상태가 바뀌었다는 신호도 함께 보냄.
    화면은 그 신호를 받으면 방 정보를 다시 받아옴"""
    recent = (
        db.query(Message)
        .filter(Message.room_id == room_id, Message.kind == "system")
        .order_by(Message.created_at.desc())
        .limit(3)
        .all()
    )
    for msg in reversed(recent):
        await manager.broadcast(room_id, message_payload(msg))

    # 거래 상태가 달라졌으니 화면더러 다시 확인하라는 신호
    await manager.broadcast(room_id, {"type": "room_changed"})


# ---------------------------------------------------------------
# 전체 알림 연결
#
# 위의 manager 는 "방마다" 연결을 모아둠 — 채팅방을 열고 있을 때만 소식이 옴.
# 여기는 "사람마다" 모아둬서, 어느 화면에 있든 새 메시지를 알려줄 수 있음
# ---------------------------------------------------------------
class UserConnectionManager:
    """회원 번호별로 열려 있는 연결을 모아둠.
    한 사람이 여러 탭을 열 수도 있어서 목록으로 관리함"""

    def __init__(self):
        self.users: dict[int, list[WebSocket]] = {}

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        self.users.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: int, ws: WebSocket):
        conns = self.users.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self.users.pop(user_id, None)

    async def send(self, user_id: int, payload: dict):
        """그 사람의 모든 탭에 보냄. 접속해 있지 않으면 그냥 넘어감"""
        dead = []
        for ws in list(self.users.get(user_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)


user_manager = UserConnectionManager()


async def notify_new_message(room: ChatRoom, msg: Message):
    """새 메시지가 왔다고 상대에게 알림.
    보낸 사람에게는 보내지 않음 — 자기가 보낸 걸 알림으로 받으면 이상함"""
    seller_id = room.post.seller_id
    # 보낸 사람이 구매자면 판매자에게, 반대면 구매자에게
    target = seller_id if msg.sender_id == room.buyer_id else room.buyer_id
    if target == msg.sender_id:
        return

    sender = room.buyer if msg.sender_id == room.buyer_id else room.post.seller

    await user_manager.send(target, {
        "type": "chat",
        "room_id": room.id,
        "post_title": room.post.title,
        "sender_nickname": sender.nickname if sender else "상대",
        # 사진 메시지는 내용 대신 표시용 글자로
        "preview": "사진을 보냈어요" if msg.kind == "image" else msg.content[:40],
    })
