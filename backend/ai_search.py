"""
의미 검색 — 뜻이 비슷한 매물 찾기

글자 검색은 "노트북"으로 "랩탑"을 못 찾음.
문장을 숫자 목록(벡터)으로 바꾸면 뜻이 비슷한 것끼리 가까워져서
글자가 안 겹쳐도 찾을 수 있음.

모델이 없는 기기에서는 조용히 꺼짐 — 앱은 그대로 돌아가고
글자 검색만 쓰게 됨
"""

import json
import math
from typing import Optional

# 한국어 문장 임베딩 모델. 400MB 정도, CPU로도 돌아감
MODEL_NAME = "jhgan/ko-sroberta-multitask"

# 1단계 문턱 — 후보를 뽑는 기준. 넉넉하게 잡음.
# 여기서 조이면 "갤럭시북3 프로" 처럼 제목이 길어 점수가 희석된 것을 놓침
MIN_SCORE = 0.42

# 2단계 문턱 — 제목의 낱말 하나라도 검색어와 이만큼 가까워야 통과.
#
# 제목 전체로 재면 "갤럭시북3 프로"(노트북)와 "갤럭시 S24"(폰)가
# 둘 다 0.4대로 뭉뚱그려짐. 낱말로 쪼개면
#   "갤럭시북" ↔ "노트북" = 높음 / "S24" ↔ "노트북" = 낮음
# 으로 갈려서 부류가 다른 것을 걸러낼 수 있음
WORD_SCORE = 0.50

# 최고 점수의 이 비율 아래도 버림
RELATIVE_RATIO = 0.75

# 의미 검색으로 추가할 최대 개수
MAX_RESULTS = 10


# 모델은 무거워서 한 번만 불러와 재사용함
_model = None
# None = 아직 안 해봄 / True = 쓸 수 있음 / False = 못 씀
_available: Optional[bool] = None


def get_model():
    """모델을 가져옴. 처음 부를 때 한 번만 불러오고 그다음은 재사용.
    설치가 안 됐거나 내려받기에 실패하면 None을 돌려주고 다시 시도하지 않음"""
    global _model, _available

    if _available is False:
        return None
    if _model is not None:
        return _model

    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
        _available = True
        print(f"[의미 검색] 모델 준비 완료 ({MODEL_NAME})")
        return _model
    except Exception as e:
        _available = False
        print(f"[의미 검색] 사용 안 함 — {e}")
        return None


def is_ready() -> bool:
    """의미 검색을 쓸 수 있는 상태인지"""
    return get_model() is not None


def embed_text(text: str) -> Optional[list[float]]:
    """문장 하나를 숫자 목록으로. 실패하면 None"""
    model = get_model()
    if model is None or not text.strip():
        return None
    try:
        vec = model.encode(text, convert_to_numpy=True)
        return [float(x) for x in vec]
    except Exception:
        return None


def post_text(post) -> str:
    """매물에서 뜻을 담은 부분만 모음.

    제목만 씀. 본문과 카테고리는 일부러 뺐음
      · 본문 — "상태 좋아요" 처럼 어느 매물에나 있는 말이라 제목의 뜻을 묻음
      · 카테고리 — "노트북" 과 "갤럭시 S24" 가 둘 다 디지털기기라
        카테고리를 넣으면 서로 가까워져서, 노트북을 찾는데 스마트폰이 딸려 나옴
    """
    return (post.title or "").strip()


def embed_post(post) -> Optional[str]:
    """매물 하나를 벡터로 만들어 저장할 문자열로.
    SQLite에는 목록 타입이 없어서 JSON 글자로 넣음"""
    vec = embed_text(post_text(post))
    return json.dumps(vec) if vec else None


def cosine(a: list[float], b: list[float]) -> float:
    """두 벡터가 얼마나 같은 방향인지. 1에 가까울수록 비슷함.
    길이는 무시하고 방향만 보기 때문에 문장 길이에 덜 흔들림"""
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def split_words(title: str) -> list[str]:
    """제목을 검색에 쓸 만한 낱말로 쪼갬.

    "삼성 갤럭시북3 프로" → ["삼성", "갤럭시북3", "프로"]
    숫자만 있거나 한 글자인 것은 뜻이 없어서 뺌
    """
    import re
    words = []
    for w in re.sub(r"[^가-힣a-zA-Z0-9]", " ", title or "").split():
        if len(w) >= 2 and not w.isdigit():
            words.append(w)
    return words[:6]        # 제목이 길어도 앞쪽 몇 개만


def word_match(q_vec: list[float], title: str, cache: dict) -> float:
    """제목의 낱말 중 검색어와 가장 가까운 것의 점수.

    cache — 같은 낱말을 여러 매물에서 또 계산하지 않으려고 모아둠
    """
    best = 0.0
    for word in split_words(title):
        if word not in cache:
            vec = embed_text(word)
            cache[word] = vec if vec else []
        score = cosine(q_vec, cache[word])
        if score > best:
            best = score
    return best


def rank_posts(query: str, posts: list, exclude_ids: set = None) -> list[tuple]:
    """검색어와 가까운 매물을 골라 (매물, 점수) 목록으로 돌려줌.
    exclude_ids = 이미 글자 검색으로 찾은 것들. 중복해서 보여주지 않으려고"""
    q_vec = embed_text(query)
    if q_vec is None:
        return []

    exclude_ids = exclude_ids or set()
    scored = []

    for post in posts:
        if post.id in exclude_ids or not post.embedding:
            continue
        try:
            p_vec = json.loads(post.embedding)
        except Exception:
            continue

        score = cosine(q_vec, p_vec)
        if score >= MIN_SCORE:
            scored.append((post, score))

    if not scored:
        return []

    scored.sort(key=lambda x: -x[1])

    # 2단계 — 제목 낱말 중 하나라도 검색어와 가까운 것만 남김.
    # 후보가 많으면 오래 걸리므로 상위 30개만 검사
    cache: dict[str, list[float]] = {}
    passed = []

    for post, score in scored[:30]:
        if word_match(q_vec, post.title, cache) >= WORD_SCORE:
            passed.append((post, score))

    if not passed:
        return []

    # 최고 점수에 비해 너무 처지는 것은 버림
    top = passed[0][1]
    kept = [(p, s) for p, s in passed if s >= top * RELATIVE_RATIO]

    return kept[:MAX_RESULTS]
