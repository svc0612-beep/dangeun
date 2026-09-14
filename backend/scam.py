"""
사기 예방 — 위험 신호 찾기

완벽한 차단은 불가능함. 목표는 "막는 것" 이 아니라
구매자가 위험 신호를 미리 보고 스스로 판단하게 하는 것.

지금 잡는 것
  · 위험 문구 (선입금 / 택배거래만 / 카톡아이디 ...)
  · 시세보다 지나치게 싼 가격
  · 사진이 없는 매물
  · 거래 이력 없이 취소만 있는 판매자
  · 남의 매물 사진을 가져다 쓴 것 (image_check)
"""

from typing import Optional

from sqlalchemy.orm import Session

from database import Post
from schemas import RiskFlag
from config import SCAM_PHRASES, ACCOUNT_PATTERN, PRICE_ALERT_RATIO, PRICE_MIN_SAMPLES
import image_check
import badwords




def find_bad_words(text: str) -> list[str]:
    """욕설·사기 문구를 찾음.

    글자를 씻어낸 뒤 비교하므로 "ㄱ ㅐ ㅅ ㅐ ㄲ ㅣ" 같은 변형도 걸림
    """
    return badwords.find_bad(text)


def find_scam_phrases(text: str) -> list[str]:
    """글에서 위험 문구를 찾아 목록으로 돌려줌"""
    lowered = (text or "").replace(" ", "")
    hits = []
    for phrase in SCAM_PHRASES:
        if phrase.replace(" ", "") in lowered:
            hits.append(phrase)
    return hits




def check_price_risk(post: Post, db: Session) -> Optional[RiskFlag]:
    """같은 카테고리 매물들의 중앙값과 비교.
    평균이 아니라 중앙값을 쓰는 이유 — 값 하나가 아주 크면 평균이 끌려가서
    시세를 왜곡함. 중앙값은 그런 값에 흔들리지 않음"""
    if post.price <= 0:
        return None    # 나눔은 비교 대상이 아님

    prices = [
        p.price for p in db.query(Post)
        .filter(Post.category == post.category, Post.price > 0, Post.id != post.id)
        .all()
    ]
    if len(prices) < PRICE_MIN_SAMPLES:
        return None    # 표본이 적으면 시세라고 할 수 없음

    prices.sort()
    mid = len(prices) // 2
    median = prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / 2

    if post.price < median * PRICE_ALERT_RATIO:
        return RiskFlag(
            code="price_too_low",
            level="warn",
            message=f"같은 카테고리 시세({int(median):,}원)보다 많이 낮습니다. 거래 전에 상태를 꼭 확인하세요.",
        )
    return None




def check_post_risks(post: Post, db: Session) -> list[RiskFlag]:
    """매물 하나의 위험 신호를 모두 모음"""
    flags: list[RiskFlag] = []

    # ① 위험 문구. 글자를 씻어낸 뒤 보므로 띄어쓰기로 피해 가는 것도 걸림
    hits = find_bad_words(post.title + " " + post.content)
    if hits:
        flags.append(RiskFlag(
            code="scam_phrase",
            level="danger",
            message=(f"주의가 필요한 표현이 있습니다 ({', '.join(hits[:3])}). "
                     "이 앱은 직거래만 합니다 — 만나서 물건을 확인하고 그 자리에서 주고받으세요."),
        ))

    # ④ 시세 이탈
    price_flag = check_price_risk(post, db)
    if price_flag:
        flags.append(price_flag)

    # 사진이 없는 매물
    if not post.images:
        flags.append(RiskFlag(
            code="no_image",
            level="info",
            message="사진이 없는 매물입니다. 사진을 요청해보세요.",
        ))

    # 판매 이력이 없고 취소 이력만 있는 판매자
    seller = post.seller
    if seller.completed_deals == 0 and seller.cancel_count > 0:
        flags.append(RiskFlag(
            code="new_seller",
            level="warn",
            message=f"거래 완료 이력이 없고 취소 이력이 {seller.cancel_count}회 있는 판매자입니다.",
        ))

    # ⑤ 사진 도용 — 다른 사람의 매물과 같은 사진을 쓰고 있는지
    if image_check.is_ready():
        stolen = []
        for image in post.images:
            stolen += image_check.find_duplicates(
                image.image_hash, post.id, post.seller_id, db
            )

        # 나보다 "먼저" 올라온 매물과 겹칠 때만 경고함.
        # 사진을 도용당한 원본 판매자까지 의심받으면 안 되기 때문
        earlier = [h for h in stolen if h["created_at"] < post.created_at]

        if earlier:
            first = earlier[0]
            flags.append(RiskFlag(
                code="duplicate_image",
                level="danger",
                message=(
                    f"이 매물의 사진이 더 먼저 올라온 다른 판매자"
                    f"({first['seller_nickname']})의 매물에도 쓰였습니다. "
                    f"사진을 퍼온 매물일 수 있으니 주의하세요."
                ),
            ))

    # --- 3층에서 더 붙일 자리 ---
    # ⑥ 대화 분석: LLM 판정 결과를 flags.append(...)

    return flags
