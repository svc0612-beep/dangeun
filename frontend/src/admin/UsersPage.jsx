// 회원 — 목록, 가입·탈퇴 현황, 탈퇴 사유

import { useState, useEffect } from "react";

import { callApi, jsonPost, auth } from "../api";
import { LineChart, BarChart, StatCard, GREEN } from "./Charts";

export default function UsersPage({ token }) {
  const [tab, setTab] = useState("list");
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState("");
  const [stats, setStats] = useState(null);
  const [quits, setQuits] = useState(null);

  function load() {
    const p = new URLSearchParams({ limit: 50 });
    if (keyword) p.set("keyword", keyword);
    callApi("/admin/users?" + p, { headers: auth(token) })
      .then((d) => { setRows(d.목록); setTotal(d.total); })
      .catch(() => {});
  }

  useEffect(load, [token]);

  useEffect(() => {
    const h = { headers: auth(token) };
    callApi("/admin/stats/users?days=14", h).then(setStats).catch(() => {});
    callApi("/admin/withdrawals", h).then(setQuits).catch(() => {});
  }, [token]);

  function warn(u) {
    const reason = window.prompt(`${u.닉네임}(${u.아이디}) 님에게 보낼 경고 사유`);
    if (!reason) return;
    const detail = window.prompt("자세한 내용 (사용자가 그대로 읽습니다)", "");

    callApi(`/admin/users/${u.번호}/warn`, {
      ...jsonPost({ reason, detail: detail || null }),
      headers: { "Content-Type": "application/json", ...auth(token) },
    })
      .then((res) => alert(`경고를 보냈습니다. (누적 ${res.누적경고}회)`))
      .catch((e) => alert(e.message));
  }

  function block(u) {
    const reason = window.prompt(`${u.닉네임}(${u.아이디}) 님을 정지하는 이유를 적어주세요`);
    if (!reason) return;
    callApi(`/admin/users/${u.번호}/block`, {
      ...jsonPost({ reason }),
      headers: { "Content-Type": "application/json", ...auth(token) },
    }).then(load).catch((e) => alert(e.message));
  }

  function unblock(u) {
    callApi(`/admin/users/${u.번호}/unblock`, {
      method: "POST", headers: auth(token),
    }).then(load).catch((e) => alert(e.message));
  }

  return (
    <>
      <div className="adm-tabs">
        <span className={tab === "list" ? "adm-tab adm-tab--on" : "adm-tab"}
          onClick={() => setTab("list")}>회원 목록</span>
        <span className={tab === "stats" ? "adm-tab adm-tab--on" : "adm-tab"}
          onClick={() => setTab("stats")}>가입·탈퇴 현황</span>
      </div>

      {tab === "list" ? (
        <>
          <div className="adm-filter">
            <input className="adm-input" placeholder="아이디·닉네임으로 찾기"
              value={keyword} onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") load(); }} />
            <button className="adm-btn" onClick={load}>찾기</button>
            <span className="adm-count">{total}명</span>
          </div>

          <table className="adm-table">
            <thead>
              <tr>
                <th>번호</th><th>아이디</th><th>닉네임</th><th>동네</th>
                <th>온도</th><th>매물</th><th>판매</th><th>구매</th>
                <th>취소</th><th>신고당함</th><th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((u) => (
                <tr key={u.번호} className={u.정지 ? "adm-row--hidden" : ""}>
                  <td>{u.번호}</td>
                  <td>{u.아이디}</td>
                  <td className="adm-td-title">
                    {u.닉네임}
                    {u.정지 && <span className="tag tag--red">정지</span>}
                  </td>
                  <td>{u.동네}</td>
                  <td>{u.매너온도}</td>
                  <td>{u.매물}</td>
                  <td>{u.판매}</td>
                  <td>{u.구매}</td>
                  <td className={u.취소 > 2 ? "adm-td-warn" : ""}>{u.취소}</td>
                  <td className={u.신고당함 > 0 ? "adm-td-warn" : ""}>{u.신고당함}</td>
                  <td>
                    {u.정지
                      ? <button className="adm-btn" onClick={() => unblock(u)}>해제</button>
                      : <>
                          <button className="adm-btn adm-btn--warn"
                            onClick={() => warn(u)}>경고</button>
                          <button className="adm-btn adm-btn--red"
                            onClick={() => block(u)}>정지</button>
                        </>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <>
          {stats && (
            <>
              <div className="adm-stats">
                <StatCard label="총 탈퇴" value={stats.총탈퇴} />
                <StatCard label="최근 2주 가입"
                  value={stats.가입.reduce((a, b) => a + b.수, 0)} />
                <StatCard label="최근 2주 탈퇴"
                  value={stats.탈퇴.reduce((a, b) => a + b.수, 0)} />
              </div>

              <div className="adm-card">
                <p className="adm-card__head">가입과 탈퇴</p>
                <LineChart series={[
                  { 이름: "가입", 색: GREEN, 자료: stats.가입 },
                  { 이름: "탈퇴", 색: "#D64545", 자료: stats.탈퇴 },
                ]} />
              </div>

              <div className="adm-grid2">
                <div className="adm-card">
                  <p className="adm-card__head">탈퇴 사유</p>
                  <BarChart data={stats.탈퇴사유} color="#D64545" unit="명" />
                </div>
                <div className="adm-card">
                  <p className="adm-card__head">얼마나 쓰다 떠났나</p>
                  <BarChart data={stats.사용기간} color="#8E8E93" unit="명" />
                </div>
              </div>
            </>
          )}

          {quits && quits.count > 0 && (
            <>
              <p className="adm-sec">탈퇴하며 남긴 말</p>
              <table className="adm-table">
                <thead>
                  <tr><th>사유</th><th>남긴 말</th><th>지역</th><th>쓴 기간</th><th>매물</th><th>거래</th><th>떠난 날</th></tr>
                </thead>
                <tbody>
                  {quits.목록.map((w, i) => (
                    <tr key={i}>
                      <td className="adm-td-title">{w.사유}</td>
                      <td>{w.내용 || "-"}</td>
                      <td>{w.지역}</td>
                      <td>{w.쓴기간}</td>
                      <td>{w.올린매물}</td>
                      <td>{w.거래완료}</td>
                      <td>{new Date(w.떠난날 + "Z").toLocaleDateString("ko-KR")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </>
      )}
    </>
  );
}
