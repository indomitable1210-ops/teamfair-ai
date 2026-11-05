import os, tempfile
os.environ["TEAMFAIR_DB"] = os.path.join(tempfile.mkdtemp(), "ui.db")
from streamlit.testing.v1 import AppTest
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
