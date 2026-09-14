// 매물 목록 (홈)
// 지역·카테고리 필터, 검색바와 추천창, 인기 검색어, 의미 검색 결과까지

import { useState, useEffect } from "react";
import { Search, X, Star, PenSquare } from "lucide-react";

import { callApi, jsonPost, auth } from "../api";
import { splitRegion } from "../utils";
import { TabBar } from "../components/ui";
import PostCard from "../components/PostCard";
import SearchRanking from "../components/SearchRanking";
import CategoryRow from "../components/CategoryRow";
import FeatureStrip from "../components/FeatureStrip";
import QueryHint from "../components/QueryHint";

// ===============================================================
// 매물 목록 화면 (검색 + 카테고리 칩 포함)
// ===============================================================
export default function PostList({
  me, token, regionTree, categories,
  onSelect, onLogout, onWrite, onChat, onMy, onHome, onWriteReview, onAdmin,
}) {
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
  const [photoPosts, setPhotoPosts] = useState([]);      // 사진에 그게 찍힌 매물
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
        if (!keyword) { setSimilarPosts([]); setPhotoPosts([]); return; }

        const sp = new URLSearchParams({ keyword });
        if (region) sp.set("region", region);
        if (category) sp.set("category", category);
        if (data.length) sp.set("exclude", data.map((x) => x.id).join(","));

        callApi("/search/similar?" + sp.toString())
          .then(setSimilarPosts)
          .catch(() => setSimilarPosts([]));

        // 사진에 무엇이 찍혔는지로도 찾아봄.
        // 제목에 없는 말("파란색 자전거")로도 걸릴 수 있음
        const pp = new URLSearchParams({ q: keyword });
        if (region) pp.set("region", region);

        callApi("/search/by-photo?" + pp.toString())
          .then((found) => {
            // 위에서 이미 나온 매물은 빼서 같은 게 두 번 보이지 않게
            const shown = new Set(data.map((x) => x.id));
            setPhotoPosts(found.filter((x) => !shown.has(x.id)));
          })
          .catch(() => setPhotoPosts([]));
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
        {/* 로고를 누르면 검색·필터를 풀고 처음 상태로 */}
        <span className="topbar__brand" onClick={onHome}>당근</span>

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
          {/* 관리자만 보이는 길. 일반 화면을 둘러보다 돌아갈 때 씀 */}
          {me.is_admin && (
            <span className="topbar__admin" onClick={onAdmin}>관리자</span>
          )}
          <span onClick={onChat}>채팅</span>
          <span onClick={onMy}>마이페이지</span>
          <span className="topbar__logout" onClick={onLogout}>로그아웃</span>
        </nav>

        {/* 글쓰기는 가장 자주 쓰는 동작이라 버튼으로 따로 뺌 */}
        <button className="btn-write" onClick={onWrite}>
          <PenSquare size={16} strokeWidth={2} />
          제품등록하기
        </button>
      </header>

      {/* 지역 고르기. 상단바에서 내려 아래 줄로 뺌 */}
      <div className="region-row">
        <select className="select-region" value={sido}
          onChange={(e) => pickSido(e.target.value)}>
          <option value="">전국</option>
          {Object.keys(regionTree).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        <select className="select-region" value={gu} disabled={!sido}
          onChange={(e) => setGu(e.target.value)}>
          <option value="">{sido ? sido + " 전체" : "시/군/구"}</option>
          {(regionTree[sido] || []).map((g) => <option key={g} value={g}>{g}</option>)}
        </select>

        <span className="region-count">{posts.length}건</span>
      </div>

      {/* 카테고리 — 동그란 아이콘으로 훑어보기 쉽게 */}
      <CategoryRow categories={categories} value={category} onPick={setCategory} />

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
      </div>

      {/* 긴 문장으로 검색했을 때만. 모델이 없으면 아무것도 안 뜸 */}
      {keyword && (
        <QueryHint
          keyword={keyword}
          onPickKeyword={(w) => runSearch(w)}
          onPickCategory={(c) => setCategory(c)}
        />
      )}

      {/* 넓은 화면에서는 왼쪽 목록 · 오른쪽 인기 키워드로 나뉨.
          좁은 화면에서는 위아래로 쌓임 */}
      <div className="home">
        <div className="home__main">

      <p className="sec-head">
        {keyword ? `“${keyword}” 검색 결과` : "추천 상품"}
        <span className="sec-count">{posts.length}건</span>
      </p>

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

      {/* 사진에 그게 찍힌 매물. 제목에 없는 말로도 걸림 */}
      {photoPosts.length > 0 && (
        <>
          <p className="similar-head">
            사진에서 찾았어요
            <span>“{keyword}” 가 사진에 보이는 매물</span>
          </p>
          <main className="grid">
            {photoPosts.map((post) => (
              <PostCard key={post.id} post={post} onClick={() => onSelect(post.id)} />
            ))}
          </main>
        </>
      )}

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

        </div>

        {/* 오른쪽 패널. 검색 중일 때는 결과에 집중하도록 숨김 */}
        {!keyword && (
          <div className="home__side">
            <SearchRanking onPick={(w) => runSearch(w)} />
          </div>
        )}
      </div>

      {/* 이 앱이 무엇을 지켜주는지. 맨 아래 안내 */}
      <FeatureStrip />

      <TabBar active="home" onHome={onHome} onWrite={onWrite}
        onChat={onChat} onMy={onMy} />
    </div>
  );
}
