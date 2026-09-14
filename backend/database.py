"""
당근 클론 - DB 정의
users / posts / favorites / post_images 4개 테이블
"""

import os
from datetime import datetime  # 생성시각 기본값으로 쓸 파이썬 표준 날짜 모듈

from sqlalchemy import (
    create_engine,   # DB에 실제로 연결하는 엔진을 만드는 함수
    Column,          # 테이블의 "열(컬럼)"을 정의할 때 쓰는 클래스
    Integer,         # 정수 타입
    String,          # 짧은 문자열 타입 (길이 제한 있음)
    Text,            # 긴 문자열 타입 (본문처럼 길이 제한 없는 것)
    Float,           # 소수 타입 (매너온도 36.5 같은 값)
    Boolean,         # 참/거짓 타입
    DateTime,        # 날짜+시간 타입
    ForeignKey,      # 다른 테이블의 id를 참조하는 "외래키"
    UniqueConstraint,  # "이 조합은 중복 불가" 라는 제약조건
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# ---------------------------------------------------------------
# 1) DB 연결 설정
# ---------------------------------------------------------------

# sqlite:/// 뒤에 파일 경로. 이 파일이 곧 DB 하나.
# 어디서 실행하든 backend 폴더의 danggeun.db 를 쓰게 함.
# "./danggeun.db" 로 두면 scripts/ 에서 돌릴 때 엉뚱한 자리에 DB 가 생김
_HERE = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(_HERE, 'danggeun.db')}"

# 엔진 = DB로 가는 통로
engine = create_engine(
    DATABASE_URL,
    # SQLite는 기본적으로 여러 스레드 접근을 막아놔서 풀어주는 설정
    connect_args={"check_same_thread": False},
    echo=False,  # SQL 로그 끄기. 자세히 보고 싶을 때만 True 로
)

# 세션 = DB와 대화하는 창구 하나
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

# Base = 모든 테이블 클래스가 상속받을 부모
Base = declarative_base()


# ---------------------------------------------------------------
# 2) users 테이블 - 회원
# ---------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)   # 로그인 아이디
    password_hash = Column(String(255), nullable=False)          # 암호화된 비밀번호
    nickname = Column(String(50), nullable=False)                # 화면에 보이는 이름
    region = Column(String(50), nullable=False)                  # 내 동네 (거래 지역)

    # --- 회원 상세 정보 (회원가입 때 받음) ---
    name = Column(String(50), nullable=False)                    # 실명. 아이디 찾기에 씀
    # unique=True → 같은 이메일/폰으로 계정을 두 개 만들 수 없음
    # 아이디 찾기를 하려면 이 값으로 사람이 특정되어야 하기 때문
    email = Column(String(100), unique=True, nullable=False)     # 이메일
    phone = Column(String(20), unique=True, nullable=False)      # 폰 번호
    address = Column(String(200), nullable=False)                # 집주소

    # --- 비밀번호 재설정용 ---
    # 평소엔 비어 있고, 재설정 요청할 때만 채워짐
    reset_code = Column(String(6))       # 6자리 인증코드
    reset_expires = Column(DateTime)     # 이 시각이 지나면 코드 무효 (10분)
    manner_temp = Column(Float, default=36.5, nullable=False)    # 매너온도

    # 누적 카운터. posts 테이블을 세지 않고 여기에 따로 쌓음
    # 매물을 나중에 삭제해도 이 숫자는 줄어들지 않음
    total_posts = Column(Integer, default=0, nullable=False)      # 지금까지 올린 매물 수
    completed_deals = Column(Integer, default=0, nullable=False)  # 판매 완료 횟수

    # 구매자로서의 기록. 판매 기록만 있으면 구매자는 이력이 안 남아
    # 서로의 이력을 서로가 볼 수 있어야 한쪽만 불리해지지 않음
    completed_purchases = Column(Integer, default=0, nullable=False)  # 구매 완료 횟수
    # 취소를 "누른 사람" 에게 쌓임. 판매자가 노쇼 때문에 눌러도 판매자 것이 올라감.
    # 그래야 취소 버튼을 함부로 못 씀
    cancel_count = Column(Integer, default=0, nullable=False)

    # 관리자 여부. 3층 관리자 대시보드에서 씀.
    # 지금은 아무도 True가 아니지만, 칸을 미리 두면 그때 DB를 다시 안 만들어도 됨
    is_admin = Column(Boolean, default=False, nullable=False)

    # --- 관리자가 취한 조치 ---
    # 정지된 회원은 로그인은 되지만 글쓰기·채팅을 할 수 없음.
    # 지우지 않는 이유 — 지우면 거래 기록과 후기가 함께 사라져서
    # 상대방의 이력까지 망가짐
    is_blocked = Column(Boolean, default=False, nullable=False)
    blocked_reason = Column(String(200))
    blocked_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    posts = relationship("Post", back_populates="seller")
    favorites = relationship("Favorite", back_populates="user")


