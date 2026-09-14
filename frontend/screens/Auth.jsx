// 로그인 전 화면 네 개
// 로그인 · 회원가입 · 아이디 찾기 · 비밀번호 찾기

import { useState } from "react";

import { callApi, jsonPost } from "../api";
import { onEnter, splitRegion } from "../utils";
import { Field, RegionField } from "../components/ui";

// ===============================================================
// 로그인 화면
// ===============================================================
export function LoginScreen({ onLogin, go }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (busy) return;              // 엔터 연타 방지
    setError(null);
    setBusy(true);
    try {
      const data = await callApi("/login", jsonPost({ username, password }));
      onLogin(data.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page page--auth" onKeyDown={onEnter(submit)}>
      <h1 className="logo">당근</h1>
      <p className="logo-sub">우리 동네 중고거래</p>

      {/* autoComplete로 브라우저 자동완성을 끔.
          비밀번호 칸에 off 대신 new-password를 쓰는 건 크롬이 off를 자주 무시해서 */}
      <Field label="아이디" placeholder="아이디" value={username}
        autoComplete="off"
        onChange={(e) => setUsername(e.target.value)} />
      <Field label="비밀번호" type="password" placeholder="비밀번호" value={password}
        autoComplete="new-password"
        onChange={(e) => setPassword(e.target.value)} />

      {error && <p className="msg-error">{error}</p>}

      <button className="btn-primary" onClick={submit} disabled={busy}>
        {busy ? "확인 중…" : "로그인"}
      </button>

      <div className="link-row">
        <span className="link" onClick={() => go("findId")}>아이디 찾기</span>
        <span className="divider">|</span>
        <span className="link" onClick={() => go("findPw")}>비밀번호 찾기</span>
        <span className="divider">|</span>
        <span className="link" onClick={() => go("signup")}>회원가입</span>
      </div>
    </div>
  );
}

// ===============================================================
// 회원가입 화면
// ===============================================================
export function SignupScreen({ onSignedUp, go, regionTree }) {
  const [f, setF] = useState({
    name: "", username: "", password: "", password2: "",
    nickname: "", region: "", email: "", phone: "", address: "",
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  // 중복확인을 통과한 아이디를 기억. 이후 아이디를 고치면 무효가 됨
  const [checkedId, setCheckedId] = useState(null);
  const [checkMsg, setCheckMsg] = useState(null);

  function change(key, value) {
    setF({ ...f, [key]: value });
    if (key === "username") { setCheckedId(null); setCheckMsg(null); }
  }

  async function checkUsername() {
    if (f.username.length < 4) {
      setCheckMsg({ ok: false, text: "아이디는 4자 이상이어야 합니다" });
      return;
    }
    try {
      const data = await callApi("/check-username?username=" + encodeURIComponent(f.username));
      if (data.available) {
        setCheckedId(f.username);
        setCheckMsg({ ok: true, text: "사용할 수 있는 아이디입니다" });
      } else {
        setCheckedId(null);
        setCheckMsg({ ok: false, text: "이미 사용 중인 아이디입니다" });
      }
    } catch (err) {
      setCheckMsg({ ok: false, text: err.message });
    }
  }

  async function submit() {
    if (busy) return;
    setError(null);

    if (checkedId !== f.username) {
      setError("아이디 중복확인을 해주세요");
      return;
    }
    if (f.password !== f.password2) {
      setError("비밀번호가 서로 다릅니다");
      return;
    }
    // "서울 " 처럼 시/도만 고른 상태를 걸러냄
    if (!splitRegion(f.region).gu) {
      setError("지역을 끝까지 골라주세요");
      return;
    }

    setBusy(true);
    try {
      // password2는 서버에 안 보냄. 오타 검사용이라 저장할 이유가 없음
      await callApi("/signup", jsonPost({
        username: f.username, password: f.password,
        nickname: f.nickname, region: f.region,
        name: f.name, email: f.email, phone: f.phone, address: f.address,
      }));
      onSignedUp(f.username, f.password);   // 가입 성공 → 자동 로그인
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="page page--auth" onKeyDown={onEnter(submit)}>
      <span className="back-btn" onClick={() => go("login")}>← 로그인으로</span>
      <h2 className="form-title">회원가입</h2>

      <Field label="이름" placeholder="김민수" value={f.name}
        onChange={(e) => change("name", e.target.value)} />

      {/* 아이디 칸만 옆에 중복확인 버튼이 붙음 */}
      <div className="field">
        <label className="label">아이디</label>
        <div className="input-row">
          <input className="input" placeholder="4~20자" value={f.username}
            onChange={(e) => change("username", e.target.value)} />
          <button className="btn-small" onClick={checkUsername}>중복확인</button>
        </div>
        {checkMsg && (
          <p className={checkMsg.ok ? "msg-ok" : "msg-error"}>{checkMsg.text}</p>
        )}
      </div>

      <Field label="비밀번호" type="password" placeholder="8자 이상" value={f.password}
        onChange={(e) => change("password", e.target.value)} />
      <Field label="비밀번호 확인" type="password" placeholder="한 번 더 입력" value={f.password2}
        onChange={(e) => change("password2", e.target.value)} />

      <Field label="닉네임" placeholder="화면에 보일 이름" value={f.nickname}
        onChange={(e) => change("nickname", e.target.value)} />

      <RegionField label="지역" value={f.region} regionTree={regionTree}
        onChange={(v) => change("region", v)} />

      <Field label="이메일" placeholder="minsu@example.com" value={f.email}
        onChange={(e) => change("email", e.target.value)} />
      <Field label="휴대폰 번호" placeholder="010-1234-5678" value={f.phone}
        onChange={(e) => change("phone", e.target.value)} />
      <Field label="집주소" placeholder="서울시 강남구 역삼동 123" value={f.address}
        onChange={(e) => change("address", e.target.value)} />

      {error && <p className="msg-error">{error}</p>}

      <button className="btn-primary" onClick={submit} disabled={busy}>
        {busy ? "가입 중…" : "가입하기"}
      </button>
    </div>
  );
}

// ===============================================================
// 아이디 찾기
// ===============================================================
export function FindIdScreen({ go }) {
  const [f, setF] = useState({ name: "", email: "", phone: "" });
  const [found, setFound] = useState(null);
  const [error, setError] = useState(null);

  function change(key, value) { setF({ ...f, [key]: value }); }

  async function submit() {
    setError(null);
    setFound(null);
    try {
      const data = await callApi("/find-username", jsonPost(f));
      setFound(data.username);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="page page--auth" onKeyDown={onEnter(submit)}>
      <span className="back-btn" onClick={() => go("login")}>← 로그인으로</span>
      <h2 className="form-title">아이디 찾기</h2>
      <p className="guide">가입할 때 입력한 정보를 그대로 넣어주세요.</p>

      <Field label="이름" placeholder="김민수" value={f.name}
        onChange={(e) => change("name", e.target.value)} />
      <Field label="이메일" placeholder="minsu@example.com" value={f.email}
        onChange={(e) => change("email", e.target.value)} />
      <Field label="휴대폰 번호" placeholder="010-1234-5678" value={f.phone}
        onChange={(e) => change("phone", e.target.value)} />

      {error && <p className="msg-error">{error}</p>}

      {found && (
        <div className="result-box">
          <p className="result-label">회원님의 아이디</p>
          <p className="result-value">{found}</p>
        </div>
      )}

      {found ? (
        <button className="btn-primary" onClick={() => go("login")}>로그인하러 가기</button>
      ) : (
        <button className="btn-primary" onClick={submit}>아이디 찾기</button>
      )}
    </div>
  );
}

// ===============================================================
// 비밀번호 찾기 — 한 화면에서 2단계
// ===============================================================
export function FindPwScreen({ go }) {
  const [step, setStep] = useState(1);   // 1 = 본인확인, 2 = 코드입력
  const [f, setF] = useState({ username: "", email: "", phone: "" });
  const [code, setCode] = useState("");
  const [newPw, setNewPw] = useState("");
  const [newPw2, setNewPw2] = useState("");
  const [demoCode, setDemoCode] = useState(null);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  function change(key, value) { setF({ ...f, [key]: value }); }

  // 1단계 — 본인 확인하고 코드 받기
  async function requestCode() {
    setError(null);
    try {
      const data = await callApi("/request-reset", jsonPost(f));
      setDemoCode(data.demo_code || null);
      setStep(2);
    } catch (err) {
      setError(err.message);
    }
  }

  // 2단계 — 코드 확인하고 비밀번호 변경
  async function resetPassword() {
    setError(null);
    if (newPw !== newPw2) {
      setError("비밀번호가 서로 다릅니다");
      return;
    }
    try {
      await callApi("/reset-password", jsonPost({
        username: f.username, code, new_password: newPw,
      }));
      setDone(true);
    } catch (err) {
      setError(err.message);
    }
  }

  if (done) {
    return (
      <div className="page page--auth">
        <h2 className="form-title">변경 완료</h2>
        <p className="guide">새 비밀번호로 로그인해주세요.</p>
        <button className="btn-primary" onClick={() => go("login")}>로그인하러 가기</button>
      </div>
    );
  }

  return (
    <div className="page page--auth"
      onKeyDown={onEnter(step === 1 ? requestCode : resetPassword)}>
      <span className="back-btn" onClick={() => go("login")}>← 로그인으로</span>
      <h2 className="form-title">비밀번호 찾기</h2>

      {step === 1 ? (
        <>
          <p className="guide">가입할 때 입력한 정보를 그대로 넣어주세요.</p>

          <Field label="아이디" placeholder="minsu01" value={f.username}
            onChange={(e) => change("username", e.target.value)} />
          <Field label="이메일" placeholder="minsu@example.com" value={f.email}
            onChange={(e) => change("email", e.target.value)} />
          <Field label="휴대폰 번호" placeholder="010-1234-5678" value={f.phone}
            onChange={(e) => change("phone", e.target.value)} />

          {error && <p className="msg-error">{error}</p>}

          <button className="btn-primary" onClick={requestCode}>인증코드 받기</button>
        </>
      ) : (
        <>
          {/* 실제 서비스라면 메일/문자로 갔을 자리 */}
          {demoCode && (
            <div className="result-box">
              <p className="result-label">인증코드 (10분 유효)</p>
              <p className="result-value">{demoCode}</p>
            </div>
          )}

          <Field label="인증코드" placeholder="6자리 숫자" value={code}
            onChange={(e) => setCode(e.target.value)} />
          <Field label="새 비밀번호" type="password" placeholder="8자 이상" value={newPw}
            onChange={(e) => setNewPw(e.target.value)} />
          <Field label="새 비밀번호 확인" type="password" placeholder="한 번 더 입력" value={newPw2}
            onChange={(e) => setNewPw2(e.target.value)} />

          {error && <p className="msg-error">{error}</p>}

          <button className="btn-primary" onClick={resetPassword}>비밀번호 변경</button>
        </>
      )}
    </div>
  );
}