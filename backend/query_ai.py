"""
Ollama 로 하는 두 가지

  1) 질의 해석  — 긴 문장을 카테고리와 키워드로 번역
  2) 설명 생성  — 판매자가 올린 사진을 보고 매물 설명 초안 쓰기

둘 다 같은 모델(gemma3:12b)을 씀. Ollama 가 모델을 한 번만 메모리에
올려놓고 돌려쓰기 때문에 기능을 늘려도 무게가 늘지 않음

    "캠핑장 가야하는데 초보 캠퍼한테 맞는 의자랑 테이블 추천해줘"
        ↓
    카테고리: 스포츠/레저
    키워드:   캠핑 의자, 캠핑 테이블

의미 검색(ai_search)이 "노트북 ↔ 랩탑" 을 잇는다면,
여기는 문장 자체를 읽어서 무엇을 찾는지 알아냄.

Ollama 가 없는 기기(노트북·배포 서버)에서는 조용히 꺼지고,
검색은 지금까지 하던 방식 그대로 돌아감.

추가 패키지가 필요 없도록 표준 라이브러리만 씀
"""

import json
import re
import urllib.request
import urllib.error
from typing import Optional

from config import (
    OLLAMA_URL, OLLAMA_MODEL, QUERY_AI_TIMEOUT,
    QUERY_AI_MIN_LENGTH, CATEGORIES, DESCRIBE_TIMEOUT,
)

# None = 아직 확인 안 함 / True = 쓸 수 있음 / False = 못 씀
_available: Optional[bool] = None

# 같은 문장을 또 물어보지 않게 답을 기억해둠.
# LLM 호출은 1~3초 걸려서 같은 검색을 반복하면 체감이 크게 나빠짐
_cache: dict[str, dict] = {}
_CACHE_MAX = 200


def _post_json(path: str, payload: dict, timeout: int) -> Optional[dict]:
    """Ollama 에 요청을 보내고 답을 받아옴. 실패하면 None"""
    req = urllib.request.Request(
        OLLAMA_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception:
        return None


def is_ready() -> bool:
    """Ollama 가 켜져 있고 모델이 있는지. 한 번만 확인하고 결과를 기억함"""
    global _available
    if _available is not None:
        return _available

    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=3) as res:
            data = json.loads(res.read().decode("utf-8"))
        names = [m.get("name", "") for m in data.get("models", [])]

        # 태그(:12b)까지 정확히 같지 않아도 앞부분이 맞으면 인정
        head = OLLAMA_MODEL.split(":")[0]
        _available = any(n == OLLAMA_MODEL or n.startswith(head) for n in names)

        if _available:
            print(f"[질의 해석] 준비 완료 ({OLLAMA_MODEL})")
        else:
            print(f"[질의 해석] 사용 안 함 — {OLLAMA_MODEL} 모델이 없습니다")
    except Exception as e:
        _available = False
        print(f"[질의 해석] 사용 안 함 — Ollama에 연결할 수 없습니다 ({e})")

    return _available


def _build_prompt(text: str) -> str:
    """모델에게 시킬 말.
    형식을 아주 엄격하게 못박아야 딴 얘기를 안 함"""
    return f"""너는 중고거래 앱의 검색 도우미다.
사용자가 쓴 문장을 읽고 무엇을 찾는지 알아내라.

카테고리는 반드시 아래 목록에서만 고른다:
{", ".join(CATEGORIES)}

키워드는 중고거래 사이트에서 실제로 검색할 만한 짧은 물건 이름으로 쓴다.
"추천", "저렴한", "좋은" 같은 꾸밈말은 넣지 않는다.

반드시 아래 형식의 JSON만 출력한다. 설명이나 인사는 절대 쓰지 않는다.

{{"categories": ["카테고리1"], "keywords": ["물건1", "물건2"], "summary": "한 줄 요약"}}

규칙
- categories 는 0~2개
- keywords 는 1~4개, 각각 2~10글자
- summary 는 "무엇을 찾고 있는지" 를 20자 안쪽으로

사용자 문장: {text}"""