# ---------------------------------------------------------------
# 3) posts 테이블 - 중고 물품 글
# image_url 칸은 없앴음. 사진은 post_images 테이블이 전담함
# ---------------------------------------------------------------
class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    price = Column(Integer, nullable=False, default=0)    # 0이면 나눔
    category = Column(String(30), nullable=False)
    region = Column(String(50), nullable=False, index=True)

    # 거래 희망 장소. "역삼역 2번 출구" 같은 글자
    place_name = Column(String(100))

    # 거래 장소의 좌표. 지도에 찍고 거리를 재는 데 씀.
    # 판매자 집이 아니라 "만나기로 한 곳"이라 공개해도 안전함

    # AI가 사진을 보고 쓴 설명. 판매자가 쓴 content 와 따로 둠 —
    # 섞어버리면 누가 쓴 글인지 구분할 수 없어서 화면에 표시할 수 없음
    ai_description = Column(Text)

    # 의미 검색용 벡터. 제목·카테고리·본문을 숫자 목록으로 바꾼 것을
    # JSON 글자로 저장함 (SQLite에는 목록 타입이 없음).
    # 모델이 없는 기기에서는 비어 있고, 그때는 글자 검색만 씀
    embedding = Column(Text)

    # 위험 신호를 이미 알렸는지. 같은 매물로 알림이 되풀이되지 않게
    risk_notified = Column(Boolean, default=False, nullable=False)

    # 관리자가 숨긴 매물. 목록·검색에서 빠지지만 지워지지는 않음
    is_hidden = Column(Boolean, default=False, nullable=False)
    hidden_reason = Column(String(200))

    status = Column(String(10), default="판매중", nullable=False, index=True)
    view_count = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # 끌올 시각. 목록 정렬은 created_at이 아니라 이걸 기준으로 함
    bumped_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    seller = relationship("User", back_populates="posts")

    @property
    def seller_nickname(self) -> str:
        """카드에 "누가 올렸는지" 를 보여주기 위한 값.
        DB 칸이 아니라 그때그때 꺼내오는 것이라 저장 공간을 쓰지 않음"""
        return self.seller.nickname if self.seller else ""

    favorites = relationship(
        "Favorite", back_populates="post", cascade="all, delete-orphan"
    )

    # post.images 로 그 매물의 사진 목록을 꺼낼 수 있음
    # order_by : 항상 sort_order 순서(0번이 대표 사진)로 정렬해서 가져옴
    # cascade : 매물이 지워지면 딸린 사진 기록도 같이 지워짐
    images = relationship(
        "PostImage",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="PostImage.sort_order",
    )

    # 매물이 지워지면 그 매물의 채팅방도 같이 지워짐
    chat_rooms = relationship(
        "ChatRoom", back_populates="post", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------
# 4) favorites 테이블 - 관심(하트)
# ---------------------------------------------------------------
class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="favorites")
    post = relationship("Post", back_populates="favorites")

    # 한 사람이 같은 글에 하트를 두 번 못 누르게 막는 제약조건
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_user_post_favorite"),
    )


