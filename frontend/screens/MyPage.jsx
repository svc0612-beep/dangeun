// 마이페이지 — 탭 다섯 개
//   찜 / 판매 / 거래 / 후기 / 내 정보
//
// 탭 상태(tab)는 부모가 들고 있음 — 상세를 다녀와도 탭이 유지되게

import { useState, useEffect } from "react";

import { API, callApi, jsonPost, jsonPatch, auth } from "../api";
import { formatPrice, timeAgo, bumpLeft, splitRegion, STATUS_OPTIONS } from "../utils";
import { Field, RegionField, TabBar } from "../components/ui";
import PostCard from "../components/PostCard";

function MyInfo({ me, token, regionTree, onMeChanged, onDeleted, onProfile }) {
  // 현재 값으로 폼을 채워둠
  const [f, setF] = useState({
    nickname: me.nickname, region: me.region,
    email: me.email, phone: me.phone, address: me.address,
  });
  const [msg, setMsg] = useState(null);      // { ok, text }
  const [busy, setBusy] = useState(false);

  const [pw, setPw] = useState({ current: "", next: "", next2: "" });
  const [pwMsg, setPwMsg] = useState(null);

  // 탈퇴용
  const [delPw, setDelPw] = useState("");
  const [delMsg, setDelMsg] = useState(null);

  function change(key, value) { setF({ ...f, [key]: value }); }
  function changePw(key, value) { setPw({ ...pw, [key]: value }); }

  async function saveProfile() {
    if (busy) return;
    setMsg(null);
    if (!splitRegion(f.region).gu) {
      setMsg({ ok: false, text: "지역을 끝까지 골라주세요" });
      return;
    }
    setBusy(true);
    try {
      const data = await callApi("/me", jsonPatch(token, f));
      onMeChanged(data);   // 상단바 닉네임 등을 바로 갱신
      setMsg({ ok: true, text: "저장했습니다" });
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    } finally {
      setBusy(false);
    }
  }

  async function savePassword() {
    setPwMsg(null);
    if (pw.next !== pw.next2) {
      setPwMsg({ ok: false, text: "새 비밀번호가 서로 다릅니다" });
      return;
    }
    try {
      await callApi("/me/password", jsonPatch(token, {
        current_password: pw.current, new_password: pw.next,
      }));
      setPw({ current: "", next: "", next2: "" });   // 입력칸 비우기
      setPwMsg({ ok: true, text: "비밀번호를 변경했습니다" });
    } catch (err) {
      setPwMsg({ ok: false, text: err.message });
    }
  }

  async function deleteAccount() {
    setDelMsg(null);

    // 되돌릴 수 없으니 두 번 물어봄
    if (!window.confirm("정말 탈퇴하시겠습니까?\n올린 매물과 사진이 모두 삭제되며 되돌릴 수 없습니다.")) return;
    if (!window.confirm("마지막 확인입니다. 탈퇴를 진행할까요?")) return;

    try {
      await callApi("/me", {
        method: "DELETE",
        headers: { "Content-Type": "application/json", ...auth(token) },
        body: JSON.stringify({ password: delPw }),
      });
      alert("탈퇴가 완료되었습니다.");
      onDeleted();   // 토큰 지우고 로그인 화면으로
    } catch (err) {
      setDelMsg(err.message);
    }
  }

  return (
    <div className="info-box">
      {/* 바꿀 수 없는 것들은 읽기 전용으로 보여줌 */}
      <div className="info-row">
        <span className="info-label">아이디</span>
        <span className="info-value">{me.username}</span>
      </div>
      <div className="info-row">
        <span className="info-label">이름</span>
        <span className="info-value">{me.name}</span>
      </div>
      <div className="info-row">
        <span className="info-label">매너온도</span>
        <span className="info-value">{me.manner_temp}°C</span>
      </div>
      <div className="info-row">
        <span className="info-label">거래</span>
        <span className="info-value">
          판매 {me.completed_deals}건 · 구매 {me.completed_purchases}건
          {me.cancel_count > 0 && ` · 취소 ${me.cancel_count}건`}
        </span>
      </div>

      {/* 남들에게 내가 어떻게 보이는지 확인 */}
      <p className="seller-more" onClick={() => onProfile(me.id)}>
        다른 사람에게 보이는 내 프로필 보기 →
      </p>

      <h3 className="section-title">정보 수정</h3>

      <Field label="닉네임" value={f.nickname}
        onChange={(e) => change("nickname", e.target.value)} />

      <RegionField label="지역" value={f.region} regionTree={regionTree}
        onChange={(v) => change("region", v)} />

      <Field label="이메일" value={f.email}
        onChange={(e) => change("email", e.target.value)} />
      <Field label="휴대폰 번호" value={f.phone}
        onChange={(e) => change("phone", e.target.value)} />
      <Field label="집주소" value={f.address}
        onChange={(e) => change("address", e.target.value)} />

      {msg && <p className={msg.ok ? "msg-ok" : "msg-error"}>{msg.text}</p>}

      <button className="btn-primary" onClick={saveProfile} disabled={busy}>
        {busy ? "저장 중…" : "저장하기"}
      </button>

      <h3 className="section-title">비밀번호 변경</h3>
      <p className="guide">
        로그인 상태여도 현재 비밀번호를 한 번 더 확인합니다.
      </p>

      <Field label="현재 비밀번호" type="password" value={pw.current}
        onChange={(e) => changePw("current", e.target.value)} />
      <Field label="새 비밀번호" type="password" placeholder="8자 이상" value={pw.next}
        onChange={(e) => changePw("next", e.target.value)} />
      <Field label="새 비밀번호 확인" type="password" value={pw.next2}
        onChange={(e) => changePw("next2", e.target.value)} />

      {pwMsg && <p className={pwMsg.ok ? "msg-ok" : "msg-error"}>{pwMsg.text}</p>}

      <button className="btn-primary" onClick={savePassword}>비밀번호 변경</button>

      <div className="danger-zone">
        <h3 className="danger-title">회원 탈퇴</h3>
        <p className="guide">
          탈퇴하면 올린 매물과 사진이 모두 삭제되고 되돌릴 수 없습니다.
          확인을 위해 비밀번호를 입력해주세요.
        </p>

        <Field label="비밀번호" type="password" value={delPw}
          onChange={(e) => setDelPw(e.target.value)} />

        {delMsg && <p className="msg-error">{delMsg}</p>}

        <button className="btn-danger-full" onClick={deleteAccount}>
          탈퇴하기
        </button>
      </div>
    </div>
  );
}

