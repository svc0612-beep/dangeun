// 서버와 이야기하는 곳
//
// 주소를 바꾸거나 오류 문구를 손볼 일이 있으면 이 파일만 보면 됨

// 서버 주소를 정하는 규칙
//
//   1) .env 에 VITE_API_URL 이 있으면 그걸 씀 (배포용)
//   2) 없으면 화면이 열린 주소를 그대로 따라감 (개발용)
//
// localhost 를 코드에 박아두면 폰으로 열었을 때 "폰 자신"을 가리켜서
// PC 서버를 못 찾음. 그래서 열린 주소의 호스트를 그대로 쓰는 것
export const API =
  import.meta.env.VITE_API_URL ||
  `${window.location.protocol}//${window.location.hostname}:8000`;

// WebSocket 주소. https 로 열렸으면 wss, http 면 ws 를 써야 함.
// 규약이 어긋나면 브라우저가 연결을 막아버림
export const WS_BASE = API.replace(/^http/, "ws");

// ===============================================================
// 공통 도구
// ===============================================================

// 서버에 요청하고 JSON을 돌려주는 함수.
// 실패하면 서버가 준 에러 메시지를 그대로 던져줌
export async function callApi(path, options = {}) {
  const res = await fetch(API + path, options);
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const d = data?.detail;
    let msg = "요청에 실패했습니다";
    if (typeof d === "string") {
      msg = d;
    } else if (d?.[0]) {
      // loc = ["body","title"] 형태라 마지막 값이 문제가 된 칸 이름
      const field = d[0].loc?.[d[0].loc.length - 1];
      msg = (field ? field + ": " : "") + d[0].msg;
    }
    throw new Error(msg);
  }
  return data;
}

export function jsonPost(body) {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

// 로그인이 필요한 요청에 붙일 헤더
export function auth(token) {
  return { Authorization: "Bearer " + token };
}

// JSON을 보내면서 로그인도 필요한 요청 (PATCH 등)
export function jsonPatch(token, body) {
  return {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...auth(token) },
    body: JSON.stringify(body),
  };
}
