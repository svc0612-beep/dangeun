"""
당근 클론 - 백엔드 서버
실행: uvicorn main:app --reload

이 파일은 "조립" 만 함. 실제 기능은 아래 파일들에 나뉘어 있음

  config.py      설정값과 고정 목록 (지역·카테고리·문턱값 …)
  schemas.py     주고받는 값의 형태
  deps.py        DB 창구 · 비밀번호 · 토큰 · 로그인 확인
  korean.py      한글 자모/초성 도구
  errors.py      입력값 오류를 한글로
  chat_core.py   채팅방 공통 + 실시간 연결 관리

  scam.py        사기 예방 (위험 문구 · 시세 · 사진 도용)
  ai_search.py   의미 검색 (뜻으로 찾기)
  image_check.py 사진 도용 탐지 (지문 대조)
  chat_tips.py   대화를 분석해 추천 문구 만들기

  routers/auth.py     회원
  routers/posts.py    매물 · 사진 · 찜
  routers/search.py   검색 · 인기 검색어
  routers/chats.py    채팅 · 거래 확정
  routers/reviews.py  후기 · 프로필
  routers/reports.py  신고
  routers/admin.py    관리 도구
  routers/dashboard.py 관리자 대시보드 자료
"""

import os
import threading

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles   # 저장된 사진을 브라우저에 보여주기
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from database import SessionLocal, Post, PostImage
from config import (
    UPLOAD_DIR, BUMP_COOLDOWN_HOURS, CATEGORIES,
    IS_PROD, SHOW_DOCS, ALLOWED_ORIGINS, DEV_ORIGIN_REGEX,
)
from errors import korean_validation_error
import ai_search
import image_check
import vision
import query_ai
import chat_tips
import risk_watch

from routers import auth, posts, search, chats, reviews, reports, admin, dashboard


app = FastAPI(
    title="당근 클론 API",
    # 배포에서는 API 설명서를 닫음 — 어떤 API가 있고 무엇을 받는지
    # 그대로 보여주기 때문. 개발 중에는 /docs 로 계속 볼 수 있음
    docs_url="/docs" if SHOW_DOCS else None,
    redoc_url="/redoc" if SHOW_DOCS else None,
    openapi_url="/openapi.json" if SHOW_DOCS else None,
)

# 어디서 오는 요청을 받아줄지.
#   개발 — localhost·같은 와이파이 안의 기기(폰 확인용)를 폭넓게 허용
#   배포 — 환경변수 DANGGEUN_ORIGINS 에 적은 주소만 허용
if IS_PROD:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        # 포트를 하나만 적어두면 Vite가 5174로 밀렸을 때 막혀서
        # "서버에 연결할 수 없습니다" 가 뜸. 개발 중엔 넉넉하게
        allow_origin_regex=DEV_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 입력값 오류를 영어 대신 한글로 돌려줌
app.add_exception_handler(RequestValidationError, korean_validation_error)

# /uploads 주소로 요청이 오면 uploads 폴더의 파일을 그대로 돌려줌.
# 이게 있어야 브라우저에서 localhost:8000/uploads/abc.jpg 로 사진을 볼 수 있음
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ---------------------------------------------------------------
# 기능별 라우터 연결
# 순서는 상관없지만, 주소가 겹치지 않게 주의해야 함
# (예: /posts/similar 는 /posts/{post_id} 와 부딪혀서 /search/similar 로 뺐음)
# ---------------------------------------------------------------
app.include_router(auth.router)
app.include_router(posts.router)
app.include_router(search.router)
app.include_router(chats.router)
app.include_router(reviews.router)
app.include_router(reports.router)
app.include_router(admin.router)
app.include_router(dashboard.router)


# ---------------------------------------------------------------
# 서버 확인용
# ---------------------------------------------------------------
@app.get("/")
def read_root():
    return {"message": "당근 서버 살아있음"}


@app.get("/health")
def health_check():
    """서버가 살아있는지, AI 기능이 준비됐는지 한눈에.
    /docs 없이도 주소창에 쳐서 확인할 수 있음"""
    db = SessionLocal()
    try:
        total = db.query(Post).count()
        with_vec = db.query(Post).filter(Post.embedding.isnot(None)).count()
    except Exception:
        total = with_vec = 0
    finally:
        db.close()

    return {
        "status": "ok",
        "features": {
            # 뜻으로 찾기 (노트북 ↔ 맥북)
            "의미검색": ai_search.is_ready(),
            # 문장 해석 (캠핑장 가는데... → 캠핑 의자)
            "문장해석": query_ai.is_ready(),
            # 사진 도용 탐지
            "사진검사": image_check.is_ready(),
            # 사진에 무엇이 찍혔는지 이해 (카테고리 추천·말로 사진 찾기)
            "사진이해": vision.is_ready(),
        },
        "posts": {"전체": total, "벡터준비됨": with_vec},
    }


