// 조치 기록 — 누가 언제 무엇을 했나
//
// "왜 정지됐냐" 는 물음에 답하려면 기록이 있어야 함

import { useState, useEffect } from "react";

import { callApi, auth } from "../api";

export default function ActionsPage({ token }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    callApi("/admin/actions?limit=100", { headers: auth(token) })
      .then((d) => setRows(d.목록))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <p className="adm-empty">불러오는 중…</p>;
  if (rows.length === 0) return <p className="adm-empty">아직 조치한 기록이 없습니다.</p>;

  return (
    <table className="adm-table">
      <thead>
        <tr><th>한 일</th><th>대상</th><th>사유</th><th>관리자</th><th>시각</th></tr>
      </thead>
      <tbody>
        {rows.map((a, i) => (
          <tr key={i}>
            <td className="adm-td-title">{a.한일}</td>
            <td>{a.대상종류} #{a.대상번호}</td>
            <td>{a.사유 || "-"}</td>
            <td>{a.관리자}</td>
            <td>{new Date(a.시각 + "Z").toLocaleString("ko-KR")}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
