// 제재 대기 — 채팅 규칙을 반복해서 어긴 회원
//
// 자동으로 정지시키지 않는다. 증거(어긴 규칙·실제 문장)를 보여주고
// 관리자가 판단한다.
//   · [정지]   — 무거운 조치. 사유를 받아 기존 정지 API 호출
//   · [무혐의] — 오탐이었거나 봐줄 만하면 활성 위반을 없던 일로 (카운트 리셋)

import { useState, useEffect } from "react";
import { Ban } from "lucide-react";

import { callApi, jsonPost, auth } from "../api";

export default function PenaltyPage({ token }) {
  const [rows, setRows] = useState([]);      // 제재 대기 목록
  const [loading, setLoading] = useState(true);

  // 목록 불러오기
  function load() {
    setLoading(true);
    callApi("/admin/penalties", { headers: auth(token) })
      .then((d) => setRows(d.목록))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }

  useEffect(load, [token]);

  // 계정 정지 — 사유를 받아서 기존 정지 API 를 부름
  function block(u) {
    const reason = window.prompt(`${u.닉네임} 님을 정지하는 이유`, "채팅 규칙 반복 위반");
    if (!reason) return;
    callApi(`/admin/users/${u.회원번호}/block`, {
      ...jsonPost({ reason }),
      headers: { "Content-Type": "application/json", ...auth(token) },
    })
      .then(load)                        // 처리 후 목록 새로고침
      .catch((e) => alert(e.message));
  }

  // 무혐의 — 활성 위반을 cleared 처리 (카운트에서 빠짐, 이력은 남음)
  function clear(u) {
    if (!window.confirm(`${u.닉네임} 님의 위반을 무혐의 처리할까요? (카운트가 0이 됩니다)`)) return;
    callApi(`/admin/users/${u.회원번호}/clear-violations`, {
      method: "POST",
      headers: auth(token),
    })
      .then(load)
      .catch((e) => alert(e.message));
  }

  if (loading) return <p className="adm-empty">살펴보는 중…</p>;
  if (rows.length === 0) return <p className="adm-empty">제재 대기 중인 회원이 없습니다.</p>;

  return (
    <>
      <p className="adm-note">
        채팅 규칙을 반복해서 어긴 회원입니다. 증거를 보고 판단하세요 — 최종 정지는 직접 눌러야 합니다.
      </p>

      <div className="risk-list">
        {rows.map((u) => (
          <div key={u.회원번호} className="risk-item">
            <div className="risk-item__top">
              {/* 위반 4회 이상이면 빨간 아이콘 */}
              <Ban size={16} strokeWidth={2}
                className={u.위반수 >= 4 ? "risk-icon risk-icon--high" : "risk-icon"} />
              <span className="risk-item__title">
                {u.닉네임} <small>@{u.아이디}</small>
              </span>
              <span className="risk-item__who">
                위반 {u.위반수}회 · 매너 {u.매너온도}℃
              </span>
              {u.정지 && <span className="flag flag--danger">정지됨</span>}
              <button className="adm-btn" onClick={() => clear(u)}>무혐의</button>
              <button className="adm-btn adm-btn--red" onClick={() => block(u)}>정지</button>
            </div>

            {/* 증거 — 어떤 규칙을 어긴 실제 문장 */}
            <ul className="risk-item__flags">
              {u.증거.map((v, i) => (
                <li key={i} className="flag">
                  [{v.규칙}] "{v.문장}"
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </>
  );
}
