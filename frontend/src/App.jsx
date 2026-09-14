// 화면 전환만 맡는 곳
//
// 로그인 여부로 크게 나누고, screen 값에 따라 화면을 골라 보여줌.
// 화면을 오가도 유지돼야 하는 값(토큰·내 정보·어디서 왔는지)은 전부 여기 있음 —
// 자식 화면은 바뀔 때 통째로 버려져서 그 안의 상태가 사라지기 때문
//
// 실제 화면은 screens/ 안에, 여러 곳에서 쓰는 조각은 components/ 안에 있음

import { useState, useEffect } from "react";

import { WS_BASE, callApi, jsonPost, auth } from "./api";
import { LoginScreen, SignupScreen, FindIdScreen, FindPwScreen } from "./screens/Auth";
import { WriteScreen, EditScreen } from "./screens/PostForm";
import PostList from "./screens/PostList";
import PostDetail from "./screens/PostDetail";
import ChatList from "./screens/ChatList";
import ChatRoom from "./screens/ChatRoom";
import ReviewScreen from "./screens/Review";
import UserProfile from "./screens/UserProfile";
import MyPage from "./screens/MyPage";
import Toast from "./components/Toast";
import WarningModal from "./components/WarningModal";
import AdminLayout from "./admin/AdminLayout";

