// 매물 목록 (홈)
// 지역·카테고리 필터, 검색바와 추천창, 인기 검색어, 의미 검색 결과까지

import { useState, useEffect } from "react";
import { Search, X, Star } from "lucide-react";

import { callApi, jsonPost, auth } from "../api";
import { splitRegion } from "../utils";
import { TabBar } from "../components/ui";
import PostCard from "../components/PostCard";
import SearchRanking from "../components/SearchRanking";

// ===============================================================
// 매물 목록 화면 (검색 + 카테고리 칩 포함)
// ===============================================================
export default function PostList({ me, regionTree, categories, onSelect, onLogout, onWrite, onChat, onMy }) {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // 필터. 처음엔 내 지역을 보여줌
  const mine = splitRegion(me.region);
  const [sido, setSido] = useState(mine.sido);
  const [gu, setGu] = useState(mine.gu);
  const [category, setCategory] = useState("");

  // input = 지금 타이핑 중인 글자, keyword = 엔터로 확정된 검색어
  // 둘을 나눠야 타이핑할 때마다 목록이 흔들리지 않음
  const [input, setInput] = useState("");
  const [keyword, setKeyword] = useState("");

  const [similarPosts, setSimilarPosts] = useState([]);  // 뜻이 비슷한 매물
  const [suggests, setSuggests] = useState([]);   // 추천 낱말
  const [similar, setSimilar] = useState([]);     // 오타 보정 후보
  const [openBox, setOpenBox] = useState(false);  // 추천창 열림 여부

  // 최근 검색어. 브라우저에 저장해서 새로고침해도 남음
  const [recent, setRecent] = useState(() => {
    try { return JSON.parse(localStorage.getItem("recentSearch") || "[]"); }
    catch { return []; }
  });

  const region = gu ? sido + " " + gu : sido;

  // --- 목록 불러오기 ---
  useEffect(() => {
    setLoading(true);
    // URLSearchParams = 주소 뒤 ?a=1&b=2 를 안전하게 만들어줌
    const p = new URLSearchParams();
    if (region) p.set("region", region);
    if (category) p.set("category", category);
    if (keyword) p.set("keyword", keyword);

    callApi("/posts?" + p.toString())
      .then((data) => {
        setPosts(data);
        setLoading(false);

        // 검색어가 있을 때만 "이런 매물은 어때요?" 를 채움.
        // 이미 나온 것은 빼서 같은 매물이 두 번 보이지 않게 함
        if (!keyword) { setSimilarPosts([]); return; }

        const sp = new URLSearchParams({ keyword });
        if (region) sp.set("region", region);
        if (category) sp.set("category", category);
        if (data.length) sp.set("exclude", data.map((x) => x.id).join(","));

        callApi("/search/similar?" + sp.toString())
          .then(setSimilarPosts)
          .catch(() => setSimilarPosts([]));
      })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, [region, category, keyword]);

  // --- 타이핑하면 추천 낱말 받아오기 ---
  useEffect(() => {
    const word = input.trim();
    if (!word) { setSuggests([]); setSimilar([]); return; }

    // 글자를 칠 때마다 요청하면 낭비라, 250ms 멈춘 뒤에만 보냄
    const timer = setTimeout(() => {
      callApi("/suggest?q=" + encodeURIComponent(word))
        .then((data) => { setSuggests(data.suggestions); setSimilar(data.similar); })
        .catch(() => { setSuggests([]); setSimilar([]); });
    }, 250);

    // 다음 글자가 들어오면 이전 예약을 취소함
    return () => clearTimeout(timer);
  }, [input]);

  // --- 검색 실행 ---
  function runSearch(word) {
    const w = (word ?? input).trim();
    setInput(w);
    setKeyword(w);
    setOpenBox(false);

    if (w) {
      // 같은 말이 이미 있으면 빼고 맨 앞에. 최대 5개만 보관
      const next = [w, ...recent.filter((x) => x !== w)].slice(0, 5);
      setRecent(next);
      localStorage.setItem("recentSearch", JSON.stringify(next));

      // 인기 검색어 집계용으로 서버에도 남김.
      // 실패해도 검색 자체는 그대로 진행되게 조용히 넘어감
      callApi("/search-logs", {
        ...jsonPost({ keyword: w }),
        headers: { "Content-Type": "application/json", ...auth(token) },
      }).catch(() => {});
    }
  }

  function clearSearch() {
    setInput("");
    setKeyword("");
    setOpenBox(false);
  }

  function pickSido(v) {
    setSido(v);
    setGu("");   // 시/도가 바뀌면 시·군·구는 초기화
  }

  return (
    <div className="page page--list">
      <header className="topbar">
        <span className="topbar__brand">당근</span>

        <select className="select-region" value={sido}
          onChange={(e) => pickSido(e.target.value)}>
          <option value="">전체</option>
          {Object.keys(regionTree).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        <select className="select-region" value={gu} disabled={!sido}
          onChange={(e) => setGu(e.target.value)}>
          <option value="">{sido ? sido + " 전체" : "시/군/구"}</option>
          {(regionTree[sido] || []).map((g) => <option key={g} value={g}>{g}</option>)}
        </select>

        {/* 검색바. position:relative 라서 추천창이 바로 아래 붙음 */}
        <div className="search-wrap">
          <div className="search-box">
            <Search size={17} strokeWidth={2} />
            <input
              className="search-input"
              placeholder="물품을 검색하고 엔터를 누르세요"
              value={input}
              onFocus={() => setOpenBox(true)}
              // 클릭이 먼저 처리되도록 잠깐 뒤에 닫음
              onBlur={() => setTimeout(() => setOpenBox(false), 150)}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
            />
            {input && <X size={17} strokeWidth={2} className="search-x" onClick={clearSearch} />}
          </div>

          {/* 타이핑 중이면 추천, 비었으면 최근 검색어 */}
          {openBox && (input.trim() ? suggests.length > 0 : recent.length > 0) && (
            <div className="suggest-box">
              {!input.trim() && <p className="suggest-label">최근 검색어</p>}
              {(input.trim() ? suggests : recent).map((w) => (
                <div key={w} className="suggest-item"
                  onMouseDown={() => runSearch(w)}>
                  <Search size={14} strokeWidth={2} />
                  {w}
                </div>
              ))}
            </div>
          )}
        </div>

        <nav className="topbar__nav">
          <span onClick={onWrite}>판매등록</span>
          <span onClick={onChat}>채팅</span>
          <span onClick={onMy}>마이페이지</span>
        </nav>
        <span className="topbar__user">{me.nickname}</span>
        <span className="topbar__logout" onClick={onLogout}>로그아웃</span>
      </header>

      {/* 카테고리 칩 줄 */}
      <div className="cat-row">
        <span className={category === "" ? "cat-chip cat-chip--on" : "cat-chip"}
          onClick={() => setCategory("")}>전체</span>
        {categories.map((c) => (
          <span key={c} className={category === c ? "cat-chip cat-chip--on" : "cat-chip"}
            onClick={() => setCategory(c)}>{c}</span>
        ))}
      </div>

      {/* 지금 걸린 조건들. × 로 하나씩 뗌 */}
      <div className="active-chips">
        {keyword && (
          <span className="chip-on">
            "{keyword}"
            <X size={13} strokeWidth={2.5} onClick={clearSearch} />
          </span>
        )}
        {region && (
          <span className="chip-on">
            {region}
            <X size={13} strokeWidth={2.5} onClick={() => { setSido(""); setGu(""); }} />
          </span>
        )}
        {category && (
          <span className="chip-on">
            {category}
            <X size={13} strokeWidth={2.5} onClick={() => setCategory("")} />
          </span>
        )}
        <span className="filter-count">{posts.length}건</span>
      </div>

      {/* 검색 중일 때는 결과에 집중하도록 숨김 */}
      {!keyword && <SearchRanking onPick={(w) => runSearch(w)} />}

      <main className="grid">
        {loading && <p className="notice">불러오는 중…</p>}
        {error && <p className="notice">불러오지 못했습니다: {error}</p>}

        {!loading && !error && posts.length === 0 && (
          <div className="empty-box">
            <p className="empty-title">
              {region ? region + "에 결과가 없습니다." : "결과가 없습니다."}
            </p>

            {/* 오타 보정 — "이걸 찾으셨나요?" */}
            {keyword && similar.length > 0 && (
              <p className="empty-sub">
                혹시 이걸 찾으셨나요?{" "}
                {similar.map((w) => (
                  <span key={w} className="link" onClick={() => runSearch(w)}>{w}</span>
                ))}
              </p>
            )}

            {/* 시·군·구까지 좁혀놨으면 넓혀보라고 권함 */}
            {gu ? (
              <button className="btn-line" onClick={() => setGu("")}>
                {sido} 전체에서 찾기
              </button>
            ) : sido ? (
              <button className="btn-line" onClick={() => setSido("")}>
                전국에서 찾기
              </button>
            ) : (
              <p className="empty-sub">다른 검색어를 써보세요.</p>
            )}
          </div>
        )}

        {posts.map((post) => (
          <PostCard key={post.id} post={post} onClick={() => onSelect(post.id)} />
        ))}
      </main>

      {/* 글자가 안 겹쳐도 뜻이 비슷한 매물.
          "노트북" 으로 검색해도 "맥북 에어" 가 여기 나옴 */}
      {similarPosts.length > 0 && (
        <>
          <p className="similar-head">
            이런 매물은 어때요?
            <span>“{keyword}” 와 비슷한 매물</span>
          </p>
          <main className="grid">
            {similarPosts.map((post) => (
              <PostCard key={post.id} post={post} onClick={() => onSelect(post.id)} />
            ))}
          </main>
        </>
      )}

      <TabBar active="home" onHome={() => {}} onWrite={onWrite}
        onChat={onChat} onMy={onMy} />
    </div>
  );
}