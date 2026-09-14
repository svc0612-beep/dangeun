// 신고 창
//
// 매물 상세와 채팅방에서 함께 씀.
// 사유를 고르고 자세한 내용을 적을 수 있게 함 —
// 사유만 받으면 나중에 조사할 때 근거가 부족함

import { useState, useEffect } from "react";
import { Flag, X } from "lucide-react";

import { callApi, jsonPost, auth } from "../api";

export default function ReportModal({ targetType, targetId, targetName, token, onClose }) {
  const [reasons, setReasons] = useState([]);
  const [reason, setReason] = useState("");
  const [detail, setDetail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    callApi("/report-reasons")
      .then((d) => setReasons(d.reasons))
      .catch(() => setReasons([]));
  }, []);

  async function submit() {
    if (busy) return;
    if (!reason) { setError("신고 사유를 골라주세요"); return; }

    setBusy(true);
    setError(null);
    try {
      await callApi("/reports", {
        ...jsonPost({
          target_type: targetType,
          target_id: targetId,
          reason,
          detail: detail.trim() || null,
        }),
        headers: { "Content-Type": "application/json", ...auth(token) },
      });
      setDone(true);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  // 접수된 뒤 화면
  if (done) {
    return (
      <div className="modal-back" onClick={onClose}>
        <div className="modal" onClick={(e) => e.stopPropagation()}>
          <p className="modal-title">신고가 접수됐어요</p>
          <p className="modal-guide">
            확인 후 조치하겠습니다. 처리 결과는 따로 알려드리지 않습니다.
          </p>
          <button className="btn-primary" onClick={onClose}>확인</button>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal modal--left" onClick={(e) => e.stopPropagation()}>
        <p className="report-head">
          <Flag size={17} strokeWidth={2} />
          신고하기
          <X size={18} strokeWidth={2} className="report-x" onClick={onClose} />
        </p>

        {targetName && <p className="report-target">{targetName}</p>}

        <p className="label">신고 사유</p>
        <div className="report-reasons">
          {reasons.map((r) => (
            <span key={r}
              className={reason === r ? "report-pick report-pick--on" : "report-pick"}
              onClick={() => setReason(r)}>
              {r}
            </span>
          ))}
        </div>

        <p className="label" style={{ marginTop: 16 }}>자세한 내용 (선택)</p>
        <textarea className="input textarea" rows={4} maxLength={500}
          placeholder="어떤 점이 문제였는지 적어주시면 확인에 도움이 됩니다"
          value={detail} onChange={(e) => setDetail(e.target.value)} />

        <p className="report-note">
          거짓 신고를 되풀이하면 이용이 제한될 수 있습니다.
        </p>

        {error && <p className="msg-error">{error}</p>}

        <button className="btn-primary" onClick={submit} disabled={busy}>
          {busy ? "접수 중…" : "신고하기"}
        </button>
      </div>
    </div>
  );
}