# ---------------------------------------------------------------
# 5) post_images 테이블 - 매물 사진 (새로 추가)
# 사진 "파일"은 여기 안 들어감. 서버 폴더에 저장되고, 여기엔 경로만 기록됨
# ---------------------------------------------------------------
class PostImage(Base):
    __tablename__ = "post_images"

    id = Column(Integer, primary_key=True)

    # 어느 매물의 사진인지
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)

    # 파일 경로. 예: "/uploads/a1b2c3.jpg"
    # 실제 파일은 backend/uploads/ 폴더에 저장됨
    image_url = Column(String(255), nullable=False)

    # 몇 번째 사진인지. 0번이 대표 사진(목록 썸네일에 쓰임)
    # "order"는 SQL 예약어라 못 쓰기 때문에 sort_order로 이름 지음
    sort_order = Column(Integer, default=0, nullable=False)

    # 사진의 "지문". 같은 사진인지 비교할 때 씀.
    # 3층에서 사진 도용(남의 매물 사진을 퍼온 것)을 잡는 데 쓸 자리.
    # 지금은 비어 있고, 그때 채워 넣으면 됨
    image_hash = Column(String(64), index=True)

    # 사진의 뜻을 담은 벡터(CLIP). "파란 자전거" 같은 말로 사진을 찾거나,
    # 사진만 보고 카테고리를 짐작하는 데 씀.
    # image_hash 는 "같은 사진인가", 이건 "무엇이 찍혔나" 를 봄
    image_vec = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    post = relationship("Post", back_populates="images")


# ---------------------------------------------------------------
# 6) chat_rooms - 채팅방
#
# 방 하나 = 매물 하나 + 구매자 한 명.
# 판매자는 post.seller_id 로 알 수 있어서 따로 저장하지 않음.
# 한 매물에 여러 구매자가 각자 방을 가짐
# ---------------------------------------------------------------
class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # --- 거래 확정 ---
    # 누른 "시각"을 저장함. 비어 있으면 아직 안 누른 것.
    # 둘 다 채워지면 거래 확정
    buyer_decided_at = Column(DateTime)      # 구매자가 "구매 결정"을 누른 시각
    seller_confirmed_at = Column(DateTime)   # 판매자가 "판매 확인"을 누른 시각

    # --- 안 읽은 메시지 세기 ---
    # 이 시각 이후에 온 메시지가 안 읽은 것
    buyer_read_at = Column(DateTime)
    seller_read_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # 채팅 목록을 최근 대화 순으로 정렬할 때 씀
    last_message_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    post = relationship("Post", back_populates="chat_rooms")
    buyer = relationship("User")

    messages = relationship(
        "Message",
        back_populates="room",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    # 같은 사람이 같은 매물에 방을 두 개 만들지 못하게 막음
    __table_args__ = (
        UniqueConstraint("post_id", "buyer_id", name="uq_post_buyer_room"),
    )


# ---------------------------------------------------------------
# 7) messages - 대화 한 줄
# ---------------------------------------------------------------
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False, index=True)

    # 시스템 메시지("거래가 확정됐어요")는 보낸 사람이 없어서 비어 있음
    sender_id = Column(Integer, ForeignKey("users.id"))

    content = Column(Text, nullable=False)

    # "text" = 사람이 쓴 말, "system" = 서버가 남긴 안내, "image" = 사진
    # 화면에서 그리는 방식이 달라서 구분함
    kind = Column(String(10), default="text", nullable=False)

    # 사진 메시지일 때만 채워짐. 매물 사진과 같은 방식으로 경로만 저장
    image_url = Column(String(255))

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    room = relationship("ChatRoom", back_populates="messages")
    sender = relationship("User")


