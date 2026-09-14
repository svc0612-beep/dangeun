// 화면 아래에 붙는 안내 줄
//
// 이 앱이 무엇을 지켜주는지 네 가지로 요약.
// 기능이 아니라 안내라서 홈 화면 맨 아래에만 둠

import { ShieldCheck, MessageSquare, MapPin, Leaf } from "lucide-react";

const ITEMS = [
  { Icon: ShieldCheck,    title: "안전한 거래",  lines: ["신고·위험 감지로", "안심하고 거래하세요"] },
  { Icon: MessageSquare,  title: "편리한 소통",  lines: ["채팅으로 빠르고 편하게", "이야기 나눠요"] },
  { Icon: MapPin,         title: "직거래만 합니다",  lines: ["우리 동네에서 만나", "확인하고 주고받아요"] },
  { Icon: Leaf,           title: "환경을 지켜요", lines: ["쓸 만한 물건을 나누며", "지구를 더 깨끗하게"] },
];

export default function FeatureStrip() {
  return (
    <div className="feat">
      {ITEMS.map(({ Icon, title, lines }) => (
        <div key={title} className="feat__item">
          <span className="feat__circle">
            <Icon size={22} strokeWidth={1.8} />
          </span>
          <div>
            <p className="feat__title">{title}</p>
            {lines.map((l) => <p key={l} className="feat__line">{l}</p>)}
          </div>
        </div>
      ))}
    </div>
  );
}
