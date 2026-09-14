"""
사진 이해 (CLIP)

사진과 글자를 같은 공간의 숫자로 바꿔주는 모델.
사진 벡터와 글자 벡터를 견줄 수 있어서 두 가지가 가능해짐

  1) 카테고리 자동 추천 — 사진만 보고 "디지털기기 같아요"
  2) 말로 사진 찾기     — "파란색 자전거" 로 그런 사진이 달린 매물 찾기

image_check(pHash)와 하는 일이 다름
  pHash — "이 사진과 저 사진이 같은가"   (도용 탐지)
  CLIP  — "이 사진에 무엇이 찍혔나"      (뜻 이해)

한계는 분명함. 대분류는 꽤 맞히지만
"갤럭시 S24 울트라" 같은 모델명이나 정품 여부는 알 수 없음.

모델이 없는 기기에서는 조용히 꺼지고 앱은 그대로 돌아감
"""

import json
import math
from typing import Optional

# 사진을 벡터로 바꾸는 모델
IMAGE_MODEL = "clip-ViT-B-32"
# 한국어 글자를 같은 공간의 벡터로 바꾸는 모델.
# 짝을 맞춰 써야 사진과 글자를 견줄 수 있음
TEXT_MODEL = "clip-ViT-B-32-multilingual-v1"

# 카테고리 추천에서 이 점수 아래는 버림
MIN_CATEGORY_SCORE = 0.15
# 사진 검색에서 이 점수 아래는 버림
MIN_SEARCH_SCORE = 0.20

_img_model = None
_txt_model = None
_available: Optional[bool] = None

# 카테고리 설명문의 벡터. 한 번 만들어두고 다시 씀
_category_vecs: dict[str, list[float]] = {}


# 카테고리 이름만으로는 사진과 잘 안 맞아서, 그 카테고리에 흔한 물건을
# 풀어 쓴 문장을 함께 씀. CLIP 은 짧은 이름보다 설명문에 더 잘 반응함
CATEGORY_HINTS = {
    "디지털기기": "노트북, 스마트폰, 태블릿, 모니터, 키보드 같은 전자기기 사진",
    "생활가전": "냉장고, 세탁기, 에어컨, 청소기, 전자레인지 같은 가전제품 사진",
    "가구인테리어": "책상, 의자, 소파, 침대, 옷장 같은 가구 사진",
    "생활/주방": "냄비, 그릇, 컵, 프라이팬 같은 주방용품 사진",
    "유아동": "유모차, 아기 침대, 카시트, 장난감 같은 육아용품 사진",
    "의류": "옷, 패딩, 운동화, 가방 같은 의류와 잡화 사진",
    "도서": "책, 문제집, 만화책 같은 도서 사진",
    "스포츠/레저": "자전거, 텐트, 캠핑 의자, 운동기구 같은 스포츠 레저용품 사진",
    "기타": "그 밖의 물건 사진",
}


def is_ready() -> bool:
    """모델을 쓸 수 있는지. 처음 한 번만 확인하고 결과를 기억함"""
    global _img_model, _txt_model, _available

    if _available is not None:
        return _available

    try:
        from sentence_transformers import SentenceTransformer
        _img_model = SentenceTransformer(IMAGE_MODEL)
        _txt_model = SentenceTransformer(TEXT_MODEL)
        _available = True
        print(f"[사진 이해] 준비 완료 ({IMAGE_MODEL})")
    except Exception as e:
        _available = False
        print(f"[사진 이해] 사용 안 함 — {e}")

    return _available


def embed_image(path: str) -> Optional[list[float]]:
    """사진 파일 하나를 벡터로. 실패하면 None"""
    if not is_ready():
        return None
    try:
        from PIL import Image
        vec = _img_model.encode(Image.open(path), convert_to_numpy=True)
        return [float(x) for x in vec]
    except Exception:
        return None


def embed_text(text: str) -> Optional[list[float]]:
    """글자를 사진과 같은 공간의 벡터로"""
    if not is_ready() or not text.strip():
        return None
    try:
        vec = _txt_model.encode(text, convert_to_numpy=True)
        return [float(x) for x in vec]
    except Exception:
        return None


def cosine(a: list[float], b: list[float]) -> float:
    """두 벡터가 얼마나 같은 방향인지. 1에 가까울수록 비슷함"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def category_vectors() -> dict[str, list[float]]:
    """카테고리 설명문의 벡터. 처음 한 번만 계산"""
    global _category_vecs
    if _category_vecs or not is_ready():
        return _category_vecs

    for name, hint in CATEGORY_HINTS.items():
        vec = embed_text(hint)
        if vec:
            _category_vecs[name] = vec
    return _category_vecs


def guess_category(image_path: str, top: int = 3) -> list[dict]:
    """사진만 보고 어느 카테고리인지 짐작.
    확신하는 게 아니라 "이럴 것 같다" 를 순서대로 돌려줌"""
    img_vec = embed_image(image_path)
    if img_vec is None:
        return []

    scored = []
    for name, vec in category_vectors().items():
        score = cosine(img_vec, vec)
        if score >= MIN_CATEGORY_SCORE:
            scored.append({"category": name, "score": round(score, 3)})

    scored.sort(key=lambda x: -x["score"])
    return scored[:top]


def search_images(query: str, images: list, top: int = 20) -> list[tuple]:
    """말로 사진 찾기. (사진, 점수) 목록을 돌려줌

    images 는 image_vec 이 채워진 PostImage 목록
    """
    q_vec = embed_text(query.strip())
    if q_vec is None:
        return []

    scored = []
    for image in images:
        if not image.image_vec:
            continue
        try:
            vec = json.loads(image.image_vec)
        except Exception:
            continue

        score = cosine(q_vec, vec)
        if score >= MIN_SEARCH_SCORE:
            scored.append((image, score))

    scored.sort(key=lambda x: -x[1])
    return scored[:top]
