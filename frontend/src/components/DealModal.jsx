// 거래가 확정된 순간 화면 가운데 뜨는 안내창
// 상단 고정 정보는 지나치기 쉬워서, 중요한 순간엔 눈앞에 띄움

import { useState } from "react";
import { Star } from "lucide-react";

import { formatPrice } from "../utils";

// 거래가 확정된 순간 화면 가운데 뜨는 안내창.
// 상단 고정 정보는 지나치기 쉬워서, 중요한 순간엔 눈앞에 띄움
export default function DealModal({ room, onReview, onClose, onProfile }) {
  const p = room.partner;
  return (
    <div className="modal-back" onClick={onClose}>
      {/* 안쪽을 눌렀을 때 창이 닫히지 않게 이벤트를 멈춤 */}
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <p className="modal-title">거래가 확정됐어요</p>
        <p className="modal-sub">{room.post.title} · {formatPrice(room.post.price)}</p>

        <div className="modal-card" onClick={onProfile}>
          <p className="modal-who">
            {p.nickname}
            <span className="modal-region">{p.region}</span>
          </p>
          <div className="prof-stats">
            <div className="prof-stat">
              <span className="prof-num" style={{ color: "var(--orange)" }}>
                {p.manner_temp}°C
              </span>
              <span className="prof-label">매너온도</span>
            </div>
            <div className="prof-stat">
              <span className="prof-num">{p.completed_deals}</span>
              <span className="prof-label">판매</span>
            </div>
            <div className="prof-stat">
              <span className="prof-num">{p.completed_purchases}</span>
              <span className="prof-label">구매</span>
            </div>
            <div className="prof-stat">
              <span className="prof-num">{p.cancel_count}</span>
              <span className="prof-label">취소</span>
            </div>
          </div>
          <p className="modal-more">눌러서 프로필·후기 보기</p>
        </div>

        {/* 판매자가 만날 곳을 적어둔 경우에만 */}
        {room.post.place_name && (
          <p className="modal-place">거래 장소 · {room.post.place_name}</p>
        )}

        <p className="modal-guide">
          물건을 주고받으셨나요? 후기는 거래를 마친 뒤에 남겨주세요.
        </p>

        <button className="btn-primary" onClick={onClose}>확인</button>
        <p className="link" style={{ marginTop: 12 }} onClick={onReview}>
          지금 후기 남기기
        </p>
      </div>
    </div>
  );
}
