"""
채팅 — 방 열기 · 목록 · 대화 · 사진 · 거래 확정/취소 · 추천 문구 · 실시간 연결
"""

import os
import shutil
import uuid
import threading
from datetime import datetime
from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query,
    UploadFile, File, WebSocket, WebSocketDisconnect,
)
from sqlalchemy.orm import Session

from database import SessionLocal, User, Post, ChatRoom, Message, Review
from schemas import (
    ChatRoomResponse, ChatDetailResponse, MessageResponse,
    MessageCreate, CancelReason,
)
from deps import get_db, get_current_user, get_active_user
from config import UPLOAD_DIR, ALLOWED_EXT, MAX_IMAGE_BYTES, ACCOUNT_PATTERN, CHAT_SUGGESTIONS
from chat_core import (
    get_room_or_404, build_room, add_system_message,
    manager, user_manager, user_from_token, message_payload, notify_room,
    notify_new_message,
)
from scam import find_bad_words
import badwords
import chat_tips
import prevention

router = APIRouter(tags=["채팅"])


def bad_word_notice(kind: str, hits: list[str]) -> str:
    """걸린 종류에 맞는 안내 문구.
    욕설에 "직거래를 권합니다" 라고 하면 앞뒤가 안 맞으므로 나눠 씀"""
    if kind == "curse":
        return "서로 존중하는 말로 대화해주세요. 신고 대상이 될 수 있습니다."

    if kind == "scam":
        found = ", ".join(hits[:2])
        # 이 앱은 직거래만 한다. 택배·선입금은 규칙 위반이자 사기의 길목
        return (f"주의가 필요한 표현이 있어요 ({found}). "
                "이 앱은 직거래만 합니다 — 만나서 물건을 확인하고 그 자리에서 주고받으세요.")

    return "거래에 어울리지 않는 내용이 있어요. 신고 대상이 될 수 있습니다."




# ---------------------------------------------------------------
# 채팅방 열기 (없으면 새로 만듦)
# 매물 상세의 "구매 결정" 버튼이 이걸 호출함
# ---------------------------------------------------------------
@router.post("/posts/{post_id}/chat", status_code=201, response_model=ChatRoomResponse)
def open_chat(
    post_id: int,
    db: Session = Depends(get_db),
    # 정지된 회원은 새 대화를 열 수 없음
    current_user: User = Depends(get_active_user),
):
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="매물을 찾을 수 없습니다")

    if post.seller_id == current_user.id:
        raise HTTPException(status_code=400, detail="본인 매물에는 채팅할 수 없습니다")

    # 이미 대화한 적이 있으면 그 방을 그대로 씀.
    # 버튼을 여러 번 눌러도 방이 늘어나지 않음
    room = (
        db.query(ChatRoom)
        .filter(ChatRoom.post_id == post_id, ChatRoom.buyer_id == current_user.id)
        .first()
    )

    if room is None:
        room = ChatRoom(post_id=post_id, buyer_id=current_user.id)
        db.add(room)
        db.commit()
        db.refresh(room)

    return build_room(room, current_user, db)




# ---------------------------------------------------------------
# 내 채팅 목록 (구매자로 참여한 방 + 내 매물에 들어온 방)
# ---------------------------------------------------------------
@router.get("/me/chats", response_model=list[ChatRoomResponse])
def my_chats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 내가 구매자인 방
    as_buyer = db.query(ChatRoom).filter(ChatRoom.buyer_id == current_user.id).all()

    # 내가 올린 매물에 들어온 방
    as_seller = (
        db.query(ChatRoom)
        .join(Post, ChatRoom.post_id == Post.id)
        .filter(Post.seller_id == current_user.id)
        .all()
    )

    rooms = as_buyer + as_seller
    # 최근 대화 순으로
    rooms.sort(key=lambda r: r.last_message_at, reverse=True)

    return [build_room(r, current_user, db) for r in rooms]