# ---------------------------------------------------------------
# 8) reports - 신고
#
# 지금은 쌓아두기만 함. 3층 관리자 대시보드에서 이 목록을 보고 처리함
# ---------------------------------------------------------------
class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 무엇을 신고했는지. "post" = 매물, "user" = 사용자
    target_type = Column(String(10), nullable=False)
    target_id = Column(Integer, nullable=False, index=True)

    reason = Column(String(30), nullable=False)   # 사기 의심 / 허위 매물 / ...
    detail = Column(Text)                          # 자유 서술 (선택)

    # "접수" → "처리완료"(문제 있었음) 또는 "기각"(문제없음). 관리자가 바꿈
    status = Column(String(10), default="접수", nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # --- 에이전트가 조사한 결과 ---
    # 신고가 들어오면 서버가 스스로 조사해 여기에 적어둠.
    # 관리자는 이미 정리된 내용을 보고 판단만 하면 됨
    ai_risk = Column(String(10))        # 높음 / 보통 / 낮음
    ai_action = Column(String(30))      # 계정 정지 검토 / 경고 발송 / ...
    ai_summary = Column(Text)           # 한 줄 요약
    ai_grounds = Column(Text)           # 근거들 (JSON 글자)
    ai_steps = Column(Text)             # 어떤 도구를 어떤 순서로 봤는지 (JSON)
    ai_coverage = Column(Text)          # 무엇을 봤고 무엇을 못 봤는지 (JSON)
    ai_score = Column(Text)             # 항목별 채점 내역 (JSON)
    ai_mode = Column(String(20))        # 어떤 방식으로 조사했나
    ai_debate = Column(Text)            # 검사·변호인·정리 담당의 말 (JSON)
    ai_note = Column(Text)              # 관리자가 조사 전에 남긴 지시
    ai_checked_at = Column(DateTime)    # 조사한 시각

    reporter = relationship("User")

    # 같은 사람이 같은 대상을 여러 번 신고하지 못하게
    __table_args__ = (
        UniqueConstraint("reporter_id", "target_type", "target_id", name="uq_one_report"),
    )


# ---------------------------------------------------------------
# 9) reviews - 거래 후기
#
# 한 거래(채팅방)당 사람마다 한 번씩. 판매자→구매자, 구매자→판매자.
#
# 공개 규칙: 양쪽이 다 쓰거나, 쓴 지 7일이 지나야 남에게 보임.
# 상대가 뭐라 썼는지 모르는 상태에서 써야 보복 후기가 안 생김
# ---------------------------------------------------------------
class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False, index=True)

    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reviewee_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    rating = Column(Integer, nullable=False)   # 1~5 별점

    # 고른 태그들. SQLite에는 목록 타입이 없어서 쉼표로 이어 붙여 저장함
    tags = Column(String(300))
    comment = Column(Text)                     # 자유 서술 (선택)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    room = relationship("ChatRoom")
    # 같은 users 테이블을 두 번 가리켜서 어느 칸을 쓸지 알려줘야 함
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    reviewee = relationship("User", foreign_keys=[reviewee_id])

    # 한 거래에 한 사람이 두 번 쓰지 못하게
    __table_args__ = (
        UniqueConstraint("room_id", "reviewer_id", name="uq_one_review_per_deal"),
    )


# ---------------------------------------------------------------
# 10) withdrawals - 탈퇴 기록
#
# 회원을 지우면 왜 떠났는지 알 수 없게 됨.
# 사람을 특정할 수 있는 정보는 남기지 않고, 통계에 쓸 것만 남김
# ---------------------------------------------------------------
class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id = Column(Integer, primary_key=True)

    # 누구였는지는 남기지 않음. 언제·왜 떠났는지만
    reason = Column(String(50), nullable=False)      # 고른 사유
    detail = Column(Text)                            # 자유 서술 (선택)

    # 통계에 쓸 값들. 개인을 알아볼 수는 없음
    region = Column(String(50))
    days_used = Column(Integer)          # 며칠 썼는지
    total_posts = Column(Integer)        # 올린 매물 수
    completed_deals = Column(Integer)    # 거래 완료 수

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


