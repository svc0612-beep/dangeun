// 여기저기서 쓰는 자잘한 도구들
//
// 값을 보기 좋게 바꾸거나(가격·시간), 글자를 쪼개는 함수들.
// 화면을 그리지 않는 순수한 계산만 모아둠

// 엔터키를 누르면 fn을 실행하는 핸들러
export function onEnter(fn) {
  return (e) => {
    // 설명 칸(textarea)에서는 엔터가 줄바꿈이어야 하니 제외
    if (e.key === "Enter" && e.target.tagName !== "TEXTAREA") fn();
  };
}

export function formatPrice(price) {
  if (price === 0) return "나눔";
  return price.toLocaleString() + "원";
}

// 서버가 보내는 시각은 UTC인데 시간대 표시가 없음.
// 그냥 두면 브라우저가 한국 시간으로 착각해서 9시간이 어긋남.
// Z를 붙여 "이건 UTC다"라고 알려줘야 함
export function parseUtc(isoString) {
  if (!isoString) return null;
  // 이미 Z나 +09:00 같은 표시가 있으면 그대로 씀
  const hasZone = /Z|[+-]\d{2}:\d{2}$/.test(isoString);
  return new Date(hasZone ? isoString : isoString + "Z");
}

export function timeAgo(isoString) {
  const then = parseUtc(isoString);
  if (!then) return "";
  const diffSec = Math.floor((new Date() - then) / 1000);
  if (diffSec < 60) return "방금 전";
  if (diffSec < 3600) return Math.floor(diffSec / 60) + "분 전";
  if (diffSec < 86400) return Math.floor(diffSec / 3600) + "시간 전";
  return Math.floor(diffSec / 86400) + "일 전";
}

// 채팅 말풍선 옆에 붙일 시각. "오후 3:07" 형태
export function formatTime(isoString) {
  const d = parseUtc(isoString);
  if (!d) return "";
  return d.toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" });
}

// 날짜가 바뀌면 대화 사이에 넣을 구분선 글자
export function formatDay(isoString) {
  const d = parseUtc(isoString);
  if (!d) return "";
  return d.toLocaleDateString("ko-KR", { month: "long", day: "numeric", weekday: "short" });
}

// 끌올까지 남은 시간을 문자로. 지금 가능하면 null
export function bumpLeft(bumpedAt, cooldownHours) {
  const last = parseUtc(bumpedAt);
  if (!last || !cooldownHours) return null;

  const nextOk = last.getTime() + cooldownHours * 3600 * 1000;
  const leftMs = nextOk - Date.now();
  if (leftMs <= 0) return null;   // 이제 끌올 가능

  const hours = Math.floor(leftMs / 3600000);
  const mins = Math.floor((leftMs % 3600000) / 60000);
  return hours > 0 ? `${hours}시간 뒤` : `${mins}분 뒤`;
}

// "서울 강남구" → { sido: "서울", gu: "강남구" }
export function splitRegion(region) {
  const [sido = "", gu = ""] = (region || "").split(" ");
  return { sido, gu };
}

// ===============================================================
// 매물 등록 화면
// ===============================================================
export const CATEGORIES = [
  "디지털기기", "생활가전", "가구인테리어", "생활/주방",
  "유아동", "의류", "도서", "스포츠/레저", "기타",
];

// ===============================================================
// 마이페이지 — 내 정보 탭
// ===============================================================
export const STATUS_OPTIONS = ["판매중", "예약중", "거래완료"];
