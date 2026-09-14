// 매물 상세
// 사진 · 판매자 정보 · 위험 배너 · 찜 · 채팅하기 · 신고

import { useState, useEffect } from "react";
import { Heart, AlertTriangle, Flag } from "lucide-react";

import { API, callApi, jsonPost, auth } from "../api";
import ReportModal from "../components/ReportModal";
import { formatPrice, timeAgo } from "../utils";

// ===============================================================
// 매물 상세 화면
// ===============================================================
export default function PostDetail({ postId, me, token, onBack, onDeleted, onEdit, onChat, onProfile, onHome }) {
  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reporting, setReporting] = useState(false);   // 신고 창 열림
  const [busy, setBusy] = useState(false);

  // 찜 상태와 개수. 서버가 준 값으로 시작해서 누를 때마다 갱신됨
  const [liked, setLiked] = useState(false);
  const [likeCount, setLikeCount] = useState(0);

  useEffect(() => {
    setLoading(true);
    // 토큰을 같이 보내야 "내가 찜했는지"를 서버가 알려줄 수 있음
    callApi("/posts/" + postId, { headers: auth(token) })
      .then((data) => {
        setPost(data);
        setLiked(data.is_favorited);
        setLikeCount(data.favorite_count);
        setLoading(false);
      })
      .catch((err) => { setError(err.message); setLoading(false); });
  }, [postId, token]);

  async function toggleLike() {
    try {
      // 찜 상태에 따라 POST(찜하기) 또는 DELETE(취소)
      const data = await callApi("/posts/" + postId + "/favorite", {
        method: liked ? "DELETE" : "POST",
        headers: auth(token),
      });
      // 서버가 돌려준 값으로 갱신. 화면에서 혼자 계산하지 않음
      setLiked(data.is_favorited);
      setLikeCount(data.favorite_count);
    } catch (err) {
      setError(err.message);
    }
  }

  // 채팅방을 열고(없으면 만들고) 그 방으로 이동
  async function startChat() {
    setBusy(true);
    try {
      const data = await callApi("/posts/" + postId + "/chat", {
        method: "POST", headers: auth(token),
      });
      onChat(data.id);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }


  async function remove() {
    // confirm = 브라우저 기본 확인창. 취소를 누르면 false를 돌려줌
    if (!window.confirm("이 매물을 삭제할까요? 되돌릴 수 없습니다.")) return;

    setBusy(true);
    try {
      await callApi("/posts/" + postId, { method: "DELETE", headers: auth(token) });
      onDeleted();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  if (loading) return <div className="page"><p className="notice">불러오는 중…</p></div>;

  if (error && !post) {
    return (
      <div className="page">
        <p className="notice">불러오지 못했습니다: {error}</p>
        <p className="notice"><span className="back-btn" onClick={onBack}>← 목록으로</span></p>
      </div>
    );
  }

  // 내가 올린 매물인지. 이 값으로 하단 버튼이 달라짐
  const isMine = post.seller_id === me.id;

  return (
    <div className="page page--detail">
      {reporting && (
        <ReportModal
          targetType="post"
          targetId={post.id}
          targetName={post.title}
          token={token}
          onClose={() => setReporting(false)}
        />
      )}

      <header className="detail-header">
        <span className="back-btn" onClick={onBack}>← 뒤로</span>
        {/* 어느 화면에서든 처음으로 돌아갈 수 있게 */}
        <span className="head-home" onClick={onHome}>당근</span>
      </header>

      {/* 사진 여러 장을 가로로. 넘치면 옆으로 스크롤 */}
      <div className="photo-strip">
        {post.images.length > 0 ? (
          post.images.map((img) => (
            <img key={img.id} className="detail-img" src={API + img.image_url} alt="" />
          ))
        ) : (
          <div className="detail-noimg">사진 없음</div>
        )}
      </div>

      {/* 사기 예방 배너. level에 따라 색이 달라짐 */}
      {post.risk_flags?.length > 0 && (
        <div className="risk-box">
          {post.risk_flags.map((f) => (
            <div key={f.code} className={"risk risk--" + f.level}>
              <AlertTriangle size={15} strokeWidth={2} />
              <span>{f.message}</span>
            </div>
          ))}
        </div>
      )}

      <div className="seller-box">
        <div className="seller-top seller-top--link"
          onClick={() => onProfile(post.seller.id)}>
          <div>
            <p className="seller-name">{post.seller.nickname}</p>
            <p className="meta">{post.seller.region}</p>
          </div>
          <div style={{ textAlign: "right" }}>
            <p className="seller-temp">{post.seller.manner_temp}°C</p>
            <p className="meta-sm">매너온도</p>
          </div>
        </div>

        {/* 두 숫자를 비율이 아니라 나란히 */}
        <p className="seller-stats">
          판매 {post.seller.total_posts}건 · 거래완료 {post.seller.completed_deals}건
        </p>

        {/* 자세한 후기는 프로필에서. 여기선 들어가는 길만 */}
        <p className="seller-more" onClick={() => onProfile(post.seller.id)}>
          프로필·거래 후기 보기 →
        </p>
      </div>

      <div className="detail-body">
        <h2 className="detail-title">{post.title}</h2>
        <p className="meta">
          {post.category} · {timeAgo(post.created_at)} ·{" "}
          <span className={post.status === "거래완료" ? "badge badge--done" : "badge"}>
            {post.status}
          </span>
        </p>
        <p className="detail-price">{formatPrice(post.price)}</p>
        {/* 판매자가 직접 쓴 글 */}
        <p className="writer-tag">판매자가 쓴 설명</p>
        <p className="detail-content">{post.content}</p>

        {/* AI가 사진을 보고 쓴 글. 누가 썼는지 분명히 구분해서 보여줌 —
            사는 사람이 무엇을 믿을지 스스로 판단할 수 있어야 하기 때문 */}
        {post.ai_description && (
          <div className="ai-box ai-box--detail">
            <p className="ai-box__head">
              <span className="ai-badge">AI</span>
              사진을 보고 쓴 설명
            </p>
            <p className="ai-box__text">{post.ai_description}</p>
            <p className="ai-box__note">
              사진에 보이는 것만 적은 것이라 실제와 다를 수 있어요.
              중요한 내용은 판매자에게 직접 물어보세요.
            </p>
          </div>
        )}

        {/* 판매자가 적어둔 만날 곳 */}
        {post.place_name && (
          <div className="place-row">거래 희망 장소 · {post.place_name}</div>
        )}

        <p className="meta">관심 {likeCount} · 조회 {post.view_count}</p>

        {/* 내 매물이 아닐 때만 신고 */}
        {post.seller_id !== me.id && (
          <p className="report-link" onClick={() => setReporting(true)}>
            <Flag size={13} strokeWidth={2} /> 이 매물 신고하기
          </p>
        )}
      </div>

      {error && <p className="msg-error" style={{ padding: "0 16px" }}>{error}</p>}

      <div className="bottom-bar">
        {isMine ? (
          // 내 매물이면 수정 / 삭제
          <>
            <span className="bar-price">{formatPrice(post.price)}</span>
            <button className="btn-line" onClick={() => onEdit(postId)}>수정</button>
            <button className="btn-danger" onClick={remove} disabled={busy}>
              {busy ? "삭제 중…" : "삭제"}
            </button>
          </>
        ) : (
          // 남의 매물이면 찜 + 구매 결정
          <>
            {/* fill="currentColor" = 찜했을 때 속을 색으로 채움 */}
            <span className={liked ? "heart heart--on" : "heart"} onClick={toggleLike}>
              <Heart size={24} strokeWidth={1.8} fill={liked ? "currentColor" : "none"} />
            </span>
            <span className="bar-price">{formatPrice(post.price)}</span>
            <button className="btn-buy" onClick={startChat} disabled={busy}>
              {busy ? "여는 중…" : "채팅하기"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
