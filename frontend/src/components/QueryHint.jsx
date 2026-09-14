// 문장 해석 결과
//
// 긴 문장으로 검색하면 서버가 카테고리·키워드로 번역해줌.
//   "캠핑장 가야하는데 초보용 의자랑 테이블 추천해줘"
//     → 스포츠/레저 · 캠핑 의자 · 캠핑 테이블
//
// 모델이 없는 기기에서는 아무것도 안 뜸 (available=false)

import { useState, useEffect } from "react";
import { Sparkles } from "lucide-react";

import { callApi } from "../api";

export default function QueryHint({ keyword, onPickKeyword, onPickCategory }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const word = (keyword || "").trim();
    // 짧은 말은 서버도 해석하지 않으므로 아예 묻지 않음
    if (word.length < 8) { setData(null); return; }

    setLoading(true);
    callApi("/search/interpret?q=" + encodeURIComponent(word))
      .then((d) => setData(d.available ? d.result : null))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [keyword]);

  if (loading) {
    return (
      <div className="qh qh--loading">
        <Sparkles size={15} strokeWidth={2} />
        문장을 읽고 있어요…
      </div>
    );
  }

  if (!data) return null;

  const { categories = [], keywords = [], summary } = data;
  if (categories.length === 0 && keywords.length === 0) return null;

  return (
    <div className="qh">
      <p className="qh__head">
        <Sparkles size={15} strokeWidth={2} />
        찾으시는 게 이건가요?
        {summary && <span className="qh__sum">{summary}</span>}
      </p>

      {/* 카테고리를 누르면 그 분류만 보게 걸러줌 */}
      {categories.length > 0 && (
        <div className="qh__row">
          {categories.map((c) => (
            <span key={c} className="qh__cat" onClick={() => onPickCategory(c)}>
              #{c}
            </span>
          ))}
        </div>
      )}

      {/* 키워드를 누르면 그 말로 다시 검색 */}
      {keywords.length > 0 && (
        <div className="qh__row">
          {keywords.map((k) => (
            <span key={k} className="qh__key" onClick={() => onPickKeyword(k)}>
              {k}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
