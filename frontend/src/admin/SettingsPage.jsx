// 설정 — 관리자 비밀번호 변경

import { useState } from "react";

import { callApi, auth } from "../api";

export default function SettingsPage({ token }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [msg, setMsg] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setMsg(null);
    setError(null);

    if (next !== again) { setError("새 비밀번호가 서로 다릅니다"); return; }
    if (next.length < 8) { setError("새 비밀번호는 8자 이상이어야 합니다"); return; }

    setBusy(true);
    try {
      const res = await callApi("/admin/password", {
        method: "PATCH",
        body: JSON.stringify({ current_password: current, new_password: next }),
        headers: { "Content-Type": "application/json", ...auth(token) },
      });
      setMsg(res.message);
      setCurrent(""); setNext(""); setAgain("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="adm-card adm-card--form">
      <p className="adm-card__head">관리자 비밀번호 변경</p>
      <p className="adm-note">
        자리를 비운 사이 남이 바꾸지 못하도록 현재 비밀번호를 다시 확인합니다.
      </p>

      <label className="adm-label">현재 비밀번호</label>
      <input className="adm-input" type="password" autoComplete="off"
        value={current} onChange={(e) => setCurrent(e.target.value)} />

      <label className="adm-label">새 비밀번호 (8자 이상)</label>
      <input className="adm-input" type="password" autoComplete="new-password"
        value={next} onChange={(e) => setNext(e.target.value)} />

      <label className="adm-label">새 비밀번호 확인</label>
      <input className="adm-input" type="password" autoComplete="new-password"
        value={again} onChange={(e) => setAgain(e.target.value)} />

      {error && <p className="msg-error">{error}</p>}
      {msg && <p className="adm-ok">{msg}</p>}

      <button className="adm-btn adm-btn--main" onClick={submit} disabled={busy}>
        {busy ? "바꾸는 중…" : "비밀번호 변경"}
      </button>
    </div>
  );
}
