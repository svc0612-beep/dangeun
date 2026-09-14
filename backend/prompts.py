"""
에이전트 지시서 읽어오기

에이전트에게 주는 지시를 파이썬 코드가 아니라 agents/ 폴더의
.md 파일에 둔다.

왜 밖으로 뺐나
  · 코드를 안 고치고 지시를 다듬을 수 있다
  · 지시서가 파일 하나로 보이니 "이 조사관은 무엇을 하는가" 가 분명해진다
  · 프로그래머가 아닌 사람도 읽고 고칠 수 있다

읽는 방법
  prompts.load("검사")            → agents/검사.md 내용
  prompts.load("공용/조사규칙")    → agents/공용/조사규칙.md

파일이 없으면 오류를 내지 않고 빈 글을 돌려준다.
지시서 하나가 없다고 앱 전체가 멈추면 곤란하므로
"""

import os
import threading

# 이 파일이 있는 곳 기준으로 agents/ 를 찾음
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents")

# 한 번 읽은 것은 기억해둠. 매번 파일을 열면 느려짐
_cache: dict = {}
_lock = threading.Lock()


def path_of(name: str) -> str:
    """이름을 실제 파일 경로로"""
    return os.path.join(BASE, name.replace("/", os.sep) + ".md")


def load(name: str, **values) -> str:
    """지시서를 읽어옴.

    values 를 주면 {이름} 자리에 끼워 넣는다.
    예: load("prosecutor", tools="- 매물_보기: ...")
    """
    with _lock:
        text = _cache.get(name)

    if text is None:
        try:
            with open(path_of(name), encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            print(f"[지시서] {name}.md 를 찾을 수 없습니다")
            text = ""
        except Exception as e:
            print(f"[지시서] {name}.md 를 읽지 못했습니다 — {e}")
            text = ""

        with _lock:
            _cache[name] = text

    if not values:
        return text

    return fill(text, **values)


def fill(text: str, **values) -> str:
    """{이름} 자리를 채움.

    지시서에 {} 를 그대로 쓴 곳(JSON 예시)이 있으므로
    format() 대신 하나씩 바꿔 넣는다
    """
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def build(name: str, **values) -> str:
    """지시서를 읽고, 그 안의 {공용조각} 도 함께 채워 넣는다.

    예를 들어 solo.md 안에 {trade_rule} 이 있으면
    agents/shared/trade_rule.md 를 읽어 그 자리에 넣는다.
    같은 내용을 여러 지시서에 베껴 쓰지 않아도 된다
    """
    import re

    text = load(name)

    # {trade_rule} 처럼 shared 폴더에 같은 이름이 있으면 끼워 넣음.
    # 최대 3겹까지만 — 서로를 부르며 끝없이 도는 것을 막는다
    for _ in range(3):
        holes = re.findall(r"\{([A-Za-z_]+)\}", text)
        replaced = False

        for hole in set(holes):
            if hole in values:
                continue
            shared = load("shared/" + hole)
            if shared:
                text = text.replace("{" + hole + "}", shared)
                replaced = True

        if not replaced:
            break

    return fill(text, **values)


def reload(name: str = None):
    """기억해둔 것을 지움. 지시서를 고친 뒤 서버를 안 껐다 켜도 되게"""
    with _lock:
        if name:
            _cache.pop(name, None)
        else:
            _cache.clear()


def list_all() -> list:
    """agents/ 안의 지시서 목록"""
    found = []
    for root, _, files in os.walk(BASE):
        for f in files:
            if not f.endswith(".md"):
                continue
            full = os.path.join(root, f)
            name = os.path.relpath(full, BASE)[:-3].replace(os.sep, "/")
            found.append({
                "이름": name,
                "글자수": os.path.getsize(full),
            })
    return sorted(found, key=lambda x: x["이름"])
