"""
에이전트가 잘 도는지 눈으로 확인

관리자 대시보드가 없어도 터미널에서 바로 시험할 수 있음.
조사 과정을 한 걸음씩 보여줘서 "무엇을 왜 봤는지" 가 드러남

실행
    python scripts/check_agent.py                 신고 목록 보기
    python scripts/check_agent.py 3               3번 신고를 조사
    python scripts/check_agent.py post 12         12번 매물을 신고 없이 조사
    python scripts/check_agent.py --tools         도구 하나씩 시험
    python scripts/check_agent.py --fake          가짜 사기 매물을 만들어 조사
    python scripts/check_agent.py --team          세 가지 방식을 나란히 견줌
    python scripts/check_agent.py --debate   검사·변호인·정리 방식만
    python scripts/check_agent.py --note "지시"    지시를 주고 조사
    python scripts/check_agent.py --more 3        3번 신고에서 안 본 것을 더 조사
"""


# --- 이 파일은 scripts/ 안에 있지만 backend 의 파일들을 씁니다 ---
# 파이썬은 실행한 파일이 있는 폴더만 찾아보므로, 한 칸 위(backend)도
# 찾도록 알려줍니다. 이 세 줄이 없으면 "No module named 'database'" 가 납니다
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ------------------------------------------------------------------

import json
import sys
import time
from datetime import datetime

from database import SessionLocal, User, Post, Report
import agent
import agent_tools
import query_ai


LINE = "=" * 60


def show_reports(db):
    """신고 목록과 조사 결과"""
    rows = db.query(Report).order_by(Report.created_at.desc()).limit(20).all()

    if not rows:
        print("신고가 없습니다.")
        print("앱에서 매물이나 채팅방의 신고 버튼을 눌러보세요.")
        print("또는:  python check_agent.py --fake")
        return

    print(LINE)
    print(f"신고 {len(rows)}건")
    print(LINE)

    for r in rows:
        if r.target_type == "post":
            post = db.get(Post, r.target_id)
            name = post.title if post else "(삭제됨)"
        else:
            user = db.get(User, r.target_id)
            name = user.nickname if user else "(탈퇴)"

        print(f"\n  #{r.id}  {r.reason}  ·  {name}")
        print(f"      상태 {r.status}")

        if r.ai_checked_at:
            print(f"      조사됨 → {r.ai_risk} / {r.ai_action}")
            print(f"      {r.ai_summary}")
        else:
            print(f"      아직 조사 안 됨")

    print()
    print("한 건을 조사하려면:  python check_agent.py <번호>")


def run(question: str, db, mode: str = "solo", note: str = None):
    """조사를 돌리면서 걸음마다 보여줌.

    mode — solo: 혼자 다 봄 / team: 조사관 셋이 나눠 봄
           debate: 검사·변호인·정리
    note — 관리자가 남기는 지시
    """
    if not query_ai.is_ready():
        return None

    print(LINE)
    print("조사할 건")
    print(f"  {question}")
    if note:
        print(f"  관리자 지시: {note}")
    print(LINE)
    print()

    started = time.time()

    def on_step(step):
        """도구를 부를 때마다 여기로 옴"""
        who = f"[{step['조사관']}] " if step.get("조사관") else ""
        print(f"  {who}{step['도구']}({step['인자']})")
        print(f"          왜: {step['이유']}")

        result = step["결과"]
        # 결과를 보기 좋게 몇 줄만
        if isinstance(result, dict):
            for key, value in list(result.items())[:6]:
                text = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
                print(f"          {key}: {str(text)[:70]}")
        print()

    if mode == "team":
        import agent_team
        out = agent_team.investigate(question, db, on_step=on_step, note=note)
    elif mode == "debate":
        import agent_debate
        out = agent_debate.investigate(question, db, on_step=on_step, note=note)
    else:
        out = agent.investigate(question, db, on_step=on_step, note=note)
    took = time.time() - started

    if "오류" in out:
        print("오류:", out["오류"])
        return None

    c = out["결론"]
    graded = out.get("채점", {})

    if out.get("재판"):
        t = out["재판"]
        print(LINE)
        print("재판")
        print(LINE)

        print(f"  검사 ({t['검사'].get('걸린시간', '?')}초)")
        for x in t["검사"].get("주장", []):
            print(f"    · {x}")

        print(f"\n  변호인 ({t['변호인'].get('걸린시간', '?')}초)")
        for x in t["변호인"].get("반론", []):
            print(f"    · {x}")
        for x in t["변호인"].get("인정", []):
            print(f"    (인정) {x}")

        # 예전 기록은 "판사" 로 저장돼 있다
        last = t.get("정리") or t.get("판사") or {}
        print(f"\n  정리 ({last.get('걸린시간', '?')}초)")
        print(f"    {last.get('정리', '')}")
        for x in last.get("남은의문", []):
            print(f"    ? {x}")
        print()

    if out.get("조사관"):
        print(LINE)
        print("조사관별")
        for a in out["조사관"]:
            note = f" — {a['요약']}" if a.get("요약") else ""
            print(f"  {a['이름']:12} {a['걸음']}걸음 {a['걸린시간']}초{note}")
        print()

    print(LINE)
    print(f"결론  ({len(out['단계'])}걸음 · {took:.0f}초 걸림)")
    print(LINE)
    print(f"  위험도  {c['위험도']}  ({graded.get('총점', 0)}점)")
    print(f"  권고    {c['권고']}")

    # 점수보다 무거운 권고가 나왔으면 왜 그런지
    if graded.get("권고사유"):
        print(f"          ↳ {graded['권고사유']}")

    # 왜 이 점수인지. 규칙으로 계산한 것이라 늘 같은 답이 나온다
    if graded.get("신호"):
        print(f"  채점")
        for h in graded["신호"]:
            print(f"    +{h['점수']}  {h['신호']:22} {h['설명']}")
        print(f"    ({graded.get('기준', '')})")
    print(f"  요약    {c['요약']}")
    print(f"  근거")
    for g in c["근거"]:
        print(f"    · {g}")

    cov = out.get("점검", {})
    if cov:
        print(f"  확인함    {', '.join(cov.get('확인함', []))}")
        missing = cov.get("확인못함", [])
        if missing:
            must = cov.get("필수누락", [])
            marks = [f"{m}(필수)" if m in must else m for m in missing]
            print(f"  확인못함  {', '.join(marks)}")
    print()

    return out


