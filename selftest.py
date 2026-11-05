"""헤드리스 자가 점검: DB, 데모 시드, 주차 상태, 팝업 트리거, 규칙 기반 검토/리포트, OpenAI 호환 클라이언트 생성."""
import os, tempfile, json
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
