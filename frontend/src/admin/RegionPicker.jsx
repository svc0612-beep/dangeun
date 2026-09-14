// 지역 고르기 — 시/도 → 시/군/구 두 단계
//
// 매물이 실제로 있는 지역만 보여줌.
// 229개 시군구를 다 늘어놓으면 대부분 0건이라 고르기 어려움

import { useState, useEffect } from "react";

import { callApi, auth } from "../api";

export default function RegionPicker({ token, value, onChange }) {
  const [tree, setTree] = useState({ 시도: [], 시군구: {} });

  // value 는 "서울 강남구" 또는 "서울" 또는 "" (전국)
  const sido = value ? value.split(" ")[0] : "";

  useEffect(() => {
    callApi("/admin/regions", { headers: auth(token) })
      .then(setTree)
      .catch(() => {});
  }, [token]);

  const guList = tree.시군구[sido] || [];

  return (
    <>
      <select className="adm-select" value={sido}
        onChange={(e) => onChange(e.target.value)}>
        <option value="">전국</option>
        {tree.시도.map((s) => (
          <option key={s.이름} value={s.이름}>{s.이름} ({s.수})</option>
        ))}
      </select>

      <select className="adm-select" value={value} disabled={!sido}
        onChange={(e) => onChange(e.target.value)}>
        <option value={sido}>{sido ? sido + " 전체" : "시/군/구"}</option>
        {guList.map((g) => (
          <option key={g.이름} value={g.이름}>
            {g.이름.split(" ")[1]} ({g.수})
          </option>
        ))}
      </select>
    </>
  );
}
