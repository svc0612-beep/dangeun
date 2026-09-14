// 함께 움직이는 무리
//
// 혼자 하는 사기는 매물·이력만 봐도 잡히지만,
// 여럿이 나눠서 하면 각자는 깨끗해 보인다.
// 누구와 어떻게 이어져 있는지를 보여줘서 관리자가 판단할 수 있게 함

import { useState, useEffect } from "react";
import { Users2, AlertTriangle } from "lucide-react";

import { callApi, jsonPost, auth } from "../api";

export default function GroupsPage({ token }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);

  function load() {
    setLoading(true);
    callApi("/admin/groups?limit=20", { headers: auth(token) })
      .then((d) => setRows(d.목록))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }

  useEffect(load, [token]);

  function warn(member, groupName) {
    const reason = window.prompt(
      `${member.닉네임} 님에게 보낼 경고 사유`,
      `특정 상대와만 거래·후기를 주고받는 정황 (${groupName})`
    );
    if (!reason) return;

    callApi(`/admin/users/${member.번호}/warn`, {
      ...jsonPost({ reason, detail: null }),
      headers: { "Content-Type": "application/json", ...auth(token) },
    })
      .then((res) => alert(`경고를 보냈습니다. (누적 ${res.누적경고}회)`))
      .catch((e) => alert(e.message));
  }

  function block(member) {
    const reason = window.prompt(`${member.닉네임} 님을 정지하는 이유`);
    if (!reason) return;

    callApi(`/admin/users/${member.번호}/block`, {
      ...jsonPost({ reason }),
      headers: { "Content-Type": "application/json", ...auth(token) },
    })
      .then(() => { alert("정지했습니다."); load(); })
      .catch((e) => alert(e.message));
  }

  if (loading) return <p className="adm-empty">관계를 살펴보는 중…</p>;

  if (rows.length === 0) {
    return <p className="adm-empty">함께 움직이는 것으로 보이는 무리가 없습니다.</p>;
  }

  return (
    <>
      <p className="adm-note">
        서로에게만 거래하거나 후기를 주고받는 사람들입니다.
        <b> 이것만으로는 사기라고 단정할 수 없습니다</b> —
        실제로 친한 사이일 수도 있으니 자세한 내용을 보고 판단해주세요.
      </p>

      <div className="grp-list">
        {rows.map((g, i) => (
          <div key={i} className="grp">
            <div className="grp__head" onClick={() => setOpen(open === i ? null : i)}>
              <Users2 size={17} strokeWidth={2}
                className={g.총점 >= 12 ? "grp__icon grp__icon--high" : "grp__icon"} />

              <span className="grp__names">
                {g.대표.닉네임}
                {g.구성원.map((m) => ` · ${m.닉네임}`).join("")}
              </span>

              <span className="grp__count">{g.인원}명</span>
              <span className={g.총점 >= 12 ? "grp__score grp__score--high" : "grp__score"}>
                {g.총점}점
              </span>
            </div>

            {open === i && (
              <div className="grp__body">
                <p className="grp__who">
                  대표 — {g.대표.닉네임} ({g.대표.아이디})
                </p>

                {g.구성원.map((m) => (
                  <div key={m.번호} className="grp__member">
                    <div className="grp__member-top">
                      <span className="grp__member-name">
                        {m.닉네임}
                        <span className="grp__member-score">{m.점수}점</span>
                      </span>
                      <button className="adm-btn adm-btn--warn"
                        onClick={() => warn(m, g.대표.닉네임)}>경고</button>
                      <button className="adm-btn adm-btn--red"
                        onClick={() => block(m)}>정지</button>
                    </div>

                    <ul className="grp__signs">
                      {m.신호.map((sg, j) => <li key={j}>{sg}</li>)}
                    </ul>
                  </div>
                ))}

                <p className="grp__note">
                  <AlertTriangle size={12} strokeWidth={2} />
                  점수는 신호를 더한 값일 뿐입니다. 높다고 사기가 확정된 것은 아닙니다.
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