// ===============================================================
// 전체 관리 — 로그인 여부로 화면을 완전히 나눔
// 화면을 오가도 유지돼야 하는 값은 전부 여기에 둠.
// 자식 컴포넌트는 화면이 바뀌면 통째로 버려져서 상태가 사라지기 때문
// ===============================================================
export default function App() {
  // 함수를 넣으면 처음 한 번만 실행. 새로고침해도 토큰을 다시 읽어옴
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [me, setMe] = useState(null);
  const [checking, setChecking] = useState(true);

  // 지역 트리는 서버에서 받아옴. { "서울": ["강남구", ...], ... } 형태
  const [regionTree, setRegionTree] = useState({});
  // 끌올 대기 시간. 서버에서 받아옴
  const [cooldownHours, setCooldownHours] = useState(24);
  // 카테고리 목록도 서버에서 받아옴
  const [categories, setCategories] = useState([]);

  const [authScreen, setAuthScreen] = useState("login");
  // 로그인 후 화면. "list" | "detail" | "write" | "edit" | "my"
  const [screen, setScreen] = useState("list");
  const [selectedId, setSelectedId] = useState(null);
  // 상세로 들어오기 전에 어느 화면에 있었는지 기억
  const [cameFrom, setCameFrom] = useState("list");
  // 지금 보고 있는 채팅방 번호
  const [roomId, setRoomId] = useState(null);
  // 지금 보고 있는 프로필의 회원 번호
  const [profileId, setProfileId] = useState(null);
  // 프로필에서 뒤로 갈 화면
  const [profileFrom, setProfileFrom] = useState("detail");
  // 후기 화면에서 뒤로 갈 화면
  const [reviewFrom, setReviewFrom] = useState("chatRoom");

  function openProfile(id, from) {
    setProfileId(id);
    setProfileFrom(from);
    setScreen("profile");
  }

  // 후기 화면에서 뒤로 갈 곳. 채팅방에서 왔는지 마이페이지에서 왔는지 기억
  function openReview(id, from) {
    setRoomId(id);
    setReviewFrom(from);
    setScreen("review");
  }
  // 마이페이지 탭. 상세를 다녀와도 유지되게 여기에 둠
  const [myTab, setMyTab] = useState("favorites");
  // 홈을 누를 때마다 1씩 오름. 목록 화면의 key 로 써서
  // 검색어·지역·카테고리가 전부 처음 상태로 돌아가게 함
  const [homeKey, setHomeKey] = useState(0);
  // 방금 도착한 메시지 알림. 없으면 null
  const [toast, setToast] = useState(null);
  // 관리자가 보낸 경고 중 아직 확인 안 한 것들
  const [warnings, setWarnings] = useState([]);

  // 앱이 뜰 때 지역 목록을 한 번만 받아옴 (로그인 불필요)
  useEffect(() => {
    callApi("/regions")
      .then((data) => setRegionTree(data.regions || {}))
      .catch(() => setRegionTree({}));
  }, []);

  // 앱이 뜰 때 설정값도 한 번 받아옴
  useEffect(() => {
    callApi("/config")
      .then((data) => {
        setCooldownHours(data.bump_cooldown_hours);
        setCategories(data.categories || []);
      })
      .catch(() => {});
  }, []);

  // 로그인해 있는 동안 알림 연결을 열어둠.
  // 채팅방 연결(/ws/chats/..)과 달리 이건 어느 화면에 있든 살아 있어서
  // 다른 화면을 보고 있어도 새 메시지가 온 걸 알 수 있음
  useEffect(() => {
    if (!token) return;

    const wsUrl = WS_BASE + "/ws/notify?token=" + encodeURIComponent(token);
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "chat") setToast(data);
    };

    // 토큰이 낡아 서버가 연결을 거절하면(회원이 사라졌거나 기간 만료)
    // 다시 시도해봐야 소용없으므로 로그인 화면으로 보냄
    ws.onclose = (e) => {
      if (e.code === 1008 || e.code === 1006) {
        // 1008 = 서버가 인증을 거절, 1006 = 연결이 비정상 종료
        // /me 확인이 이미 돌고 있으므로 여기서는 더 붙잡지 않음
      }
    };

    return () => {
      // 아직 연결 중이면 바로 못 닫으므로 열린 뒤에 닫도록 예약
      if (ws.readyState === WebSocket.OPEN) ws.close();
      else ws.onopen = () => ws.close();
    };
  }, [token]);

  // 관리자가 보낸 경고가 있는지 확인.
  // 안 읽은 것이 있으면 화면 가운데에 띄우고, 확인을 눌러야 넘어감
  useEffect(() => {
    if (!token || !me) return;

    callApi("/me/warnings", { headers: auth(token) })
      .then((d) => setWarnings(d.목록.filter((w) => !w.읽음)))
      .catch(() => {});
  }, [me?.id]);

  // 로그인할 때 그동안 온 메시지가 있는지 확인.
  // 알림 연결은 접속 중일 때만 살아 있어서, 로그아웃한 사이에 온 것은
  // 이렇게 따로 챙겨야 놓치지 않음
  useEffect(() => {
    if (!token || !me) return;

    callApi("/me/unread", { headers: auth(token) })
      .then((d) => {
        if (d.count > 0) {
          const first = d.rooms[0];
          setToast({
            kind: "unread",          // 평소 알림과 생김새를 구분하려고
            count: d.count,
            room_id: first.room_id,
            post_title: first.post_title,
            sender_nickname: first.partner_nickname,
            preview: first.preview,
          });
        }
      })
      .catch(() => {});
    // me 가 채워진 뒤 한 번만. 화면을 옮길 때마다 다시 뜨지 않게
  }, [me?.id]);

  useEffect(() => {
    if (!token) { setMe(null); setChecking(false); return; }

    setChecking(true);
    callApi("/me", { headers: auth(token) })
      .then((data) => { setMe(data); setChecking(false); })
      .catch(() => {
        // 토큰이 만료됐거나 잘못된 경우 지워버림
        localStorage.removeItem("token");
        setToken(null);
        setChecking(false);
      });
  }, [token]);

  function saveToken(t) {
    localStorage.setItem("token", t);   // 새로고침해도 남음
    setToken(t);
    setScreen("list");
  }

  function logout() {
    localStorage.removeItem("token");
    setToken(null);
    setSelectedId(null);
    setScreen("list");
    setAuthScreen("login");
  }

  async function autoLogin(username, password) {
    try {
      const data = await callApi("/login", jsonPost({ username, password }));
      saveToken(data.access_token);
    } catch {
      setAuthScreen("login");
    }
  }

  // from = 어느 화면에서 눌렀는지. 뒤로가기가 거기로 돌아감
  // 알림을 누르면 그 채팅방으로 이동
  function openToast() {
    if (!toast) return;
    setRoomId(toast.room_id);
    setScreen("chatRoom");
    setToast(null);
  }

  // 경고를 확인함. 여러 건이면 하나씩 차례로 보여줌
  function confirmWarning(id) {
    callApi(`/me/warnings/${id}/read`, { method: "POST", headers: auth(token) })
      .catch(() => {})
      .finally(() => setWarnings((list) => list.filter((w) => w.id !== id)));
  }

  // 로고를 누르면 처음 화면으로. 어느 화면에서든 같은 곳으로 돌아옴.
  //
  // 검색어·지역·카테고리는 목록 화면 안에 들어 있어서 여기서 직접 못 지움.
  // key 를 바꾸면 React 가 그 화면을 통째로 새로 만들어서 전부 초기화됨
  function goHome() {
    setScreen("list");
    setHomeKey((n) => n + 1);
  }

  function openDetail(id, from = "list") {
    setSelectedId(id);
    setCameFrom(from);
    setScreen("detail");
  }

  // 관리자는 대시보드를 먼저 봄. 일반 화면은 "일반 화면 보기" 로 갈 수 있음
  const [adminMode, setAdminMode] = useState(true);

  // 어떤 화면을 보여줄지 고름.
  // 알림 창은 어느 화면 위에나 떠야 해서, 고른 결과를 아래에서 감쌈
  function pickScreen() {
    // me.is_admin 은 서버가 정해줌. 화면에서 켤 수 있는 값이 아님
    if (me?.is_admin && adminMode) {
      return (
        <AdminLayout
          me={me}
          token={token}
          onExit={() => setAdminMode(false)}
          onLogout={logout}
        />
      );
    }

    if (checking) {
      return <div className="page page--auth"><p className="notice">불러오는 중…</p></div>;
    }

    // --- 로그인 전 ---
    if (!me) {
      if (authScreen === "signup") {
        return <SignupScreen onSignedUp={autoLogin} go={setAuthScreen} regionTree={regionTree} />;
      }
      if (authScreen === "findId") return <FindIdScreen go={setAuthScreen} />;
      if (authScreen === "findPw") return <FindPwScreen go={setAuthScreen} />;
      return <LoginScreen onLogin={saveToken} go={setAuthScreen} />;
    }

    // --- 로그인 후 ---
    if (screen === "write") {
      return (
        <WriteScreen
          token={token}
          me={me}
          regionTree={regionTree}
          // 등록이 끝나면 새로고침해서 목록을 새로 불러옴
          onDone={() => { setScreen("list"); window.location.reload(); }}
          onCancel={() => setScreen("list")}
          onHome={goHome}
      />
      );
    }

    if (screen === "edit") {
      return (
        <EditScreen
          postId={selectedId}
          token={token}
          regionTree={regionTree}
          // 수정이 끝나면 상세로 돌아가되, 새로 불러오려고 새로고침
          onDone={() => { setScreen("detail"); window.location.reload(); }}
          onCancel={() => setScreen("detail")}
          onHome={goHome}
      />
      );
    }

    if (screen === "detail") {
      return (
        <PostDetail
          postId={selectedId}
          me={me}
          token={token}
          // 어디서 왔든 그 화면으로 되돌아감
          onBack={() => setScreen(cameFrom)}
          onDeleted={() => { setScreen(cameFrom); window.location.reload(); }}
          onEdit={() => setScreen("edit")}
          onChat={(id) => { setRoomId(id); setScreen("chatRoom"); }}
          onProfile={(uid) => openProfile(uid, "detail")}
          onHome={goHome}
      />
      );
    }

    if (screen === "profile") {
      return (
        <UserProfile
          userId={profileId}
          onBack={() => setScreen(profileFrom)}
          onSelectPost={(id) => openDetail(id, "profile")}
          onHome={goHome}
      />
      );
    }

    if (screen === "chatList") {
      return (
        <ChatList
          me={me}
          token={token}
          onOpen={(id) => { setRoomId(id); setScreen("chatRoom"); }}
          onHome={goHome}
          onWrite={() => setScreen("write")}
          onMy={() => setScreen("my")}
          onLogout={logout}
        />
      );
    }

    if (screen === "chatRoom") {
      return (
        <ChatRoom
          roomId={roomId}
          me={me}
          token={token}
          onBack={() => setScreen("chatList")}
          onHome={goHome}
          onReview={(id) => openReview(id, "chatRoom")}
          onProfile={(uid) => openProfile(uid, "chatRoom")}
          onPost={(pid) => openDetail(pid, "chatRoom")}
        />
      );
    }

    if (screen === "review") {
      return (
        <ReviewScreen
          roomId={roomId}
          token={token}
          onDone={() => setScreen(reviewFrom)}
          onCancel={() => setScreen(reviewFrom)}
          onHome={goHome}
      />
      );
    }

    if (screen === "my") {
      return (
        <MyPage
          me={me}
          token={token}
          regionTree={regionTree}
          cooldownHours={cooldownHours}
          tab={myTab}
          setTab={setMyTab}
          onSelect={(id) => openDetail(id, "my")}
          onHome={goHome}
          onWrite={() => setScreen("write")}
          onChat={() => setScreen("chatList")}
          onLogout={logout}
          onMeChanged={setMe}
          onDeleted={logout}
          onProfile={(uid) => openProfile(uid, "my")}
          onOpenChat={(id) => { setRoomId(id); setScreen("chatRoom"); }}
          onWriteReview={(id) => openReview(id, "my")}
        />
      );
    }

    return (
      <PostList
        key={homeKey}
        me={me}
        token={token}
        regionTree={regionTree}
        categories={categories}
        onHome={goHome}
        onAdmin={() => setAdminMode(true)}
        onWriteReview={(id) => openReview(id, "list")}
        onSelect={openDetail}
        onLogout={logout}
        onWrite={() => setScreen("write")}
        onChat={() => setScreen("chatList")}
        onMy={() => setScreen("my")}
      />
    );
  }

  // 이미 그 방을 보고 있으면 알림이 필요 없음
  const showToast =
    toast && !(screen === "chatRoom" && roomId === toast.room_id);

  return (
    <>
      {pickScreen()}

      {/* 정지된 계정이면 왜 정지됐는지 알려줌.
          이유를 모른 채 아무것도 안 되면 사용자는 고장인 줄 안다 */}
      {me?.is_blocked && (
        <div className="blocked-bar">
          이용이 제한된 계정입니다
          {me.blocked_reason && <span> — {me.blocked_reason}</span>}
        </div>
      )}

      {/* 경고는 알림보다 먼저. 확인을 눌러야 넘어감 */}
      {warnings.length > 0 && (
        <WarningModal
          item={warnings[0]}
          rest={warnings.length - 1}
          onConfirm={confirmWarning}
        />
      )}

      {showToast && (
        <Toast item={toast} onOpen={openToast} onClose={() => setToast(null)} />
      )}
    </>
  );
}

