// 현황 — 대시보드에 들어오면 처음 보는 화면
//
// 오늘 무슨 일이 있었는지, 처리할 게 얼마나 남았는지부터 보여줌

import { useState, useEffect } from "react";

import { callApi, auth } from "../api";
import { LineChart, BarChart, StatCard, GREEN, ORANGE } from "./Charts";

export default function Overview({ token, onGo }) {
  const [sum, setSum] = useState(null);
  const [posts, setPosts] = useState(null);
  const [users, setUsers] = useState(null);

  useEffect(() => {
    const h = { headers: auth(token) };
    callApi("/admin/summary", h).then(setSum).catch(() => {});
    callApi("/admin/stats/posts?days=14", h).then(setPosts).catch(() => {});
    callApi("/admin/stats/users?days=14", h).then(setUsers).catch(() => {});
  }, [token]);

  if (!sum) return <p className="adm-empty">불러오는 중…</p>;

  const todo = sum.처리할것;
  const hasTodo = todo.미처리신고 > 0 || todo.안읽은알림 > 0;

  return (
    <>
      {/* 손봐야 할 게 있으면 맨 위에 */}
      {hasTodo && (
        <div className="adm-todo">
          <p className="adm-todo__head">처리할 것이 있습니다</p>
          <div className="adm-todo__row">
            {todo.미처리신고 > 0 && (
              <span onClick={() => onGo("reports")}>
                미처리 신고 <b>{todo.미처리신고}</b>건
              </span>
            )}
            {todo.안읽은알림 > 0 && (
              <span onClick={() => onGo("reports")}>
                안 읽은 알림 <b>{todo.안읽은알림}</b>건
              </span>
            )}
            {todo.정지된회원 > 0 && (
              <span onClick={() => onGo("users")}>
                정지된 회원 <b>{todo.정지된회원}</b>명
              </span>
            )}
            {todo.숨긴매물 > 0 && (
              <span onClick={() => onGo("posts")}>
                숨긴 매물 <b>{todo.숨긴매물}</b>개
              </span>
            )}
          </div>
        </div>
      )}

      <p className="adm-sec">오늘</p>
      <div className="adm-stats">
        <StatCard label="새 회원" value={sum.오늘.새회원} sub={`이번주 ${sum.이번주.새회원}`} />
        <StatCard label="새 매물" value={sum.오늘.새매물} sub={`이번주 ${sum.이번주.새매물}`} />
        <StatCard label="거래 완료" value={sum.오늘.거래완료} sub={`이번주 ${sum.이번주.거래완료}`} />
        <StatCard label="새 신고" value={sum.오늘.새신고} sub={`이번주 ${sum.이번주.새신고}`}
          tone={sum.오늘.새신고 > 0 ? "warn" : null} />
        <StatCard label="탈퇴" value={sum.오늘.탈퇴} sub={`이번주 ${sum.이번주.탈퇴}`} />
      </div>

      <p className="adm-sec">전체</p>
      <div className="adm-stats">
        <StatCard label="회원" value={sum.전체.회원} />
        <StatCard label="매물" value={sum.전체.매물} />
        <StatCard label="판매중" value={sum.전체.판매중} />
        <StatCard label="거래완료" value={sum.전체.거래완료} />
      </div>

      {posts && (
        <>
          <p className="adm-sec">최근 2주 — 매물 등록과 거래</p>
          <div className="adm-card">
            <LineChart series={[
              { 이름: "등록", 색: GREEN, 자료: posts.등록 },
              { 이름: "거래", 색: ORANGE, 자료: posts.거래 },
            ]} />
          </div>

          <div className="adm-grid2">
            <div className="adm-card">
              <p className="adm-card__head">카테고리별 매물</p>
              <BarChart data={posts.카테고리별} />
            </div>
            <div className="adm-card">
              <p className="adm-card__head">지역별 매물</p>
              <BarChart data={posts.지역별} />
            </div>
          </div>
        </>
      )}

      {users && (
        <>
          <p className="adm-sec">최근 2주 — 가입과 탈퇴</p>
          <div className="adm-card">
            <LineChart series={[
              { 이름: "가입", 색: GREEN, 자료: users.가입 },
              { 이름: "탈퇴", 색: "#D64545", 자료: users.탈퇴 },
            ]} />
          </div>
        </>
      )}
    </>
  );
}
