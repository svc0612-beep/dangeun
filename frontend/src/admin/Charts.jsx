// 그래프 조각들
//
// 라이브러리를 새로 깔지 않고 SVG로 직접 그림.
// 막대와 꺾은선 정도는 이 편이 가볍고, 색·모양을 마음대로 맞출 수 있음

// 색은 CSS 변수 대신 직접 씀 — SVG 안에서는 변수가 잘 안 먹는 브라우저가 있음
const GREEN = "#23A26D";
const ORANGE = "#FF6F0F";
const GRAY = "#8E8E93";
const LINE = "#EFEFEF";


// ---------------------------------------------------------------
// 꺾은선 — 날짜별 흐름 (등록·거래·가입·탈퇴)
// ---------------------------------------------------------------
export function LineChart({ series, height = 180 }) {
  // series = [{ 이름, 색, 자료: [{날짜, 수}] }]
  const first = series[0]?.자료 || [];
  if (first.length === 0) return <p className="chart-empty">자료가 없습니다</p>;

  const W = 640;
  const H = height;
  const pad = { top: 16, right: 12, bottom: 26, left: 34 };

  // 모든 줄을 통틀어 가장 큰 값. 0이면 1로 둬서 나누기 오류를 막음
  const max = Math.max(1, ...series.flatMap((s) => s.자료.map((d) => d.수)));

  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;

  const x = (i) => pad.left + (innerW * i) / Math.max(1, first.length - 1);
  const y = (v) => pad.top + innerH - (innerH * v) / max;

  // 가로 눈금 네 줄
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((r) => Math.round(max * r));

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg">
        {/* 눈금선과 숫자 */}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} y1={y(t)} x2={W - pad.right} y2={y(t)}
              stroke={LINE} strokeWidth="1" />
            <text x={pad.left - 6} y={y(t) + 4} fontSize="10" fill={GRAY}
              textAnchor="end">{t}</text>
          </g>
        ))}

        {/* 날짜 — 너무 빽빽하지 않게 몇 개만 */}
        {first.map((d, i) => {
          const step = Math.ceil(first.length / 7);
          if (i % step !== 0) return null;
          return (
            <text key={d.날짜} x={x(i)} y={H - 8} fontSize="10" fill={GRAY}
              textAnchor="middle">{d.날짜.slice(5)}</text>
          );
        })}

        {/* 줄 그리기 */}
        {series.map((s) => (
          <g key={s.이름}>
            <polyline
              points={s.자료.map((d, i) => `${x(i)},${y(d.수)}`).join(" ")}
              fill="none" stroke={s.색} strokeWidth="2"
              strokeLinejoin="round" strokeLinecap="round" />
            {s.자료.map((d, i) => (
              <circle key={i} cx={x(i)} cy={y(d.수)} r="2.5" fill={s.색} />
            ))}
          </g>
        ))}
      </svg>

      <div className="chart-legend">
        {series.map((s) => (
          <span key={s.이름} className="chart-legend__item">
            <i style={{ background: s.색 }} />
            {s.이름}
          </span>
        ))}
      </div>
    </div>
  );
}


// ---------------------------------------------------------------
// 가로 막대 — 분류별 개수 (카테고리·지역·탈퇴사유)
// ---------------------------------------------------------------
export function BarChart({ data, color = GREEN, unit = "개" }) {
  // data = [{ 이름, 수 }]
  const rows = (data || []).filter((d) => d.수 > 0);
  if (rows.length === 0) return <p className="chart-empty">자료가 없습니다</p>;

  const max = Math.max(...rows.map((d) => d.수));

  return (
    <div className="bars">
      {rows.map((d) => (
        <div key={d.이름} className="bar-row">
          <span className="bar-name">{d.이름}</span>
          <div className="bar-track">
            <div className="bar-fill"
              style={{ width: `${(d.수 / max) * 100}%`, background: color }} />
          </div>
          <span className="bar-value">{d.수.toLocaleString()}{unit}</span>
        </div>
      ))}
    </div>
  );
}


// ---------------------------------------------------------------
// 숫자 카드 — 오늘·이번주 요약
// ---------------------------------------------------------------
export function StatCard({ label, value, sub, tone }) {
  return (
    <div className={tone ? `stat stat--${tone}` : "stat"}>
      <p className="stat-label">{label}</p>
      <p className="stat-value">{typeof value === "number" ? value.toLocaleString() : value}</p>
      {sub && <p className="stat-sub">{sub}</p>}
    </div>
  );
}

export { GREEN, ORANGE, GRAY };