// ===============================================================
// 마이페이지 — 거래 내역 탭
// "무엇을 누구와 거래했고, 후기를 주고받았는지"
// ===============================================================
function MyDeals({ data, loading, onOpenChat, onWriteReview, onProfile }) {
  if (loading || !data?.deals) {
    return <p className="notice">불러오는 중…</p>;
  }

  const deals = data.deals;
  if (deals.length === 0) return <p className="notice">완료된 거래가 없습니다.</p>;

  return (
    <div className="deal-list">
      {deals.map((d) => (
        <div key={d.room_id} className="deal-card">
          <div className="deal-top">
            <div className="deal-thumb">
              {d.post.thumbnail
                ? <img src={API + d.post.thumbnail} alt="" />
                : <span className="card__empty">사진</span>}
            </div>
            <div className="deal-info">
              <p className="deal-role">
                <span className={d.my_role === "buyer" ? "role role--buy" : "role role--sell"}>
                  {d.my_role === "buyer" ? "구매" : "판매"}
                </span>
                <span className="deal-when">{timeAgo(d.done_at)}</span>
              </p>
              <p className="deal-title">{d.post.title}</p>
              <p className="deal-price">{formatPrice(d.post.price)}</p>
              <p className="deal-partner" onClick={() => onProfile(d.partner_id)}>
                {d.partner_nickname} 님과 거래 →
              </p>
            </div>
          </div>

          {/* 내가 쓴 후기 */}
          <div className="deal-review">
            <p className="deal-review__head">내가 남긴 후기</p>
            {d.my_review ? (
              <>
                <p className="review-card__top">
                  <span className="review-card__stars">
                    {"★".repeat(d.my_review.rating)}{"☆".repeat(5 - d.my_review.rating)}
                  </span>
                  <span className="review-card__label">{d.my_review.rating_label}</span>
                </p>
                {d.my_review.tags.length > 0 && (
                  <div className="tag-row">
                    {d.my_review.tags.map((t) => <span key={t} className="chip">{t}</span>)}
                  </div>
                )}
                {d.my_review.comment && (
                  <p className="review-card__text">{d.my_review.comment}</p>
                )}
              </>
            ) : (
              <p className="deal-none">
                아직 안 남겼어요.{" "}
                <span className="link" onClick={() => onWriteReview(d.room_id)}>
                  후기 남기러 가기
                </span>
              </p>
            )}
          </div>

          {/* 상대가 쓴 후기 */}
          <div className="deal-review">
            <p className="deal-review__head">{d.partner_nickname} 님이 남긴 후기</p>
            {d.their_review ? (
              <>
                <p className="review-card__top">
                  <span className="review-card__stars">
                    {"★".repeat(d.their_review.rating)}{"☆".repeat(5 - d.their_review.rating)}
                  </span>
                  <span className="review-card__label">{d.their_review.rating_label}</span>
                </p>
                {d.their_review.tags.length > 0 && (
                  <div className="tag-row">
                    {d.their_review.tags.map((t) => <span key={t} className="chip">{t}</span>)}
                  </div>
                )}
                {d.their_review.comment && (
                  <p className="review-card__text">{d.their_review.comment}</p>
                )}
              </>
            ) : d.their_review_waiting ? (
              <p className="deal-none">
                후기를 남겼어요. <b>내 후기를 작성하면 볼 수 있어요.</b>
              </p>
            ) : (
              <p className="deal-none">아직 남기지 않았어요.</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ===============================================================
// 마이페이지 — 받은 후기 탭
// ===============================================================
function MyReviews({ data, loading, token, onWriteReview }) {
  const [side, setSide] = useState("received");   // 받은 것 / 쓴 것
  // 아직 후기를 안 남긴 거래 목록
  const [pending, setPending] = useState([]);

  useEffect(() => {
    callApi("/me/pending-reviews", { headers: auth(token) })
      .then((d) => setPending(d.pending))
      .catch(() => setPending([]));
  }, [token]);

  // data가 아직 없거나 모양이 다를 수 있으니 항상 확인하고 씀
  if (loading || !data?.received) {
    return <p className="notice">불러오는 중…</p>;
  }

  const list = (side === "received" ? data.received : data.written) || [];

  return (
    <div className="info-box">
      {/* 받은 후기 요약 */}
      <div className="myrev-head">
        <span className="rate-num">{data.average_rating ?? "-"}</span>
        <span className="rate-stars">
          {data.average_rating
            ? "★".repeat(Math.round(data.average_rating)) +
              "☆".repeat(5 - Math.round(data.average_rating))
            : "☆☆☆☆☆"}
        </span>
        <span className="prof-label">받은 후기 {data.received_count}개</span>
      </div>

      {data.hidden_count > 0 && (
        <p className="myrev-hidden">
          아직 못 본 후기 {data.hidden_count}개 — 내 후기를 남기면 함께 공개돼요
        </p>
      )}

      {/* 누구에게 안 썼는지 이름과 물건까지 보여줌.
          숫자만 있으면 "누구였더라"를 알 수가 없음 */}
      {pending.length > 0 && (
        <div className="pending-box">
          <p className="pending-box__head">
            후기를 기다리는 거래 {pending.length}건
          </p>
          {pending.map((x) => (
            <div key={x.room_id} className="pending-item">
              <div className="pending-item__body">
                <p className="pending-item__who">{x.partner_nickname} 님과의 거래</p>
                <p className="pending-item__post">
                  {x.post_title} · {timeAgo(x.done_at)}
                </p>
              </div>
              <button className="btn-small" onClick={() => onWriteReview(x.room_id)}>
                후기 쓰기
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 받은 것 / 쓴 것 전환 */}
      <div className="side-row">
        <span className={side === "received" ? "side side--on" : "side"}
          onClick={() => setSide("received")}>받은 후기</span>
        <span className={side === "written" ? "side side--on" : "side"}
          onClick={() => setSide("written")}>내가 쓴 후기</span>
      </div>

      {list.length === 0 ? (
        <p className="notice">
          {side === "received" ? "받은 후기가 없습니다." : "작성한 후기가 없습니다."}
        </p>
      ) : (
        list.map((r) => (
          <div key={r.id} className="review-card">
            <p className="review-card__top">
              <span className="review-card__stars">
                {"★".repeat(r.rating)}{"☆".repeat(5 - r.rating)}
              </span>
              <span className="review-card__label">{r.rating_label}</span>
              <span className="review-card__who">
                {side === "received" ? r.reviewer_nickname : r.partner_nickname}
              </span>
            </p>
            {r.post_title && <p className="review-card__post">{r.post_title}</p>}
            {r.tags.length > 0 && (
              <div className="tag-row">
                {r.tags.map((t) => <span key={t} className="chip">{t}</span>)}
              </div>
            )}
            {r.comment && <p className="review-card__text">{r.comment}</p>}
          </div>
        ))
      )}
    </div>
  );
}

// ===============================================================
// 마이페이지
// tab / setTab을 부모에게서 받음 — 상세를 다녀와도 탭이 유지되게
// ===============================================================
export default function MyPage({ me, token, regionTree, cooldownHours, tab, setTab,
                  onSelect, onHome, onWrite, onChat, onLogout, onMeChanged,
                  onDeleted, onProfile, onOpenChat, onWriteReview }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);   // 끌올 결과 안내

  // 탭이 바뀔 때마다 그 탭에 맞는 것을 불러옴
  useEffect(() => {
    if (tab === "info") { setLoading(false); return; }

    setLoading(true);
    // 탭마다 자료의 모양이 다름(목록 탭은 배열, 거래·후기 탭은 객체).
    // 이전 탭의 자료가 남아 있으면 엉뚱한 모양을 읽어서 터지므로 먼저 비움
    setItems(null);

    const paths = {
      favorites: "/me/favorites",
      posts: "/me/posts",
      deals: "/me/deals",
      reviews: "/me/reviews",
    };
    callApi(paths[tab], { headers: auth(token) })
      .then((data) => { setItems(data); setLoading(false); })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, [tab, token]);

  async function reloadMyPosts() {
    const data = await callApi("/me/posts", { headers: auth(token) });
    setItems(data);
  }

  // 찜·판매 탭은 배열, 거래·후기 탭은 객체로 옴.
  // 탭이 막 바뀐 순간엔 이전 자료가 남아 있어서 모양을 확인하고 씀
  const listItems = Array.isArray(items) ? items : [];

  // 판매내역에서 상태를 바꿀 때
  async function changeStatus(postId, status) {
    setMsg(null);
    try {
      await callApi("/posts/" + postId + "/status", jsonPatch(token, { status }));
      await reloadMyPosts();
      // 거래완료 건수가 바뀌었을 수 있으니 내 정보도 갱신
      const meData = await callApi("/me", { headers: auth(token) });
      onMeChanged(meData);
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  }

  // 끌어올리기
  async function bump(postId) {
    setMsg(null);
    try {
      await callApi("/posts/" + postId + "/bump", {
        method: "POST",
        headers: auth(token),
      });
      await reloadMyPosts();
      setMsg({ ok: true, text: "맨 위로 끌어올렸습니다" });
    } catch (err) {
      // 쿨다운이면 "N시간 뒤에..." 메시지가 그대로 나옴
      setMsg({ ok: false, text: err.message });
    }
  }

  return (
    <div className="page page--my">
      <header className="topbar">
        {/* 로고를 누르면 홈으로 */}
        <span className="topbar__brand" onClick={onHome}>당근</span>
        <span className="topbar__title">마이페이지</span>
        <nav className="topbar__nav">
          <span onClick={onHome}>홈</span>
          <span onClick={onWrite}>판매등록</span>
          <span onClick={onChat}>채팅</span>
        </nav>
        <span className="topbar__user">{me.nickname}</span>
        <span className="topbar__logout" onClick={onLogout}>로그아웃</span>
      </header>

      <div className="mytabs">
        <span className={tab === "favorites" ? "mytab mytab--on" : "mytab"}
          onClick={() => setTab("favorites")}>찜</span>
        <span className={tab === "posts" ? "mytab mytab--on" : "mytab"}
          onClick={() => setTab("posts")}>판매</span>
        <span className={tab === "deals" ? "mytab mytab--on" : "mytab"}
          onClick={() => setTab("deals")}>거래</span>
        <span className={tab === "reviews" ? "mytab mytab--on" : "mytab"}
          onClick={() => setTab("reviews")}>후기</span>
        <span className={tab === "info" ? "mytab mytab--on" : "mytab"}
          onClick={() => setTab("info")}>내 정보</span>
      </div>

      {msg && (
        <p className={msg.ok ? "msg-ok" : "msg-error"} style={{ padding: "0 16px" }}>
          {msg.text}
        </p>
      )}

      {tab === "info" ? (
        <MyInfo me={me} token={token} regionTree={regionTree}
          onMeChanged={onMeChanged} onDeleted={onDeleted} onProfile={onProfile} />
      ) : tab === "deals" ? (
        <MyDeals data={items} loading={loading} onOpenChat={onOpenChat}
          onWriteReview={onWriteReview} onProfile={onProfile} />
      ) : tab === "reviews" ? (
        <MyReviews data={items} loading={loading} token={token}
          onWriteReview={onWriteReview} />
      ) : (
        <main className="grid">
          {/* 이 탭은 배열을 기대함. 다른 탭 자료가 남아 있으면 빈 배열로 취급 */}
          {loading && <p className="notice">불러오는 중…</p>}
          {error && <p className="notice">{error}</p>}
          {!loading && !error && listItems.length === 0 && (
            <p className="notice">
              {tab === "favorites" ? "찜한 매물이 없습니다." : "올린 매물이 없습니다."}
            </p>
          )}

          {listItems.map((post) => (
            <div key={post.id}>
              <PostCard post={post} onClick={() => onSelect(post.id)} />

              {/* 판매 내역 탭에서만 상태 변경 + 끌올이 붙음 */}
              {tab === "posts" && (() => {
                // 남은 시간이 있으면 아직 못 끌올함
                const left = bumpLeft(post.bumped_at, cooldownHours);
                const done = post.status === "거래완료";
                return (
                  <div className="status-row">
                    <select className="select-sm" value={post.status}
                      onChange={(e) => changeStatus(post.id, e.target.value)}>
                      {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>

                    {/* 거래완료거나 대기 중이면 버튼을 잠금 */}
                    <button className="btn-small" onClick={() => bump(post.id)}
                      disabled={done || !!left}>
                      끌올
                    </button>

                    {done ? (
                      <span className="cooldown-text">거래완료</span>
                    ) : left ? (
                      <span className="cooldown-text">{left} 가능</span>
                    ) : (
                      <span className="cooldown-text">지금 가능</span>
                    )}
                  </div>
                );
              })()}
            </div>
          ))}
        </main>
      )}

      <TabBar active="my" onHome={onHome} onWrite={onWrite}
        onChat={onChat} onMy={() => {}} />
    </div>
  );
}