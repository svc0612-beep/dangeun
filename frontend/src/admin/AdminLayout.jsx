// 관리자 대시보드 뼈대
//
// 왼쪽 사이드바 + 오른쪽 내용. 일반 사용자 화면과 완전히 다른 틀이라
// 기존 App 화면들과 섞지 않고 여기서 따로 관리함

import { useState, useEffect } from "react";
import {
  BarChart3, Package, Coins, Users, Flag,
  AlertTriangle, ScrollText, Settings, Bell, LogOut, Users2, Ban,
} from "lucide-react";

import { callApi, auth } from "../api";

import Overview from "./Overview";
import PostsPage from "./PostsPage";
import SoldPage from "./SoldPage";
import UsersPage from "./UsersPage";
import ReportsPage from "./ReportsPage";
import RiskyPage from "./RiskyPage";
import GroupsPage from "./GroupsPage";
import PenaltyPage from "./PenaltyPage";
import ActionsPage from "./ActionsPage";
import SettingsPage from "./SettingsPage";

const MENU = [
  { key: "overview", label: "현황",      Icon: BarChart3 },
  { key: "posts",    label: "매물",      Icon: Package },
  { key: "sold",     label: "판매 내역", Icon: Coins },
  { key: "users",    label: "회원",      Icon: Users },
  { key: "reports",  label: "신고 내역", Icon: Flag },
  { key: "risky",    label: "위험 매물", Icon: AlertTriangle },
  { key: "groups",   label: "의심 무리",  Icon: Users2 },
  { key: "penalties", label: "제재 대기", Icon: Ban },
  { key: "actions",  label: "조치 기록", Icon: ScrollText },
  { key: "settings", label: "설정",      Icon: Settings },
];

export default function AdminLayout({ me, token, onExit, onLogout }) {
  const [page, setPage] = useState("overview");
  const [unread, setUnread] = useState(0);
  const [notices, setNotices] = useState([]);
  const [showNotices, setShowNotices] = useState(false);

  // 안 읽은 알림 수를 주기적으로 확인.
  // 에이전트 조사는 뒤에서 도니까 화면을 켜둔 채로도 새 알림이 생김
  useEffect(() => {
    function load() {
      callApi("/admin/notices?limit=20", { headers: auth(token) })
        .then((d) => { setUnread(d.안읽음); setNotices(d.목록); })
        .catch(() => {});
    }
    load();
    const timer = setInterval(load, 30000);   // 30초마다
    return () => clearInterval(timer);
  }, [token]);

  function openNotice(n) {
    callApi(`/admin/notices/${n.id}/read`, { method: "PATCH", headers: auth(token) })
      .then(() => setUnread((v) => Math.max(0, v - 1)))
      .catch(() => {});

    // 알림 종류에 맞는 화면으로
    if (n.연결?.종류 === "report") setPage("reports");
    else if (n.연결?.종류 === "post") setPage("risky");
    else if (n.연결?.종류 === "user") setPage("penalties");
    setShowNotices(false);
  }

  function readAll() {
    callApi("/admin/notices/read-all", { method: "POST", headers: auth(token) })
      .then(() => { setUnread(0); setShowNotices(false); })
      .catch(() => {});
  }

  const pages = {
    overview: <Overview token={token} onGo={setPage} />,
    posts:    <PostsPage token={token} />,
    sold:     <SoldPage token={token} />,
    users:    <UsersPage token={token} />,
    reports:  <ReportsPage token={token} />,
    risky:    <RiskyPage token={token} />,
    groups:   <GroupsPage token={token} />,
    penalties: <PenaltyPage token={token} />,
    actions:  <ActionsPage token={token} />,
    settings: <SettingsPage token={token} />,
  };

  return (
    <div className="adm">
      <aside className="adm-side">
        <p className="adm-brand">
          당근 <span>관리자</span>
        </p>

        <nav className="adm-menu">
          {MENU.map(({ key, label, Icon }) => (
            <span key={key}
              className={page === key ? "adm-menu__item adm-menu__item--on" : "adm-menu__item"}
              onClick={() => setPage(key)}>
              <Icon size={17} strokeWidth={1.9} />
              {label}
            </span>
          ))}
        </nav>

        <div className="adm-side__foot">
          <span className="adm-menu__item" onClick={onExit}>
            일반 화면 보기
          </span>
          <span className="adm-menu__item" onClick={onLogout}>
            <LogOut size={16} strokeWidth={1.9} />
            로그아웃
          </span>
        </div>
      </aside>

      <main className="adm-main">
        <header className="adm-top">
          <p className="adm-title">
            {MENU.find((m) => m.key === page)?.label}
          </p>

          {/* 알림 종 */}
          <span className="adm-bell" onClick={() => setShowNotices(!showNotices)}>
            <Bell size={19} strokeWidth={1.9} />
            {unread > 0 && <i className="adm-bell__dot">{unread}</i>}
          </span>

          <span className="adm-who">{me.nickname}</span>
        </header>

        {/* 알림 목록 */}
        {showNotices && (
          <div className="adm-notices">
            <p className="adm-notices__head">
              알림
              {unread > 0 && (
                <span className="link" onClick={readAll}>모두 읽음</span>
              )}
            </p>

            {notices.length === 0 ? (
              <p className="adm-empty">알림이 없습니다.</p>
            ) : (
              notices.map((n) => (
                <div key={n.id}
                  className={n.읽음 ? "adm-notice" : "adm-notice adm-notice--new"}
                  onClick={() => openNotice(n)}>
                  <p className="adm-notice__title">
                    <span className={`risk risk--${n.위험도}`}>{n.위험도}</span>
                    {n.제목}
                  </p>
                  {n.내용 && <p className="adm-notice__body">{n.내용}</p>}
                </div>
              ))
            )}
          </div>
        )}

        <div className="adm-body">{pages[page]}</div>
      </main>
    </div>
  );
}
