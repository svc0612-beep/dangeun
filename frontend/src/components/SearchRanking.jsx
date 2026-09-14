// 인기 검색어
//
// 최근 7일 집계. 지난주 등수와 견줘 오르내림을 함께 보여줌.
// 넓은 화면에서는 목록 오른쪽에 붙는 패널로,
// 좁은 화면에서는 목록 위에 접히는 상자로 나옴

import { useState, useEffect } from "react";
import { Flame, ChevronUp, ChevronDown } from "lucide-react";

import { callApi } from "../api";

export default function SearchRanking({ onPick }) {
  const [list, setList] = useState([]);

  useEffect(() => {
    callApi("/search-ranking")
      .then((d) => setList(d.ranking))
      .catch(() => setList([]));
  }, []);

  if (list.length === 0) return null;

  return (
    <aside className="rank">
      <p className="rank__head">
        <Flame size={16} strokeWidth={2} />
        우리 동네 인기 키워드
      </p>
      <p className="rank__sub">지금 우리 동네에서 많이 검색해요</p>

      <div className="rank__tags">
        {list.map((item) => (
          <span key={item.keyword} className="rank__tag"
            onClick={() => onPick(item.keyword)}>
            {/* 몇 위인지 숫자로. 1~3위는 색을 진하게 */}
            <b className={item.rank <= 3 ? "rank__no rank__no--top" : "rank__no"}>
              {item.rank}
            </b>
            {item.keyword}
            <RankChange change={item.change} />
          </span>
        ))}
      </div>
    </aside>
  );
}

// 오르내림 표시. "new" 이거나 숫자(양수=상승, 음수=하락, 0=그대로)
function RankChange({ change }) {
  if (change === "new") return <em className="rank__new">NEW</em>;
  if (change === 0) return null;

  const up = change > 0;
  return (
    <em className={up ? "rank__up" : "rank__down"}>
      {up ? <ChevronUp size={11} strokeWidth={3} /> : <ChevronDown size={11} strokeWidth={3} />}
      {Math.abs(change)}
    </em>
  );
}
