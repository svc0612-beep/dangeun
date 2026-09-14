// 인기 검색어
// 최근 7일 집계. 지난주 등수와 견줘 오르내림을 함께 보여줌

import { useState, useEffect } from "react";
import { TrendingUp, ChevronUp, ChevronDown } from "lucide-react";

import { callApi } from "../api";

// ===============================================================
// 인기 검색어
// 최근 7일 집계. 지난주 등수와 견줘 오르내림을 함께 보여줌
// ===============================================================
export default function SearchRanking({ onPick }) {
  const [list, setList] = useState([]);
  const [open, setOpen] = useState(true);

  useEffect(() => {
    callApi("/search-ranking")
      .then((d) => setList(d.ranking))
      .catch(() => setList([]));
  }, []);

  if (list.length === 0) return null;

  // 순위를 두 줄로 나눔 — 1~5위 왼쪽, 6~10위 오른쪽
  const half = Math.ceil(list.length / 2);
  const columns = [list.slice(0, half), list.slice(half)];

  return (
    <div className="rank-box">
      <div className="rank-head" onClick={() => setOpen(!open)}>
        <TrendingUp size={15} strokeWidth={2.2} />
        <span className="rank-title">인기 검색어</span>
        <span className="rank-period">최근 7일</span>
        <span className="rank-toggle">{open ? "접기" : "펼치기"}</span>
      </div>

      {open && (
        <div className="rank-cols">
          {columns.map((col, ci) => (
            <div key={ci} className="rank-col">
              {col.map((item) => (
                <div key={item.keyword} className="rank-item"
                  onClick={() => onPick(item.keyword)}>
                  <span className={item.rank <= 3 ? "rank-no rank-no--top" : "rank-no"}>
                    {item.rank}
                  </span>
                  <span className="rank-word">{item.keyword}</span>
                  <RankChange change={item.change} />
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// 오르내림 표시. "new" 이거나 숫자(양수=상승, 음수=하락, 0=그대로)
function RankChange({ change }) {
  if (change === "new") return <span className="rank-new">NEW</span>;
  if (change === 0) return <span className="rank-same">–</span>;

  const up = change > 0;
  return (
    <span className={up ? "rank-up" : "rank-down"}>
      {up ? <ChevronUp size={12} strokeWidth={3} /> : <ChevronDown size={12} strokeWidth={3} />}
      {Math.abs(change)}
    </span>
  );
}