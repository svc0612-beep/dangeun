# 배포하기

만들면서 넣어둔 안전장치들이 `DANGGEUN_ENV=production` 하나로 한꺼번에 켜집니다.

---

## 1. 백엔드

### 열쇠 만들기

```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

나온 문자열을 아래 `DANGGEUN_SECRET` 에 넣습니다.

### 설정 파일

`backend/.env.example` 을 복사해 `backend/.env` 로 만들고 값을 채웁니다.

```
DANGGEUN_ENV=production
DANGGEUN_SECRET=위에서_만든_문자열
DANGGEUN_ORIGINS=https://내주소.com
```

`.env` 를 읽으려면 패키지가 하나 더 필요합니다.

```
pip install python-dotenv
```

그리고 `main.py` 맨 위에 두 줄을 넣습니다.

```python
from dotenv import load_dotenv
load_dotenv()
```

### 켜기

```
uvicorn main:app --host 0.0.0.0 --port 8000
```

배포에서는 `--reload` 를 빼야 합니다. 파일이 바뀔 때마다 재시작하느라 느려집니다.

### 확인

- `https://주소/docs` 가 **404** 여야 합니다 (설명서가 닫힘)
- `https://주소/health` 는 `{"status":"ok"}`

---

## 2. 프론트엔드

`frontend/.env.example` 을 복사해 `frontend/.env.production` 으로 만듭니다.

```
VITE_API_URL=https://api.내주소.com
```

만들기:

```
npm run build
```

`dist` 폴더가 생깁니다. 이 폴더를 웹 서버에 올리면 됩니다.
`npm run dev` 는 개발용이라 배포에 쓰면 안 됩니다.

---

## 3. HTTPS

화면이 `https` 인데 서버가 `http` 면 브라우저가 막습니다. 채팅(WebSocket)도
`wss` 로 자동으로 바뀌므로 서버 쪽도 반드시 HTTPS 여야 합니다.

무료로 받으려면 Let's Encrypt 를 씁니다. 대부분의 호스팅이 자동으로 해줍니다.

---

## 4. 관리자 계정 만들기

관리 기능(다시 계산하기 등)은 `is_admin` 인 사람만 쓸 수 있습니다.

```
python -c "from database import SessionLocal, User; db=SessionLocal(); u=db.query(User).filter(User.username=='내아이디').first(); u.is_admin=True; db.commit(); print(u.username, u.is_admin)"
```

---

## 5. 올리기 전에 확인할 것

- [ ] `.env` 가 GitHub 에 안 올라갔는지 (`.gitignore` 에 넣어뒀습니다)
- [ ] `DANGGEUN_SECRET` 을 기본값에서 바꿨는지
      (안 바꾸면 서버가 아예 안 뜨게 막아뒀습니다)
- [ ] `DANGGEUN_ORIGINS` 에 실제 주소를 넣었는지
- [ ] 관리자 계정을 하나 만들어뒀는지
- [ ] `danggeun.db` 와 `uploads/` 를 올리지 않았는지

---

## 아직 남은 것

**SQLite 는 소규모용입니다.** 사람이 많아지면 PostgreSQL 로 옮겨야 합니다.
`database.py` 의 `DATABASE_URL` 한 줄만 바꾸면 되도록 되어 있습니다.

**사진이 서버 폴더에 쌓입니다.** 서버를 옮기면 사진이 사라지므로,
규모가 커지면 S3 같은 저장소로 옮기는 게 좋습니다.

**비밀번호 찾기가 메일을 안 보냅니다.** 배포에서는 코드가 서버 로그에만
남으므로 사용자가 받을 방법이 없습니다. 메일 발송을 붙이거나
이 기능을 잠시 감춰야 합니다.
