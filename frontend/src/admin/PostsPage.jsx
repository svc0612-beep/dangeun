// 매물 — 세 가지 보기
//
//   전체 목록   표로 훑어보며 숨김 처리
//   카테고리별  어느 분류에 얼마나 있는지
//   지역별      어느 동네에 무엇이 올라오는지

import { useState, useEffect } from "react";

import { callApi, jsonPost, auth } from "../api";
import { BarChart, StatCard, GREEN, ORANGE } from "./Charts";
import RegionPicker from "./RegionPicker";

const CATEGORIES = [
  "디지털기기", "생활가전", "가구인테리어", "생활/주방",
  "유아동", "의류", "도서", "스포츠/레저", "기타",
];

const TABS = [
  { key: "list",     label: "전체 목록" },
  { key: "category", label: "카테고리별" },
  { key: "region",   label: "지역별" },
];


export default function PostsPage({ token }) {
  const [tab, setTab] = useState("list");

  return (
    <>
      <div className="adm-tabs">
        {TABS.map((t) => (
          <span key={t.key}
            className={tab === t.key ? "adm-tab adm-tab--on" : "adm-tab"}
            onClick={() => setTab(t.key)}>
            {t.label}
          </span>
        ))}
      </div>

      {tab === "list" && <ListView token={token} />}
      {tab === "category" && <CategoryView token={token} />}
      {tab === "region" && <RegionView token={token} />}
    </>
  );
}


