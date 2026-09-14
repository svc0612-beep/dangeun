// 새 메시지 알림 창
//
// 화면 위쪽에 잠깐 떴다가 사라짐. 누르면 그 채팅방으로 바로 이동.
// 채팅방을 이미 열고 있을 때는 띄우지 않음 (App.jsx 에서 걸러냄)

import { useEffect } from "react";
import { MessageCircle, X } from "lucide-react";

export default function Toast({ item, onOpen, onClose }) {
  // 로그인했을 때 뜨는 "그동안 온 메시지" 알림은 조금 더 오래 둠
  const isSummary = item.kind === "unread";

  useEffect(() => {
    const timer = setTimeout(onClose, isSummary ? 9000 : 6000);
    return () => clearTimeout(timer);
  }, [item, onClose, isSummary]);

  return (
    <div className="toast" onClick={onOpen}>
      <MessageCircle size={18} strokeWidth={2} />

      <div className="toast__body">
        <p className="toast__top">
          <span className="toast__who">
            {isSummary
              ? `안 읽은 메시지 ${item.count}건`
              : item.sender_nickname}
          </span>
          <span className="toast__post">{item.post_title}</span>
        </p>
        <p className="toast__msg">
          {isSummary
            ? `${item.sender_nickname} · ${item.preview}`
            : item.preview}
        </p>
      </div>

      {/* 닫기를 눌렀을 때 채팅방으로 가지 않게 이벤트를 멈춤 */}
      <X size={16} strokeWidth={2} className="toast__x"
        onClick={(e) => { e.stopPropagation(); onClose(); }} />
    </div>
  );
}
