"""
회원 — 가입 · 로그인 · 찾기 · 내 정보 · 탈퇴
"""

import os
from datetime import datetime, timedelta

import secrets   # 추측하기 어려운 무작위 코드 생성
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import User, Post, Favorite, ChatRoom, Withdrawal, Warning_
from schemas import (
    SignupRequest, LoginRequest, TokenResponse, UserResponse,
    ProfileUpdate, PasswordChange, FindUsernameRequest,
    ResetRequest, ResetConfirm, DeleteAccount,
)
from deps import (
    get_db, get_current_user, check_region,
    hash_password, verify_password, create_access_token,
)
from config import RESET_CODE_MINUTES, DEMO_MODE, WITHDRAW_REASONS

router = APIRouter(tags=["회원"])




# ---------------------------------------------------------------
# 회원가입
# ---------------------------------------------------------------
@router.post("/signup", status_code=201, response_model=UserResponse)
def signup(
    data: SignupRequest,
    db: Session = Depends(get_db),
):
    # 0) 지역이 목록에 있는지 확인
    check_region(data.region)

    # 1) 중복 검사 — 아이디, 이메일, 폰번호 세 가지 모두
    # 이메일/폰이 중복되면 나중에 아이디 찾기가 "누구인지" 특정을 못 함
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다")
    if db.query(User).filter(User.phone == data.phone).first():
        raise HTTPException(status_code=409, detail="이미 가입된 전화번호입니다")

    # 2) 새 회원 만들기 (manner_temp, created_at은 DB 기본값이 채움)
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),  # 평문은 절대 저장 안 함
        nickname=data.nickname,
        region=data.region,
        name=data.name,
        email=data.email,
        phone=data.phone,
        address=data.address,
    )

    # 3) 저장
    db.add(user)
    db.commit()
    db.refresh(user)

    return user




# ---------------------------------------------------------------
# 로그인
# ---------------------------------------------------------------
@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    # 아이디로 회원 찾기
    user = db.query(User).filter(User.username == data.username).first()

    # 아이디가 없거나 비밀번호가 틀린 경우
    # 둘을 구분해서 알려주지 않음 — "아이디는 맞다"는 정보도 공격자에겐 힌트가 됨
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다")

    # 통과했으면 토큰 발급
    return TokenResponse(
        access_token=create_access_token(user.id),
        token_type="bearer",
    )




# ---------------------------------------------------------------
# 내 정보 조회 (로그인 필요)
# Depends(get_current_user) 하나로 로그인 검사가 끝남
# ---------------------------------------------------------------
@router.get("/me", response_model=UserResponse)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user




# ---------------------------------------------------------------
# 아이디 중복 확인 (회원가입 화면의 "중복체크" 버튼용)
# ---------------------------------------------------------------
@router.get("/check-username")
def check_username(
    username: str = Query(min_length=4, max_length=20),
    db: Session = Depends(get_db),
):
    taken = db.query(User).filter(User.username == username).first() is not None
    # available = 쓸 수 있는지 여부. 화면에서 이 값으로 메시지를 바꿈
    return {"username": username, "available": not taken}




@router.post("/find-username")
def find_username(
    data: FindUsernameRequest,
    db: Session = Depends(get_db),
):
    # 세 조건을 모두 만족하는 회원 찾기
    user = (
        db.query(User)
        .filter(
            User.name == data.name,
            User.email == data.email,
            User.phone == data.phone,
        )
        .first()
    )

    if user is None:
        raise HTTPException(status_code=404, detail="일치하는 회원 정보가 없습니다")

    return {"username": user.username, "created_at": user.created_at}




@router.post("/request-reset")
def request_reset(
    data: ResetRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(
            User.username == data.username,
            User.email == data.email,
            User.phone == data.phone,
        )
        .first()
    )

    if user is None:
        raise HTTPException(status_code=404, detail="일치하는 회원 정보가 없습니다")

    # secrets.randbelow(1000000) → 0 ~ 999999 중 하나
    # :06d = 6자리로 맞추고 앞을 0으로 채움 (예: 42 → "000042")
    code = f"{secrets.randbelow(1000000):06d}"

    user.reset_code = code
    # 지금부터 10분 뒤까지만 유효
    user.reset_expires = datetime.utcnow() + timedelta(minutes=RESET_CODE_MINUTES)
    db.commit()

    # 실제 서비스라면 이 자리에서 send_email(user.email, code) 를 호출함
    print("=" * 50)
    print(f"[비밀번호 재설정] {user.username} 님의 인증코드: {code}")
    print(f"유효시간: {RESET_CODE_MINUTES}분")
    print("=" * 50)

    # 개발 중에는 코드를 화면에 그대로 보여줌 — 메일을 못 보내니까.
    # 배포에서는 절대 내보내면 안 됨. 아이디·이메일·폰만 알면
    # 남의 비밀번호를 마음대로 바꿀 수 있게 되기 때문
    if DEMO_MODE:
        return {
            "message": f"인증코드를 발급했습니다. ({RESET_CODE_MINUTES}분 유효)",
            "demo_code": code,
        }

    return {
        "message": f"인증코드를 보냈습니다. 메일을 확인해주세요. ({RESET_CODE_MINUTES}분 유효)"
    }




