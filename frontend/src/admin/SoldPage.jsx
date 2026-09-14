// 판매 내역 — 오늘 / 어제 / 이번주
//
// 지역별로 함께 보여줌. 어느 동네에서 중고거래가 활발한지
// 한눈에 알 수 있어야 관리자가 판단할 수 있음

import { useState, useEffect } from "react";

import { callApi, auth } from "../api";
import { BarChart, StatCard, GREEN, ORANGE } from "./Charts";

const TABS = [
  { key: "today",     label: "오늘" },
  { key: "yesterday", label: "어제" },
  { key: "week",      label: "이번주" },
];

export default function SoldPage({ token }) {
  const [period, setPeriod] = useState("week");
  const [data, setData] = useState(null);

  useEffect(() => {
    setData(null);
    callApi(`/admin/sold?period=${period}`, { headers: auth(token) })
      .then(setData)
      .catch(() => {});
  }, [token, period]);

  return (
    <>
      <div className="adm-tabs">
        {TABS.map((t) => (
          <span key={t.key}
            className={period === t.key ? "adm-tab adm-tab--on" : "adm-tab"}
            onClick={() => setPeriod(t.key)}>
            {t.label}
          </span>
        ))}
      </div>

      {!data ? <p className="adm-empty">불러오는 중…</p> : (
        <>
          <div className="adm-stats">
            <StatCard label="거래 건수" value={data.count} />
            <StatCard label="합계 금액" value={data.합계금액.toLocaleString() + "원"} />
            <StatCard label="거래된 지역" value={data.지역별.length} />
            <StatCard label="카테고리 수" value={data.카테고리별.length} />
          </div>

          {data.count > 0 && (
            <>
              <div className="adm-grid2">
                <div className="adm-card">
                  <p className="adm-card__head">시·도별 거래 건수</p>
                  <BarChart data={data.시도별} unit="건" />
                </div>
                <div className="adm-card">
                  <p className="adm-card__head">동네별 거래 건수</p>
                  <BarChart data={data.지역별} color={ORANGE} unit="건" />
                </div>
              </div>

              <div className="adm-grid2">
                <div className="adm-card">
                  <p className="adm-card__head">동네별 거래 금액</p>
                  <BarChart data={data.지역별금액} color="#3B7DD8" unit="원" />
                </div>
                <div className="adm-card">
                  <p className="adm-card__head">카테고리별 거래</p>
                  <BarChart data={data.카테고리별} unit="건" />
                </div>
              </div>
            </>
          )}

          {data.count === 0 ? (
            <p className="adm-empty">이 기간에 완료된 거래가 없습니다.</p>
          ) : (
            <>
              <p className="adm-sec">거래 목록</p>
              <table className="adm-table">
                <thead>
                  <tr>
                    <th>제품명</th><th>카테고리</th><th>가격</th>
                    <th>지역</th><th>판매자</th><th>구매자</th><th>거래 시각</th>
                  </tr>
                </thead>
                <tbody>
                  {data.목록.map((s, i) => (
                    <tr key={i}>
                      <td className="adm-td-title">{s.제목}</td>
                      <td>{s.카테고리}</td>
                      <td>{s.가격.toLocaleString()}원</td>
                      <td>{s.지역}</td>
                      <td>{s.판매자}</td>
                      <td>{s.구매자}</td>
                      <td>{new Date(s.거래시각 + "Z").toLocaleString("ko-KR")}</td>
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