# ---------------------------------------------------------------
# 채팅방 하나 열기 — 매물 정보 + 지난 대화 전부
# 여는 순간 "여기까지 읽음"으로 표시됨
# ---------------------------------------------------------------
@router.get("/chats/{room_id}", response_model=ChatDetailResponse)
def get_chat(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = get_room_or_404(room_id, db, current_user)

    # 읽음 처리
    now = datetime.utcnow()
    if current_user.id == room.buyer_id:
        room.buyer_read_at = now
    else:
        room.seller_read_at = now
    db.commit()

    data = build_room(room, current_user, db)
    data["unread_count"] = 0            # 방금 다 읽었으니 0
    data["messages"] = room.messages    # order_by 설정 덕분에 시간순
    return data




@router.post("/chats/{room_id}/messages", status_code=201, response_model=MessageResponse)
async def send_message(
    room_id: int,
    data: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_active_user),
):
    room = get_room_or_404(room_id, db, current_user)

    msg = Message(room_id=room.id, sender_id=current_user.id, content=data.content)
    db.add(msg)
    db.flush()   # 아래 시스템 메시지보다 먼저 저장되도록 순서를 확정

    # ② 계좌번호처럼 보이는 숫자가 있으면 안내를 남김.
    # 메시지 자체는 막지 않음 — 정상적인 숫자일 수도 있으니
    if ACCOUNT_PATTERN.search(data.content):
        add_system_message(
            db, room,
            "계좌번호로 보이는 내용이 있어요. 만나서 물건을 확인한 뒤에 주고받으세요.",
        )

    # 욕설이나 사기 문구가 나오면 안내. 종류에 따라 다른 말을 띄움
    kind, hits = badwords.classify(data.content)
    if kind:
        add_system_message(db, room, bad_word_notice(kind, hits))

    # 사전 예방 — 위반이면 기록·누진·조치. 아래 db.commit 으로 함께 저장됨
    prevention.check(db, room, current_user, data.content)

    room.last_message_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)

    # 이 말을 추천 문구 셈에 바로 반영.
    # 별도 흐름이라 보낸 사람은 기다리지 않음
    threading.Thread(
        target=chat_tips.learn_later, args=(msg.id, room.id), daemon=True
    ).start()

    # 같은 방을 열어둔 사람에게 바로 보여줌
    await manager.broadcast(room_id, message_payload(msg))
    # 상대가 다른 화면에 있어도 알 수 있게 알림도 보냄
    await notify_new_message(room, msg)

    return msg


# ---------------------------------------------------------------
# 채팅에 사진 보내기
#
# WebSocket은 글자만 주고받음. 파일은 일반 업로드로 보내고,
# 저장한 뒤 그 방에 연결된 사람들에게 실시간으로 밀어줌.
# 그래서 이 함수는 async — 안에서 await 로 브로드캐스트해야 하기 때문
# ---------------------------------------------------------------
@router.post("/chats/{room_id}/images", status_code=201, response_model=MessageResponse)
async def send_chat_image(
    room_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = get_room_or_404(room_id, db, current_user)

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="이미지 파일만 보낼 수 있습니다")

    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, saved_name)

    with open(saved_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    if os.path.getsize(saved_path) > MAX_IMAGE_BYTES:
        os.remove(saved_path)
        raise HTTPException(status_code=400, detail="사진은 5MB 이하만 보낼 수 있습니다")

    msg = Message(
        room_id=room.id,
        sender_id=current_user.id,
        content="사진",              # 채팅 목록의 "마지막 대화"에 쓰임
        kind="image",
        image_url=f"/{UPLOAD_DIR}/{saved_name}",
    )
    db.add(msg)
    room.last_message_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)

    # 상대 화면에도 바로 뜨게 밀어줌
    await manager.broadcast(room_id, message_payload(msg))
    await notify_new_message(room, msg)

    return msg




