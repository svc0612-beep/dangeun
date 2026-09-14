"""
사진 도용 탐지 — 같은 사진이 여러 매물에 쓰였는지 찾기

pHash(지각 해시)를 씀. 사진을 아주 작은 흑백으로 줄여서 64비트 지문을 만드는 방식.
같은 사진이면 지문이 같고, 크기나 밝기가 조금 달라져도 거의 같음.

무엇을 잡는가
  - 남의 매물 사진을 그대로 복사해서 올린 것
  - 한 사람이 같은 사진으로 매물 여러 개를 올린 것
무엇을 못 잡는가
  - 사진을 크게 잘라낸 것
  - 인터넷에서 퍼온 것 (우리 DB에 비교 대상이 없음)

같은 물건을 다른 각도로 찍은 사진들은 지문이 크게 달라서 서로 안 걸림
"""

from typing import Optional

# 지문 사이의 거리가 이 값 이하면 "같은 사진"으로 봄.
# 0 = 완전히 동일, 4~5 = 크기·밝기만 달라진 정도, 12 이상 = 다른 사진
MAX_DISTANCE = 5

_available: Optional[bool] = None


def is_ready() -> bool:
    """imagehash 를 쓸 수 있는지. 없으면 이 기능만 조용히 꺼짐"""
    global _available
    if _available is None:
        try:
            import imagehash          # noqa: F401
            from PIL import Image     # noqa: F401
            _available = True
        except Exception as e:
            _available = False
            print(f"[사진 검사] 사용 안 함 — {e}")
    return _available


def make_hash(file_path: str) -> Optional[str]:
    """사진 파일의 지문을 만듦. 16글자짜리 문자열이 나옴"""
    if not is_ready():
        return None
    try:
        import imagehash
        from PIL import Image
        return str(imagehash.phash(Image.open(file_path)))
    except Exception:
        return None   # 손상된 파일 등


def distance(a: str, b: str) -> int:
    """두 지문이 얼마나 다른지. 0이면 같은 사진.
    16진수 글자를 2진수로 펼쳐서 서로 다른 자리 수를 셈"""
    if not a or not b or len(a) != len(b):
        return 999

    diff = 0
    for x, y in zip(a, b):
        # int(x, 16) = 16진수 한 글자를 숫자로. ^ = 다른 자리만 1로 남김
        diff += bin(int(x, 16) ^ int(y, 16)).count("1")
    return diff


def find_duplicates(image_hash: str, post_id: int, seller_id: int, db) -> list[dict]:
    """이 지문과 같은 사진을 쓴 다른 매물을 찾음.

    같은 매물 안의 사진과 같은 판매자의 다른 매물은 제외함 —
    자기 사진을 다시 쓰는 건 사기가 아니라 흔한 일이기 때문.
    다른 사람의 매물과 겹칠 때만 도용으로 봄
    """
    if not image_hash:
        return []

    # 순환 참조를 피하려고 함수 안에서 불러옴
    from database import PostImage, Post

    rows = (
        db.query(PostImage, Post)
        .join(Post, PostImage.post_id == Post.id)
        .filter(
            PostImage.image_hash.isnot(None),
            PostImage.post_id != post_id,      # 같은 매물 제외
            Post.seller_id != seller_id,       # 같은 판매자 제외
        )
        .all()
    )

    hits = []
    for image, post in rows:
        d = distance(image_hash, image.image_hash)
        if d <= MAX_DISTANCE:
            hits.append({
                "post_id": post.id,
                "post_title": post.title,
                "seller_nickname": post.seller.nickname,
                "distance": d,
                "created_at": post.created_at,
            })

    # 먼저 올라온 것이 원본일 가능성이 높으니 오래된 순으로
    hits.sort(key=lambda h: h["created_at"])
    return hits
