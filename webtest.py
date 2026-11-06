"""Vercel 웹 서버(api/index.py) 헤드리스 테스트: 실제 HTTP 요청으로 전체 흐름 확인. 임시 SQLite 사용."""
import os, re, sys, tempfile
os.environ["TEAMFAIR_NO_ENV_LOCAL"] = "1"  # 공용 AI 키 예산 보호: 테스트는 규칙 기반
os.environ["TEAMFAIR_FORCE_SQLITE"] = "1"
os.environ["TEAMFAIR_DB"] = os.path.join(tempfile.mkdtemp(), "web.db")
for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "TILON_API_KEY"):
    os.environ.pop(k, None)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "web"))
from fastapi.testclient import TestClient
import index, db

c = TestClient(index.app)
ok = lambda r, *must: [(_ for _ in ()).throw(AssertionError((r.status_code, m, r.text[:600]))) for m in must if m not in r.text] or r

r = c.get("/"); ok(r, "팀플에 참여하지", "아니요, 참여할게요", 'href="/start"'); assert "비밀번호 찾기" not in r.text
r = c.get("/start"); ok(r, "로그인", "회원가입", "비밀번호 찾기", "데모 팀")
ok(c.get("/"), "아니요, 참여할게요")  # 로그인 전에는 첫 주소로 올 때마다 시작화면
ok(c.get("/intro"), "아니요, 참여할게요")
for pth, mime in (("/icon-32.png", "image/png"), ("/icon-180.png", "image/png"), ("/favicon.ico", "image/x-icon")):
    rr = c.get(pth); assert rr.status_code == 200 and rr.headers["content-type"].startswith(mime) and len(rr.content) > 500, pth
ok(c.get("/intro"), 'href="/icon-32.png"', 'src="/icon-180.png"')
print("splash ok")
assert c.get("/healthz").json()["storage"].startswith("SQLite")

# 데모: 로그인 없이 → 박지훈 팝업
r = c.post("/demo"); assert r.status_code == 200, r.status_code; ok(r, "팀플에 참여하지 않으시겠습니까?", "박지훈")
r = c.get("/t/DEMO01?pd=confirm"); ok(r, "혼자 F를 받는 것에 동의한다는 건가요?")
r = c.post("/t/DEMO01/peace/no"); ok(r, "하루 연장")          # 1주차 연장 → 2주차 팝업
ok(c.get("/t/DEMO01"), "2주차</b> 작업물")
for tab in ("board", "upload", "roles", "report", "logs", "tools"):
    assert c.get(f"/t/DEMO01?tab={tab}&snooze=1").status_code == 200, tab
r = c.post("/t/DEMO01/briefing", data={"week": "2"}); ok(r, "브리핑을 만들었습니다", "박지훈")
r = c.post("/t/DEMO01/report"); ok(r, "보고서 .md 다운로드", "%")
# 복붙 제출 → 미인정 + 유사도
copy = "GS25·CU·세븐일레븐 앱 평가 완료. 항목별 점수표와 스크린샷 18장, 주요 문제점 12건을 정리했습니다. 세븐일레븐 결제 단계가 가장 길었습니다(7단계)."
r = c.post("/t/DEMO01/submit", data={"week": "2", "text": copy, "link": ""}); ok(r, "미인정", "복붙")
# 성실 제출 + 파일 → 인정, 파일 다운로드
good = "설문 문항 15개 초안 작성 완료. 인구통계 4문항, 이용행태 6문항, 만족도 5문항(5점 척도)으로 구성했고 구글폼으로 만들어 링크 첨부합니다. 파일럿 3명 응답 확인."
r = c.post("/t/DEMO01/submit", data={"week": "1", "text": good, "link": "https://forms.gle/x"}, files={"file": ("설문 초안.txt", "문항 목록".encode())})
assert re.search(r"판정: (인정|조건부 인정)", r.text), r.text[:500]
fn = re.search(r'href="/file/([^"]+)"', c.get("/t/DEMO01?snooze=1").text).group(1)
assert c.get(f"/file/{fn}").content == "문항 목록".encode()
# 시간 이동·내보내기·로그
ok(c.post("/t/DEMO01/time", data={"delta": "7"}), "오프셋 7일")
assert c.get("/t/DEMO01/export.json").json()["team"]["code"] == "DEMO01"
# 다른 팀원으로 전환 → F 동의 흐름
c.post("/t/DEMO01/time", data={"delta": "0"})
r = c.post("/t/DEMO01/as", data={"name": "박지훈"})
ok(c.get("/t/DEMO01?pd=sign"), "학점 포기 동의 서약서", "F 학점을 받는 것에 동의", "sigpad")
import base64; sig = "data:image/png;base64," + base64.b64encode(b"PNGDATA" + b"0" * 400).decode()
ok(c.post("/t/DEMO01/peace/agree", data={"signed_name": "박지훈", "signature": "", "agree": "1", "week": "1"}), "자필 서명을 해 주세요")
ok(c.post("/t/DEMO01/peace/agree", data={"signed_name": "김민수", "signature": sig, "agree": "1", "week": "1"}), "본인 이름(박지훈)")
ok(c.post("/t/DEMO01/peace/agree", data={"signed_name": "박지훈", "signature": sig, "week": "1"}), "동의에 체크")
r = c.post("/t/DEMO01/peace/agree", data={"signed_name": "박지훈", "signature": sig, "agree": "1", "week": "1"}); ok(r, "서약서에 서명이 완료되었습니다", "서명한 서약서 보기")
pj = db.get_member(db.get_team("DEMO01")["id"], "박지훈")
ok(c.get(f"/t/DEMO01/oath/{pj['id']}"), "학점 포기 동의 서약서", "1주차", "박지훈", sig[:60])
ok(c.get("/t/DEMO01?snooze=1"), "학점 포기 서약서 보기")
assert c.get(f"/t/DEMO01/oath/{db.get_member(pj['team_id'], '김민수')['id']}").status_code == 404
print("oath sign flow ok")
ok(c.get("/t/DEMO01?tab=upload"), "F 동의 상태에서는 제출할 수 없습니다")
print("demo flow ok")

