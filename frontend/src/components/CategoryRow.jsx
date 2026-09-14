// 카테고리 아이콘 줄
//
// 글자 칩보다 아이콘이 있으면 훑어보기가 빠름.
// 카테고리 이름은 서버(/config)에서 오고, 아이콘은 여기서 짝지어줌

import {
  LayoutGrid, Monitor, WashingMachine, Sofa, CookingPot,
  Baby, Shirt, BookOpen, Bike, Package,
} from "lucide-react";

// 카테고리 이름 → 아이콘.
// 서버가 목록을 바꿔도 여기 없는 이름은 기본 아이콘으로 나옴
const ICONS = {
  "디지털기기": Monitor,
  "생활가전": WashingMachine,
  "가구인테리어": Sofa,
  "생활/주방": CookingPot,
  "유아동": Baby,
  "의류": Shirt,
  "도서": BookOpen,
  "스포츠/레저": Bike,
  "기타": Package,
};

export default function CategoryRow({ categories, value, onPick }) {
  // 맨 앞에 "전체" 를 끼워넣음
  const items = [{ name: "", label: "전체", Icon: LayoutGrid }].concat(
    categories.map((c) => ({ name: c, label: c, Icon: ICONS[c] || Package }))
  );

  return (
    <div className="catbar">
      {items.map(({ name, label, Icon }) => (
        <div
          key={label}
          className={value === name ? "catbar__item catbar__item--on" : "catbar__item"}
          onClick={() => onPick(name)}
        >
          <span className="catbar__circle">
            <Icon size={22} strokeWidth={1.8} />
          </span>
          <span className="catbar__name">{label}</span>
        </div>
      ))}
    </div>
  );
}
