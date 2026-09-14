// 매물 등록 · 수정 화면
//
// 둘이 거의 같지만 수정 화면은 두 가지가 다름
//   1) 기존 값을 서버에서 받아와 채움
//   2) 이미 올린 사진을 지우거나 새로 더할 수 있음

import { useState, useEffect } from "react";

import { API, callApi, jsonPost, jsonPatch, auth } from "../api";
import { onEnter, splitRegion, CATEGORIES } from "../utils";
import { Field, RegionField } from "../components/ui";

export function WriteScreen({ token, me, regionTree, onDone, onCancel, onHome }) {
  const [f, setF] = useState({
    title: "", content: "", price: "",
    category: "", region: me.region, place_name: "",
  });
  const [files, setFiles] = useState([]);   // 선택한 사진 파일들
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  // 사진을 보고 짐작한 카테고리. 모델이 없는 기기에서는 늘 빈 목록
  const [guesses, setGuesses] = useState([]);
  const [guessing, setGuessing] = useState(false);

  // 사진을 보고 쓴 설명 초안. 판매자 글과 섞지 않고 따로 들고 있음
  const [aiText, setAiText] = useState("");
  const [writing, setWriting] = useState(false);
  const [writeMsg, setWriteMsg] = useState(null);

  function change(key, value) { setF({ ...f, [key]: value }); }

  // 파일 선택 상자에서 고른 것들. 최대 10장까지만
  function pickFiles(e) {
    const picked = Array.from(e.target.files).slice(0, 10);
    setFiles(picked);

    // 아직 카테고리를 안 골랐으면 첫 사진을 보고 짐작해달라고 요청.
    // 이미 골랐다면 사용자의 선택을 건드리지 않음
    if (picked.length > 0 && !f.category) {
      askCategory(picked[0]);
    }
  }

  async function askCategory(file) {
    setGuessing(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await callApi("/vision/guess-category", {
        method: "POST",
        headers: auth(token),      // Content-Type 은 브라우저가 알아서 붙임
        body: form,
      });
      setGuesses(res.available ? res.guesses : []);
    } catch {
      setGuesses([]);              // 실패해도 등록은 그대로 진행
    } finally {
      setGuessing(false);
    }
  }

  // 사진을 보고 설명 초안을 받아옴.
  // 5~15초 걸려서 사진을 고르는 즉시가 아니라 버튼을 눌렀을 때만 부름
  async function writeDescription() {
    if (files.length === 0) {
      setWriteMsg("사진을 먼저 올려주세요.");
      return;
    }

    setWriting(true);
    setWriteMsg(null);
    try {
      const form = new FormData();
      form.append("file", files[0]);        // 첫 사진만 보고 씀
      form.append("title", f.title || "");
      form.append("category", f.category || "");

      const res = await callApi("/vision/describe", {
        method: "POST",
        headers: auth(token),
        body: form,
      });

      if (!res.available) {
        setWriteMsg("이 기기에서는 설명 생성을 쓸 수 없어요.");
      } else if (!res.description) {
        setWriteMsg("설명을 만들지 못했어요. 다시 눌러보세요.");
      } else {
        // 여러 번 눌러도 쌓이지 않고 새 것으로 바뀜.
        // 판매자가 쓴 글(f.content)은 건드리지 않음
        setAiText(res.description);
      }
    } catch (err) {
      setWriteMsg(err.message);
    } finally {
      setWriting(false);
    }
  }

  async function submit() {
    if (busy) return;
    setError(null);
    if (!f.category) { setError("카테고리를 골라주세요"); return; }
    if (!splitRegion(f.region).gu) { setError("지역을 끝까지 골라주세요"); return; }

    setBusy(true);
    try {
      // 1) 매물을 먼저 만들고 id를 받아옴
      const post = await callApi("/posts", {
        ...jsonPost({
          title: f.title,
          content: f.content,
          price: Number(f.price) || 0,      // 빈칸이면 0 = 나눔
          category: f.category,
          region: f.region,
          place_name: f.place_name || null, // 안 적었으면 null
          ai_description: aiText || null,
        }),
        headers: { "Content-Type": "application/json", ...auth(token) },
      });

      // 2) 사진은 한 장씩 따로 올림 (API가 한 장 단위라)
      for (const file of files) {
        // FormData = 파일을 담아 보내는 전용 그릇
        const form = new FormData();
        form.append("file", file);
        await callApi("/posts/" + post.id + "/images", {
          method: "POST",
          // Content-Type을 직접 쓰면 안 됨. 브라우저가 알아서 붙여야 함
          headers: auth(token),
          body: form,
        });
      }

      onDone();   // 목록으로 돌아가기
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="page page--auth" onKeyDown={onEnter(submit)}>
      <div className="form-head">
        <span className="back-btn" onClick={onCancel}>← 취소</span>
        <span className="head-home" onClick={onHome}>당근</span>
      </div>
      <h2 className="form-title">내 물건 팔기</h2>

      <Field label="제목" placeholder="에어프라이어 팔아요" value={f.title}
        onChange={(e) => change("title", e.target.value)} />

      <div className="field">
        <label className="label">카테고리</label>
        <select className="input" value={f.category}
          onChange={(e) => change("category", e.target.value)}>
          <option value="">선택해주세요</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>

        {/* 사진을 보고 짐작한 것. 확신이 아니라 제안이라 눌러야 들어감 */}
        {guessing && <p className="guess-line">사진을 보는 중…</p>}
        {!guessing && guesses.length > 0 && (
          <div className="guess-row">
            <span className="guess-label">사진을 보니</span>
            {guesses.map((g) => (
              <span key={g.category} className="guess-chip"
                onClick={() => change("category", g.category)}>
                {g.category}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 이 앱의 원칙. 규칙을 모르면 지킬 수 없다 */}
      <div className="rule-note">
        이 앱은 <b>직거래만</b> 합니다. 만나서 물건을 확인하고 그 자리에서 주고받으세요.
        택배·선입금을 요구하는 글은 신고 대상이 됩니다.
      </div>

      <Field label="가격 (0을 넣으면 나눔)" type="number" placeholder="27000"
        value={f.price} onChange={(e) => change("price", e.target.value)} />

      <div className="field">
        <div className="label-row">
          <label className="label">설명</label>

          {/* 사진을 보고 초안을 써줌. 완성이 아니라 시작점 */}
          <button type="button" className="btn-ai"
            onClick={writeDescription} disabled={writing}>
            {writing ? "사진을 보는 중…" : "✨ 사진 보고 써주기"}
          </button>
        </div>
        <textarea className="input textarea" rows={5}
          placeholder="상태, 사용 기간, 구성품 등을 적어주세요"
          value={f.content} onChange={(e) => change("content", e.target.value)} />

        {writeMsg && <p className="guess-line">{writeMsg}</p>}
        {writing && (
          <p className="guess-line">
            10초쯤 걸려요. 그동안 다른 칸을 채우셔도 됩니다.
          </p>
        )}

        {/* AI가 쓴 것은 따로 보여줌. 매물에도 따로 저장돼서
            사는 사람이 "누가 쓴 글인지" 알 수 있음 */}
        {aiText && (
          <div className="ai-box">
            <p className="ai-box__head">
              <span className="ai-badge">AI</span>
              사진을 보고 쓴 설명
              <span className="link ai-box__del" onClick={() => setAiText("")}>
                지우기
              </span>
            </p>
            <p className="ai-box__text">{aiText}</p>
            <p className="ai-box__note">
              사진에 보이는 것만 적은 것이라 사실과 다를 수 있어요.
              직접 확인한 내용은 위 설명 칸에 적어주세요.
            </p>
          </div>
        )}
      </div>

      <RegionField label="지역" value={f.region} regionTree={regionTree}
        onChange={(v) => change("region", v)} />

      <Field label="거래 희망 장소 (선택)" placeholder="예: 역삼역 2번 출구"
        value={f.place_name} onChange={(e) => change("place_name", e.target.value)} />

      <div className="field">
        <label className="label">사진 (최대 10장)</label>
        {/* multiple = 여러 장 한 번에, accept = 이미지 파일만 보이게 */}
        <input className="input" type="file" multiple accept="image/*" onChange={pickFiles} />

        {/* 미리보기. createObjectURL = 파일을 임시 주소로 만들어줌 */}
        {files.length > 0 && (
          <div className="preview-row">
            {files.map((file, i) => (
              <img key={i} className="preview-img" src={URL.createObjectURL(file)} alt="" />
            ))}
          </div>
        )}
      </div>

      {error && <p className="msg-error">{error}</p>}

      <button className="btn-primary" onClick={submit} disabled={busy}>
        {busy ? "올리는 중…" : "등록하기"}
      </button>
    </div>
  );
}

// ===============================================================
// 매물 수정 화면
// 등록 화면과 비슷하지만 두 가지가 다름
//  1) 기존 값을 서버에서 받아와 채움
//  2) 이미 올린 사진을 지우거나 새로 더할 수 있음
// ===============================================================
export function EditScreen({ postId, token, regionTree, onDone, onCancel, onHome }) {
  const [f, setF] = useState(null);             // null이면 아직 불러오는 중
  const [images, setImages] = useState([]);     // 서버에 이미 있는 사진들
  const [removed, setRemoved] = useState([]);   // 지우기로 표시한 사진 id들
  const [newFiles, setNewFiles] = useState([]); // 새로 고른 파일들
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    callApi("/posts/" + postId, { headers: auth(token) })
      .then((post) => {
        setF({
          title: post.title,
          content: post.content,
          price: String(post.price),
          category: post.category,
          region: post.region,
          place_name: post.place_name || "",
          ai_description: post.ai_description || "",
        });
        setImages(post.images);
      })
      .catch((err) => setError(err.message));
  }, [postId, token]);

  function change(key, value) { setF({ ...f, [key]: value }); }

  // 지우기 표시를 켰다 껐다 함. 실제 삭제는 저장할 때
  function toggleRemove(id) {
    setRemoved(removed.includes(id)
      ? removed.filter((x) => x !== id)
      : [...removed, id]);
  }

  function pickFiles(e) {
    setNewFiles(Array.from(e.target.files).slice(0, 10));
  }

  async function submit() {
    if (busy) return;
    setError(null);
    if (!f.category) { setError("카테고리를 골라주세요"); return; }
    if (!splitRegion(f.region).gu) { setError("지역을 끝까지 골라주세요"); return; }

    setBusy(true);
    try {
      // 1) 글 내용 수정
      await callApi("/posts/" + postId, jsonPatch(token, {
        title: f.title,
        content: f.content,
        price: Number(f.price) || 0,
        category: f.category,
        region: f.region,
        place_name: f.place_name || null,
        ai_description: f.ai_description || null,
      }));

      // 2) 지우기로 표시한 사진 삭제
      for (const imageId of removed) {
        await callApi("/posts/" + postId + "/images/" + imageId, {
          method: "DELETE",
          headers: auth(token),
        });
      }

      // 3) 새로 고른 사진 업로드
      for (const file of newFiles) {
        const form = new FormData();
        form.append("file", file);
        await callApi("/posts/" + postId + "/images", {
          method: "POST",
          headers: auth(token),
          body: form,
        });
      }

      onDone();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  if (error && !f) {
    return (
      <div className="page page--auth">
        <p className="msg-error">{error}</p>
        <button className="btn-primary" onClick={onCancel}>돌아가기</button>
      </div>
    );
  }
  if (!f) return <div className="page"><p className="notice">불러오는 중…</p></div>;

  return (
    <div className="page page--auth" onKeyDown={onEnter(submit)}>
      <div className="form-head">
        <span className="back-btn" onClick={onCancel}>← 취소</span>
        <span className="head-home" onClick={onHome}>당근</span>
      </div>
      <h2 className="form-title">매물 수정</h2>

      <Field label="제목" value={f.title}
        onChange={(e) => change("title", e.target.value)} />

      <div className="field">
        <label className="label">카테고리</label>
        <select className="input" value={f.category}
          onChange={(e) => change("category", e.target.value)}>
          <option value="">선택해주세요</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      <Field label="가격 (0을 넣으면 나눔)" type="number" value={f.price}
        onChange={(e) => change("price", e.target.value)} />

      <div className="field">
        <label className="label">설명</label>
        <textarea className="input textarea" rows={5} value={f.content}
          onChange={(e) => change("content", e.target.value)} />

        {/* 등록할 때 AI가 쓴 설명. 여기서는 지우기만 할 수 있음 */}
        {f.ai_description && (
          <div className="ai-box">
            <p className="ai-box__head">
              <span className="ai-badge">AI</span>
              사진을 보고 쓴 설명
              <span className="link ai-box__del"
                onClick={() => change("ai_description", "")}>지우기</span>
            </p>
            <p className="ai-box__text">{f.ai_description}</p>
          </div>
        )}
      </div>

      <RegionField label="지역" value={f.region} regionTree={regionTree}
        onChange={(v) => change("region", v)} />

      <Field label="거래 희망 장소 (선택)" placeholder="예: 역삼역 2번 출구"
        value={f.place_name} onChange={(e) => change("place_name", e.target.value)} />

      {/* 기존 사진. × 를 누르면 흐려지고, 저장할 때 실제로 삭제됨 */}
      {images.length > 0 && (
        <div className="field">
          <label className="label">
            올린 사진 {removed.length > 0 && `(${removed.length}장 삭제 예정)`}
          </label>
          <div className="img-edit-row">
            {images.map((img) => {
              const off = removed.includes(img.id);
              return (
                <div key={img.id}
                  className={off ? "img-edit-item img-edit-item--off" : "img-edit-item"}>
                  <img src={API + img.image_url} alt="" />
                  <button className="img-del-btn" onClick={() => toggleRemove(img.id)}>
                    {off ? "↩" : "×"}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="field">
        <label className="label">사진 추가</label>
        <input className="input" type="file" multiple accept="image/*" onChange={pickFiles} />

        {newFiles.length > 0 && (
          <div className="preview-row">
            {newFiles.map((file, i) => (
              <img key={i} className="preview-img" src={URL.createObjectURL(file)} alt="" />
            ))}
          </div>
        )}
      </div>

      {error && <p className="msg-error">{error}</p>}

      <button className="btn-primary" onClick={submit} disabled={busy}>
        {busy ? "저장 중…" : "수정하기"}
      </button>
    </div>
  );
}
