import os, tempfile
os.environ["TEAMFAIR_DB"] = os.path.join(tempfile.mkdtemp(), "ui.db")
from streamlit.testing.v1 import AppTest
import db
at = AppTest.from_file("app.py", default_timeout=90)
at.run(); assert not at.exception, at.exception
print("landing ok; buttons:", [b.label for b in at.button][:6])
demo = [b for b in at.button if "데모 팀" in b.label][0]
demo.click().run(); assert not at.exception, at.exception
print("session:", at.session_state["team_code"], at.session_state["me"])
print("titles:", [t.value for t in at.title]); print("metrics:", [(m.label, m.value) for m in at.metric])
print("tabs:", [t.label for t in at.tabs]); print("errors:", [e.value for e in at.error])
# 팀장으로 전환
at.session_state["me"] = "김민수"; at.run(); assert not at.exception, at.exception
print("as leader ok; selectboxes:", [s.label for s in at.selectbox][:5])
# 리포트 생성 버튼
rep = [b for b in at.button if "리포트 생성" in b.label][0]; rep.click().run(); assert not at.exception, at.exception
print("report metrics:", [(m.label, m.value) for m in at.metric if "%" in str(m.value)])
bb = [b for b in at.button if "브리핑 생성" in b.label][0]; bb.click().run(); assert not at.exception, at.exception
print("briefing rendered:", any("브리핑" in m.value for m in at.markdown))
print("UI TEST PASSED")

# ── 로그인 흐름: 회원가입 → 내 팀 없음 → 팀 만들기 → 입장 → 로그아웃
at2 = AppTest.from_file("app.py", default_timeout=90); at2.run(); assert not at2.exception, at2.exception
assert any("로그인" in t.label for t in at2.tabs), [t.label for t in at2.tabs]
su = at2.text_input(key="su_email"); su.input("kim@univ.ac.kr")
at2.text_input(key="su_pw1").input("secret1"); at2.text_input(key="su_pw2").input("secret1")
[t for t in at2.text_input if "이름" in t.label][0].input("김민수")
[b for b in at2.button if "가입하고" in b.label][0].click().run(); assert not at2.exception, at2.exception
assert at2.session_state["user"]["email"] == "kim@univ.ac.kr", at2.session_state
print("signup ok; token in URL:", bool(at2.query_params.get("s")))
# 팀 만들기 폼
ta = {t.label: t for t in at2.text_area}; ti = {t.label: t for t in at2.text_input}
ti["팀플 수업 이름"].input("경영정보시스템"); ti["팀 이름"].input("7조")
[t for l, t in ta.items() if "구성원" in l][0].input("김민수, kim@univ.ac.kr\n이서연, seo@univ.ac.kr\n박지훈")
[t for l, t in ta.items() if "과제" in l][0].input("편의점 앱 UX 비교 보고서")
[b for b in at2.button if "팀 만들기" in b.label][0].click().run(); assert not at2.exception, at2.exception
assert at2.session_state["me"] == "김민수" and at2.session_state.get("team_code"), dict(at2.session_state)
print("team created as leader; tabs:", [t.label for t in at2.tabs][:3])
# 로그아웃 → 다시 로그인 화면
[b for b in at2.button if b.label == "로그아웃"][0].click().run(); assert not at2.exception, at2.exception
assert "user" not in at2.session_state and any("로그인" in t.label for t in at2.tabs)
# 다른 계정으로 가입 후 초대 코드로 참여 → 비어 있는 이름만 선택 가능
code = db.teams_for_email("kim@univ.ac.kr")[0]["code"]
at2.text_input(key="su_email").input("park@univ.ac.kr"); at2.text_input(key="su_pw1").input("secret1"); at2.text_input(key="su_pw2").input("secret1")
[t for t in at2.text_input if "이름" in t.label][0].input("박지훈")
[b for b in at2.button if "가입하고" in b.label][0].click().run(); assert not at2.exception, at2.exception
[t for t in at2.text_input if t.label == "초대 코드"][0].input(code); at2.run(); assert not at2.exception, at2.exception
sel = [s for s in at2.selectbox if "내 이름" in s.label][0]; assert sel.options == ["박지훈"], sel.options
[b for b in at2.button if "연결하고 입장" in b.label][0].click().run(); assert not at2.exception, at2.exception
assert at2.session_state["me"] == "박지훈"
print("joined by code as 박지훈 (이서연/김민수 locked) · UI AUTH TEST PASSED")
