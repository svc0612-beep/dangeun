// 여러 화면에서 공통으로 쓰는 조각들
//
// 입력칸 하나, 지역 고르는 드롭다운 두 개, 하단 탭바

import { Home, PlusSquare, MessageCircle, User } from "lucide-react";

import { splitRegion } from "../utils";

// 입력칸 하나. 라벨 + 인풋 묶음
export function Field({ label, ...rest }) {
  return (
    <div className="field">
      <label className="label">{label}</label>
      <input className="input" {...rest} />
    </div>
  );
}

// ---------------------------------------------------------------
// 지역 고르는 드롭다운 두 개 (시/도 → 시·군·구)
// value는 "서울 강남구" 한 덩어리로 주고받음
// ---------------------------------------------------------------
export function RegionField({ label, value, onChange, regionTree }) {
  const { sido, gu } = splitRegion(value);
  const guList = regionTree[sido] || [];

  function pickSido(newSido) {
    // 시/도를 바꾸면 시·군·구는 초기화. 이전 구가 남아 있으면 안 맞음
    onChange(newSido ? newSido + " " : "");
  }

  function pickGu(newGu) {
    onChange(newGu ? sido + " " + newGu : sido + " ");
  }

  return (
    <div className="field">
      <label className="label">{label}</label>
      <div className="input-row">
        <select className="input" value={sido} onChange={(e) => pickSido(e.target.value)}>
          <option value="">시/도</option>
          {Object.keys(regionTree).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        {/* 시/도를 안 골랐으면 두 번째 칸은 잠금 */}
        <select className="input" value={gu} disabled={!sido}
          onChange={(e) => pickGu(e.target.value)}>
          <option value="">시/군/구</option>
          {guList.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
      </div>
    </div>
  );
}

// 하단 탭바. 목록/마이페이지에서 같이 씀
export function TabBar({ active, onHome, onWrite, onChat, onMy }) {
  // size = 아이콘 크기, strokeWidth = 선 굵기
  const ico = { size: 22, strokeWidth: 1.8 };

  return (
    <nav className="tabbar">
      <span className={active === "home" ? "tab tab--on" : "tab"} onClick={onHome}>
        <Home {...ico} />
        홈
      </span>
      <span className="tab" onClick={onWrite}>
        <PlusSquare {...ico} />
        등록
      </span>
      <span className={active === "chat" ? "tab tab--on" : "tab"} onClick={onChat}>
        <MessageCircle {...ico} />
        채팅
      </span>
      <span className={active === "my" ? "tab tab--on" : "tab"} onClick={onMy}>
        <User {...ico} />
        마이
      </span>
    </nav>
  );
}