def _extract_json(raw: str) -> Optional[dict]:
    """모델이 말을 덧붙여도 JSON 부분만 뽑아냄"""
    if not raw:
        return None

    # ```json ... ``` 로 감싸는 경우가 흔함
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    if fenced:
        raw = fenced.group(1)
    else:
        brace = re.search(r"\{.*\}", raw, re.S)
        if not brace:
            return None
        raw = brace.group(0)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def interpret(text: str) -> Optional[dict]:
    """문장을 카테고리·키워드로 바꿔줌. 못 하면 None"""
    word = (text or "").strip()

    # 짧은 말은 그냥 물건 이름일 가능성이 높아서 굳이 모델을 부르지 않음.
    # "노트북" 같은 검색까지 1~3초 기다리게 하면 손해
    if len(word) < QUERY_AI_MIN_LENGTH:
        return None
    if not is_ready():
        return None

    if word in _cache:
        return _cache[word]

    data = _post_json("/api/generate", {
        "model": OLLAMA_MODEL,
        "prompt": _build_prompt(word),
        "stream": False,
        # format=json 을 주면 모델이 JSON 형식을 지키도록 강제됨
        "format": "json",
        "options": {
            "temperature": 0.2,   # 낮게 — 매번 비슷한 답이 나오게
            "num_predict": 200,   # 짧게 — 길게 쓸 이유가 없음
        },
    }, QUERY_AI_TIMEOUT)

    if data is None:
        return None

    parsed = _extract_json(data.get("response", ""))
    if not parsed:
        return None

    # 모델이 엉뚱한 값을 줄 수 있으니 우리 목록·길이로 걸러냄
    cats = [c for c in parsed.get("categories", []) if c in CATEGORIES][:2]

    words = []
    for k in parsed.get("keywords", []):
        k = str(k).strip()
        if 2 <= len(k) <= 10 and k not in words:
            words.append(k)
    words = words[:4]

    if not words and not cats:
        return None          # 건질 게 없으면 없는 것으로

    result = {
        "query": word,
        "categories": cats,
        "keywords": words,
        "summary": str(parsed.get("summary", ""))[:40],
    }

    # 오래된 것부터 버리며 최대 개수 유지
    if len(_cache) >= _CACHE_MAX:
        _cache.pop(next(iter(_cache)))
    _cache[word] = result

    return result


# ===============================================================
# 사진 보고 설명 쓰기
#
# 목표는 "사진 캡션"이 아니라 "판매글 초안".
# 예전 프롬프트는 보이는 걸 다 나열하게 해서
# "터치패드가 있습니다" 처럼 뻔한 문장이 나왔음.
# 이제는 판매자 말투로, 살 사람이 궁금할 것만 쓰게 함
# ===============================================================
def _describe_prompt(title: str, category: str) -> str:
    hint = ""                                       # 제목·카테고리가 있으면 힌트로 붙임
    if title:
        hint += f"\n판매자가 적은 제목: {title}"
    if category:
        hint += f"\n카테고리: {category}"

        return f"""당신은 한국 중고거래 앱의 판매자입니다.
사진 속 물건을 사고 싶어지도록, 매력적인 판매글 초안을 쓰세요.{hint}

【목표】
- 읽는 사람이 "이거 괜찮네, 사고 싶다" 는 마음이 들게 씁니다.
- 첫 문장은 이 물건의 좋은 점(색, 디자인, 깔끔함)으로 밝게 시작합니다.
- 소심하게 "사용감이 있습니다" 로 시작하지 않습니다.

【말투】
- 밝고 친근한 판매자 말투. 자신 있게 소개합니다.
- "사진 속에는", "~로 보이며" 같은 관찰자 말투는 쓰지 않습니다.
- 딱딱한 "구매 전 직접 확인 부탁드립니다" 로 끝맺지 않습니다.
  꼭 필요하면 가볍게 "궁금한 점 편하게 물어보세요" 정도로만.

【정직 — 이건 반드시 지킵니다】
- 사진으로 알 수 없는 것(모델명, 연식, 정품 여부, 작동 여부)은 지어내지 않습니다.
- "새것같은", "최상급", "무결점" 같은 거짓 과장은 쓰지 않습니다.
- 흠집·사용감이 뚜렷이 보이면 숨기지 말고, 부담 없게 한 번만 언급합니다.
- 없는 구성품을 있다고 쓰지 않습니다.
- 그 물건 종류면 당연한 부품(노트북 키보드·터치패드 등)은 나열하지 않습니다.

【형식】
- 2~3문장, 150자 안쪽
- 밝은 존댓말 (~해요 / ~합니다)
- 인사말·머리말 없이 본문만
- 반드시 한국어로만. 외래어는 한글로. (예: silver → 은색)

【좋은 예】
깔끔한 화이트 노트북 내놓아요! 색감도 깨끗하고 디자인이 심플해서 들고 다니기 좋아요.
잘 관리해서 써온 거라 찾으시던 분께 바로 추천드려요.

판매글 초안:"""


