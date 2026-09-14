// 매물 등록 · 수정 화면
//
// 둘이 거의 같지만 수정 화면은 두 가지가 다름
//   1) 기존 값을 서버에서 받아와 채움
//   2) 이미 올린 사진을 지우거나 새로 더할 수 있음

import { useState, useEffect } from "react";

import { API, callApi, jsonPost, jsonPatch, auth } from "../api";
import { onEnter, splitRegion, CATEGORIES } from "../utils";
import { Field, RegionField } from "../components/ui";

export function WriteScreen({ token, me, regionTree, onDone, onCancel }) {
  const [f, setF] = useState({
    title: "", content: "", price: "",
    category: "", region: me.region, place_name: "",
  });
  const [files, setFiles] = useState([]);   // 선택한 사진 파일들
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  function change(key, value) { setF({ ...f, [key]: value }); }

  // 파일 선택 상자에서 고른 것들. 최대 10장까지만
  function pickFiles(e) {
    setFiles(Array.from(e.target.files).slice(0, 10));
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
      <span className="back-btn" onClick={onCancel}>← 취소</span>
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
      </div>

      <Field label="가격 (0을 넣으면 나눔)" type="number" placeholder="27000"
        value={f.price} onChange={(e) => change("price", e.target.value)} />

      <div className="field">
        <label className="label">설명</label>
        <textarea className="input textarea" rows={5}
          placeholder="상태, 사용 기간, 구성품 등을 적어주세요"
          value={f.content} onChange={(e) => change("content", e.target.value)} />
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
export function EditScreen({ postId, token, regionTree, onDone, onCancel }) {
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
      <span className="back-btn" onClick={onCancel}>← 취소</span>
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