// ---------------------------------------------------------------
// 전체 목록 — 표로 훑어보며 숨김 처리
// ---------------------------------------------------------------
function ListView({ token }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [keyword, setKeyword] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(true);

  const LIMIT = 30;

  function load() {
    setLoading(true);
    const p = new URLSearchParams({ skip, limit: LIMIT });
    if (keyword) p.set("keyword", keyword);
    if (category) p.set("category", category);
    if (status) p.set("status", status);

    callApi("/admin/posts?" + p, { headers: auth(token) })
      .then((d) => { setRows(d.목록); setTotal(d.total); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(load, [token, skip, category, status]);

  function hide(post) {
    const reason = window.prompt(`"${post.제목}" 을 숨기는 이유를 적어주세요`);
    if (!reason) return;
    callApi(`/admin/posts/${post.번호}/hide`, {
      ...jsonPost({ reason }),
      headers: { "Content-Type": "application/json", ...auth(token) },
    }).then(load).catch((e) => alert(e.message));
  }

  function unhide(post) {
    callApi(`/admin/posts/${post.번호}/unhide`, {
      method: "POST", headers: auth(token),
    }).then(load).catch((e) => alert(e.message));
  }

  return (
    <>
      <div className="adm-filter">
        <input className="adm-input" placeholder="제목으로 찾기"
          value={keyword} onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { setSkip(0); load(); } }} />

        <select className="adm-select" value={category}
          onChange={(e) => { setCategory(e.target.value); setSkip(0); }}>
          <option value="">카테고리 전체</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>

        <select className="adm-select" value={status}
          onChange={(e) => { setStatus(e.target.value); setSkip(0); }}>
          <option value="">상태 전체</option>
          <option value="판매중">판매중</option>
          <option value="예약중">예약중</option>
          <option value="거래완료">거래완료</option>
        </select>

        <span className="adm-count">{total.toLocaleString()}건</span>
      </div>

      {loading ? <p className="adm-empty">불러오는 중…</p> : (
        <table className="adm-table">
          <thead>
            <tr>
              <th>번호</th><th>제목</th><th>가격</th><th>카테고리</th>
              <th>지역</th><th>판매자</th><th>상태</th><th>조회</th><th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.번호} className={p.숨김 ? "adm-row--hidden" : ""}>
                <td>{p.번호}</td>
                <td className="adm-td-title">
                  {p.제목}
                  {p.숨김 && <span className="tag tag--red">숨김</span>}
                </td>
                <td>{p.가격.toLocaleString()}원</td>
                <td>{p.카테고리}</td>
                <td>{p.지역}</td>
                <td>{p.판매자}</td>
                <td>{p.상태}</td>
                <td>{p.조회수}</td>
                <td>
                  {p.숨김
                    ? <button className="adm-btn" onClick={() => unhide(p)}>숨김 해제</button>
                    : <button className="adm-btn adm-btn--red" onClick={() => hide(p)}>숨기기</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="adm-page">
        <button className="adm-btn" disabled={skip === 0}
          onClick={() => setSkip(Math.max(0, skip - LIMIT))}>이전</button>
        <span>{Math.floor(skip / LIMIT) + 1} / {Math.max(1, Math.ceil(total / LIMIT))}</span>
        <button className="adm-btn" disabled={skip + LIMIT >= total}
          onClick={() => setSkip(skip + LIMIT)}>다음</button>
      </div>
    </>
  );
}


// ---------------------------------------------------------------
// 카테고리별 — 어느 분류에 얼마나 있는지
// ---------------------------------------------------------------
function CategoryView({ token }) {
  const [region, setRegion] = useState("");
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(null);

  useEffect(() => {
    setData(null);
    const p = region ? `?region=${encodeURIComponent(region)}` : "";
    callApi("/admin/posts/by-category" + p, { headers: auth(token) })
      .then(setData)
      .catch(() => {});
  }, [token, region]);

  return (
    <>
      <div className="adm-filter">
        <RegionPicker token={token} value={region} onChange={setRegion} />
        {data && <span className="adm-count">{data.총매물}건</span>}
      </div>

      {!data ? <p className="adm-empty">불러오는 중…</p> : (
        <>
          <div className="adm-card">
            <p className="adm-card__head">{data.지역} 카테고리별 매물</p>
            <BarChart data={data.묶음.map((g) => ({ 이름: g.카테고리, 수: g.수 }))} />
          </div>

          {data.묶음.map((g) => (
            <div key={g.카테고리} className="cat-group">
              <div className="cat-group__head"
                onClick={() => setOpen(open === g.카테고리 ? null : g.카테고리)}>
                <span className="cat-group__name">{g.카테고리}</span>
                <span className="cat-group__count">{g.수}건</span>
                <span className="cat-group__avg">
                  평균 {g.평균가.toLocaleString()}원
                </span>
                <span className="cat-group__more">
                  {open === g.카테고리 ? "접기" : "펼치기"}
                </span>
              </div>

              {open === g.카테고리 && (
                <table className="adm-table">
                  <thead>
                    <tr><th>제목</th><th>가격</th><th>지역</th><th>판매자</th><th>상태</th></tr>
                  </thead>
                  <tbody>
                    {g.매물.map((p) => (
                      <tr key={p.번호}>
                        <td className="adm-td-title">{p.제목}</td>
                        <td>{p.가격.toLocaleString()}원</td>
                        <td>{p.지역}</td>
                        <td>{p.판매자}</td>
                        <td>{p.상태}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}
        </>
      )}
    </>
  );
}


// ---------------------------------------------------------------
// 지역별 — 어느 동네에 무엇이 올라오는지
// ---------------------------------------------------------------
function RegionView({ token }) {
  const [region, setRegion] = useState("");
  const [stats, setStats] = useState(null);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    callApi("/admin/stats/posts", { headers: auth(token) })
      .then(setStats)
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    // 지역을 고르면 그 지역 매물만 서버에서 받아옴
    if (!region) { setRows([]); setTotal(0); return; }

    const p = new URLSearchParams({ limit: 50, region });
    callApi("/admin/posts?" + p, { headers: auth(token) })
      .then((d) => { setRows(d.목록); setTotal(d.total); })
      .catch(() => {});
  }, [token, region]);

  return (
    <>
      <div className="adm-filter">
        <RegionPicker token={token} value={region} onChange={setRegion} />
        {region && <span className="adm-count">{total}건</span>}
      </div>

      {stats && (
        <div className="adm-grid2">
          <div className="adm-card">
            <p className="adm-card__head">시·도별 매물</p>
            <BarChart data={stats.시도별} />
          </div>
          <div className="adm-card">
            <p className="adm-card__head">시·군·구별 매물</p>
            <BarChart data={stats.지역별} color={ORANGE} />
          </div>
        </div>
      )}

      {region && (
        rows.length === 0 ? (
          <p className="adm-empty">{region} 에 올라온 매물이 없습니다.</p>
        ) : (
          <>
            <p className="adm-sec">{region} 매물</p>
            <table className="adm-table">
              <thead>
                <tr><th>제목</th><th>가격</th><th>카테고리</th><th>판매자</th><th>상태</th><th>조회</th></tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.번호}>
                    <td className="adm-td-title">{p.제목}</td>
                    <td>{p.가격.toLocaleString()}원</td>
                    <td>{p.카테고리}</td>
                    <td>{p.판매자}</td>
                    <td>{p.상태}</td>
                    <td>{p.조회수}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )
      )}
    </>
  );
}
