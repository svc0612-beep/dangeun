당근 클론 - 백엔드

폴더 구조
  main.py          앱 조립 · 라우터 연결만
  config.py        설정값과 고정 목록 (지역·카테고리·문턱값)
  schemas.py       주고받는 값의 형태
  deps.py          DB 창구 · 비밀번호 · 토큰 · 로그인 확인
  korean.py        한글 자모/초성 도구
  errors.py        입력값 오류를 한글로
  chat_core.py     채팅방 공통 + 실시간 연결 관리
  scam.py          사기 예방
  ai_search.py     의미 검색
  image_check.py   사진 도용 탐지
  chat_tips.py     대화 분석 → 추천 문구
  database.py      DB 테이블 정의
  routers/         화면이 부르는 API들

처음 실행
  venv\Scripts\activate
  pip install fastapi uvicorn sqlalchemy bcrypt PyJWT python-multipart websockets
  pip install sentence-transformers imagehash
  python database.py
  python scripts/seed_chats.py
  python scripts/seed_searches.py
  uvicorn main:app --reload