@router.post("/reset-password")
def reset_password(
    data: ResetConfirm,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == data.username).first()

    # 회원이 없거나, 코드를 발급받은 적이 없는 경우
    if user is None or not user.reset_code:
        raise HTTPException(status_code=400, detail="재설정 요청을 먼저 해주세요")

    # 유효시간이 지났는지 확인
    if user.reset_expires is None or datetime.utcnow() > user.reset_expires:
        user.reset_code = None       # 만료된 코드는 지워버림
        user.reset_expires = None
        db.commit()
        raise HTTPException(status_code=400, detail="인증코드가 만료되었습니다. 다시 요청해주세요")

    if user.reset_code != data.code:
        raise HTTPException(status_code=400, detail="인증코드가 일치하지 않습니다")

    # 통과 → 비밀번호 변경
    user.password_hash = hash_password(data.new_password)
    # 쓴 코드는 즉시 폐기. 안 지우면 같은 코드로 계속 바꿀 수 있음
    user.reset_code = None
    user.reset_expires = None
    db.commit()

    return {"message": "비밀번호가 변경되었습니다"}




@router.patch("/me", response_model=UserResponse)
def update_me(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.region is not None:
        check_region(data.region)

    # 이메일 중복 검사. User.id != 나 조건이 있어야
    # "내 이메일 그대로 두고 닉네임만 바꾸기"가 막히지 않음
    if data.email is not None and data.email != current_user.email:
        dup = (
            db.query(User)
            .filter(User.email == data.email, User.id != current_user.id)
            .first()
        )
        if dup:
            raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다")

    if data.phone is not None and data.phone != current_user.phone:
        dup = (
            db.query(User)
            .filter(User.phone == data.phone, User.id != current_user.id)
            .first()
        )
        if dup:
            raise HTTPException(status_code=409, detail="이미 사용 중인 전화번호입니다")

    # 보낸 칸만 골라서 덮어씀
    # exclude_unset=True = 아예 안 보낸 칸은 목록에서 빠짐
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(current_user, key, value)   # current_user.nickname = value 와 같음

    db.commit()
    db.refresh(current_user)
    return current_user




@router.patch("/me/password")
def change_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다")

    # 같은 비밀번호로 바꾸는 건 의미가 없으니 막아줌
    if verify_password(data.new_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="현재 비밀번호와 다른 것으로 정해주세요")

    current_user.password_hash = hash_password(data.new_password)
    db.commit()

    return {"message": "비밀번호가 변경되었습니다"}




@router.delete("/me", status_code=204)
def delete_me(
    data: DeleteAccount,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(data.password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="비밀번호가 올바르지 않습니다")

    # 1) 내가 올린 매물 — 사진 파일부터 지우고 매물 삭제
    my_posts = db.query(Post).filter(Post.seller_id == current_user.id).all()
    for post in my_posts:
        for image in post.images:
            file_path = image.image_url.lstrip("/")
            if os.path.exists(file_path):
                os.remove(file_path)
        # cascade 설정 덕분에 post_images와 그 매물에 달린 찜은 같이 지워짐
        db.delete(post)

    # 2) 내가 남의 매물에 누른 찜
    db.query(Favorite).filter(Favorite.user_id == current_user.id).delete()

    # 3) 내가 구매자로 참여한 채팅방 (딸린 메시지는 cascade로 정리됨)
    # 내가 판매자인 방은 위에서 매물을 지울 때 함께 사라짐
    for room in db.query(ChatRoom).filter(ChatRoom.buyer_id == current_user.id).all():
        db.delete(room)

    # 4) 왜 떠나는지 남김. 누구였는지는 남기지 않고 통계에 쓸 것만.
    # 이게 없으면 "사람이 줄었다" 만 알고 "왜" 를 알 수 없음
    days = (datetime.utcnow() - current_user.created_at).days
    db.add(Withdrawal(
        reason=data.reason if data.reason in WITHDRAW_REASONS else "기타",
        detail=(data.detail or "").strip() or None,
        region=current_user.region,
        days_used=days,
        total_posts=current_user.total_posts,
        completed_deals=current_user.completed_deals,
    ))

    # 5) 마지막에 회원 삭제.
    # 위에서 참조를 다 끊어놨기 때문에 이제 안전함
    db.delete(current_user)
    db.commit()


@router.get("/withdraw-reasons")
def withdraw_reasons():
    """탈퇴 화면의 사유 목록"""
    return {"reasons": WITHDRAW_REASONS}


# ---------------------------------------------------------------
# 내가 받은 경고
#
# 관리자가 보낸 경고를 사용자가 봄. 앱을 열 때마다 확인해서
# 안 읽은 것이 있으면 화면에 띄움
# ---------------------------------------------------------------
@router.get("/me/warnings")
def my_warnings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Warning_)
        .filter(Warning_.user_id == current_user.id)
        .order_by(Warning_.created_at.desc())
        .limit(20)
        .all()
    )
    unread = [w for w in rows if not w.is_read]

    return {
        "안읽음": len(unread),
        "전체": len(rows),
        "목록": [
            {
                "id": w.id,
                "사유": w.reason,
                "내용": w.detail,
                "읽음": w.is_read,
                "보낸때": w.created_at,
            }
            for w in rows
        ],
    }


@router.post("/me/warnings/{warning_id}/read")
def read_warning(
    warning_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """확인 버튼을 눌렀을 때. 남의 경고는 읽음 처리할 수 없음"""
    warn = db.get(Warning_, warning_id)
    if warn is None or warn.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="경고를 찾을 수 없습니다")

    warn.is_read = True
    warn.read_at = datetime.utcnow()
    db.commit()

    return {"id": warn.id, "읽음": True}