def _is_korean_enough(text: str) -> bool:
    """한국어로 잘 쓰였는지 검사.

    모델이 가끔 일본어나 영어를 섞어서 내놓음.
    한글이 아닌 글자가 많으면 다시 시키려고 여기서 걸러냄
    """
    if not text:
        return False

    hangul = other = 0
    for ch in text:
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3 or 0x3131 <= code <= 0x318E:
            hangul += 1                      # 한글
        elif 0x3040 <= code <= 0x30FF:
            return False                     # 일본어가 하나라도 있으면 탈락
        elif 0x4E00 <= code <= 0x9FFF:
            return False                     # 한자도 탈락
        elif ch.isalpha():
            other += 1                       # 영어 등

    if hangul < 10:
        return False

    # 영어가 전체의 15%를 넘으면 섞인 것으로 봄.
    # 제품명에 영어가 조금 들어가는 건 자연스러워서 아주 막지는 않음
    return other / (hangul + other) <= 0.15


def describe_image(image_b64: str, title: str = "", category: str = "") -> Optional[str]:
    """사진 하나를 보고 설명 초안을 씀. 못 하면 None

    image_b64 = 사진을 base64 로 바꾼 글자. Ollama 는 사진을 이 형태로 받음

    한국어가 아닌 글자가 섞여 나오면 최대 두 번까지 다시 시킴 —
    모델이 가끔 일본어나 영어로 빠지는데, 그대로 내보내면 쓸 수 없기 때문
    """
    for attempt in range(3):
        text = _describe_once(image_b64, title, category)
        if text is None:
            return None
        if _is_korean_enough(text):
            return text
        print(f"[설명 생성] 한국어가 아닌 글자가 섞여 다시 시도 ({attempt + 1}/3)")

    # 세 번 모두 실패하면 포기. 이상한 글을 내보내는 것보다 나음
    return None


def _describe_once(image_b64: str, title: str, category: str) -> Optional[str]:
    """한 번 시켜보기"""
    if not is_ready() or not image_b64:
        return None

    data = _post_json("/api/generate", {
        "model": OLLAMA_MODEL,
        "prompt": _describe_prompt(title.strip(), category.strip()),
        "images": [image_b64],
        "stream": False,
        "options": {
            # 조금 자연스럽게. 너무 낮으면 매번 같은 문장이 나옴
            "temperature": 0.4,
            "num_predict": 300,
        },
    }, DESCRIBE_TIMEOUT)

    if data is None:
        return None

    text = (data.get("response") or "").strip()
    if not text:
        return None

    # 모델이 가끔 따옴표나 머리말을 붙임 — 다듬어서 돌려줌
    text = text.strip('"\'` \n')
    for prefix in ("설명:", "초안:", "물건 설명:"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    return text[:600]