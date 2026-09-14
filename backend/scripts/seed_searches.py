"""
가짜 검색 기록 만들기 — 인기 검색어 화면을 확인하기 위한 재료

실제로는 사용자가 검색할 때마다 기록이 쌓이지만,
지금은 데이터가 없어 순위가 안 나오므로 임의로 심어둠.

이번 주와 지난주의 횟수를 다르게 줘서
상승(▲) · 하락(▼) · 신규(NEW) 가 모두 보이게 만듦

실행:  python seed_searches.py
"""


# --- 이 파일은 scripts/ 안에 있지만 backend 의 파일들을 씁니다 ---
# 파이썬은 실행한 파일이 있는 폴더만 찾아보므로, 한 칸 위(backend)도
# 찾도록 알려줍니다. 이 세 줄이 없으면 "No module named 'database'" 가 납니다
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ------------------------------------------------------------------

import random
from datetime import datetime, timedelta

from database import SessionLocal, init_db, SearchLog

random.seed(7)

# (검색어, 이번 주 횟수, 지난주 횟수)
# 지난주가 0이면 NEW, 이번 주가 더 많으면 상승
PLAN = [
    ("에어프라이어", 42, 18),   # 크게 상승
    ("노트북",       38, 40),   # 살짝 하락
    ("캠핑의자",     31,  0),   # 신규
    ("자전거",       27, 33),   # 하락
    ("맥북",         24,  9),   # 상승
    ("아이패드",     21, 22),
    ("겨울패딩",     18,  0),   # 신규
    ("전자레인지",   15, 25),   # 크게 하락
    ("책상",         12, 11),
    ("유모차",       10,  6),
    ("운동화",        8, 14),
    ("텐트",          6,  0),
    ("냄비",          4,  3),
    ("덤벨",          3,  0),
]


def add_logs(db, keyword: str, count: int, start_days: int, end_days: int):
    """start_days ~ end_days 일 전 사이에 검색 기록을 흩뿌림"""
    now = datetime.utcnow()
    for _ in range(count):
        # 기간 안에서 무작위 시각. 실제 검색처럼 고르지 않게 퍼짐
        offset = random.uniform(end_days, start_days)
        when = now - timedelta(days=offset)
        db.add(SearchLog(keyword=keyword, user_id=None, created_at=when))


def main():
    init_db()
    db = SessionLocal()

    try:
        before = db.query(SearchLog).count()

        for keyword, this_week, last_week in PLAN:
            # 이번 주: 0 ~ 7일 전
            add_logs(db, keyword, this_week, 7, 0)
            # 지난주: 7 ~ 14일 전
            add_logs(db, keyword, last_week, 14, 7)

        db.commit()
        total = db.query(SearchLog).count()
        print(f"검색 기록 {total - before}건 추가 (전체 {total}건)")
        print("서버를 켜고 홈 화면에서 인기 검색어를 확인하세요.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
