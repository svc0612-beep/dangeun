"""
에이전트가 쓸 도구들

에이전트는 이 목록에 있는 것만 부를 수 있음.
DB를 마음대로 뒤지는 게 아니라, 우리가 열어준 창구로만 봄.

모든 도구는 "읽기" 만 함 — 지우거나 정지시키는 도구는 일부러 두지 않음.
조사는 AI가 하고 결정은 사람이 하기 위해서
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from database import User, Post, PostImage, ChatRoom, Message, Review, Report
import image_check
import badwords
import network


def _ago(when: Optional[datetime]) -> str:
    """며칠 전인지 사람이 읽기 좋게"""
    if not when:
        return "알 수 없음"
    days = (datetime.utcnow() - when).days
    if days == 0:
        return "오늘"
    if days < 30:
        return f"{days}일 전"
    return f"{days // 30}개월 전"


# ---------------------------------------------------------------
# 도구 1 — 매물 보기
# ---------------------------------------------------------------
def get_post(post_id: int, db: Session) -> dict:
    """매물의 제목·본문·가격·상태를 봄"""
    post = db.get(Post, post_id)
    if post is None:
        return {"오류": "그런 매물이 없습니다"}

    kind, bad = badwords.classify(f"{post.title} {post.content}")

    # 이 앱은 직거래만 하므로, 택배·비대면 관련 표현은 그 자체로 규칙 위반.
    # 에이전트가 이 뜻을 알 수 있게 종류를 함께 알려줌
    kind_text = {
        "scam": "직거래 원칙 위반 또는 사기 신호",
        "curse": "욕설",
        "other": "거래에 어울리지 않는 내용",
    }.get(kind, "")

    return {
        "번호": post.id,
        "제목": post.title,
        "본문": (post.content or "")[:400],
        "가격": f"{post.price:,}원" if post.price else "나눔",
        "카테고리": post.category,
        "지역": post.region,
        "상태": post.status,
        "올린때": _ago(post.created_at),
        "조회수": post.view_count,
        "사진수": len(post.images),
        "위험문구": bad if bad else "없음",
        "위험문구종류": kind_text if kind_text else "없음",
        "판매자번호": post.seller_id,
    }


# ---------------------------------------------------------------
# 도구 2 — 판매자 이력 보기
# ---------------------------------------------------------------
def get_seller(user_id: int, db: Session) -> dict:
    """판매자가 어떤 사람인지. 실명·연락처는 절대 넣지 않음"""
    user = db.get(User, user_id)
    if user is None:
        return {"오류": "그런 회원이 없습니다"}

    # 이 사람이 지금까지 신고당한 횟수
    reported = (
        db.query(Report)
        .filter(Report.target_type == "user", Report.target_id == user_id)
        .count()
    )
    post_reported = (
        db.query(Report)
        .join(Post, Report.target_id == Post.id)
        .filter(Report.target_type == "post", Post.seller_id == user_id)
        .count()
    )

    return {
        "번호": user.id,
        "닉네임": user.nickname,
        "동네": user.region,
        "가입": _ago(user.created_at),
        "매너온도": user.manner_temp,
        "올린매물수": user.total_posts,
        "판매완료": user.completed_deals,
        "구매완료": user.completed_purchases,
        "거래취소": user.cancel_count,
        "신고당한횟수": reported + post_reported,
    }


# ---------------------------------------------------------------
# 도구 3 — 사진 도용 검사
# ---------------------------------------------------------------
def check_images(post_id: int, db: Session) -> dict:
    """이 매물의 사진이 다른 사람 매물에도 쓰였는지"""
    post = db.get(Post, post_id)
    if post is None:
        return {"오류": "그런 매물이 없습니다"}
    if not post.images:
        return {"결과": "사진이 없는 매물입니다"}
    if not image_check.is_ready():
        return {"결과": "사진 검사 기능을 쓸 수 없습니다"}

    hits = []
    for image in post.images:
        for hit in image_check.find_duplicates(
            image.image_hash, post.id, post.seller_id, db
        ):
            # 나보다 먼저 올라온 것만 — 도용당한 쪽이 의심받지 않게
            if hit["created_at"] < post.created_at:
                hits.append({
                    "겹친매물": hit["post_title"],
                    "그판매자": hit["seller_nickname"],
                    "먼저올림": _ago(hit["created_at"]),
                })

    if not hits:
        return {"결과": "다른 사람 매물과 겹치는 사진 없음"}
    return {"결과": f"{len(hits)}건 겹침", "겹친것": hits[:3]}


# ---------------------------------------------------------------
# 도구 4 — 채팅 기록 보기
# ---------------------------------------------------------------
def get_chats(post_id: int, db: Session) -> dict:
    """이 매물에서 오간 대화. 사기는 대개 채팅에서 드러남"""
    rooms = db.query(ChatRoom).filter(ChatRoom.post_id == post_id).all()
    if not rooms:
        return {"결과": "대화가 없습니다"}

    seller_id = rooms[0].post.seller_id
    out = []

    for room in rooms[:5]:          # 방이 많으면 앞의 몇 개만
        lines = []
        for msg in room.messages[:20]:
            if msg.kind == "system":
                continue
            who = "판매자" if msg.sender_id == seller_id else "구매자"
            lines.append(f"{who}: {msg.content[:80]}")

        if lines:
            out.append({"방번호": room.id, "대화": lines})

    if not out:
        return {"결과": "대화가 없습니다"}

    # 위험 문구가 있었는지 함께 알려줌
    joined = " ".join(l for r in out for l in r["대화"])
    kind, bad = badwords.classify(joined)

    return {
        "방수": len(out),
        "위험문구": bad if bad else "없음",
        "위험문구종류": {
            "scam": "직거래 원칙 위반 또는 사기 신호",
            "curse": "욕설",
            "other": "거래에 어울리지 않는 내용",
        }.get(kind, "없음"),
        "대화들": out,
    }


# ---------------------------------------------------------------
# 도구 5 — 시세 견주기
# ---------------------------------------------------------------
def compare_price(post_id: int, db: Session) -> dict:
    """같은 카테고리 매물들과 가격을 견줌"""
    post = db.get(Post, post_id)
    if post is None:
        return {"오류": "그런 매물이 없습니다"}
    if post.price <= 0:
        return {"결과": "나눔이라 견줄 수 없습니다"}

    prices = [
        p.price for p in db.query(Post)
        .filter(Post.category == post.category, Post.price > 0, Post.id != post.id)
        .all()
    ]
    if len(prices) < 3:
        return {"결과": "견줄 매물이 모자랍니다"}

    prices.sort()
    mid = len(prices) // 2
    median = prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / 2
    ratio = post.price / median if median else 1

    return {
        "이매물가격": f"{post.price:,}원",
        "같은분류중간값": f"{int(median):,}원",
        "비율": f"중간값의 {int(ratio * 100)}%",
        "표본수": len(prices),
    }


# ---------------------------------------------------------------
# 도구 6 — 신고자가 믿을 만한지
# ---------------------------------------------------------------
def get_reporter(user_id: int, db: Session) -> dict:
    """이 사람이 지금까지 낸 신고가 얼마나 맞았는지.
    거짓 신고를 되풀이하는 사람의 말은 덜 믿어야 함"""
    rows = db.query(Report).filter(Report.reporter_id == user_id).all()
    if not rows:
        return {
            "결과": "신고 이력 없음 (처음 신고)",
            "믿을만한가": "판단할 자료 없음 — 신고 내용보다 실제 자료로 확인하세요",
        }

    accepted = sum(1 for r in rows if r.status == "처리완료")
    rejected = sum(1 for r in rows if r.status == "기각")
    waiting = sum(1 for r in rows if r.status == "접수")
    judged = accepted + rejected

    # 판정된 것 중 몇 %가 실제 문제였나.
    # 이 값이 낮으면 이 사람 신고는 걸러 들어야 함
    if judged == 0:
        verdict = "아직 판정된 신고가 없음 — 판단할 자료 없음"
    else:
        rate = int(accepted / judged * 100)
        if rate >= 70:
            verdict = f"판정된 신고 중 {rate}%가 실제 문제였음 — 믿을 만함"
        elif rate >= 30:
            verdict = f"판정된 신고 중 {rate}%가 실제 문제였음 — 보통"
        else:
            verdict = (f"판정된 신고 {judged}건 중 {accepted}건만 인정됨 ({rate}%) — "
                       "거짓 신고가 잦은 사람입니다. 신고 내용을 믿지 말고 자료로만 판단하세요")

    return {
        "총신고": len(rows),
        "인정됨": accepted,
        "기각됨": rejected,
        "처리중": waiting,
        "믿을만한가": verdict,
    }


# ---------------------------------------------------------------
# 도구 7 — 함께 움직이는 사람이 있는지
#
# 혼자 하는 사기는 매물·이력만 봐도 잡히지만,
# 여럿이 나눠서 하면 각자는 깨끗해 보인다. 관계를 봐야 보인다
# ---------------------------------------------------------------
def check_group(user_id: int, db: Session) -> dict:
    """이 사람이 특정 상대와만 거래하거나 후기를 주고받는지"""
    result = network.find_group(user_id, db)
    if "오류" in result:
        return result

    return {
        "거래총횟수": result["거래총횟수"],
        "이어진사람수": result["이어진사람수"],
        "의심되는상대": result["의심되는상대"],
        "판단": result["판단"],
        # 자세한 것은 상위 다섯 명만. 너무 길면 모델이 헷갈림
        "관계": [
            {
                "닉네임": x["닉네임"],
                "아이디": x["아이디"],
                "거래횟수": x["거래횟수"],
                "신호": x["신호"],
            }
            for x in result["관계"][:5]
        ],
    }


# ---------------------------------------------------------------
# 에이전트에게 알려줄 도구 목록
# ---------------------------------------------------------------
TOOLS = {
    "매물_보기": {
        "함수": get_post,
        "설명": "매물의 제목·본문·가격·상태를 본다. 인자: 매물번호",
    },
    "판매자_이력": {
        "함수": get_seller,
        "설명": "판매자의 거래·취소·신고당한 횟수를 본다. 인자: 회원번호",
    },
    "사진_도용검사": {
        "함수": check_images,
        "설명": "이 매물 사진이 남의 매물에도 쓰였는지 본다. 인자: 매물번호",
    },
    "채팅_기록": {
        "함수": get_chats,
        "설명": "이 매물에서 오간 대화를 본다. 인자: 매물번호",
    },
    "시세_견주기": {
        "함수": compare_price,
        "설명": "같은 분류 매물들과 가격을 견준다. 인자: 매물번호",
    },
    "신고자_이력": {
        "함수": get_reporter,
        "설명": "신고한 사람의 지난 신고가 얼마나 맞았는지 본다. 인자: 회원번호",
    },
    "무리_확인": {
        "함수": check_group,
        "설명": ("이 사람이 특정 상대와만 거래하거나 후기를 주고받는지 본다. "
                 "여럿이 짜고 하는 사기를 찾을 때 쓴다. 인자: 회원번호"),
    },
}


def tool_list_text(only: list = None) -> str:
    """프롬프트에 넣을 도구 설명.

    only 를 주면 그 도구들만. 조사관마다 볼 수 있는 것을 다르게 할 때 씀 —
    매물 조사관에게 신고자 이력까지 주면 남의 몫까지 들여다보게 된다
    """
    names = only if only else list(TOOLS)
    return "\n".join(
        f"- {n}: {TOOLS[n]['설명']}" for n in names if n in TOOLS
    )


def run_tool(name: str, arg: int, db: Session, only: list = None) -> dict:
    """도구 하나를 실제로 실행. 목록에 없으면 거절.

    only 를 주면 그 안에 있는 도구만 허용한다.
    프롬프트에서 빼는 것만으로는 부족하다 — 모델이 다른 이름을 지어내 부를 수 있으므로
    """
    if only and name not in only:
        return {"오류": f"'{name}' 은(는) 이번 조사에서 쓸 수 없는 도구입니다"}
    if name not in TOOLS:
        return {"오류": f"'{name}' 이라는 도구는 없습니다"}

    # 인자는 반드시 번호여야 함. 모델이 "abc" 같은 것을 넣을 수 있으므로
    # 파이썬 오류를 그대로 흘리지 않고 알아듣게 돌려준다
    try:
        number = int(arg)
    except (TypeError, ValueError):
        return {"오류": f"인자는 번호여야 합니다. '{arg}' 는 번호가 아닙니다"}

    if number < 1:
        return {"오류": f"번호는 1 이상이어야 합니다 ({number})"}

    try:
        return TOOLS[name]["함수"](number, db)
    except Exception as e:
        return {"오류": f"실행 중 문제가 생겼습니다: {e}"}
