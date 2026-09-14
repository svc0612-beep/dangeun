"""
오래된 위반 이력 정리

config.HISTORY_KEEP_DAYS(기본 15일)가 지난 violations 기록을 지웁니다.
프라이버시를 위한 청소입니다 — 오래된 채팅 위반 근거를 계속 들고 있지 않기 위함.

활성 카운트(제재)는 STRIKE_WINDOW_HOURS(48시간)처럼 훨씬 짧은 창을 보므로,
15일 지난 기록을 지워도 제재 판정에는 전혀 영향이 없습니다.

실행:
    python scripts/cleanup_violations.py          몇 건이 지워질지 보여주기만 함(미리보기)
    python scripts/cleanup_violations.py --yes    실제로 지움

가끔 수동으로 돌리거나, 윈도우 작업 스케줄러로 하루 1번 걸어두면 됩니다.
"""

# --- 이 파일은 scripts/ 안에 있지만 backend 의 파일들을 씁니다 ---
# 한 칸 위(backend)도 import 경로에 넣어줍니다. 없으면 'No module named database' 오류
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ------------------------------------------------------------------

from datetime import datetime, timedelta

from database import SessionLocal, Violation
from config import HISTORY_KEEP_DAYS


def main():
    # 실제로 지울지, 미리보기만 할지 (기본은 미리보기 — 실수 방지)
    do_delete = "--yes" in sys.argv

    # 이 시각보다 오래된 기록이 대상
    cutoff = datetime.utcnow() - timedelta(days=HISTORY_KEEP_DAYS)

    db = SessionLocal()
    try:
        # 대상 건수부터 셈
        q = db.query(Violation).filter(Violation.created_at < cutoff)
        count = q.count()

        if count == 0:
            print(f"[정리] {HISTORY_KEEP_DAYS}일 지난 위반 기록이 없습니다.")
            return

        if not do_delete:
            # 미리보기 — 무엇이 지워질지만 보여주고 끝
            print(f"[미리보기] {HISTORY_KEEP_DAYS}일 지난 위반 {count}건이 삭제 대상입니다.")
            print("           실제로 지우려면:  python scripts/cleanup_violations.py --yes")
            return

        # 실제 삭제
        deleted = q.delete(synchronize_session=False)
        db.commit()
        print(f"[정리] {HISTORY_KEEP_DAYS}일 지난 위반 {deleted}건을 삭제했습니다.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