# ---------------------------------------------------------------
# 거래 확정 — 구매자는 "구매 결정", 판매자는 "판매 확인"
# 누가 눌렀는지는 토큰으로 알 수 있어서 API 하나로 처리함
#
# 둘 다 누르면 매물이 거래완료로 바뀌고 판매자의 거래 횟수가 올라감
# ---------------------------------------------------------------
@router.post("/chats/{room_id}/decide", response_model=ChatRoomResponse)
async def decide_deal(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = get_room_or_404(room_id, db, current_user)
    post = room.post

    # 이미 다른 사람과 거래가 끝난 매물이면 막음.
    # 한 매물을 두 사람에게 파는 일을 방지
    if post.status == "거래완료" and not (room.buyer_decided_at and room.seller_confirmed_at):
        raise HTTPException(status_code=400, detail="이미 다른 분과 거래가 완료된 매물입니다")

    now = datetime.utcnow()
    is_buyer = current_user.id == room.buyer_id

    if is_buyer:
        if room.buyer_decided_at is None:      # 이미 눌렀으면 다시 안 함
            room.buyer_decided_at = now
            add_system_message(db, room, f"{room.buyer.nickname}님이 구매를 결정했어요")
    else:
        if room.seller_confirmed_at is None:
            room.seller_confirmed_at = now
            add_system_message(db, room, f"{post.seller.nickname}님이 판매를 확인했어요")

    # 양쪽이 다 눌렸는지 확인
    both = room.buyer_decided_at is not None and room.seller_confirmed_at is not None

    if both:
        if post.status != "거래완료":
            post.status = "거래완료"
            post.seller.completed_deals += 1        # 판매자 기록
            room.buyer.completed_purchases += 1     # 구매자 기록
            add_system_message(db, room, "거래가 확정됐어요")
    else:
        # 한쪽만 눌린 상태 = 예약중
        if post.status == "판매중":
            post.status = "예약중"

    db.commit()
    db.refresh(room)

    # 상대 화면에도 바로 반영되게 알림.
    # 이게 없으면 버튼을 누른 사람만 확정된 걸 알고, 상대는 새로고침해야 함
    await notify_room(room.id, db)

    return build_room(room, current_user, db)




@router.post("/chats/{room_id}/cancel", response_model=ChatRoomResponse)
async def cancel_deal(
    room_id: int,
    data: CancelReason,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = get_room_or_404(room_id, db, current_user)
    post = room.post

    if not room.buyer_decided_at and not room.seller_confirmed_at:
        raise HTTPException(status_code=400, detail="취소할 예약이 없습니다")

    both = room.buyer_decided_at is not None and room.seller_confirmed_at is not None
    is_buyer = current_user.id == room.buyer_id

    # 확정된 거래를 되돌리는 건 판매자만.
    # 구매자가 마음대로 지우면 판매 기록이 흔들림
    if both and is_buyer:
        raise HTTPException(status_code=403, detail="확정된 거래는 판매자만 취소할 수 있습니다")

    # 취소를 누른 사람에게 기록이 쌓임
    current_user.cancel_count += 1

    if both:
        # 거래완료를 되돌림. 올렸던 횟수도 같이 내림
        post.status = "판매중"
        if post.seller.completed_deals > 0:
            post.seller.completed_deals -= 1
        if room.buyer.completed_purchases > 0:
            room.buyer.completed_purchases -= 1
        room.buyer_decided_at = None
        room.seller_confirmed_at = None
        who = post.seller.nickname
    else:
        # 예약 상태를 풂. 누른 사람 것만 지움
        if is_buyer:
            room.buyer_decided_at = None
            who = room.buyer.nickname
        else:
            room.seller_confirmed_at = None
            who = post.seller.nickname

        # 이 매물의 다른 방에 아직 예약이 남아 있는지 확인.
        # 없어야 판매중으로 되돌림
        others = (
            db.query(ChatRoom)
            .filter(
                ChatRoom.post_id == post.id,
                ChatRoom.id != room.id,
                ChatRoom.buyer_decided_at.isnot(None),
            )
            .count()
        )
        if others == 0 and post.status == "예약중":
            post.status = "판매중"

    text = f"{who}님이 거래를 취소했어요"
    if data.reason:
        text += f" ({data.reason})"
    add_system_message(db, room, text)

    db.commit()
    db.refresh(room)

    await notify_room(room.id, db)

    return build_room(room, current_user, db)




@router.get("/chats/{room_id}/suggestions")
def chat_suggestions(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    room = get_room_or_404(room_id, db, current_user)
    is_buyer = current_user.id == room.buyer_id
    role = "buyer" if is_buyer else "seller"

    # 사람이 쓴 말이 몇 개나 오갔는지 (시스템 안내는 빼고)
    talked = (
        db.query(Message)
        .filter(Message.room_id == room_id, Message.kind != "system")
        .count()
    )

    both_decided = room.buyer_decided_at is not None and room.seller_confirmed_at is not None
    one_decided = room.buyer_decided_at is not None or room.seller_confirmed_at is not None

    # 상황을 하나 고름. 아래로 갈수록 나중 단계
    if both_decided:
        key = ("both", "done")
    elif one_decided:
        key = ("both", "reserved")
    elif talked == 0:
        key = (role, "first")
    else:
        key = (role, "talking")

    # 실제 대화에서 뽑은 것을 먼저 쓰고, 모자라면 기본 목록으로 채움
    learned = chat_tips.LEARNED_TIPS.get(key, [])
    base = CHAT_SUGGESTIONS.get(key, [])

    merged = list(learned)
    for t in base:
        if t not in merged:
            merged.append(t)

    return {
        "stage": key[1],
        "suggestions": merged[:chat_tips.MAX_TIPS],
        "learned_count": len(learned),   # 몇 개가 실제 대화에서 왔는지
    }




@router.websocket("/ws/chats/{room_id}")
async def chat_socket(websocket: WebSocket, room_id: int, token: str = Query(...)):
    db = SessionLocal()
    try:
        user = user_from_token(token, db)
        if user is None:
            # 1008 = 정책 위반. 인증 실패를 알리는 관례적인 코드
            await websocket.close(code=1008)
            return

        room = db.get(ChatRoom, room_id)
        if room is None or (user.id != room.buyer_id and user.id != room.post.seller_id):
            await websocket.close(code=1008)
            return

        await manager.connect(room_id, websocket)

        try:
            while True:
                # 상대가 보낼 때까지 여기서 기다림
                data = await websocket.receive_json()
                text = (data.get("content") or "").strip()
                if not text or len(text) > 1000:
                    continue

                # 저장은 일반 API와 똑같이. 규칙이 두 벌이 되면 어긋남
                msg = Message(room_id=room_id, sender_id=user.id, content=text)
                db.add(msg)
                db.flush()

                room.last_message_at = datetime.utcnow()
                db.commit()
                db.refresh(msg)

                # 추천 문구 셈에 바로 반영
                threading.Thread(
                    target=chat_tips.learn_later, args=(msg.id, room_id), daemon=True
                ).start()

                await manager.broadcast(room_id, message_payload(msg))
                await notify_new_message(room, msg)

                # 사기 예방 안내도 실시간으로 같이 보냄
                warns = []
                if ACCOUNT_PATTERN.search(text):
                    warns.append("계좌번호로 보이는 내용이 있어요. 만나서 물건을 확인한 뒤에 주고받으세요.")
                kind, hits = badwords.classify(text)
                if kind:
                    warns.append(bad_word_notice(kind, hits))

                for w in warns:
                    sys_msg = add_system_message(db, room, w)
                    db.commit()
                    db.refresh(sys_msg)
                    await manager.broadcast(room_id, message_payload(sys_msg))

                # 사전 예방 — 실시간 경로에서도 동일하게 위반 누진·조치
                prevention.check(db, room, user, text)
                db.commit()

        except WebSocketDisconnect:
            manager.disconnect(room_id, websocket)

    finally:
        db.close()


# ---------------------------------------------------------------
# 전체 알림 연결
#
# 채팅방 연결(/ws/chats/{id})은 그 방을 열고 있을 때만 살아 있음.
# 이건 앱을 켜 두는 동안 계속 열려 있어서, 어느 화면에 있든
# "새 메시지가 왔다"를 받을 수 있음
# ---------------------------------------------------------------
@router.websocket("/ws/notify")
async def notify_socket(websocket: WebSocket, token: str = Query(...)):
    db = SessionLocal()
    try:
        user = user_from_token(token, db)
        if user is None:
            await websocket.close(code=1008)   # 1008 = 정책 위반(인증 실패)
            return

        await user_manager.connect(user.id, websocket)
        try:
            while True:
                # 이쪽에서 보낼 건 없지만, 연결을 살려두려면 받고 있어야 함
                await websocket.receive_text()
        except WebSocketDisconnect:
            user_manager.disconnect(user.id, websocket)
    finally:
        db.close()


# ---------------------------------------------------------------
# 안 읽은 메시지 모아보기
#
# 알림(/ws/notify)은 접속해 있을 때만 옴.
# 로그아웃한 사이에 온 메시지는 놓치므로, 로그인할 때 이걸로 확인함
# ---------------------------------------------------------------
@router.get("/me/unread")
def my_unread(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    as_buyer = db.query(ChatRoom).filter(ChatRoom.buyer_id == current_user.id).all()
    as_seller = (
        db.query(ChatRoom)
        .join(Post, ChatRoom.post_id == Post.id)
        .filter(Post.seller_id == current_user.id)
        .all()
    )

    rooms = []
    total = 0

    for room in as_buyer + as_seller:
        is_buyer = current_user.id == room.buyer_id

        # 내가 마지막으로 읽은 시각 이후에 온, 내가 안 보낸 메시지
        read_at = room.buyer_read_at if is_buyer else room.seller_read_at
        q = db.query(Message).filter(
            Message.room_id == room.id,
            Message.sender_id != current_user.id,
            Message.kind != "system",     # 서버 안내는 세지 않음
        )
        if read_at is not None:
            q = q.filter(Message.created_at > read_at)

        count = q.count()
        if count == 0:
            continue

        last = q.order_by(Message.created_at.desc()).first()
        partner = room.post.seller if is_buyer else room.buyer

        total += count
        rooms.append({
            "room_id": room.id,
            "post_title": room.post.title,
            "partner_nickname": partner.nickname,
            "unread_count": count,
            "preview": "사진을 보냈어요" if last.kind == "image" else last.content[:40],
            "last_at": last.created_at,
        })

    # 최근 것부터
    rooms.sort(key=lambda r: r["last_at"], reverse=True)
    return {"count": total, "rooms": rooms}
