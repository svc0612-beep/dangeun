// 신고 내역 — 현재(접수) / 과거(처리완료·기각)
//
// 신고가 들어오면 에이전트가 알아서 조사해 결과를 붙여둠.
// 관리자는 그 결과를 보고 정지·기각을 결정함

import { useState, useEffect } from "react";
import { Bot, RefreshCw, ChevronRight, Check, X as XIcon,
         Scale, Users2 } from "lucide-react";

import { callApi, jsonPost, auth } from "../api";

const TABS = [
  { key: "접수",     label: "현재 신고" },
  { key: "처리완료", label: "처리한 것" },
  { key: "기각",     label: "기각한 것" },
];

export default function ReportsPage({ token }) {
  const [status, setStatus] = useState("접수");
  const [rows, setRows] = useState([]);
  const [open, setOpen] = useState(null);      // 펼쳐 본 신고 번호
  const [busy, setBusy] = useState(null);      // 조사 중인 신고 번호
  // 펼쳐 본 도구 결과. "신고번호-순서" 를 열쇠로 씀
  const [openStep, setOpenStep] = useState(null);
  // 조사 전에 관리자가 남기는 지시. 신고 번호별로 따로 기억
  const [notes, setNotes] = useState({});
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    callApi(`/admin/reports?status=${encodeURIComponent(status)}`, { headers: auth(token) })
      .then((d) => setRows(d.reports))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }

  useEffect(load, [token, status]);

  // 에이전트에게 다시 조사시키기.
  // mode — solo: 혼자 / team: 셋이 나눠 / debate: 검사·변호인·정리
  function investigate(r, mode = "solo") {
    setBusy(r.id);
    callApi(`/admin/reports/${r.id}/investigate`, {
      ...jsonPost({ mode, note: notes[r.id] || null }),
      headers: { "Content-Type": "application/json", ...auth(token) },
    })
      .then(() => { load(); setOpen(r.id); })
      .catch((e) => alert(e.message))
      .finally(() => setBusy(null));
  }

  function decide(r, next) {
    callApi(`/admin/reports/${r.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: next }),
      headers: { "Content-Type": "application/json", ...auth(token) },
    }).then(load).catch((e) => alert(e.message));
  }

  // 안 본 것만 더 조사. 처음부터 다시 하면 오래 걸리고 이미 본 것을 또 본다
  function followUp(r, tools) {
    if (!tools?.length) return;
    setBusy(r.id);
    callApi(`/admin/reports/${r.id}/follow-up`, {
      ...jsonPost({ tools, note: notes[r.id] || null }),
      headers: { "Content-Type": "application/json", ...auth(token) },
    })
      .then(() => { load(); setOpen(r.id); })
      .catch((e) => alert(e.message))
      .finally(() => setBusy(null));
  }

  // 경고 보내기. 정지는 무겁고 그냥 두기는 곤란할 때
  function warnUser(r) {
    const target = r.대상?.판매자;
    if (!target) { alert("대상을 찾을 수 없습니다."); return; }

    const reason = window.prompt(
      `${target.닉네임}(${target.아이디}) 님에게 보낼 경고 사유`,
      r.조사?.요약 || r.사유
    );
    if (!reason) return;

    // 사용자가 그대로 읽게 되므로 무엇을 고쳐야 하는지 적을 수 있게 함
    const detail = window.prompt(
      "자세한 내용 (사용자가 그대로 읽습니다. 비워도 됩니다)",
      ""
    );

    callApi(`/admin/users/${target.번호}/warn`, {
      ...jsonPost({ reason, detail: detail || null, report_id: r.id }),
      headers: { "Content-Type": "application/json", ...auth(token) },
    })
      .then((res) => {
        decide(r, "처리완료");
        alert(`경고를 보냈습니다. (이 회원의 누적 경고 ${res.누적경고}회)`);
      })
      .catch((e) => alert(e.message));
  }

  function blockSeller(r) {
    // 매물 신고면 그 매물을 올린 사람을, 회원 신고면 그 회원을 정지함.
    // 매물 번호를 잘못 넣으면 엉뚱한 사람이 정지되므로 여기서 정확히 집음
    const target = r.대상?.판매자;
    if (!target) { alert("대상을 찾을 수 없습니다."); return; }

    const ok = window.confirm(
      `${target.닉네임}(${target.아이디}) 님을 정지합니다.\n계속할까요?`
    );
    if (!ok) return;

    const reason = window.prompt("정지 사유", r.조사?.요약 || r.사유);
    if (!reason) return;

    const uid = target.번호;

    callApi(`/admin/users/${uid}/block`, {
      ...jsonPost({ reason }),
      headers: { "Content-Type": "application/json", ...auth(token) },
    })
      .then(() => { decide(r, "처리완료"); alert("정지했습니다."); })
      .catch((e) => alert(e.message));
  }

  return (
    <>
      <div className="adm-tabs">
        {TABS.map((t) => (
          <span key={t.key}
            className={status === t.key ? "adm-tab adm-tab--on" : "adm-tab"}
            onClick={() => setStatus(t.key)}>
            {t.label}
          </span>
        ))}
      </div>

      {loading ? <p className="adm-empty">불러오는 중…</p>
        : rows.length === 0 ? <p className="adm-empty">해당하는 신고가 없습니다.</p> : (
        <div className="rep-list">
          {rows.map((r) => (
            <div key={r.id} className="rep">
              <div className="rep-head" onClick={() => setOpen(open === r.id ? null : r.id)}>
                <span className="rep-reason">{r.사유}</span>

                {/* 신고당한 사람 — 판단해야 할 대상이라 접힌 상태에서도 보여줌 */}
                <span className="rep-who">
                  {r.대상?.판매자
                    ? `${r.대상.판매자.닉네임} (${r.대상.판매자.아이디})`
                    : r.대상이름}
                  {r.대상?.판매자?.정지 && <span className="tag tag--red">정지됨</span>}
                </span>

                <span className="rep-target">{r.대상이름}</span>

                {r.조사 ? (
                  <span className={`risk risk--${r.조사.위험도}`}>
                    {r.조사.위험도}
                  </span>
                ) : (
                  <span className="rep-wait">조사 전</span>
                )}

                <span className="rep-when">
                  {new Date(r.접수 + "Z").toLocaleDateString("ko-KR")}
                </span>
              </div>

              {open === r.id && (
                <div className="rep-body">
                  {/* 왜 신고됐는지 — 사유와 신고자가 적은 내용 */}
                  <div className="rep-why">
                    <p className="rep-why__head">신고 내용</p>
                    <p className="rep-line"><b>사유</b> {r.사유}</p>
                    <p className="rep-line">
                      <b>적은 내용</b> {r.내용 || "(따로 적지 않음)"}
                    </p>
                    <p className="rep-line">
                      <b>신고자</b> {r.신고자} (#{r.신고자번호})
                      {/* 거짓 신고가 잦은 사람이면 걸러 들을 수 있게 */}
                      {r.신고자신뢰도 && r.신고자신뢰도.total > 0 && (
                        <span className={
                          r.신고자신뢰도.rejected > r.신고자신뢰도.accepted
                            ? "trust trust--bad" : "trust"
                        }>
                          신고 {r.신고자신뢰도.total}건 ·
                          인정 {r.신고자신뢰도.accepted} ·
                          기각 {r.신고자신뢰도.rejected}
                        </span>
                      )}
                    </p>
                  </div>

                  {/* 누가 신고당했는지 */}
                  {r.대상 && (
                    <div className="rep-who-box">
                      <p className="rep-why__head">
                        신고된 {r.대상.종류}
                      </p>

                      {r.대상.종류 === "매물" && (
                        <>
                          <p className="rep-line"><b>제목</b> {r.대상.제목}</p>
                          <p className="rep-line">
                            <b>가격</b> {r.대상.가격.toLocaleString()}원
                            <span className="rep-dim">
                              · {r.대상.카테고리} · {r.대상.지역} · {r.대상.상태}
                            </span>
                          </p>
                          <p className="rep-line"><b>본문</b> {r.대상.본문}</p>
                        </>
                      )}

                      <p className="rep-line">
                        <b>{r.대상.종류 === "매물" ? "판매자" : "회원"}</b>
                        {r.대상.판매자.닉네임} ({r.대상.판매자.아이디}) · #{r.대상.판매자.번호}
                      </p>
                      <p className="rep-line">
                        <b>이력</b>
                        매너온도 {r.대상.판매자.매너온도}
                        <span className="rep-dim">
                          · 판매 {r.대상.판매자.판매}
                          · 취소 {r.대상.판매자.취소}
                          · 신고당함 {r.대상.신고당한횟수}회
                        </span>
                      </p>
                    </div>
                  )}

                  {r.조사 ? (
                    <div className="rep-ai">
                      <p className="rep-ai__head">
                        <Bot size={15} strokeWidth={2} />
                        에이전트 조사 결과
                        {r.조사.방식 && (
                          <span className="rep-ai__mode">{r.조사.방식}</span>
                        )}
                        <span className="rep-ai__when">
                          {new Date(r.조사.조사시각 + "Z").toLocaleString("ko-KR")}
                        </span>
                      </p>

                      <p className="rep-line"><b>판단</b> {r.조사.위험도} · {r.조사.권고}</p>
                      {/* "보통 5점" 인데 "계정 정지 검토" 가 나오면 헷갈린다.
                          왜 그런지 알려준다 */}
                      {r.조사.채점?.권고사유 && (
                        <p className="rep-why-line">↳ {r.조사.채점.권고사유}</p>
                      )}
                      <p className="rep-line"><b>요약</b> {r.조사.요약}</p>

                      {/* 왜 이 점수인지. 위험도는 AI가 정한 게 아니라
                          규칙으로 계산한 것이라 관리자가 검증할 수 있음 */}
                      {r.조사.채점 && (
                        <div className="scr">
                          <p className="scr__head">
                            어떻게 {r.조사.채점.위험도}이 되었나
                            <span className="scr__total">{r.조사.채점.총점}점</span>
                          </p>

                          {(r.조사.채점.신호 || []).length === 0 ? (
                            <p className="scr__none">걸린 위험 신호가 없습니다</p>
                          ) : (
                            (r.조사.채점.신호 || []).map((h, i) => (
                              <div key={i} className="scr__row">
                                <span className="scr__pt">+{h.점수}</span>
                                <span className="scr__name">{h.신호}</span>
                                <span className="scr__why">{h.설명}</span>
                              </div>
                            ))
                          )}

                          <p className="scr__rule">{r.조사.채점.기준}</p>
                        </div>
                      )}

                      {(r.조사.근거 || []).length > 0 && (
                        <>
                          <p className="rep-line"><b>근거</b></p>
                          <ul className="rep-ul">
                            {(r.조사.근거 || []).map((g, i) => <li key={i}>{g}</li>)}
                          </ul>
                        </>
                      )}

                      {/* 검사·변호인·정리 담당이 오간 말.
                          한쪽 말만 보고 정지시키지 않도록 양쪽을 나란히 */}
                      {r.조사.재판 && (
                        <div className="trial">
                          <div className="trial__side trial__side--pro">
                            <p className="trial__who">검사</p>
                            <ul className="trial__list">
                              {(r.조사.재판.검사?.주장 || []).map((x, i) => (
                                <li key={i}>{x}</li>
                              ))}
                            </ul>
                          </div>

                          <div className="trial__side trial__side--def">
                            <p className="trial__who">변호인</p>
                            <ul className="trial__list">
                              {(r.조사.재판.변호인?.반론 || []).map((x, i) => (
                                <li key={i}>{x}</li>
                              ))}
                            </ul>
                            {r.조사.재판.변호인?.인정?.length > 0 && (
                              <p className="trial__admit">
                                변호할 수 없다고 인정 —{" "}
                                {r.조사.재판.변호인.인정.join(" / ")}
                              </p>
                            )}
                          </div>

                          {/* 예전에 조사한 건은 "판사" 로 저장돼 있다.
                              이름을 바꿨어도 옛 기록을 읽을 수 있어야 함 */}
                          {(() => {
                            const last = r.조사.재판.정리 || r.조사.재판.판사;
                            if (!last) return null;
                            return (
                              <div className="trial__judge">
                                <p className="trial__who">정리</p>
                                <p className="trial__text">{last.정리}</p>
                                {last.남은의문?.length > 0 && (
                                  <>
                                    <p className="trial__more">관리자가 더 확인하면 좋을 것</p>
                                    <ul className="trial__list">
                                      {last.남은의문.map((x, i) => <li key={i}>{x}</li>)}
                                    </ul>
                                  </>
                                )}
                              </div>
                            );
                          })()}
                        </div>
                      )}

                      {/* 무엇을 봤고 무엇을 못 봤는지.
                          못 본 것을 숨기면 조사를 완전한 것으로 오해하게 됨 */}
                      {r.조사.점검 && (
                        <div className="cov">
                          <p className="cov__head">
                            {r.조사.점검.완료
                              ? "꼭 볼 것은 모두 확인했습니다"
                              : "확인하지 못한 것이 있습니다"}
                          </p>
                          <div className="cov__row">
                            {(r.조사.점검.확인함 || []).map((t) => (
                              <span key={t} className="cov__ok">
                                <Check size={11} strokeWidth={3} />{t}
                              </span>
                            ))}
                            {/* 안 본 것을 누르면 그것만 더 조사한다 */}
                            {(r.조사.점검.확인못함 || []).map((t) => (
                              <span key={t}
                                className={(r.조사.점검.필수누락 || []).includes(t)
                                  ? "cov__no cov__no--must cov__no--click"
                                  : "cov__no cov__no--click"}
                                title="눌러서 이것만 더 조사"
                                onClick={() => followUp(r, [t])}>
                                <XIcon size={11} strokeWidth={3} />{t}
                              </span>
                            ))}
                          </div>
                          {(r.조사.점검.확인못함 || []).length > 0 && (
                            <p className="cov__more">
                              안 본 것을 눌러 더 조사하거나{" "}
                              <span className="link"
                                onClick={() => followUp(r, r.조사.점검.확인못함)}>
                                전부 더 조사
                              </span>
                            </p>
                          )}

                          {r.조사.점검.자료없음?.length > 0 && (
                            <p className="cov__note">
                              자료가 없어 판단하지 못한 것 —{" "}
                              {r.조사.점검.자료없음.map((z) => z.이유).join(" / ")}
                            </p>
                          )}
                        </div>
                      )}

                      {/* 에이전트가 본 자료 그대로.
                          요약만 보여주면 "정말 그런가" 를 확인할 방법이 없음 */}
                      {(r.조사.단계 || []).length > 0 && (
                        <>
                          <p className="rep-line" style={{ marginTop: 14 }}>
                            <b>에이전트가 본 자료</b>
                            <span className="rep-dim">눌러서 원본 확인</span>
                          </p>

                          {(r.조사.단계 || []).map((st, i) => {
                            const key = `${r.id}-${i}`;
                            const on = openStep === key;
                            return (
                              <div key={i} className="step">
                                <div className="step__head"
                                  onClick={() => setOpenStep(on ? null : key)}>
                                  <ChevronRight size={13} strokeWidth={2.5}
                                    className={on ? "step__arrow step__arrow--on" : "step__arrow"} />
                                  <span className="step__no">{st.순서 ?? i + 1}</span>
                                  <span className="step__tool">
                                    {st.도구}({st.인자})
                                  </span>
                                  <span className="step__why">{st.이유}</span>
                                </div>

                                {on && st.결과 && (
                                  <div className="step__body">
                                    {Object.entries(st.결과).map(([k, v]) => (
                                      <p key={k} className="step__line">
                                        <b>{k}</b>
                                        {typeof v === "object"
                                          ? JSON.stringify(v, null, 1)
                                          : String(v)}
                                      </p>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </>
                      )}
                    </div>
                  ) : (
                    <p className="rep-line adm-empty">아직 조사되지 않았습니다.</p>
                  )}

                  {/* 조사하기 전에 관리자가 방향을 줄 수 있다 */}
                  <div className="rep-note">
                    <input className="adm-input rep-note__input"
                      placeholder="조사 전에 남길 지시 (예: 짜고 하는지부터 봐주세요)"
                      value={notes[r.id] || ""}
                      onChange={(e) =>
                        setNotes({ ...notes, [r.id]: e.target.value })} />
                    {r.조사?.관리자지시 && (
                      <p className="rep-note__past">
                        지난 지시 — {r.조사.관리자지시}
                      </p>
                    )}
                  </div>

                  <div className="rep-actions">
                    <button className="adm-btn" onClick={() => investigate(r, "solo")}
                      disabled={busy === r.id}>
                      <RefreshCw size={13} strokeWidth={2} />
                      {busy === r.id ? "조사 중…" : "다시 조사"}
                    </button>
                    <button className="adm-btn" onClick={() => investigate(r, "team")}
                      disabled={busy === r.id} title="매물·이력·관계 조사관이 나눠 봅니다">
                      <Users2 size={13} strokeWidth={2} />
                      셋이 나눠
                    </button>
                    <button className="adm-btn" onClick={() => investigate(r, "debate")}
                      disabled={busy === r.id} title="검사가 모으고 변호인이 반박합니다">
                      <Scale size={13} strokeWidth={2} />
                      검사·변호인
                    </button>

                    {r.상태 === "접수" && (
                      <>
                        <button className="adm-btn adm-btn--warn"
                          onClick={() => warnUser(r)}>경고 보내기</button>
                        <button className="adm-btn adm-btn--red"
                          onClick={() => blockSeller(r)}>계정 정지</button>
                        <button className="adm-btn"
                          onClick={() => decide(r, "처리완료")}>처리 완료</button>
                        <button className="adm-btn"
                          onClick={() => decide(r, "기각")}>문제없음 (기각)</button>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