# ---------------------------------------------------------------
# 11) admin_notices - 관리자 알림
#
# 에이전트가 조사를 마치거나 위험한 일이 생기면 여기에 쌓임
# ---------------------------------------------------------------
class AdminNotice(Base):
    __tablename__ = "admin_notices"

    id = Column(Integer, primary_key=True)

    kind = Column(String(20), nullable=False)    # report_done / risk_post / ...
    title = Column(String(200), nullable=False)
    body = Column(Text)

    # 눌렀을 때 갈 곳. 예: report / post / user
    link_type = Column(String(20))
    link_id = Column(Integer)

    level = Column(String(10), default="보통")    # 높음 / 보통 / 낮음
    is_read = Column(Boolean, default=False, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


# ---------------------------------------------------------------
# 12) warnings - 관리자가 보낸 경고
#
# 정지는 너무 무겁고 그냥 두기는 곤란한 경우에 씀.
# 사용자는 다음에 앱을 열 때 이 경고를 보고, 확인을 눌러야 넘어감
# ---------------------------------------------------------------
class Warning_(Base):
    __tablename__ = "warnings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 왜 경고받았는지. 사용자가 그대로 읽게 되므로 분명히 적어야 함
    reason = Column(String(200), nullable=False)
    detail = Column(Text)

    # 어느 신고에서 비롯됐는지 (없을 수도 있음)
    report_id = Column(Integer, ForeignKey("reports.id"))

    # 사용자가 읽고 확인을 눌렀는지
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User", foreign_keys=[user_id])


# ---------------------------------------------------------------
# 13) admin_actions - 관리자가 한 일
#
# 누가 언제 무엇을 했는지 남김. 나중에 "왜 정지됐냐" 는 물음에 답하려면
# 기록이 있어야 함
# ---------------------------------------------------------------
class AdminAction(Base):
    __tablename__ = "admin_actions"

    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    action = Column(String(30), nullable=False)   # 계정정지 / 정지해제 / 매물숨김 / 신고기각
    target_type = Column(String(10))              # user / post / report
    target_id = Column(Integer)
    reason = Column(String(200))

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    admin = relationship("User")


# ---------------------------------------------------------------
# 14) search_logs - 검색 기록
#
# 실시간 인기 검색어를 만들기 위해 쌓음.
# 검색어 자체는 개인정보가 아니지만, 누가 검색했는지는
# 같은 사람이 같은 말을 여러 번 쳐서 순위를 올리는 걸 막는 데만 씀
# ---------------------------------------------------------------
class SearchLog(Base):
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True)

    # 검색어. 앞뒤 공백을 없애고 소문자로 통일해서 저장함
    keyword = Column(String(50), nullable=False, index=True)

    # 비로그인 검색도 세기 때문에 비어 있을 수 있음
    user_id = Column(Integer, ForeignKey("users.id"), index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


# ---------------------------------------------------------------
# 15) violations - 채팅 규칙 위반 기록 (사전 예방)
#
# 채팅에서 위험 신호(선입금·택배 등)가 잡히면 한 줄씩 여기 쌓는다.
# 숫자만 세지 않고 '증거'(어긴 규칙·실제 문장)를 함께 남겨,
# 관리자가 나중에 근거를 보고 판단할 수 있게 한다.
#   · 활성 카운트 = "최근 STRIKE_WINDOW_HOURS 안의 cleared=False 위반 수"
#   · HISTORY_KEEP_DAYS 지난 기록은 정리(삭제)한다
# ---------------------------------------------------------------
class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True)

    # 위반한 사람
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 어떤 규칙을 어겼는지 (예: "선입금", "택배거래")
    rule = Column(String(50), nullable=False)

    # 실제로 오간 문장 일부 — 증거. 관리자가 이걸 보고 판단한다
    snippet = Column(String(200))

    # 어느 채팅방에서 나왔는지 (맥락을 다시 볼 때 씀)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), index=True)

    # 위반 종류. scam(사기 신호)만 누진 카운트에 센다
    kind = Column(String(20), default="scam", nullable=False)

    # 관리자가 '무혐의'로 처리하면 True -> 카운트에서 빠짐 (되돌리기)
    cleared = Column(Boolean, default=False, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User", foreign_keys=[user_id])


# ---------------------------------------------------------------
# 16) 테이블 생성 함수
# ---------------------------------------------------------------
def init_db():
    """위에서 정의한 클래스들을 실제 DB 테이블로 만들어줌.
    이미 있는 테이블은 건드리지 않으니 여러 번 실행해도 안전함."""
    Base.metadata.create_all(bind=engine)
    migrate()


def migrate():
    """이미 있는 테이블에 새로 생긴 칸을 채워넣음.

    create_all 은 "없는 테이블" 만 만들고 "이미 있는 테이블의 새 칸" 은
    만들어주지 않음. 그래서 칸을 추가할 때마다 DB를 지워야 했는데,
    여기서 빠진 칸을 찾아 붙여주면 데이터를 지키면서 넘어갈 수 있음
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    added = []
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue

            have = {c["name"] for c in inspector.get_columns(table.name)}

            for column in table.columns:
                if column.name in have:
                    continue

                # SQLite 는 ALTER TABLE 로 칸 추가만 됨.
                # 기본값이 필요한 칸은 NULL 을 허용하는 형태로만 붙일 수 있음
                kind = column.type.compile(dialect=engine.dialect)
                conn.execute(text(
                    f'ALTER TABLE {table.name} ADD COLUMN {column.name} {kind}'
                ))

                # 붙인 칸은 기존 줄에서 비어 있음.
                # 참/거짓이나 숫자 칸이 비어 있으면 세는 곳마다 어긋나므로
                # 정해진 기본값으로 채워줌
                default = column.default
                if default is not None and not callable(getattr(default, "arg", None)):
                    value = default.arg
                    if isinstance(value, bool):
                        value = 1 if value else 0
                    if isinstance(value, (int, float, str)):
                        conn.execute(
                            text(f'UPDATE {table.name} SET {column.name} = :v '
                                 f'WHERE {column.name} IS NULL'),
                            {"v": value},
                        )

                added.append(f"{table.name}.{column.name}")

    # 예전에 붙인 칸이 비어 있을 수 있으니 한 번 훑어서 메움
    fixed = fill_missing_defaults()

    if added:
        print("[DB] 새 칸 추가:", ", ".join(added))
    if fixed:
        print("[DB] 빈 값 채움:", ", ".join(fixed))


def fill_missing_defaults() -> list[str]:
    """기본값이 있는데 비어 있는 칸을 채움.

    ALTER TABLE 로 붙인 칸은 기존 줄에서 NULL 로 남음.
    참/거짓 칸이 NULL 이면 "False 인 것" 을 세는 곳에서 빠져나가 숫자가 어긋남
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    fixed = []

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing:
                continue

            for column in table.columns:
                default = column.default
                if default is None or callable(getattr(default, "arg", None)):
                    continue

                value = default.arg
                if isinstance(value, bool):
                    value = 1 if value else 0
                if not isinstance(value, (int, float, str)):
                    continue

                result = conn.execute(
                    text(f'UPDATE {table.name} SET {column.name} = :v '
                         f'WHERE {column.name} IS NULL'),
                    {"v": value},
                )
                if result.rowcount:
                    fixed.append(f"{table.name}.{column.name}({result.rowcount})")

    return fixed


if __name__ == "__main__":
    init_db()
    print("DB 생성 완료 → danggeun.db")
