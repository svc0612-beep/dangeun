"""
여러 곳에서 함께 쓰는 준비물

DB 창구 열기, 비밀번호 암호화, 토큰 발급·검증, 로그인 확인.
API 함수에 Depends(get_current_user) 한 줄만 붙이면 로그인 검사가 끝남
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import SessionLocal, User
from config import SECRET_KEY, ALGORITHM, TOKEN_EXPIRE_HOURS, VALID_REGIONS, ADMIN_USERNAME




# HTTPBearer = "Authorization: Bearer <토큰>" 헤더를 읽어주는 도구
# 이걸 쓰면 /docs 화면 오른쪽 위에 Authorize 자물쇠 버튼이 생김
security = HTTPBearer()




# ---------------------------------------------------------------
# 선택적 로그인 — 토큰이 있으면 회원을, 없으면 None을 돌려줌
# auto_error=False : 토큰이 없어도 에러를 내지 않음
# "로그인해도 되고 안 해도 되는" API에 씀
# ---------------------------------------------------------------
security_optional = HTTPBearer(auto_error=False)




# ---------------------------------------------------------------
# DB 세션 준비 함수
# ---------------------------------------------------------------
def get_db():
    db = SessionLocal()  # 창구 열기
    try:
        yield db         # 이 창구를 API 함수에 빌려줌
    finally:
        db.close()       # 무조건 닫음




# ---------------------------------------------------------------
# 비밀번호 관련 함수
# ---------------------------------------------------------------
def hash_password(plain: str) -> str:
    """평문 비밀번호 → 암호화된 문자열"""
    hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")




def verify_password(plain: str, hashed: str) -> bool:
    """입력한 비밀번호가 저장된 것과 맞는지 확인.
    암호화된 값을 되돌리는 게 아니라, 입력값을 같은 방식으로 암호화해서 비교함."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))




# ---------------------------------------------------------------
# 토큰 발급 함수
# ---------------------------------------------------------------
def create_access_token(user_id: int) -> str:
    """회원 id를 담은 토큰을 만들어 반환"""
    payload = {
        # sub = subject. "이 토큰의 주인이 누구냐". 문자열이어야 해서 str로 변환
        "sub": str(user_id),
        # exp = expiration. 이 시각이 지나면 토큰이 자동으로 무효가 됨
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    # SECRET_KEY로 서명해서 문자열로 만듦
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)




# ---------------------------------------------------------------
# 현재 로그인한 회원을 찾아주는 함수
# 로그인이 필요한 API에 Depends(get_current_user) 를 붙이면
# 토큰 검사 → 회원 조회까지 자동으로 해줌.
# ---------------------------------------------------------------
def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(security),  # 헤더에서 토큰 추출
    db: Session = Depends(get_db),
) -> User:
    try:
        # 토큰을 열어봄. 서명이 틀리거나 만료됐으면 여기서 예외 발생
        payload = jwt.decode(cred.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    # 토큰은 멀쩡한데 그 회원이 탈퇴했을 수도 있으니 DB에서 다시 확인
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="존재하지 않는 회원입니다")

    return user




def get_current_user_optional(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if cred is None:
        return None
    try:
        payload = jwt.decode(cred.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return db.get(User, int(payload["sub"]))
    except jwt.InvalidTokenError:
        # 만료됐거나 잘못된 토큰이면 그냥 비로그인 취급
        return None




def check_region(region: str):
    """목록에 없는 지역이면 막음. 여러 곳에서 쓰려고 함수로 뺐음"""
    if region not in VALID_REGIONS:
        raise HTTPException(status_code=400, detail="지역 목록에 없는 값입니다")


# ---------------------------------------------------------------
# 관리자만 통과
#
# 다시 계산하기 같은 무거운 작업이나 신고 처리는 아무나 하면 안 됨.
# users.is_admin 이 True 인 사람만 지나갈 수 있음
#
# 관리자로 만들려면 (개발 중):
#   python -c "from database import SessionLocal, User; db=SessionLocal(); u=db.query(User).filter(User.username=='아이디').first(); u.is_admin=True; db.commit()"
# ---------------------------------------------------------------
def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """관리자만 통과.

    두 가지를 모두 만족해야 함
      1) users.is_admin 이 True
      2) 아이디가 config.ADMIN_USERNAME 과 같음

    둘 중 하나만 보면 위험함 —
    is_admin 만 보면 DB를 건드린 사람이 관리자가 되고,
    아이디만 보면 그 아이디를 쓰는 사람이 자동으로 관리자가 됨
    """
    if not current_user.is_admin or current_user.username != ADMIN_USERNAME:
        # "관리자만" 이라고 알려주지 않음 — 그 자체가 힌트가 됨
        raise HTTPException(status_code=404, detail="찾을 수 없습니다")
    return current_user


def get_active_user(current_user: User = Depends(get_current_user)) -> User:
    """정지되지 않은 회원만 통과.

    글쓰기·채팅처럼 남에게 영향을 주는 일에 붙임.
    보기만 하는 것은 정지돼도 막지 않음
    """
    if current_user.is_blocked:
        reason = current_user.blocked_reason or "이용 규칙 위반"
        raise HTTPException(
            status_code=403,
            detail=f"이용이 제한된 계정입니다. ({reason})",
        )
    return current_user
