"""
주고받는 값의 형태 (Pydantic 모델)

요청이 들어올 때는 "이 칸이 있는지, 길이가 맞는지" 를 검사하고,
응답을 보낼 때는 "어떤 칸만 내보낼지" 를 정함.
비밀번호 해시처럼 밖에 나가면 안 되는 값은 여기에 안 적으면 자동으로 빠짐
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field




# ---------------------------------------------------------------
# 입력 / 출력 형태 정의
# ---------------------------------------------------------------
class SignupRequest(BaseModel):
    username: str = Field(min_length=4, max_length=20)   # 로그인 아이디
    password: str = Field(min_length=8, max_length=64)
    nickname: str = Field(min_length=2, max_length=20)   # 화면에 보일 이름
    region: str = Field(min_length=2, max_length=50)     # 동네

    name: str = Field(min_length=2, max_length=50)       # 실명
    # pattern = 글자 형태 규칙. @와 점이 들어간 형태만 통과
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=100)
    phone: str = Field(pattern=r"^[0-9\-]{9,20}$")      # 숫자와 하이픈만
    address: str = Field(min_length=5, max_length=200)   # 집주소




class LoginRequest(BaseModel):
    # 로그인은 아이디와 비밀번호만 받음. 길이 제한은 굳이 안 검
    username: str
    password: str




class TokenResponse(BaseModel):
    access_token: str  # 발급된 토큰 문자열
    token_type: str    # 항상 "bearer". 클라이언트가 어떻게 보낼지 알려주는 값




class UserResponse(BaseModel):
    id: int
    username: str               # 아이디 (수정 불가)
    nickname: str
    region: str
    name: str                   # 실명 (수정 불가)
    email: str
    phone: str
    address: str
    manner_temp: float
    total_posts: int = 0            # 지금까지 올린 매물 수 (누적)
    completed_deals: int = 0        # 판매 완료 횟수 (누적)
    completed_purchases: int = 0    # 구매 완료 횟수 (누적)
    cancel_count: int = 0           # 취소한 횟수 (누적)

    # 관리자인지. 화면이 대시보드를 보여줄지 판단하는 데만 씀 —
    # 실제 권한 검사는 서버가 하므로 이 값을 고쳐도 소용없음
    is_admin: bool = False
    # 정지된 계정인지. 화면에 안내를 띄우려고
    is_blocked: bool = False
    blocked_reason: Optional[str] = None

    model_config = {"from_attributes": True}




# ---------------------------------------------------------------
# 내 정보 수정 (로그인 필요)
# 아이디(username)와 실명(name)은 일부러 뺐음.
#  - 아이디를 바꿀 수 있으면 거래 기록과의 연결이 끊김
#  - 실명은 아이디 찾기의 근거라 바뀌면 본인 확인이 무의미해짐
# Optional = 보낸 칸만 고침. 안 보낸 칸은 그대로 둠
# ---------------------------------------------------------------
class ProfileUpdate(BaseModel):
    nickname: Optional[str] = Field(default=None, min_length=2, max_length=20)
    region: Optional[str] = Field(default=None, min_length=2, max_length=50)
    email: Optional[str] = Field(
        default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=100
    )
    phone: Optional[str] = Field(default=None, pattern=r"^[0-9\-]{9,20}$")
    address: Optional[str] = Field(default=None, min_length=5, max_length=200)




# ---------------------------------------------------------------
# 비밀번호 변경 (로그인 필요 + 현재 비밀번호 확인)
# 로그인된 상태여도 현재 비밀번호를 다시 묻는 이유:
# 자리를 비운 사이 남이 토큰만으로 계정을 통째로 뺏을 수 있기 때문
# ---------------------------------------------------------------
class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=64)




# ---------------------------------------------------------------
# 아이디 찾기 — 이름 + 이메일 + 폰번호가 모두 일치해야 알려줌
# ---------------------------------------------------------------
class FindUsernameRequest(BaseModel):
    name: str
    email: str
    phone: str




class ResetRequest(BaseModel):
    username: str
    email: str
    phone: str




# ---------------------------------------------------------------
# 비밀번호 재설정 2단계 — 코드 확인 후 변경
# ---------------------------------------------------------------
class ResetConfirm(BaseModel):
    username: str
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=64)




# ---------------------------------------------------------------
# 회원 탈퇴 (로그인 필요 + 비밀번호 확인)
# 되돌릴 수 없으므로 비밀번호를 한 번 더 받음.
#
# 회원만 지우면 posts / favorites 가 없는 사람을 가리키게 되어 목록이 깨짐.
# 그래서 딸린 것들을 순서대로 정리한 뒤 마지막에 회원을 지움
# ---------------------------------------------------------------
class DeleteAccount(BaseModel):
    password: str
    # 왜 떠나는지. 통계에만 쓰고 누구인지는 남기지 않음
    reason: Optional[str] = Field(default=None, max_length=50)
    detail: Optional[str] = Field(default=None, max_length=500)




# ---------------------------------------------------------------
# 매물 입력 / 출력 형태
# ---------------------------------------------------------------
class PostCreate(BaseModel):
    title: str = Field(min_length=2, max_length=100)      # 목록에 뜨는 한 줄
    content: str = Field(min_length=5, max_length=2000)   # 설명 본문
    price: int = Field(ge=0, le=100_000_000)              # ge=0 → 0 이상. 0이면 나눔
    category: str = Field(min_length=1, max_length=30)    # 디지털기기, 생활가전 ...
    region: str = Field(min_length=2, max_length=50)      # 거래 동네
    # 거래 희망 장소. 안 적어도 됨
    place_name: Optional[str] = Field(default=None, max_length=100)
    ai_description: Optional[str] = Field(default=None, max_length=600)
    # 지도에서 찍은 좌표. 위도 33~39, 경도 124~132 가 한반도 범위




# ---------------------------------------------------------------
# 매물 수정 (로그인 필요 + 본인 매물만)
# 보낸 칸만 고침. bumped_at은 일부러 안 건드림 —
# 수정할 때마다 위로 올라가면 "제목에 점 하나 찍기"로 끌올을 무한히 할 수 있음
# ---------------------------------------------------------------
class PostUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=100)
    content: Optional[str] = Field(default=None, min_length=5, max_length=2000)
    price: Optional[int] = Field(default=None, ge=0, le=100_000_000)
    category: Optional[str] = Field(default=None, min_length=1, max_length=30)
    region: Optional[str] = Field(default=None, min_length=2, max_length=50)
    place_name: Optional[str] = Field(default=None, max_length=100)
    ai_description: Optional[str] = Field(default=None, max_length=600)




# 사진 한 장의 형태. PostResponse 안에 목록으로 들어감
class PostImageResponse(BaseModel):
    id: int
    image_url: str      # 예: "/uploads/a1b2c3.jpg"
    sort_order: int     # 0번이 대표 사진

    model_config = {"from_attributes": True}




class PostResponse(BaseModel):
    id: int
    seller_id: int              # 누가 올렸는지 (번호)
    seller_nickname: str = ""   # 카드에 표시할 판매자 이름
    title: str
    content: str
    price: int
    category: str
    region: str
    place_name: Optional[str]   # 거래 희망 장소
    # AI가 사진을 보고 쓴 설명. 판매자 글과 구분해서 보여주려고 따로 담음
    ai_description: Optional[str] = None
    status: str             # 판매중 / 예약중 / 거래완료
    view_count: int
    created_at: datetime
    bumped_at: datetime     # 끌올 시각. 목록 정렬은 이걸 기준으로 함

    # post.images 관계를 그대로 받아서 목록으로 내보냄
    # 아직 사진을 안 올렸으면 빈 배열 [] 이 나감
    images: list[PostImageResponse] = []

    model_config = {"from_attributes": True}




# ---------------------------------------------------------------
# 판매자 정보 (상세 페이지에서 보여줄 것만)
# ---------------------------------------------------------------
class SellerResponse(BaseModel):
    id: int
    nickname: str       # 화면에 보이는 이름
    region: str         # 판매자 동네
    manner_temp: float  # 매너온도
    total_posts: int        # 지금까지 올린 매물 수 (누적)
    completed_deals: int    # 거래완료 횟수 (누적)

    model_config = {"from_attributes": True}




class RiskFlag(BaseModel):
    """위험 신호 하나.
    3층에서 사진 도용·대화 분석 결과도 같은 형태로 여기에 담으면 됨"""
    code: str      # 프로그램이 구분하는 이름
    level: str     # "info" 안내 / "warn" 주의 / "danger" 위험
    message: str   # 화면에 그대로 보여줄 한글 문장




# ---------------------------------------------------------------
# 매물 상세 형태
# PostResponse 를 그대로 물려받고 seller 만 추가함
# (목록에는 판매자 정보가 필요 없으니 상세에만 붙임)
# ---------------------------------------------------------------
class PostDetailResponse(PostResponse):
    seller: SellerResponse
    favorite_count: int = 0    # 이 매물을 찜한 사람 수
    is_favorited: bool = False # 지금 보고 있는 내가 찜했는지
    # 사기 예방용 위험 신호. 화면에서 주의 배너로 띄움
    risk_flags: list["RiskFlag"] = []




class StatusUpdate(BaseModel):
    status: str  # 판매중 / 예약중 / 거래완료 중 하나




# ---------------------------------------------------------------
# 채팅 - 응답 형태
# ---------------------------------------------------------------
class ChatPostBrief(BaseModel):
    """채팅방 위에 항상 붙어 있는 매물 요약"""
    id: int
    title: str
    price: int
    status: str
    thumbnail: Optional[str] = None   # 대표 사진 경로
    # 거래가 확정되면 지도와 길찾기에 씀
    place_name: Optional[str] = None




class MessageResponse(BaseModel):
    id: int
    sender_id: Optional[int]    # 시스템 메시지는 보낸 사람이 없음
    content: str
    kind: str                   # "text" / "system" / "image"
    image_url: Optional[str] = None   # 사진 메시지일 때만
    created_at: datetime

    model_config = {"from_attributes": True}




class PartnerBrief(BaseModel):
    """대화 상대의 공개 가능한 이력.
    실명·이메일·전화번호·주소는 절대 넣지 않음"""
    nickname: str
    region: str
    manner_temp: float
    completed_deals: int        # 판매 완료 횟수
    completed_purchases: int    # 구매 완료 횟수
    cancel_count: int           # 취소한 횟수




class ChatRoomResponse(BaseModel):
    id: int
    partner_id: int = 0             # 상대 회원 번호. 프로필로 이동할 때 씀
    can_review: bool = False        # 거래가 확정돼 후기를 쓸 수 있는지
    my_review_done: bool = False    # 내가 이미 썼는지
    post: ChatPostBrief
    partner: PartnerBrief       # 상대 이력. 서로가 서로를 봄
    partner_nickname: str       # 상대방 (내가 구매자면 판매자, 반대도 마찬가지)
    my_role: str                # "buyer" 또는 "seller"
    buyer_decided: bool         # 구매자가 구매 결정을 눌렀는지
    seller_confirmed: bool      # 판매자가 판매 확인을 눌렀는지
    unread_count: int           # 내가 아직 안 읽은 메시지 수
    last_message: Optional[str]
    last_message_at: datetime




class ChatDetailResponse(ChatRoomResponse):
    messages: list[MessageResponse] = []




# ---------------------------------------------------------------
# 메시지 보내기
# WebSocket을 붙인 뒤에도 이 API는 남겨둠 —
# 연결이 끊겼을 때의 대비책이자, 저장 로직을 한 곳에 두기 위해
# ---------------------------------------------------------------
class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)




# ---------------------------------------------------------------
# 거래 취소 — 노쇼, 변심, 잘못 누름
#
# 확정 전(한쪽만 누름): 양쪽 다 취소 가능. 예약이 풀리고 다시 판매중으로
# 확정 후(둘 다 누름): 판매자만 가능. 거래 횟수도 같이 내려감
#
# "판매 확인"은 물건을 실제로 건넨 뒤에 누르는 것이라
# 노쇼는 대부분 확정 전 상태에서 일어남
# ---------------------------------------------------------------
class CancelReason(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=100)




class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    tags: list[str] = []
    comment: Optional[str] = Field(default=None, max_length=300)




class ReviewResponse(BaseModel):
    id: int
    rating: int
    rating_label: str
    tags: list[str]
    comment: Optional[str]
    reviewer_nickname: str
    created_at: datetime




class ReportCreate(BaseModel):
    target_type: str            # "post" 또는 "user"
    target_id: int
    reason: str
    detail: Optional[str] = Field(default=None, max_length=500)




class SearchLogCreate(BaseModel):
    keyword: str = Field(min_length=1, max_length=50)
