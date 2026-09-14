// 채팅방
// WebSocket 으로 실시간 송수신. 지난 대화는 일반 API 로 한 번 받아옴

import { useState, useEffect, useRef } from "react";
import { ArrowLeft, Send, ImagePlus, Flag } from "lucide-react";

import { API, WS_BASE, callApi, jsonPost, jsonPatch, auth } from "../api";
import { formatPrice, formatTime, formatDay } from "../utils";
import DealModal from "../components/DealModal";
import ReportModal from "../components/ReportModal";

// ===============================================================
// 채팅방
// WebSocket으로 실시간 송수신. 지난 대화는 일반 API로 한 번 받아옴
// ===============================================================
export default function ChatRoom({ roomId, me, token, onBack, onHome, onReview, onProfile, onPost }) {
  const [room, setRoom] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  // 거래가 막 확정됐을 때 띄우는 안내창
  const [showDeal, setShowDeal] = useState(false);
  // 신고 창. 사기는 대부분 채팅에서 일어나므로 여기에도 둠
  const [reporting, setReporting] = useState(false);
  // 상황에 맞는 추천 문구
  const [tips, setTips] = useState([]);

  // useRef = 화면을 다시 그리지 않으면서 값을 들고 있는 상자.
  // 연결 객체와 스크롤 위치처럼 "화면과 무관한 것"을 담음
  const wsRef = useRef(null);
  const bottomRef = useRef(null);

  // 1) 지난 대화 불러오기
  useEffect(() => {
    callApi("/chats/" + roomId, { headers: auth(token) })
      .then((data) => {
        setRoom(data);
        setMessages(data.messages);
        // 거래가 확정됐는데 아직 후기를 안 썼으면 들어올 때 안내.
        // 먼저 버튼을 누른 쪽은 확정되는 순간 화면에 없어서 못 보기 때문
        if (data.can_review) setShowDeal(true);
      })
      .catch((err) => setError(err.message));
  }, [roomId, token]);

  // 2) WebSocket 연결
  useEffect(() => {
    // http:// → ws:// 로 바꿔야 함. WebSocket은 다른 규약이라
    const wsUrl =
      WS_BASE + "/ws/chats/" + roomId + "?token=" + encodeURIComponent(token);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);

      // 거래 상태가 바뀌었다는 신호. 방 정보를 다시 받아옴.
      // 이게 없으면 버튼을 누른 사람만 확정된 걸 보고 상대는 모름
      if (msg.type === "room_changed") {
        callApi("/chats/" + roomId, { headers: auth(token) })
          .then((data) => {
            setRoom(data);
            if (data.can_review) setShowDeal(true);
          })
          .catch(() => {});
        return;
      }

      // 같은 메시지가 두 번 들어오지 않게 id로 확인
      setMessages((prev) =>
        prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]
      );
    };

    // 화면을 떠날 때 연결을 닫음. 안 닫으면 연결이 계속 쌓임
    return () => ws.close();
  }, [roomId, token]);

  // 3) 상황에 맞는 추천 문구 받아오기.
  // 메시지 수나 거래 상태가 바뀌면 단계가 달라져서 다시 물어봄
  useEffect(() => {
    callApi("/chats/" + roomId + "/suggestions", { headers: auth(token) })
      .then((d) => setTips(d.suggestions))
      .catch(() => setTips([]));
  }, [roomId, token, messages.length, room?.buyer_decided, room?.seller_confirmed]);

  // 4) 새 메시지가 오면 맨 아래로 스크롤
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 별점만 눌러 바로 후기 남기기. 태그·코멘트 없이 저장됨
  async function quickReview(rating) {
    try {
      await callApi("/chats/" + roomId + "/review", {
        ...jsonPost({ rating, tags: [], comment: null }),
        headers: { "Content-Type": "application/json", ...auth(token) },
      });
      setShowDeal(false);
      await refresh();
    } catch (err) {
      setError(err.message);
      setShowDeal(false);
    }
  }

  // 사진 보내기. 파일이라 WebSocket이 아니라 일반 업로드로 보냄
  async function sendImage(e) {
    const file = e.target.files?.[0];
    e.target.value = "";          // 같은 파일을 다시 고를 수 있게 비움
    if (!file) return;

    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const msg = await callApi("/chats/" + roomId + "/images", {
        method: "POST",
        headers: auth(token),     // Content-Type은 브라우저가 알아서 붙임
        body: form,
      });
      // WebSocket으로도 오지만, 연결이 없을 때를 대비해 직접 넣음
      setMessages((prev) =>
        prev.some((x) => x.id === msg.id) ? prev : [...prev, msg]
      );
    } catch (err) {
      setError(err.message);
    }
  }

  function send() {
    const text = input.trim();
    if (!text) return;

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ content: text }));
      setInput("");
    } else {
      // 연결이 끊겼으면 일반 API로 보냄 (대비책)
      callApi("/chats/" + roomId + "/messages", {
        ...jsonPost({ content: text }),
        headers: { "Content-Type": "application/json", ...auth(token) },
      })
        .then((msg) => { setMessages((prev) => [...prev, msg]); setInput(""); })
        .catch((err) => setError(err.message));
    }
  }

  // 거래 확정 / 취소는 일반 API. 결과를 다시 받아 화면을 맞춤
  async function refresh() {
    const data = await callApi("/chats/" + roomId, { headers: auth(token) });
    setRoom(data);
    setMessages(data.messages);
  }

  async function decide() {
    setBusy(true);
    setError(null);
    try {
      const data = await callApi("/chats/" + roomId + "/decide", {
        method: "POST", headers: auth(token),
      });
      await refresh();
      // 양쪽이 다 눌려 확정된 순간에만 안내창을 띄움
      if (data.buyer_decided && data.seller_confirmed) setShowDeal(true);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function cancel() {
    const reason = window.prompt("취소 사유를 적어주세요 (선택)");
    if (reason === null) return;   // 창을 닫으면 취소

    setBusy(true);
    setError(null);
    try {
      await callApi("/chats/" + roomId + "/cancel", {
        ...jsonPost({ reason: reason || null }),
        headers: { "Content-Type": "application/json", ...auth(token) },
      });
      await refresh();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  if (error && !room) {
    return (
      <div className="page">
        <p className="notice">{error}</p>
        <p className="notice"><span className="back-btn" onClick={onBack}>← 목록으로</span></p>
      </div>
    );
  }
  if (!room) return <div className="page"><p className="notice">불러오는 중…</p></div>;

  const isBuyer = room.my_role === "buyer";
  const iDecided = isBuyer ? room.buyer_decided : room.seller_confirmed;
  const done = room.buyer_decided && room.seller_confirmed;
  const p = room.partner;

  return (
    <div className="page page--chat">
      {reporting && (
        <ReportModal
          targetType="user"
          targetId={room.partner_id}
          targetName={room.partner.nickname + " 님"}
          token={token}
          onClose={() => setReporting(false)}
        />
      )}

      {showDeal && (
        <DealModal
          room={room}
          onReview={() => { setShowDeal(false); onReview(roomId); }}
          onClose={() => setShowDeal(false)}
          onProfile={() => { setShowDeal(false); onProfile(room.partner_id); }}
        />
      )}

      <header className="chat-head">
        <ArrowLeft size={20} strokeWidth={2} onClick={onBack} className="back-btn" />
        <span className="chat-head__name chat-head__link"
          onClick={() => onProfile(room.partner_id)}>{p.nickname}</span>
        <span className="chat-head__meta">
          {p.manner_temp}°C · 판매 {p.completed_deals} · 구매 {p.completed_purchases}
          {p.cancel_count > 0 && ` · 취소 ${p.cancel_count}`}
        </span>
        {/* 대화 중에 이상하면 바로 신고할 수 있게 */}
        <span className="chat-head__report" onClick={() => setReporting(true)}>
          <Flag size={14} strokeWidth={2} />
          신고
        </span>
        <span className="chat-head__exit" onClick={onHome}>홈</span>
      </header>

      {/* 매물 요약. 여러 명과 대화할 때 무슨 물건인지 헷갈리지 않게 항상 붙어 있음 */}
      <div className="chat-post" onClick={() => onPost(room.post.id)}>
        <div className="chat-post__thumb">
          {room.post.thumbnail
            ? <img src={API + room.post.thumbnail} alt="" />
            : <span className="card__empty">사진</span>}
        </div>
        <div className="chat-post__body">
          <p className="chat-post__title">{room.post.title}</p>
          <p className="chat-post__price">{formatPrice(room.post.price)}</p>
        </div>
        <span className={room.post.status === "거래완료"
          ? "badge badge--done" : "badge"}>{room.post.status}</span>
      </div>

      <main className="chat-body">
        {messages.map((m, i) => {
          if (m.kind === "system") {
            // 시스템 안내는 누가 한 말이 아니라서 가운데 정렬
            return <div key={m.id} className="chat-system">{m.content}</div>;
          }

          const mine = m.sender_id === me.id;
          const prev = messages[i - 1];

          // 날짜가 바뀌면 구분선을 넣음
          const newDay = !prev || formatDay(prev.created_at) !== formatDay(m.created_at);
          // 같은 사람이 이어서 보내면 이름을 다시 안 씀
          const showName = !mine && (newDay || prev?.sender_id !== m.sender_id
            || prev?.kind === "system");

          return (
            <div key={m.id}>
              {newDay && <div className="chat-day">{formatDay(m.created_at)}</div>}

              {showName && <p className="bubble-name">{room.partner.nickname}</p>}

              {/* 말풍선과 시각을 한 줄에. 내 말이면 시각이 왼쪽에 옴 */}
              <div className={mine ? "bubble-row bubble-row--mine" : "bubble-row"}>
                {m.kind === "image" ? (
                  <img className="bubble-img" src={API + m.image_url} alt=""
                    onClick={() => window.open(API + m.image_url, "_blank")} />
                ) : (
                  <div className={mine ? "bubble bubble--mine" : "bubble"}>
                    {m.content}
                  </div>
                )}
                <span className="bubble-time">{formatTime(m.created_at)}</span>
              </div>
            </div>
          );
        })}
        {/* 스크롤을 맨 아래로 보내기 위한 표식 */}
        <div ref={bottomRef} />
      </main>

      {error && <p className="msg-error" style={{ padding: "0 16px" }}>{error}</p>}

      {/* 추천 문구. 누르면 입력창에 채워지고, 고쳐서 보낼 수 있음 */}
      {tips.length > 0 && (
        <div className="tip-row">
          {tips.map((t) => (
            <span key={t} className="tip" onClick={() => setInput(t)}>{t}</span>
          ))}
        </div>
      )}

      <div className="chat-bar">
        {/* 사진 버튼. 진짜 파일 선택칸은 숨기고 아이콘을 라벨로 씀 */}
        <label className="chat-photo">
          <ImagePlus size={20} strokeWidth={2} />
          <input type="file" accept="image/*" onChange={sendImage}
            style={{ display: "none" }} />
        </label>

        <input
          className="chat-input"
          placeholder="메시지를 입력하세요"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button className="chat-send" onClick={send}>
          <Send size={18} strokeWidth={2} />
        </button>

        {/* 거래 버튼. 상태에 따라 글자와 동작이 달라짐 */}
        {/* 거래가 확정되면 후기 버튼이 제일 앞으로 */}
        {room.can_review ? (
          <button className="btn-buy" onClick={() => onReview(roomId)}>
            후기 남기기
          </button>
        ) : done ? (
          <button className="btn-line" onClick={cancel} disabled={busy || isBuyer}>
            {room.my_review_done ? "후기 완료" : isBuyer ? "거래완료" : "거래 취소"}
          </button>
        ) : iDecided ? (
          <button className="btn-line" onClick={cancel} disabled={busy}>
            취소
          </button>
        ) : (
          <button className="btn-buy" onClick={decide} disabled={busy}>
            {isBuyer ? "구매 결정" : "판매 확인"}
          </button>
        )}
      </div>
    </div>
  );
}
