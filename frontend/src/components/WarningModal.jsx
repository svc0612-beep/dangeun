// 관리자가 보낸 경고
//
// 앱을 열 때 안 읽은 경고가 있으면 화면 가운데에 띄움.
// 확인을 눌러야 넘어감 — 흘려보내면 경고의 뜻이 없어짐

import { AlertTriangle } from "lucide-react";

export default function WarningModal({ item, onConfirm, rest }) {
  return (
    <div className="modal-back">
      <div className="modal modal--left warn-modal">
        <p className="warn-modal__head">
          <AlertTriangle size={19} strokeWidth={2} />
          관리자가 경고 메시지를 보냈습니다
        </p>

        <div className="warn-modal__body">
          <p className="warn-modal__label">사유</p>
          <p className="warn-modal__reason">{item.사유}</p>

          {item.내용 && (
            <>
              <p className="warn-modal__label">자세한 내용</p>
              <p className="warn-modal__detail">{item.내용}</p>
            </>
          )}

          <p className="warn-modal__when">
            {new Date(item.보낸때 + "Z").toLocaleString("ko-KR")}
          </p>
        </div>

        <p className="warn-modal__note">
          경고가 쌓이면 이용이 제한될 수 있습니다.
          이의가 있으면 고객센터로 문의해주세요.
        </p>

        {rest > 0 && (
          <p className="warn-modal__rest">확인하지 않은 경고가 {rest}건 더 있습니다</p>
        )}

        <button className="btn-primary" onClick={() => onConfirm(item.id)}>
          확인했습니다
        </button>
      </div>
    </div>
  );
}
