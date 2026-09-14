// 채팅 목록
// 어느 매물에 대한 대화인지, 마지막 대화가 언제였는지, 안 읽은 수

import { useState, useEffect } from "react";

import { API, callApi, auth } from "../api";
import { formatPrice, timeAgo } from "../utils";
import { TabBar } from "../components/ui";

// ===============================================================
// 채팅 목록 화면
// ===============================================================
export default function ChatList({ me, token, onOpen, onHome, onWrite, onMy, onLogout }) {
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    callApi("/me/chats", { headers: auth(token) })
      .then((data) => { setRooms(data); setLoading(false); })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, [token]);

  return (
    <div className="page page--my">
      <header className="topbar">
        <span className="topbar__brand" onClick={onHome}>당근</span>
        <span className="topbar__title">채팅</span>
        <nav className="topbar__nav">
          <span onClick={onHome}>홈</span>
          <span onClick={onWrite}>판매등록</span>
          <span onClick={onMy}>마이페이지</span>
        </nav>
        <span className="topbar__user">{me.nickname}</span>
        <span className="topbar__logout" onClick={onLogout}>로그아웃</span>
      </header>

      <main>
        {loading && <p className="notice">불러오는 중…</p>}
        {error && <p className="notice">{error}</p>}
        {!loading && !error && rooms.length === 0 && (
          <p className="notice">아직 대화가 없습니다.</p>
        )}

        {rooms.map((r) => (
          <div key={r.id} className="chat-row" onClick={() => onOpen(r.id)}>
            <div className="chat-row__thumb">
              {r.post.thumbnail
                ? <img src={API + r.post.thumbnail} alt="" />
                : <span className="card__empty">사진</span>}
            </div>

            <div className="chat-row__body">
              <p className="chat-row__top">
                <span className="chat-row__name">{r.partner.nickname}</span>
                <span className="chat-row__role">
                  {r.my_role === "buyer" ? "구매" : "판매"}
                </span>
                {/* 마지막 대화가 언제였는지. 새 채팅인지 옛 채팅인지 구분됨 */}
                <span className="chat-row__time">{timeAgo(r.last_message_at)}</span>
              </p>

              {/* 어느 매물에 대한 대화인지. 매물을 여러 개 올렸을 때 필수 */}
              <p className="chat-row__post">
                {r.post.title} · {formatPrice(r.post.price)}
                {r.post.status !== "판매중" && (
                  <span className="chat-row__st">{r.post.status}</span>
                )}
              </p>

              <p className="chat-row__last">{r.last_message || "대화를 시작해보세요"}</p>
            </div>

            {/* 안 읽은 메시지가 있으면 숫자 뱃지 */}
            {r.unread_count > 0 && (
              <span className="chat-row__unread">{r.unread_count}</span>
            )}
          </div>
        ))}
      </main>

      <TabBar active="chat" onHome={onHome} onWrite={onWrite}
        onChat={() => {}} onMy={onMy} />
    </div>
  );
}