def run_report(report_id: int, db):
    report = db.get(Report, report_id)
    if report is None:
        print(f"{report_id}번 신고가 없습니다.")
        return

    out = run(agent.build_question(report, db), db)
    if out is None:
        return

    # 결과를 저장할지 물어봄
    answer = input("이 결과를 신고 기록에 저장할까요? (y/n) ").strip().lower()
    if answer == "y":
        c = out["결론"]
        report.ai_risk = c["위험도"]
        report.ai_action = c["권고"]
        report.ai_summary = c["요약"]
        report.ai_grounds = json.dumps(c["근거"], ensure_ascii=False)
        report.ai_steps = json.dumps(
            [{"도구": s["도구"], "인자": s["인자"], "이유": s["이유"]} for s in out["단계"]],
            ensure_ascii=False,
        )
        report.ai_checked_at = datetime.utcnow()
        db.commit()
        print("저장했습니다.")


def test_tools(db):
    """도구가 하나씩 잘 도는지"""
    post = db.query(Post).first()
    if post is None:
        print("매물이 없습니다.")
        return

    print(LINE)
    print(f"도구 시험  —  {post.id}번 매물 '{post.title}'")
    print(LINE)

    cases = [
        ("매물_보기", post.id),
        ("판매자_이력", post.seller_id),
        ("사진_도용검사", post.id),
        ("채팅_기록", post.id),
        ("시세_견주기", post.id),
        ("신고자_이력", post.seller_id),
        ("계정_정지", post.id),        # 없는 도구 — 거절되어야 함
    ]

    for name, arg in cases:
        result = agent_tools.run_tool(name, arg, db)
        text = json.dumps(result, ensure_ascii=False)
        print(f"\n  {name}({arg})")
        print(f"    {text[:220]}")