# 회원가입 → 복구 코드 → 팀 만들기
k = TestClient(index.app)
r = k.post("/signup", data={"name": "김민수", "email": "kim@univ.ac.kr", "pw1": "secret1", "pw2": "secret1"})
ok(r, "가입 완료", "복구 코드를 지금 적어 두세요")
code = re.search(r'class="code-big">([A-Z0-9-]+)<', r.text).group(1)
r = k.post("/ack-recovery"); assert "복구 코드를 지금" not in r.text
r = k.post("/teams", data={"course": "경영정보시스템", "tname": "7조", "members": "김민수, kim@univ.ac.kr\n이서연\n박지훈",
                           "assignment": "편의점 앱 UX 비교 보고서", "weeks": "3", "sdate": "", "use_ai": "1"})
ok(r, "팀이 만들어졌습니다", "팀장")
tcode = re.search(r"초대 코드 ([A-Z0-9]{6})", r.text).group(1)
ok(k.get("/"), "내 팀", tcode)
# 팀장 역할 수정
mid = db.get_member(db.get_team(tcode)["id"], "이서연")["id"]
ok(k.post(f"/t/{tcode}/role/{mid}", data={"role": "UX 분석", "role_desc": "평가", "goal": ["a", "b", "c"]}), "역할을 저장했습니다")
assert db.get_member(db.get_team(tcode)["id"], "이서연")["goals"] == ["a", "b", "c"]

# 다른 사람: 로그인 없이 팀 접근 불가 → 가입 → 코드로 참여(빈 이름만)
p = TestClient(index.app)
ok(p.get(f"/t/{tcode}"), "로그인이 필요합니다")
p.post("/signup", data={"name": "박지훈", "email": "park@univ.ac.kr", "pw1": "secret1", "pw2": "secret1"})
r = p.get(f"/join?code={tcode}"); ok(r, "<option selected>박지훈</option>"); assert "김민수</option>" not in r.text
ok(p.post(f"/t/{tcode}/claim", data={"name": "박지훈"}), "박지훈 으로 연결되었습니다")
ok(p.post(f"/t/{tcode}/role/{mid}", data={"role": "x"}), "팀장만 수정할 수 있습니다")
q = TestClient(index.app); q.post("/signup", data={"name": "누군가", "email": "q@x.com", "pw1": "secret1", "pw2": "secret1"})
ok(q.post(f"/t/{tcode}/claim", data={"name": "박지훈"}), "이미 다른 계정과 연결")
print("team create/join ok")

# 계정: 로그인 실패 잠금, 비밀번호 변경, 복구 코드 찾기, 재발급, 이름 변경, 모든 기기 로그아웃, 탈퇴
x = TestClient(index.app)
for _ in range(db.LOCK_AFTER):
    r = x.post("/login", data={"email": "kim@univ.ac.kr", "pw": "bad"})
ok(r, "잠겼습니다")
ok(x.post("/login", data={"email": "kim@univ.ac.kr", "pw": "secret1"}), "잠겨 있습니다")
r = x.post("/reset", data={"email": "kim@univ.ac.kr", "code": "AAAA-BBBB", "pw1": "newpass1", "pw2": "newpass1"}); ok(r, "복구 코드가 올바르지")
r = x.post("/reset", data={"email": "kim@univ.ac.kr", "code": code, "pw1": "newpass1", "pw2": "newpass1"}); ok(r, "재설정하고 로그인", "복구 코드를 지금")
ok(k.get("/?tab=login"), "회원가입")  # 기존 기기 세션은 재설정으로 종료
ok(x.post("/account/password", data={"cur": "nope", "n1": "final123", "n2": "final123"}), "현재 비밀번호가 올바르지")
ok(x.post("/account/password", data={"cur": "newpass1", "n1": "final123", "n2": "final123"}), "비밀번호를 변경했습니다")
ok(x.post("/account/recovery", data={"pw": "final123"}), "새 복구 코드를 발급", "code-big")
ok(x.post("/account/name", data={"name": "민수"}), "이름을 변경했습니다", "👤 민수")
ok(x.post("/account/logout-all"), "모든 기기에서 로그아웃")
ok(x.get("/account"), "로그인이 필요합니다")
x.post("/login", data={"email": "kim@univ.ac.kr", "pw": "final123"})
ok(x.post("/account/delete", data={"pw": "final123"}), "동의 체크가 필요")
ok(x.post("/account/delete", data={"pw": "final123", "sure": "1"}), "탈퇴가 완료")
assert db.get_user("kim@univ.ac.kr") is None and db.get_member(db.get_team(tcode)["id"], "김민수")["email"] is None
ok(c.get("/settings"), "LLM 제공자", "규칙 기반 모드")
print("WEB TEST PASSED")
