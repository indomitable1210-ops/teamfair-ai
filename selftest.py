"""헤드리스 자가 점검: DB, 데모 시드, 주차 상태, 팝업 트리거, 규칙 기반 검토/리포트, OpenAI 호환 클라이언트 생성."""
import os, tempfile, json
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "")  # 테스트는 항상 임시 SQLite. Postgres 로 돌리려면 TEST_DATABASE_URL 지정
os.environ["TEAMFAIR_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
import db, ai

db.init()
off = ai.LLM(None, "", "", enabled=False)
team = db.seed_demo(lambda **kw: ai.review_submission(off, **kw))
members = db.list_members(team["id"]); subs = db.list_submissions(team["id"]); exts = db.list_extensions(team["id"])
assert len(members) == 4 and len(subs) == 6, (len(members), len(subs))
assert db.current_week(team) == 3, db.current_week(team)
print("current week:", db.current_week(team))
for m in members:
    print(m["name"], m["role"], [db.week_status(team, m, w, subs, exts)["status"] for w in (1, 2, 3)])
pj = db.get_member(team["id"], "박지훈"); km = db.get_member(team["id"], "김민수")
a = db.pending_alert(team, pj, subs, exts); assert a and a["week"] == 1 and not a["ext_used"], a
assert db.pending_alert(team, km, subs, exts) is None
print("popup for 박지훈 -> week", a["week"])
# 아니요 → 하루 연장
db.grant_extension(team["id"], pj["id"], 1, db.team_now(team) + __import__("datetime").timedelta(days=1))
exts = db.list_extensions(team["id"])
assert db.week_status(team, pj, 1, subs, exts)["status"] == "extended"
a2 = db.pending_alert(team, pj, subs, exts); assert a2 and a2["week"] == 2, a2
print("after extension: week1 extended, next popup week", a2["week"])
# 시간 +2일 → 연장 만료 → 다시 1주차 missed, ext_used True
db.update_team(team["id"], sim_offset_days=2); team = db.get_team(team["code"])
a3 = db.pending_alert(team, pj, subs, exts); assert a3["week"] == 1 and a3["ext_used"], a3
print("after +2d: week1 missed again, ext_used =", a3["ext_used"])
# 부실 제출 → 미인정 / 성실 제출 → 인정
bad = ai.review_submission(off, member="박지훈", role=pj["role"], goal=pj["goals"][0], week=1, text="열심히 했어요", link="", filename="")
good = ai.review_submission(off, member="박지훈", role=pj["role"], goal=pj["goals"][0], week=1, link="https://forms.gle/x", filename="",
    text="설문 문항 15개 초안 작성 완료. 인구통계 4문항, 이용행태 6문항, 만족도 5문항(5점 척도)으로 구성했고 구글폼으로 만들어 링크 첨부합니다. 파일럿 3명 응답 확인.")
print("bad ->", bad["verdict"]["verdict"], "| good ->", good["verdict"]["verdict"], good["verdict"]["score"])
assert bad["verdict"]["verdict"] == "미인정" and good["verdict"]["verdict"] in ("인정", "조건부 인정")
db.add_submission(team["id"], pj["id"], 1, text="x", link="", filename="", score=good["verdict"]["score"], verdict=good["verdict"]["verdict"], review=good)
subs = db.list_submissions(team["id"])
assert db.week_status(team, pj, 1, subs, exts)["status"] in ("done", "conditional")
# F 동의
db.mark_f(pj["id"], True); pj = db.get_member(team["id"], "박지훈")
assert pj["status"] == "F" and db.pending_alert(team, pj, subs, exts) is None
print("F agreed -> no more popups, status F")
# 리포트
rep = ai.build_report(off, team={**team, "current_week": 3}, members=db.list_members(team["id"]),
    submissions=[{"member": s["member"], "week": s["week"], "verdict": s["verdict"], "score": s["score"]} for s in subs], extensions=exts)
assert abs(sum(c["percent"] for c in rep["contribution"]) - 100) <= 2
print("report:", [(c["name"], c["percent"]) for c in rep["contribution"]])
# 백업 왕복
payload = db.export_team(team); t2 = db.import_team(payload); assert len(db.list_submissions(t2["id"])) == len(subs)
# 역할 설계(규칙) + 플랜 저장
plan = ai.plan_roles(off, "수업", "과제", ["a", "b", "c"], 5); assert all(len(m["weekly_goals"]) == 5 for m in plan["members"])
# OpenAI 호환 클라이언트 생성 + 인터페이스 존재 확인
llm = ai.LLM("http://127.0.0.1:9/v1", "EMPTY", "test-model"); assert llm.available and hasattr(llm.client.chat.completions, "create")
try:
    llm.ping(); print("unexpected success")
except Exception as e:
    print("client ok; connection error as expected:", type(e).__name__)
print("ALL SELFTESTS PASSED")

# ── 추가 기능: 유사도(재탕·복붙) 감지 + 주간 브리핑
prior = [{"member": "이서연", "week": 2, "text": "GS25·CU·세븐일레븐 앱 평가 완료. 항목별 점수표와 스크린샷 18장, 주요 문제점 12건을 정리했습니다. 세븐일레븐 결제 단계가 가장 길었습니다(7단계).", "link": "https://a"},
         {"member": "최유진", "week": 1, "text": "발표 스토리라인 10슬라이드 구성안과 디자인 템플릿(브랜드 컬러 3종) 초안을 만들었습니다. 피그마 링크.", "link": "https://b"}]
copy = ai.review_submission(off, member="박지훈", role="설문", goal="설문 문항", week=2, link="", filename="",
    text="GS25·CU·세븐일레븐 앱 평가 완료. 항목별 점수표와 스크린샷 18장, 주요 문제점 12건을 정리했습니다. 세븐일레븐 결제 단계가 가장 길었습니다(7단계).", prior=prior)
assert copy["verdict"]["verdict"] == "미인정" and copy["similarity"][0]["kind"] == "복붙", copy["verdict"]
rehash = ai.review_submission(off, member="최유진", role="PPT", goal="PPT", week=2, link="https://new", filename="",
    text="발표 스토리라인 10슬라이드 구성안과 디자인 템플릿(브랜드 컬러 3종) 초안을 만들었습니다. 피그마 링크.", prior=prior)
assert rehash["verdict"]["verdict"] == "미인정" and rehash["similarity"][0]["kind"] in ("재탕", "링크만 변경"), rehash["verdict"]
fresh = ai.review_submission(off, member="최유진", role="PPT", goal="PPT 1~8장", week=2, link="https://c", filename="",
    text="PPT 1~8장 제작 완료(표지·목차·문제정의·분석 프레임·3사 개요). 서연님 스크린샷 12장 반영했고 색상 가이드 통일했습니다.", prior=prior)
assert fresh["verdict"]["verdict"] == "인정" and not fresh["similarity"], fresh["verdict"]
print("similarity: copy ->", copy["similarity"][0]["kind"], copy["similarity"][0]["ratio"], "| rehash ->", rehash["similarity"][0]["kind"], "| fresh -> 인정")
rows = [{"name": "김민수", "role": "총괄", "status_label": "✅ 70점", "goal": "g", "next_goal": "통합", "verdict": "인정", "score": 70, "summary": "목차 7장 확정", "text": ""},
        {"name": "박지훈", "role": "설문", "status_label": "❌ 미제출", "goal": "g", "next_goal": "수집", "verdict": None, "score": None, "summary": "", "text": ""}]
b = ai.weekly_briefing(off, team=team, week=1, members=[], week_rows=rows)
assert "박지훈" in b["headline"] and b["risks"] and b["waiting_on"], b
db.save_briefing(team["id"], 1, b); assert db.get_briefing(team["id"], 1)["headline"] == b["headline"]
print("briefing:", b["headline"], "| waiting:", b["waiting_on"][0])
print("ALL SELFTESTS PASSED (incl. similarity + briefing)")

# ── 추가 기능: 이메일 계정 / 로그인 세션 / 팀원-계정 연결 / 첨부 파일 DB 저장
u = db.register_user("Minsu@Univ.ac.kr", "김민수", "secret1"); assert u["email"] == "minsu@univ.ac.kr"
for bad in [("x", "a", "secret1"), ("a@b.c", "", "secret1"), ("a@b.c", "a", "123"), ("minsu@univ.ac.kr", "a", "secret1")]:
    try:
        db.register_user(*bad); raise AssertionError(bad)
    except ValueError:
        pass
assert db.verify_login("minsu@univ.ac.kr", "wrong") is None and db.verify_login("minsu@univ.ac.kr", "secret1")["name"] == "김민수"
tok = db.create_session("minsu@univ.ac.kr"); assert db.user_by_session(tok)["email"] == "minsu@univ.ac.kr"
assert db.user_by_session("nope") is None
db.delete_session(tok); assert db.user_by_session(tok) is None
t3 = db.create_team(course="c", name="n", assignment="a", start_date=__import__("datetime").date.today(), weeks=2, leader="김민수",
                    members=["김민수", "이서연", "박지훈"], emails={"김민수": "minsu@univ.ac.kr"})
assert db.member_by_email(t3["id"], "MINSU@univ.ac.kr")["name"] == "김민수"
assert [t["my_name"] for t in db.teams_for_email("minsu@univ.ac.kr")] == ["김민수"]
db.claim_member(t3["id"], "이서연", "seo@univ.ac.kr")
for bad in [("이서연", "other@x.com"), ("박지훈", "seo@univ.ac.kr"), ("없는사람", "z@x.com")]:
    try:
        db.claim_member(t3["id"], *bad); raise AssertionError(bad)
    except ValueError:
        pass
fn1 = db.save_file(t3["id"], "T_w1_김민수_a.txt", b"hello"); fn2 = db.save_file(t3["id"], "T_w1_김민수_a.txt", b"world")
assert fn1 != fn2 and db.get_file(fn1) == b"hello" and db.get_file(fn2) == b"world" and db.get_file("none") is None
try:
    db.save_file(t3["id"], "big.bin", b"0" * (db.MAX_FILE_BYTES + 1)); raise AssertionError("size limit")
except ValueError:
    pass
db.delete_team(t3["id"]); assert db.get_file(fn1) is None
print("auth/session/claim/attachments ok ·", db.storage_label())
print("ALL SELFTESTS PASSED (incl. auth)")

# 계정 기능: 잠금 / 비밀번호 변경 / 복구 코드 재설정 / 이름 변경 / 모든 기기 로그아웃 / 탈퇴
u2 = db.register_user("lock@univ.ac.kr", "잠금", "secret1"); rc = u2["recovery_code"]; assert len(rc) == 9 and rc[4] == "-", rc
for _ in range(db.LOCK_AFTER):
    assert db.verify_login("lock@univ.ac.kr", "wrong") is None
assert db.login_lock_remaining("lock@univ.ac.kr") > 0 and db.verify_login("lock@univ.ac.kr", "secret1") is None, "locked even with right pw"
# 복구 코드로 재설정 → 잠금 해제 + 새 코드 + 세션 전부 종료
tk = db.create_session("lock@univ.ac.kr")
try:
    db.reset_password_with_code("lock@univ.ac.kr", "WRONG-CODE", "newpass1"); raise AssertionError("bad code accepted")
except ValueError:
    pass
rc2 = db.reset_password_with_code("lock@univ.ac.kr", rc.lower().replace("-", " "), "newpass1")
assert rc2 != rc and db.user_by_session(tk) is None and db.login_lock_remaining("lock@univ.ac.kr") == 0
assert db.verify_login("lock@univ.ac.kr", "secret1") is None and db.verify_login("lock@univ.ac.kr", "newpass1")
try:
    db.reset_password_with_code("lock@univ.ac.kr", rc, "x" * 8); raise AssertionError("old code still valid")
except ValueError:
    pass
# 비밀번호 변경
for bad in [("wrong", "another1"), ("newpass1", "newpass1"), ("newpass1", "123")]:
    try:
        db.change_password("lock@univ.ac.kr", *bad); raise AssertionError(bad)
    except ValueError:
        pass
db.change_password("lock@univ.ac.kr", "newpass1", "final123"); assert db.verify_login("lock@univ.ac.kr", "final123")
# 복구 코드 재발급
rc3 = db.regenerate_recovery_code("lock@univ.ac.kr", "final123"); assert rc3 != rc2
try:
    db.regenerate_recovery_code("lock@univ.ac.kr", "nope"); raise AssertionError("regen without pw")
except ValueError:
    pass
# 이름 변경 / 세션 수 / 모든 기기 로그아웃
assert db.rename_user("lock@univ.ac.kr", "  새이름 ")["name"] == "새이름"
t1, t2 = db.create_session("lock@univ.ac.kr"), db.create_session("lock@univ.ac.kr"); assert db.count_sessions("lock@univ.ac.kr") == 2
assert db.delete_all_sessions("lock@univ.ac.kr") == 2 and db.user_by_session(t1) is None and db.count_sessions("lock@univ.ac.kr") == 0
# 탈퇴: 팀원 연결 해제 + 계정/세션 삭제, 팀 기록은 유지
t4 = db.create_team(course="c", name="n", assignment="a", start_date=__import__("datetime").date.today(), weeks=1, leader="새이름",
                    members=["새이름", "동료"], emails={"새이름": "lock@univ.ac.kr"})
db.create_session("lock@univ.ac.kr")
try:
    db.delete_user("lock@univ.ac.kr", "wrong"); raise AssertionError("delete without pw")
except ValueError:
    pass
assert db.delete_user("lock@univ.ac.kr", "final123") == 1
assert db.get_user("lock@univ.ac.kr") is None and db.count_sessions("lock@univ.ac.kr") == 0
assert db.get_member(t4["id"], "새이름") and db.get_member(t4["id"], "새이름")["email"] is None
assert db.register_user("lock@univ.ac.kr", "재가입", "secret1")  # 탈퇴 후 같은 이메일로 재가입 가능
db.delete_team(t4["id"])
print("account features ok · ALL SELFTESTS PASSED (incl. lock/reset/change/rename/delete)")