def make_fake(db):
    """일부러 수상한 매물을 만들어 조사시켜봄.
    진짜 사기를 잡는지 확인하는 가장 확실한 방법"""
    seller = db.query(User).filter(User.username.like("demo%")).first()
    if seller is None:
        print("demo 계정이 없습니다. python seed_chats.py 를 먼저 돌리세요.")
        return

    post = Post(
        seller_id=seller.id,
        title="아이폰 15 프로 급처분",
        content=(
            "급하게 처분합니다. 선입금 후 택배거래만 가능합니다. "
            "직거래 불가하고 카톡아이디로 연락주세요. 계좌로 먼저 보내주시면 바로 부칩니다."
        ),
        price=50000,          # 시세보다 크게 낮게
        category="디지털기기",
        region="서울 강남구",
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    print(f"수상한 매물을 만들었습니다 — {post.id}번")
    print()

    run(f"{post.id}번 매물(판매자는 {seller.id}번 회원)이 "
        f"'사기 의심' 사유로 신고됐습니다. 신고자는 {seller.id}번 회원입니다.", db)

    answer = input("이 시험용 매물을 지울까요? (y/n) ").strip().lower()
    if answer == "y":
        db.delete(post)
        db.commit()
        print("지웠습니다.")


def compare_modes(db):
    """혼자 조사와 셋이 조사를 나란히 돌려 견줌"""
    post = db.query(Post).filter(Post.status != "거래완료").first()
    if post is None:
        print("매물이 없습니다.")
        return

    question = (f"{post.id}번 매물(판매자는 {post.seller_id}번 회원)을 점검해주세요.")

    for mode, label in (("solo", "혼자 조사"),
                        ("team", "셋이 나눠 조사"),
                        ("debate", "검사·변호인·정리")):
        print()
        print("#" * 60)
        print(f"#  {label}")
        print("#" * 60)
        run(question, db, mode=mode)


def more_check(report_id: int, db):
    """이미 조사한 신고에서 안 본 것만 더 조사"""
    import json
    import follow_up

    report = db.get(Report, report_id)
    if report is None:
        print(f"{report_id}번 신고가 없습니다.")
        return
    if not report.ai_checked_at:
        print("아직 조사하지 않은 신고입니다. 먼저 조사하세요.")
        return

    cov = json.loads(report.ai_coverage) if report.ai_coverage else {}
    missing = cov.get("확인못함", [])

    if not missing:
        print("이미 모든 도구를 확인했습니다.")
        return

    print(f"확인 못한 것: {', '.join(missing)}")
    print("이것들을 더 조사합니다…")
    print()

    before = len(json.loads(report.ai_steps or "[]"))
    out = follow_up.run(report, missing, db)

    if "오류" in out:
        print("오류:", out["오류"])
        return

    print(f"  {before}걸음 → {len(out['단계'])}걸음 ({out['보충']['걸린시간']}초)")
    print()
    print(LINE)
    print(f"결론  {out['결론']['위험도']} ({out['결론']['총점']}점) / {out['결론']['권고']}")
    print(LINE)
    for h in out["채점"]["신호"]:
        print(f"    +{h['점수']}  {h['신호']:22} {h['설명']}")
    print()

    answer = input("이 결과를 저장할까요? (y/n) ").strip().lower()
    if answer == "y":
        follow_up.save(report, out, db)
        print("저장했습니다.")


def need_ollama() -> bool:
    """Ollama 가 준비됐는지 미리 확인.

    없으면 긴 오류를 토해내는 대신 무엇을 해야 하는지 한 줄로 알려줌
    """
    if query_ai.is_ready():
        return True

    print()
    print("Ollama 를 쓸 수 없어 조사를 돌릴 수 없습니다.")
    print()
    print("  1) 새 터미널을 열고:   ollama serve")
    print("  2) 모델이 없다면:      ollama pull gemma3:12b")
    print("  3) 확인:               curl http://localhost:11434/api/tags")
    print()
    print("서버 없이도 되는 것 —")
    print("  python check_agent.py           신고 목록 보기")
    print("  python check_agent.py --tools   도구만 시험")
    print()
    return False


def main():
    db = SessionLocal()
    try:
        args = sys.argv[1:]

        if not args:
            show_reports(db)
        elif args[0] == "--tools":
            test_tools(db)
        elif args[0] == "--fake":
            if need_ollama():
                make_fake(db)
        elif args[0] == "--team":
            if need_ollama():
                compare_modes(db)
        elif args[0] == "--note" and len(args) > 1:
            if not need_ollama():
                return
            post = db.query(Post).filter(Post.status != "거래완료").first()
            if post is None:
                print("매물이 없습니다.")
                return
            run(f"{post.id}번 매물(판매자는 {post.seller_id}번 회원)을 점검해주세요.",
                db, note=args[1])
        elif args[0] == "--more" and len(args) > 1:
            if need_ollama():
                more_check(int(args[1]), db)
        elif args[0] == "--debate":
            if need_ollama():
                post = db.query(Post).filter(Post.status != "거래완료").first()
                if post is None:
                    print("매물이 없습니다.")
                    return
                run(f"{post.id}번 매물(판매자는 {post.seller_id}번 회원)을 점검해주세요.",
                    db, mode="debate")
        elif args[0] == "post" and len(args) > 1:
            if not need_ollama():
                return
            post = db.get(Post, int(args[1]))
            if post is None:
                print("그런 매물이 없습니다.")
                return
            run(f"{post.id}번 매물(판매자는 {post.seller_id}번 회원)을 점검해주세요.", db)
        elif args[0].isdigit():
            if need_ollama():
                run_report(int(args[0]), db)
        else:
            print(__doc__)
    finally:
        db.close()


if __name__ == "__main__":
    main()