# ---------------------------------------------------------------
# 앱 설정값 (로그인 불필요)
# 끌올 대기 시간 같은 값을 프론트가 알아야 버튼을 잠글 수 있음.
# 서버에만 두면 값을 바꿔도 화면 코드를 안 고쳐도 됨
# ---------------------------------------------------------------
@app.get("/config")
def get_config():
    return {
        "bump_cooldown_hours": BUMP_COOLDOWN_HOURS,
        "categories": CATEGORIES,   # 화면의 카테고리 칩이 이걸 받아서 채움
        # 화면이 "이런 매물은 어때요?" 를 보여줄지 판단하는 데 씀
        "semantic_search": ai_search.is_ready(),
        # 문장 해석을 쓸 수 있는지. 모델이 없는 기기에서는 false
        "query_ai": query_ai.is_ready(),
    }


# ---------------------------------------------------------------
# 서버가 켜질 때 스스로 준비하기
#
# 의미 검색용 벡터나 사진 지문이 비어 있으면 여기서 채움.
# 사람이 /docs 에 들어가 버튼을 누를 일이 없어야 함 —
# 배포하면 /docs 는 닫히고, 사용자가 그런 걸 할 수도 없기 때문
#
# 오래 걸릴 수 있어서 별도 흐름으로 돌림. 그동안에도 서버는 정상 동작하고,
# 준비가 끝나면 그때부터 해당 기능이 켜짐
# ---------------------------------------------------------------
def prepare_in_background():
    db = SessionLocal()
    try:
        # 1) 대화를 분석해 추천 문구 만들기.
        # 대화가 적으면 예전에 저장해둔 파일을 씀
        try:
            chat_tips.prepare(db)
        except Exception as e:
            print(f"[준비] 대화 분석 건너뜀 — {e}")

        # 2) 의미 검색용 벡터가 없는 매물 채우기
        if ai_search.is_ready():
            try:
                posts = db.query(Post).filter(Post.embedding.is_(None)).all()
                for post in posts:
                    post.embedding = ai_search.embed_post(post)
                if posts:
                    db.commit()
                    print(f"[준비] 의미 검색 벡터 {len(posts)}개 생성")
            except Exception as e:
                db.rollback()
                print(f"[준비] 벡터 생성 건너뜀 — {e}")

        # 3) 아직 안 본 매물 중 위험한 것을 관리자에게 알림.
        # 앱을 껐다 켜는 사이에 올라온 것도 놓치지 않게
        try:
            found = risk_watch.scan_all(db)
            if found:
                print(f"[준비] 위험 매물 {found}건을 관리자에게 알림")
        except Exception as e:
            db.rollback()
            print(f"[준비] 위험 매물 확인 건너뜀 — {e}")

        # 4) 뜻 벡터가 없는 사진 채우기 (말로 사진 찾기용)
        if vision.is_ready():
            try:
                import json as _json
                done = 0
                for image in db.query(PostImage).filter(PostImage.image_vec.is_(None)).all():
                    path = image.image_url.lstrip("/")
                    if not os.path.exists(path):
                        continue
                    vec = vision.embed_image(path)
                    if vec:
                        image.image_vec = _json.dumps(vec)
                        done += 1
                if done:
                    db.commit()
                    print(f"[준비] 사진 뜻 벡터 {done}개 생성")
            except Exception as e:
                db.rollback()
                print(f"[준비] 사진 벡터 건너뜀 — {e}")

        # 5) 지문이 없는 사진 채우기 (도용 탐지용)
        if image_check.is_ready():
            try:
                done = 0
                for image in db.query(PostImage).filter(PostImage.image_hash.is_(None)).all():
                    path = image.image_url.lstrip("/")
                    if not os.path.exists(path):
                        continue
                    h = image_check.make_hash(path)
                    if h:
                        image.image_hash = h
                        done += 1
                if done:
                    db.commit()
                    print(f"[준비] 사진 지문 {done}개 생성")
            except Exception as e:
                db.rollback()
                print(f"[준비] 사진 지문 건너뜀 — {e}")
    finally:
        db.close()


@app.on_event("startup")
def prepare_on_start():
    # daemon=True : 서버를 끌 때 이 흐름이 붙잡지 않도록
    threading.Thread(target=prepare_in_background, daemon=True).start()
