// 공개 프로필
// "이 사람과 거래해도 될까" 를 한 화면에서 판단할 수 있게
// 별점 분포 · 많이 받은 태그 · 후기 목록 · 판매 중인 물건

import { useState, useEffect } from "react";

import { API, callApi } from "../api";
import { formatPrice } from "../utils";

// ===============================================================
// 공개 프로필 — "이 사람과 거래해도 될까"를 한 화면에서 판단
// 매물 상세의 판매자 이름, 채팅방 상대 이름을 누르면 열림
// ===============================================================
export default function UserProfile({ userId, onBack, onSelectPost, onHome }) {
  const [p, setP] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    callApi("/users/" + userId + "/profile")
      .then(setP)
      .catch((err) => setError(err.message));
  }, [userId]);

  if (error) {
    return (
      <div className="page">
        <p className="notice">{error}</p>
        <p className="notice"><span className="back-btn" onClick={onBack}>← 뒤로</span></p>
      </div>
    );
  }
  if (!p) return <div className="page"><p className="notice">불러오는 중…</p></div>;

  // 막대 길이를 %로 만들기 위해 가장 많은 개수를 찾음
  const maxCount = Math.max(1, ...Object.values(p.rating_dist));

  return (
    <div className="page page--detail">
      <header className="detail-header">
        <span className="back-btn" onClick={onBack}>← 뒤로</span>
        {/* 어느 화면에서든 처음으로 돌아갈 수 있게 */}
        <span className="head-home" onClick={onHome}>당근</span>
      </header>

      {/* 요약 — 이름, 온도, 거래 이력 */}
      <div className="prof-head">
        <p className="prof-name">{p.nickname}</p>
        <p className="prof-region">{p.region}</p>

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
      </div>

      {/* 별점 요약 + 분포 막대 */}
      <div className="prof-block">
        <h3 className="prof-title">거래 후기</h3>

        {p.review_count === 0 ? (
          <p className="prof-empty">아직 받은 후기가 없습니다.</p>
        ) : (
          <>
            <div className="rate-summary">
              <div className="rate-big">
                <span className="rate-num">{p.average_rating}</span>
                <span className="rate-stars">
                  {"★".repeat(Math.round(p.average_rating))}
                  {"☆".repeat(5 - Math.round(p.average_rating))}
                </span>
                <span className="prof-label">후기 {p.review_count}개</span>
              </div>

              {/* 5점부터 1점까지 막대로 */}
              <div className="rate-bars">
                {[5, 4, 3, 2, 1].map((n) => (
                  <div key={n} className="rate-bar-row">
                    <span className="rate-bar-label">{n}점</span>
                    <div className="rate-bar">
                      <div className="rate-bar-fill"
                        style={{ width: (p.rating_dist[n] / maxCount) * 100 + "%" }} />
                    </div>
                    <span className="rate-bar-count">{p.rating_dist[n]}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 많이 받은 태그 */}
            {p.top_tags.length > 0 && (
              <div className="tag-row" style={{ marginTop: 14 }}>
                {p.top_tags.map((t) => (
                  <span key={t.tag} className="tag-count">
                    {t.tag} <b>{t.count}</b>
                  </span>
                ))}
              </div>
            )}

            {/* 후기 목록 */}
            <div className="review-list">
              {p.reviews.map((r) => (
                <div key={r.id} className="review-card">
                  <p className="review-card__top">
                    <span className="review-card__stars">
                      {"★".repeat(r.rating)}{"☆".repeat(5 - r.rating)}
                    </span>
                    <span className="review-card__label">{r.rating_label}</span>
                    <span className="review-card__who">{r.reviewer_nickname}</span>
                  </p>
                  {r.tags.length > 0 && (
                    <div className="tag-row">
                      {r.tags.map((t) => <span key={t} className="chip">{t}</span>)}
                    </div>
                  )}
                  {r.comment && <p className="review-card__text">{r.comment}</p>}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* 지금 팔고 있는 물건 */}
      {p.selling.length > 0 && (
        <div className="prof-block">
          <h3 className="prof-title">판매 중인 물건 {p.selling.length}개</h3>
          <div className="prof-sell">
            {p.selling.map((item) => (
              <div key={item.id} className="prof-sell-item"
                onClick={() => onSelectPost(item.id)}>
                <div className="prof-sell-thumb">
                  {item.thumbnail
                    ? <img src={API + item.thumbnail} alt="" />
                    : <span className="card__empty">사진</span>}
                </div>
                <p className="prof-sell-title">{item.title}</p>
                <p className="prof-sell-price">{formatPrice(item.price)}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
