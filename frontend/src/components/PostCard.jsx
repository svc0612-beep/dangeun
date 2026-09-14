// 매물 카드 한 장
// 목록·찜목록·판매내역·검색결과에서 모두 같은 모양으로 씀

import { API } from "../api";
import { formatPrice, timeAgo } from "../utils";

// ===============================================================
// 매물 카드 (목록·찜목록·판매내역에서 공용)
// ===============================================================
export default function PostCard({ post, onClick }) {
  const firstImage = post.images?.[0];   // 0번이 대표 사진

  return (
    <div className="card" onClick={onClick}>
      <div className="card__thumb">
        {firstImage ? (
          <img className="card__img" src={API + firstImage.image_url} alt="" />
        ) : (
          <span className="card__empty">사진 없음</span>
        )}

        {/* 판매중이 아닐 때만 사진 위에 상태를 얹음 */}
        {post.status !== "판매중" && (
          <span className="card__status">{post.status}</span>
        )}
      </div>

      <div className="card__body">
        {/* 가격을 제목보다 위에, 굵게 — 중고거래에서 제일 먼저 보는 정보 */}
        <p className="card__price">{formatPrice(post.price)}</p>
        <p className="card__title">{post.title}</p>

        <div className="card__tags">
          <span className="chip">{post.category}</span>
          <span className="chip">{post.region}</span>
        </div>

        {/* 누가 올렸는지. 목록에서 판매자를 구분할 수 있어야 함 */}
        <p className="card__meta">
          {post.seller_nickname && (
            <span className="card__seller">{post.seller_nickname}</span>
          )}
          {timeAgo(post.created_at)} · 조회 {post.view_count}
        </p>
      </div>
    </div>
  );
}
