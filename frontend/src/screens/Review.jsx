// 후기 작성
// 별점을 고르면 그 뜻이 문구로 바로 보임 — 3점이 무슨 뜻인지 헷갈리지 않게

import { useState, useEffect } from "react";
import { Star } from "lucide-react";

import { callApi, jsonPost, auth } from "../api";

// ===============================================================
// 후기 작성 화면
// 별점을 고르면 그 뜻이 문구로 바로 보임 — 3점이 무슨 뜻인지 헷갈리지 않게
// ===============================================================
export default function ReviewScreen({ roomId, token, onDone, onCancel, onHome }) {
  const [opts, setOpts] = useState(null);   // 서버에서 받은 별점 문구·태그 목록
  const [rating, setRating] = useState(0);
  const [tags, setTags] = useState([]);
  const [comment, setComment] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    callApi("/review-options")
      .then(setOpts)
      .catch((err) => setError(err.message));
  }, []);

  function toggleTag(t) {
    setTags(tags.includes(t) ? tags.filter((x) => x !== t) : [...tags, t]);
  }

  async function submit() {
    if (busy) return;
    if (!rating) { setError("별점을 골라주세요"); return; }

    setBusy(true);
    setError(null);
    try {
      const res = await callApi("/chats/" + roomId + "/review", {
        ...jsonPost({ rating, tags, comment: comment.trim() || null }),
        headers: { "Content-Type": "application/json", ...auth(token) },
      });
      alert(res.message);
      onDone();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  if (!opts) return <div className="page"><p className="notice">불러오는 중…</p></div>;

  // 별점이 낮으면 아쉬운 점 태그를, 높으면 좋은 점 태그를 보여줌
  const tagList = rating >= 4 ? opts.good_tags : rating >= 1 ? opts.bad_tags : [];

  return (
    <div className="page page--auth">
      <div className="form-head">
        <span className="back-btn" onClick={onCancel}>← 취소</span>
        <span className="head-home" onClick={onHome}>당근</span>
      </div>
      <h2 className="form-title">거래 후기</h2>
      <p className="guide">
        상대도 후기를 남기면 서로에게 공개됩니다.
        ({opts.open_days}일이 지나면 한쪽만 써도 공개돼요)
      </p>

      {/* 별점. 누르면 그 개수만큼 채워짐 */}
      <div className="stars">
        {[1, 2, 3, 4, 5].map((n) => (
          <Star
            key={n}
            size={34}
            strokeWidth={1.5}
            className={n <= rating ? "star star--on" : "star"}
            fill={n <= rating ? "currentColor" : "none"}
            onClick={() => { setRating(n); setTags([]); }}
          />
        ))}
      </div>
      <p className="star-label">
        {rating ? opts.rating_labels[rating] : "별점을 골라주세요"}
      </p>

      {/* 별점을 고르면 그에 맞는 태그가 나타남 */}
      {tagList.length > 0 && (
        <div className="field">
          <label className="label">
            {rating >= 4 ? "어떤 점이 좋았나요? (선택)" : "어떤 점이 아쉬웠나요? (선택)"}
          </label>
          <div className="tag-row">
            {tagList.map((t) => (
              <span key={t}
                className={tags.includes(t) ? "tag-pick tag-pick--on" : "tag-pick"}
                onClick={() => toggleTag(t)}>
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="field">
        <label className="label">한 줄 남기기 (선택)</label>
        <textarea className="input textarea" rows={3} maxLength={300}
          value={comment} onChange={(e) => setComment(e.target.value)} />
      </div>

      {error && <p className="msg-error">{error}</p>}

      <button className="btn-primary" onClick={submit} disabled={busy}>
        {busy ? "남기는 중…" : "후기 남기기"}
      </button>
    </div>
  );
}
