// 위험 매물 — 신고가 없어도 걸러낸 것
//
// 신고를 기다리면 누군가 당한 뒤에야 알게 됨.
// 위험 신호가 겹치는 매물을 먼저 찾아 보여줌

import { useState, useEffect } from "react";
import { AlertTriangle } from "lucide-react";

import { callApi, jsonPost, auth } from "../api";

export default function RiskyPage({ token }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    callApi("/admin/risky-posts?limit=30", { headers: auth(token) })
      .then((d) => setRows(d.목록))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }

  useEffect(load, [token]);

  function hide(p) {
    const reason = window.prompt(`"${p.제목}" 을 숨기는 이유`, p.위험[0]?.내용?.slice(0, 60));
    if (!reason) return;
    callApi(`/admin/posts/${p.번호}/hide`, {
      ...jsonPost({ reason }),
      headers: { "Content-Type": "application/json", ...auth(token) },
    }).then(load).catch((e) => alert(e.message));
  }

  if (loading) return <p className="adm-empty">살펴보는 중…</p>;
  if (rows.length === 0) return <p className="adm-empty">위험해 보이는 매물이 없습니다.</p>;

  return (
    <>
      <p className="adm-note">
        신고가 없어도 위험 신호가 있는 매물입니다. 위험한 순서로 놓았습니다.
      </p>

      <div className="risk-list">
        {rows.map((p) => (
          <div key={p.번호} className="risk-item">
            <div className="risk-item__top">
              <AlertTriangle size={16} strokeWidth={2}
                className={p.점수 >= 3 ? "risk-icon risk-icon--high" : "risk-icon"} />
              <span className="risk-item__title">{p.제목}</span>
              <span className="risk-item__price">{p.가격.toLocaleString()}원</span>
              <span className="risk-item__who">{p.판매자}</span>
              <button className="adm-btn adm-btn--red" onClick={() => hide(p)}>숨기기</button>
            </div>

            <ul className="risk-item__flags">
              {p.위험.map((f, i) => (
                <li key={i} className={f.단계 === "danger" ? "flag flag--danger" : "flag"}>
                  {f.내용}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </>
  );
}
