# 당근 클론 — AI 사기 탐지 중고거래 플랫폼

> 중고거래 사기를 **사후 조사**뿐 아니라 **사전 예방**까지, 여러 AI 에이전트가 나눠 조사하고 서로 견제하며 잡아내는 풀스택 프로젝트.
> React · FastAPI · SQLite · 로컬 LLM(멀티에이전트) 기반.

<br>

## 왜 만들었나

중고거래 사기는 매년 8만 건 안팎, 2024년엔 하루 약 270건이 신고됩니다. (경찰청 사이버사기범죄 현황) 경찰 대응은 이미 포화 상태라, **사람이 다 못 잡는다면 플랫폼이 스스로 걸러야 한다**는 문제의식에서 출발했습니다. 그래서 단순한 중고거래 앱이 아니라, **AI가 사기를 잡아내는** 중고거래 앱을 만들었습니다.

<br>

## 핵심 기능

- **멀티에이전트 사기 조사** — 여러 AI 에이전트가 역할을 나눠(매물·이력·관계 조사관) 조사하고, 검사·변호인이 서로 견제해 편향을 막습니다. 최종 위험도 판정은 AI가 아니라 **규칙 엔진**이 계산해 같은 자료면 항상 같은 결과가 나옵니다.
- **사전 예방 시스템** — 신고를 기다리지 않고, 실시간 채팅에서 금칙어·사기 유도 표현(선입금·계좌·택배 등)을 문장 속에서도 잡아냅니다. `탐지 → 증거 기록 → 누진 카운트 → 단계별 조치 → 회복 → 보관`의 6단계 파이프라인으로 동작합니다.
- **똑똑한 검색** — 초성 검색(`ㄴㅌㅂ`→노트북), 의미 검색(ko-sroberta), 사진 검색(CLIP), 오타 보정을 한 검색창에서 제공합니다.
- **AI 판매글 도우미** — 사진을 보고 카테고리를 추천하고 판매글 초안을 써줍니다. (없는 정보는 지어내지 않도록 프롬프트로 제어)
- **사진 도용 탐지** — pHash로 남의 사진을 퍼온 매물을 걸러냅니다.
- **실시간 채팅** — WebSocket 기반 1:1 거래 채팅, 양쪽 확인 시 거래 완료, 대화 중 신고.
- **관리자 대시보드** — 신고·회원·매물·위험 매물·제재 대기를 한곳에서 관리.

<br>

## 기술 스택

| 영역 | 사용 기술 |
|------|-----------|
| 프론트엔드 | React 19, Vite, lucide-react |
| 백엔드 | FastAPI, SQLAlchemy(ORM), WebSocket |
| 데이터베이스 | SQLite |
| 인증 | JWT, bcrypt |
| AI (전부 로컬 실행) | gemma3:12b(Ollama) · CLIP · ko-sroberta · pHash |

<br>

## 시스템 구조

```
사용자 ──▶ React (프론트엔드) ──▶ FastAPI (백엔드) ──▶ SQLite
                                       │
                                       ▼  (무거운 작업만 호출)
                              로컬 AI 엔진
                     gemma3 · CLIP · ko-sroberta · pHash
```

### 멀티에이전트 사기 대응 (2겹 방어)

```
① 사전 예방 (대화 시점)      ② 사후 조사 (신고 후)
   금칙어·사기유도 실시간 탐지     신고 접수 → AI 조사(도구 7개)
   → 증거 기록 → 누진 카운트       → 규칙 채점 → 위험도 판정
   → 단계별 조치 → 회복·보관       → 관리자 최종 결정
```

- **설계 원칙** — 사람이 아니라 '행동(그 문장)'을 지목해 낙인을 피하고, 판정은 규칙이 하되 최종 결정은 사람이 하며, 시간이 지나면 카운트가 풀리는 '교화' 방식.
- **에이전트 지시서** — `backend/agents/*.md` 에 역할(페르소나)을 부여. 예) `prosecutor.md`(검사), `defender.md`(변호인), `summarizer.md`(정리).

<br>

## 폴더 구조

```
danggeun/
├─ backend/               FastAPI 서버
│  ├─ main.py             앱 조립 · 라우터 연결
│  ├─ config.py           설정값·고정 목록(지역·카테고리·문턱값)
│  ├─ database.py         DB 테이블 정의 (SQLAlchemy)
│  ├─ prevention.py       사전 예방 파이프라인
│  ├─ badwords.py         금칙어·사기유도 탐지
│  ├─ risk_score.py       위험도 규칙 엔진
│  ├─ agent*.py           멀티에이전트(단독/분업/토론)
│  ├─ agents/             에이전트 지시서(.md)
│  ├─ routers/            기능별 API (auth·posts·chats·admin …)
│  └─ scripts/            초기 데이터·점검 스크립트
└─ frontend/              React + Vite
   └─ src/
      ├─ screens/         화면(목록·상세·채팅·마이페이지 …)
      ├─ components/       재사용 컴포넌트(카드·모달 …)
      ├─ admin/           관리자 대시보드
      └─ styles/          CSS
```

<br>

## 실행 방법

### 사전 준비 — 로컬 AI

AI 기능은 로컬에서 [Ollama](https://ollama.com)로 실행합니다.

```bash
ollama pull gemma3:12b
```

> CLIP · ko-sroberta · pHash 는 아래 파이썬 패키지 설치 시 자동으로 받아집니다.

### 1) 백엔드

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # (macOS/Linux: source venv/bin/activate)

pip install fastapi uvicorn sqlalchemy bcrypt PyJWT python-multipart websockets
pip install sentence-transformers imagehash

python database.py               # DB·테이블 생성
python scripts/seed_chats.py     # 예시 데이터(선택)
python scripts/seed_searches.py  # 예시 데이터(선택)

uvicorn main:app --reload        # http://localhost:8000  (문서: /docs)
```

### 2) 프론트엔드

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

> 배포 설정과 안전 옵션(`DANGGEUN_ENV=production`)은 [`DEPLOY.md`](./DEPLOY.md) 참고.

<br>

## 향후 계획

- **진품·가품 판별** — 사진만으로 정품/가품을 가려내는 AI. 브랜드·모델별로 라벨링한 대량 이미지와 학습 자원이 필요해 장기 도전 목표로 두고, 우선 '가품 의심 신호 점수화'부터 접근할 예정.

<br>

## 만든 이

**주정현** ([@svc0612-beep](https://github.com/svc0612-beep))

> 학습·포트폴리오 목적의 1인 개발 프로젝트입니다.
