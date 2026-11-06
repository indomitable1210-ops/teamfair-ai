"""Vercel(FastAPI) 화면 템플릿. 배포 번들에 확실히 포함되도록 파이썬 모듈 안에 문자열로 둔다."""
from jinja2 import DictLoader, Environment, select_autoescape

BASE = r"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{% block title %}팀플 서약{% endblock %}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Nanum+Myeongjo:wght@400;700;800&display=swap">
<link rel="icon" type="image/png" href="/icon-32.png"><link rel="apple-touch-icon" href="/icon-180.png">
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#111827;--sub:#6b7280;--line:#e5e7eb;--brand:#4f46e5;--brand-ink:#fff;
--ok:#065f46;--ok-bg:#ecfdf5;--warn:#92400e;--warn-bg:#fffbeb;--bad:#991b1b;--bad-bg:#fef2f2;--info:#1e40af;--info-bg:#eff6ff}
*{box-sizing:border-box}html,body{margin:0}body{background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",sans-serif}
a{color:var(--brand)}.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:12px 20px;background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
.brand{font-weight:800;font-size:1.1rem;text-decoration:none;color:var(--ink)}.top nav{display:flex;gap:14px;align-items:center;flex-wrap:wrap;font-size:.9rem}
.top nav a{text-decoration:none}.who{color:var(--sub)}main{max-width:1120px;margin:0 auto;padding:20px 16px 60px}
footer{text-align:center;color:var(--sub);font-size:.8rem;padding:20px}
h1{font-size:1.6rem;margin:.2em 0 .3em}h2{font-size:1.25rem;margin:1.2em 0 .5em}h3{font-size:1.05rem;margin:1em 0 .4em}
.sub{color:var(--sub)}.small{color:var(--sub);font-size:.85rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:14px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.cols3{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
label{display:block;font-weight:600;font-size:.9rem;margin:10px 0 4px}
input[type=text],input[type=email],input[type=password],input[type=number],input[type=date],input[type=url],textarea,select{width:100%;padding:9px 11px;border:1px solid #d1d5db;border-radius:9px;font:inherit;background:#fff}
textarea{min-height:90px}input[type=file]{font:inherit}
.btn{display:inline-block;border:0;border-radius:9px;padding:9px 16px;font:inherit;font-weight:600;cursor:pointer;background:var(--brand);color:var(--brand-ink);text-decoration:none;text-align:center}
.btn.full{width:100%;margin-top:12px}.btn.ghost{background:#eef2ff;color:#3730a3}.btn.gray{background:#f3f4f6;color:#374151}.btn.danger{background:#dc2626}
.btn[disabled]{opacity:.5;cursor:not-allowed}button.link{background:none;border:0;color:var(--brand);cursor:pointer;font:inherit;padding:0}
form.inline{display:inline}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.alert{border-radius:10px;padding:11px 14px;margin:10px 0}.alert.success{background:var(--ok-bg);color:var(--ok)}
.alert.error{background:var(--bad-bg);color:var(--bad)}.alert.warn{background:var(--warn-bg);color:var(--warn)}.alert.info{background:var(--info-bg);color:var(--info)}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin:14px 0;overflow-x:auto}
.tabs a{padding:9px 14px;text-decoration:none;color:var(--sub);border-bottom:2px solid transparent;white-space:nowrap}
.tabs a.on{color:var(--ink);border-color:var(--brand);font-weight:700}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:10px 0}
.metric{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}.metric .k{color:var(--sub);font-size:.82rem}.metric .v{font-size:1.4rem;font-weight:800}
.member-card{border:1px solid var(--line);border-radius:14px;padding:14px 16px;background:#fff}
.member-card .nm{font-size:1.1rem;font-weight:700}.member-card .rl{color:#4b5563;font-size:.9rem}
.tag{display:inline-block;font-size:.75rem;padding:2px 8px;border-radius:999px;margin-left:6px;vertical-align:middle;background:#eef2ff;color:#3730a3}
.member-card.f{filter:grayscale(100%);opacity:.55;background:#f3f4f6}.member-card.f .nm{text-decoration:line-through}
.oath{font-size:.82rem;margin-top:6px;font-style:italic}
.tbl-wrap{overflow-x:auto}table.grid{width:100%;border-collapse:collapse;font-size:.92rem;background:#fff}
.grid th,.grid td{border-bottom:1px solid #eee;padding:8px 10px;text-align:center;white-space:nowrap}.grid th{background:#f9fafb}
.grid td:first-child,.grid th:first-child{text-align:left;font-weight:600}.grid tr.f td{filter:grayscale(100%);opacity:.5;text-decoration:line-through}
details{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:8px 0}summary{cursor:pointer;font-weight:600}
pre.code{background:#f3f4f6;border-radius:8px;padding:10px;white-space:pre-wrap;word-break:break-all;font-size:.85rem;max-height:420px;overflow:auto}
.code-big{font:700 1.6rem/1.2 ui-monospace,Consolas,monospace;letter-spacing:.08em;background:#fff;border:2px dashed #f59e0b;border-radius:10px;padding:12px;text-align:center;margin:8px 0}
.overlay{position:fixed;inset:0;background:rgba(17,24,39,.55);display:flex;align-items:center;justify-content:center;padding:16px;z-index:20}
.modal{background:#fff;border-radius:16px;max-width:520px;width:100%;padding:24px;box-shadow:0 20px 50px rgba(0,0,0,.3)}
.peace{font-size:1.5rem;font-weight:800;text-align:center;margin:14px 0 18px}.modal .row>*{flex:1}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:.8rem;background:#f3f4f6}
.modal.wide{max-width:680px;max-height:92vh;overflow:auto}
.oathdoc{background:#fffdf7;border:1px solid #d6cdb8;border-radius:6px;padding:22px 24px;margin:6px 0;color:#1f1a14;font-family:"Nanum Myeongjo","Batang",serif}
.od-title{text-align:center;font-size:1.5rem;font-weight:800;letter-spacing:.3em;margin-bottom:14px;border-bottom:2px double #1f1a14;padding-bottom:10px}
.od-meta{width:100%;border-collapse:collapse;font-size:.92rem;margin-bottom:10px}.od-meta th{background:#f3eee2;width:64px;font-weight:700}
.od-meta th,.od-meta td{border:1px solid #d6cdb8;padding:6px 8px;text-align:left}
.od-clauses{padding-left:1.3em;line-height:1.8;font-size:.95rem}.od-pledge{text-align:center;margin:12px 0 4px;font-weight:700}
.od-sign{display:flex;gap:18px;align-items:flex-end;justify-content:flex-end;flex-wrap:wrap;margin-top:14px}
.od-sigbox{position:relative;width:220px;height:90px;border-bottom:1.5px solid #1f1a14}.od-sigbox img{width:100%;height:100%;object-fit:contain}
.od-seal{position:absolute;right:-4px;bottom:4px;font-size:.8rem;color:#8a7f6c}
.sigpad{width:100%;height:150px;border:1.5px dashed #9ca3af;border-radius:10px;background:#fff;touch-action:none;cursor:crosshair;display:block}
@media print{.top,footer,.noprint{display:none!important}main{padding:0}.oathdoc{border:0}}
@media (max-width:600px){h1{font-size:1.35rem}.top{padding:10px 16px}}
</style></head><body>
<header class="top"><a class="brand" href="/"><img src="/icon-180.png" alt="" width="30" height="30" style="border-radius:50%;vertical-align:-8px;margin-right:6px">팀플 서약</a><nav>
{% if user %}<span class="who">👤 {{ user.name }}</span><a href="/account">내 계정</a><a href="/settings">AI 설정</a>
<form method="post" action="/logout" class="inline"><button class="link">로그아웃</button></form>
{% else %}<a href="/settings">AI 설정</a><a href="/">로그인 / 회원가입</a>{% endif %}
</nav></header>
<main>
{% if flash %}<div class="alert {{ flash[0] }}">{{ flash[1] }}</div>{% endif %}
{% block body %}{% endblock %}
</main>
<footer>💾 저장소: {{ storage }} · 🧠 {{ ai_status }}</footer>
</body></html>"""

AUTH = r"""{% extends "base.html" %}{% block body %}
<h1 style="display:flex;align-items:center;gap:12px"><img src="/icon-180.png" alt="" width="54" height="54" style="border-radius:50%">팀플 서약</h1>
<p style="font-size:1.25rem;margin:.2em 0 .1em"><b>기여는 기록으로, 평가는 공정하게.</b></p>
<p style="margin:0 0 .4em">역할 배분부터 기여도 리포트까지 AI가 함께합니다.</p>
<p class="small">이메일 계정으로 로그인하면 <b>내가 어느 팀의 누구인지</b>가 고정되어 다른 사람 이름으로 제출할 수 없습니다.</p>
<div class="cols">
<div class="card">
  <div class="tabs">
    <a href="/?tab=login" class="{{ 'on' if tab=='login' }}">🔑 로그인</a>
    <a href="/?tab=signup" class="{{ 'on' if tab=='signup' }}">✨ 회원가입</a>
    <a href="/?tab=reset" class="{{ 'on' if tab=='reset' }}">🔓 비밀번호 찾기</a>
  </div>
  {% if error %}<div class="alert error">{{ error }}</div>{% endif %}
  {% if tab == 'signup' %}
  <form method="post" action="/signup">
    <label>이름 (팀원 명단에 적힌 이름과 같게)</label><input type="text" name="name" maxlength="30" placeholder="예: 김민수" value="{{ form.name or '' }}" required>
    <label>이메일</label><input type="email" name="email" placeholder="name@univ.ac.kr" value="{{ form.email or '' }}" required>
    <label>비밀번호 ({{ pw_min }}자 이상)</label><input type="password" name="pw1" required>
    <label>비밀번호 확인</label><input type="password" name="pw2" required>
    <button class="btn full">가입하고 시작하기</button>
  </form>
  {% elif tab == 'reset' %}
  <p class="small">가입할 때 받은 <b>복구 코드</b>(예: 7KQF-M3PX)로 새 비밀번호를 설정합니다. 완료되면 모든 기기에서 로그아웃되고 새 복구 코드가 발급됩니다.</p>
  <form method="post" action="/reset">
    <label>이메일</label><input type="email" name="email" value="{{ form.email or '' }}" required>
    <label>복구 코드</label><input type="text" name="code" placeholder="XXXX-XXXX" required>
    <label>새 비밀번호 ({{ pw_min }}자 이상)</label><input type="password" name="pw1" required>
    <label>새 비밀번호 확인</label><input type="password" name="pw2" required>
    <button class="btn full">비밀번호 재설정</button>
  </form>
  <p class="small">복구 코드까지 잃어버렸다면 팀장에게 요청해 명단 연결을 풀고 새 계정으로 다시 가입하세요.</p>
  {% else %}
  <form method="post" action="/login">
    <label>이메일</label><input type="email" name="email" placeholder="name@univ.ac.kr" value="{{ form.email or '' }}" required>
    <label>비밀번호</label><input type="password" name="pw" required>
    <button class="btn full">로그인</button>
  </form>
  {% endif %}
</div>
<div>
  <div class="card">
    <h3 style="margin-top:0">🎬 바로 체험 (데모 팀)</h3>
    <p class="small">로그인 없이 체험할 수 있습니다. 4명 · 3주 과제 · 현재 3주차. <b>박지훈</b>은 한 번도 올리지 않아 입장하면 팝업이 뜹니다.</p>
    <form method="post" action="/demo"><button class="btn full ghost">데모 팀 생성하고 입장</button></form>
  </div>
  <div class="card">
    <b>어떻게 쓰나요?</b>
    <ol class="small" style="margin:.4em 0 0 1.1em;padding:0">
      <li>팀장이 가입 → <b>팀 만들기</b> (팀원 이름, 가능하면 이메일까지)</li>
      <li>팀원은 가입 → <b>초대 코드</b>로 참여 → 명단에서 내 이름 1회 연결</li>
      <li>매주 작업물 올리기 → AI 검토·판정 → 미제출이면 팝업</li>
    </ol>
  </div>
</div>
</div>
{% endblock %}"""

RECOVERY = r"""{% if recovery_code %}
<div class="alert warn"><b>복구 코드를 지금 적어 두세요.</b> 비밀번호를 잊으면 이 코드로만 되찾을 수 있습니다. 이 안내를 닫으면 다시 볼 수 없습니다. (잃어버리면 「내 계정」에서 재발급 가능)
<div class="code-big">{{ recovery_code }}</div>
<form method="post" action="/ack-recovery"><button class="btn">복구 코드를 안전한 곳에 저장했습니다</button></form></div>
{% endif %}"""

HOME = r"""{% extends "base.html" %}{% block body %}
{% include "recovery.html" %}
<h1 style="display:flex;align-items:center;gap:12px"><img src="/icon-180.png" alt="" width="54" height="54" style="border-radius:50%">팀플 서약</h1>
<p>안녕하세요, <b>{{ user.name }}</b> 님. 팀을 만들거나 초대 코드로 참여하세요.</p>
{% if my_teams %}<h2>📌 내 팀</h2><div class="cols3">
{% for t in my_teams %}<div class="card"><b>{{ t.course }} · {{ t.name }}</b><div class="small">나: {{ t.my_name }}{% if t.leader == t.my_name %} · 팀장{% endif %} · {{ t.weeks }}주 · 코드 {{ t.code }}</div>
<a class="btn full" href="/t/{{ t.code }}">입장</a></div>{% endfor %}</div>{% endif %}
<div class="cols">
<div class="card"><h2 style="margin-top:0">① 팀 만들기</h2>
{% if error %}<div class="alert error">{{ error }}</div>{% endif %}
<form method="post" action="/teams">
  <label>팀플 수업 이름</label><input type="text" name="course" placeholder="예: 경영정보시스템" value="{{ form.course or '' }}" required>
  <label>팀 이름</label><input type="text" name="tname" placeholder="예: 3조" value="{{ form.tname or '' }}" required>
  <label>구성원 (한 줄에 한 명 · 첫 번째가 팀장 · 이메일을 함께 적으면 자동 연결)</label>
  <textarea name="members" rows="5" placeholder="김민수, minsu@univ.ac.kr&#10;이서연, seoyeon@univ.ac.kr&#10;박지훈">{{ form.members or (user.name ~ ', ' ~ user.email ~ '\n') }}</textarea>
  <label>이 수업에서 함께 해야 하는 과제</label><textarea name="assignment" rows="3" placeholder="예: 국내 편의점 3사 앱 UX 비교 분석 보고서(10쪽) + 발표(10분)" required>{{ form.assignment or '' }}</textarea>
  <div class="cols3"><div><label>프로젝트 기간 (주)</label><input type="number" name="weeks" min="1" max="16" value="{{ form.weeks or 4 }}"></div>
  <div><label>시작일 (매주 이 요일이 마감)</label><input type="date" name="sdate" value="{{ form.sdate or today }}"></div></div>
  <label><input type="checkbox" name="use_ai" value="1" checked> AI로 역할·주차별 목표 자동 설계</label>
  <button class="btn full">팀 만들기 🚀</button>
</form></div>
<div><div class="card"><h2 style="margin-top:0">② 팀 참여하기</h2>
<form method="get" action="/join"><label>초대 코드</label><div class="row"><input type="text" name="code" placeholder="예: AB12CD" style="flex:1;text-transform:uppercase" required><button class="btn">확인</button></div></form></div>
<div class="card"><h3 style="margin-top:0">🎬 데모 팀 체험</h3><p class="small">박지훈으로 입장해 팝업을 바로 볼 수 있습니다.</p>
<form method="post" action="/demo"><button class="btn full ghost">데모 팀 생성하고 입장</button></form></div></div>
</div>
{% endblock %}"""

JOIN = r"""{% extends "base.html" %}{% block body %}
<h1>팀 참여하기</h1>
<div class="card" style="max-width:560px">
<p><b>{{ team.course }} · {{ team.name }}</b> <span class="small">· {{ team.weeks }}주 과제 · 코드 {{ team.code }}</span></p>
{% if error %}<div class="alert error">{{ error }}</div>{% endif %}
{% if mine %}<div class="alert success">이 팀에 <b>{{ mine.name }}</b> 으로 등록되어 있습니다.</div><a class="btn full" href="/t/{{ team.code }}">입장하기</a>
{% elif not free %}<div class="alert error">이 팀의 모든 이름이 이미 다른 계정과 연결되어 있습니다. 팀장에게 확인해 주세요.</div>
{% else %}<form method="post" action="/t/{{ team.code }}/claim"><label>명단에서 내 이름을 선택 (한 번 연결하면 바꿀 수 없습니다)</label>
<select name="name">{% for n in free %}<option {{ 'selected' if n == user.name }}>{{ n }}</option>{% endfor %}</select>
<button class="btn full">내 이름으로 연결하고 입장</button></form>{% endif %}
</div><a href="/">← 처음으로</a>
{% endblock %}"""

PICK = r"""{% extends "base.html" %}{% block body %}
<h1>{{ team.course }} · {{ team.name }}</h1>
<div class="card" style="max-width:520px"><p>체험할 팀원을 고르세요. <b>박지훈</b>을 고르면 미제출 팝업을 볼 수 있습니다.</p>
<form method="post" action="/t/{{ team.code }}/as"><select name="name">{% for m in members %}<option>{{ m.name }}</option>{% endfor %}</select><button class="btn full">입장</button></form></div>
{% endblock %}"""

ACCOUNT = r"""{% extends "base.html" %}{% block title %}내 계정 · 팀플 서약{% endblock %}{% block body %}
{% include "recovery.html" %}
<h1>⚙️ 내 계정</h1><p class="sub">{{ user.email }} · 가입 {{ (user.created_at or '')[:10] }}</p>
{% if error %}<div class="alert error">{{ error }}</div>{% endif %}
<div class="cols">
<div class="card"><h3 style="margin-top:0">이름 변경</h3><form method="post" action="/account/name">
<label>표시 이름</label><input type="text" name="name" maxlength="30" value="{{ user.name }}" required><button class="btn full">이름 변경</button></form>
<p class="small">팀 안에서 쓰는 이름은 팀원 명단의 이름을 따르며, 여기서 바꿔도 팀 명단은 바뀌지 않습니다.</p></div>
<div class="card"><h3 style="margin-top:0">비밀번호 변경</h3><form method="post" action="/account/password">
<label>현재 비밀번호</label><input type="password" name="cur" required>
<label>새 비밀번호 ({{ pw_min }}자 이상)</label><input type="password" name="n1" required>
<label>새 비밀번호 확인</label><input type="password" name="n2" required><button class="btn full">비밀번호 변경</button></form>
<p class="small">현재 로그인된 기기/브라우저: {{ n_sessions }}개</p>
<form method="post" action="/account/logout-all"><button class="btn gray full">모든 기기에서 로그아웃</button></form></div>
<div class="card"><h3 style="margin-top:0">복구 코드 재발급</h3><p class="small">복구 코드는 비밀번호를 잊었을 때 「비밀번호 찾기」에 쓰는 8자리 코드입니다. 재발급하면 이전 코드는 무효가 됩니다.</p>
<form method="post" action="/account/recovery"><label>비밀번호 확인</label><input type="password" name="pw" required><button class="btn full ghost">복구 코드 재발급</button></form></div>
<div class="card"><h3 style="margin-top:0">회원 탈퇴</h3><p class="small">탈퇴하면 계정과 로그인 정보가 삭제됩니다. 팀의 제출 기록은 팀원들을 위해 남지만, 내 계정과의 연결은 끊어집니다.</p>
<form method="post" action="/account/delete"><label>비밀번호</label><input type="password" name="pw" required>
<label><input type="checkbox" name="sure" value="1"> 위 내용을 이해했고 탈퇴에 동의합니다.</label><button class="btn full danger">회원 탈퇴</button></form></div>
</div>
{% endblock %}"""

SETTINGS = r"""{% extends "base.html" %}{% block title %}AI 설정 · 팀플 서약{% endblock %}{% block body %}
<h1>🧠 AI 설정</h1>
<div class="card" style="max-width:640px">
<p class="small">서버에 등록된 키가 있으면 비워둬도 AI 모드로 동작합니다. 여기서 넣은 키는 이 브라우저 쿠키에만 저장됩니다.</p>
<form method="post" action="/settings">
<label>LLM 제공자</label><select name="provider">{% for n in providers %}<option {{ 'selected' if n == cfg.provider }}>{{ n }}</option>{% endfor %}</select>
<p class="small">{% for n, p in provider_items %}<span data-p="{{ n }}">· <b>{{ n }}</b>: {{ p.help }}</span><br>{% endfor %}</p>
<label>Base URL (OpenAI 호환 엔드포인트, 비우면 제공자 기본값)</label><input type="text" name="base_url" value="{{ cfg.base_url_custom }}">
<label>모델 (비우면 제공자 기본값)</label><input type="text" name="model" value="{{ cfg.model_custom }}">
<label>API Key (비우면 서버 환경변수 사용)</label><input type="password" name="key" placeholder="{{ '저장된 키 있음' if cfg.has_cookie_key else '' }}">
<label><input type="checkbox" name="enabled" value="1" {{ 'checked' if cfg.enabled }}> AI 사용 (끄면 규칙 기반 모드)</label>
<div class="row" style="margin-top:12px"><button class="btn">저장</button><button class="btn gray" name="clear" value="1">브라우저 저장값 지우기</button></div>
</form>
<p>현재 상태: <b>{{ ai_status }}</b></p>
{% if llm_available %}<form method="post" action="/settings/ping"><button class="btn ghost">연결 테스트</button></form>{% endif %}
{% if ping %}<div class="alert {{ ping[0] }}">{{ ping[1] }}</div>{% endif %}
</div>
{% endblock %}"""

TEAM = r"""{% extends "base.html" %}{% block title %}{{ team.course }} · {{ team.name }} · 팀플 서약{% endblock %}{% block body %}
{% if modal %}<div class="overlay"><div class="modal {{ 'wide' if modal.step == 'sign' }}">
{% if modal.step == 'ask' %}
  <h3 style="margin-top:0">⚠️ 이번 주 작업물이 없습니다</h3>
  <p><b>{{ me.name }}</b> 님, <b>{{ modal.week }}주차</b> 작업물을 마감({{ modal.deadline }})까지 올리지 않으셨습니다.</p>
  <p class="small">이번 주 목표: {{ modal.goal }}</p>
  <div class="peace">팀플에 참여하지 않으시겠습니까?</div>
  <div class="row"><a class="btn danger" href="{{ base }}?pd=confirm">예</a>
  {% if modal.ext_used %}<button class="btn gray" disabled>아니요 (연장 기회 소진)</button>
  {% else %}<form method="post" action="{{ base }}/peace/no" style="flex:1"><button class="btn gray" style="width:100%">아니요</button></form>{% endif %}</div>
  {% if modal.ext_used %}<p class="small">이미 하루 연장을 사용했습니다. 지금 바로 작업물을 제출하면 팝업이 사라집니다.</p>
  <a class="btn full" href="{{ base }}?tab=upload&snooze=1">지금 올리러 가기</a>{% endif %}
{% elif modal.step == 'confirm' %}
  <div class="peace">혼자 F를 받는 것에 동의한다는 건가요?</div>
  <p class="small">'예'를 누르면 되돌릴 수 없으며, 팀 보드에서 이름이 흑백으로 표시되고 교수님께 별도 보고됩니다.</p>
  <div class="row"><a class="btn danger" href="{{ base }}?pd=sign">예</a>
  <a class="btn gray" href="{{ base }}">뒤로가기</a></div>
{% elif modal.step == 'sign' %}
  {% from "oathdoc.html" import oath_doc %}
  <p class="small" style="margin:0">마지막 단계입니다. 아래 서약서를 읽고 서명하면 F 처리됩니다.</p>
  {{ oath_doc(team, me, modal.week) }}
  <form method="post" action="{{ base }}/peace/agree" id="oathform">
    <input type="hidden" name="week" value="{{ modal.week }}"><input type="hidden" name="signature" id="sigdata">
    <label>서약자 이름 (본인 이름을 직접 입력)</label><input type="text" name="signed_name" placeholder="{{ me.name }}" autocomplete="off" required>
    <label>자필 서명 <button type="button" class="link" id="sigclear" style="font-weight:400;margin-left:8px">지우기</button></label>
    <canvas class="sigpad" id="sigpad"></canvas>
    <label><input type="checkbox" name="agree" value="1" required> 위 서약 내용에 동의하며, 학점 포기에 서명합니다.</label>
    <div class="row" style="margin-top:12px"><button class="btn danger" style="flex:1">서명하고 제출</button><a class="btn gray" href="{{ base }}?pd=confirm">뒤로가기</a></div>
  </form>
  <script>
  (function(){const c=document.getElementById('sigpad'),x=c.getContext('2d');let drawing=false,dirty=false;
  function fit(){const r=c.getBoundingClientRect(),d=window.devicePixelRatio||1;c.width=r.width*d;c.height=r.height*d;x.scale(d,d);x.lineWidth=2.4;x.lineCap='round';x.lineJoin='round';x.strokeStyle='#111';}
  fit();function p(e){const r=c.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top];}
  c.addEventListener('pointerdown',e=>{drawing=true;dirty=true;c.setPointerCapture(e.pointerId);const [a,b]=p(e);x.beginPath();x.moveTo(a,b);x.lineTo(a+.1,b+.1);x.stroke();});
  c.addEventListener('pointermove',e=>{if(!drawing)return;const [a,b]=p(e);x.lineTo(a,b);x.stroke();});
  ['pointerup','pointercancel','pointerleave'].forEach(t=>c.addEventListener(t,()=>{drawing=false;}));
  document.getElementById('sigclear').onclick=()=>{x.clearRect(0,0,c.width,c.height);dirty=false;};
  document.getElementById('oathform').addEventListener('submit',e=>{if(!dirty){e.preventDefault();alert('서명란에 자필 서명을 해 주세요.');return;}document.getElementById('sigdata').value=c.toDataURL('image/png');});})();
  </script>
{% else %}
  <div class="peace">서약서에 서명이 완료되었습니다.</div>
  <div class="member-card f"><div class="nm">{{ me.name }}</div><div class="oath">“F를 받겠습니다. 교수님께 따로 말씀드리는 것에 동의합니다.”</div></div>
  <div class="row" style="margin-top:12px"><a class="btn gray" href="{{ base }}/oath/{{ me.id }}">서명한 서약서 보기</a><a class="btn" href="{{ base }}">확인</a></div>
{% endif %}
</div></div>{% endif %}

<div class="row" style="justify-content:space-between"><h1>{{ team.course }} · {{ team.name }}</h1>
<span class="small">초대 코드 <b>{{ team.code }}</b> · 나: <b>{{ me.name }}</b>{% if is_leader %} · 팀장{% endif %}</span></div>
{% if is_demo %}<form method="post" action="{{ base }}/as" class="row small" style="margin-bottom:6px">체험 중인 팀원:
<select name="name" style="width:auto">{% for m in members %}<option {{ 'selected' if m.name == me.name }}>{{ m.name }}</option>{% endfor %}</select><button class="btn gray">전환</button></form>{% endif %}
<div class="metrics">
<div class="metric"><div class="k">현재 주차</div><div class="v">{{ cur_w }} / {{ team.weeks }}주</div></div>
<div class="metric"><div class="k">이번 주 마감</div><div class="v">{{ deadline_str }} <span class="small">{{ dday }}</span></div></div>
<div class="metric"><div class="k">이번 주 제출</div><div class="v">{{ done_cnt }} / {{ members|length }}명</div></div>
<div class="metric"><div class="k">가상 오늘</div><div class="v">{{ now_str }}</div></div>
</div>
<div class="tabs">
{% for key, label in tabs %}<a href="{{ base }}?tab={{ key }}" class="{{ 'on' if tab == key }}">{{ label }}</a>{% endfor %}
</div>

{% if tab == 'board' %}
<p><b>과제</b> · {{ team.assignment }}</p>
{% if team.advice %}<div class="alert info">🛡️ 팀 규칙 · {{ team.advice }}</div>{% endif %}
<div class="card">
<div class="row" style="justify-content:space-between"><h3 style="margin:0">🗞️ AI 주간 브리핑</h3>
<form method="post" action="{{ base }}/briefing" class="row"><select name="week" style="width:auto">{% for w in range(1, cur_w + 1) %}<option value="{{ w }}" {{ 'selected' if w == brief_w }}>{{ w }}주차</option>{% endfor %}</select>
<button class="btn">브리핑 생성/갱신</button></form></div>
{% if briefing %}
<p><b>{{ briefing.headline }}</b> <span class="small">· {{ brief_w }}주차 · {{ (briefing._created_at or '')[:16] }} · {{ 'LLM' if briefing.mode == 'llm' else '규칙 기반' }}</span></p>
<div class="cols"><div>
{% if briefing.done %}<b>✅ 이번 주 해낸 일</b><ul>{% for x in briefing.done %}<li>{{ x }}</li>{% endfor %}</ul>{% endif %}
{% if briefing.next_week_focus %}<b>🎯 다음 주 집중</b><ul>{% for x in briefing.next_week_focus %}<li>{{ x }}</li>{% endfor %}</ul>{% endif %}
</div><div>
{% if briefing.risks %}<b>⚠️ 위험 신호</b><ul>{% for x in briefing.risks %}<li>{{ x }}</li>{% endfor %}</ul>{% endif %}
{% if briefing.waiting_on %}<b>⏳ 기다리는 중</b><ul>{% for w in briefing.waiting_on %}<li>{{ w.who }} ← {{ w.for_whom }}: {{ w.what }}</li>{% endfor %}</ul>{% endif %}
</div></div>
{% if briefing.message_for_team %}<pre class="code">{{ briefing.message_for_team }}</pre>{% endif %}
{% else %}<p class="small">아직 이 주차 브리핑이 없습니다. 「브리핑 생성/갱신」을 누르면 제출물과 상태를 모아 요약합니다.</p>{% endif %}
</div>
<div class="cols3">{% for m in members %}
<div class="member-card {{ 'f' if m.status == 'F' }}"><div class="nm">{{ m.name }}{% if m.name == team.leader %}<span class="tag">팀장</span>{% endif %}</div>
<div class="rl">{{ m.role or '역할 미정' }} · {{ m.role_desc }}</div><div class="small">{{ cur_w }}주차: {{ m.cur_label }}</div>
{% if m.status == 'F' %}<div class="oath">“F를 받겠습니다. 교수님께 따로 말씀드리는 것에 동의합니다.”</div>
<a class="small" style="filter:none" href="{{ base }}/oath/{{ m.id }}">📜 학점 포기 서약서 보기</a>{% endif %}</div>{% endfor %}</div>
<h3>주차별 제출 현황</h3>
<div class="tbl-wrap"><table class="grid"><tr><th>팀원</th>{% for w in weeks %}<th>{{ w.n }}주차<br><span class="small">~{{ w.deadline }}</span></th>{% endfor %}</tr>
{% for m in members %}<tr class="{{ 'f' if m.status == 'F' }}"><td>{{ m.name }}</td>{% for l in m.labels %}<td>{{ l }}</td>{% endfor %}</tr>{% endfor %}</table></div>
<p class="small">✅ 인정 · 🟡 조건부 인정 · ⏳ 진행 중 · ⏰ 하루 연장 중 · ❌ 미제출/미인정 · ⚫ F 동의</p>
{% if recent %}<h3>최근 제출물</h3>{% for s in recent %}
<details><summary>{{ s.week }}주차 · {{ s.member }} · {{ s.verdict }} {{ s.score }}점 · {{ (s.created_at or '')[:16] }}</summary>
<p style="white-space:pre-wrap">{{ s.text }}</p>{% if s.link %}<p>🔗 <a href="{{ s.link }}" target="_blank" rel="noopener">{{ s.link }}</a></p>{% endif %}
{% if s.filename %}<p>📎 <a href="/file/{{ s.filename|urlencode }}">{{ s.filename }}</a></p>{% endif %}
{% if s.summary %}<p class="small">AI 검토 · {{ s.summary }}</p>{% endif %}</details>{% endfor %}{% endif %}

{% elif tab == 'upload' %}
{% if result %}{% set v = result.review.verdict or {} %}{% set rv = result.review.review or {} %}
<div class="card"><h2 style="margin-top:0">{{ {'인정':'✅','조건부 인정':'🟡'}.get(v.verdict, '❌') }} 판정: {{ v.verdict }} · {{ v.score }}점</h2>
<p>{{ v.reason }}</p>
{% for s in result.review.similarity or [] %}<div class="alert {{ 'warn' if s.kind == '유사' else 'error' }}">🔍 유사도 검사 · <b>{{ s.kind }}</b> 감지: {{ s.against }} 제출과 {{ (s.ratio * 100)|int }}% 동일</div>{% endfor %}
{% if v.flags %}<p class="small">판정 플래그: {{ v.flags|join(', ') }}</p>{% endif %}
{% if v.required_fix and v.required_fix != '없음' %}<div class="alert warn">보완 요구: {{ v.required_fix }}</div>{% endif %}
<div class="metrics"><div class="metric"><div class="k">관련성</div><div class="v">{{ rv.relevance or 0 }}</div></div><div class="metric"><div class="k">완성도</div><div class="v">{{ rv.completeness or 0 }}</div></div>
<div class="metric"><div class="k">노력</div><div class="v">{{ rv.effort or 0 }}</div></div><div class="metric"><div class="k">명확성</div><div class="v">{{ rv.clarity or 0 }}</div></div></div>
{% if rv.strengths %}<p><b>잘한 점</b> · {{ rv.strengths|join(' / ') }}</p>{% endif %}
{% if rv.improvements %}<p><b>보완점</b> · {{ rv.improvements|join(' / ') }}</p>{% endif %}
{% if rv.next_week_tip %}<p class="small">💡 {{ rv.next_week_tip }}</p>{% endif %}
{% if v.verdict == '미인정' %}<div class="alert error">미인정 제출은 제출로 집계되지 않습니다. 보완해서 다시 올려주세요.</div>{% endif %}
</div>{% endif %}
{% if me.status == 'F' %}<div class="alert error">F 동의 상태에서는 제출할 수 없습니다. 팀장이 '역할·주차 목표' 탭에서 되돌릴 수 있습니다.</div>
{% elif not upload_weeks %}<div class="alert success">제출할 주차가 없습니다. 모든 주차가 처리되었어요 👏</div>
{% else %}
<div class="card"><p><b>내 역할</b> {{ me.role }}</p>
<form method="post" action="{{ base }}/submit" enctype="multipart/form-data">
<label>제출 주차</label><select name="week">{% for w in upload_weeks %}<option value="{{ w.n }}" {{ 'selected' if w.n == upload_default }}>{{ w.n }}주차 · {{ w.label }} · 목표: {{ w.goal }}</option>{% endfor %}</select>
<label>이번 주에 한 일 (무엇을 · 얼마나 · 어떻게, 3줄 이상 권장)</label>
<textarea name="text" rows="6" placeholder="예: 설문 문항 15개 초안 작성. 인구통계 4 + 이용행태 6 + 만족도 5 문항, 5점 척도. 구글폼 링크 첨부."></textarea>
<label>결과물 링크 (노션/드라이브/깃허브 등)</label><input type="url" name="link" placeholder="https://">
<label>파일 첨부 (선택, 4MB 이하)</label><input type="file" name="file">
<button class="btn full">제출하고 AI 검토 받기</button>
<p class="small">유사도 검사 → 검토 AI → 판정 AI 순서로 확인합니다. AI 모드에서는 10~30초 걸릴 수 있습니다.</p>
</form></div>{% endif %}

{% elif tab == 'roles' %}
<p class="small">AI가 설계한 역할과 주차별 산출물 목표입니다. 팀장은 수정할 수 있습니다.</p>
{% if milestones %}<p><b>팀 마일스톤</b> · {% for m in milestones %}{{ loop.index }}주 {{ m }}{{ ' → ' if not loop.last }}{% endfor %}</p>{% endif %}
{% for m in members %}<details {{ 'open' if m.id == me.id }}><summary>{{ m.name }} · {{ m.role or '역할 미정' }}{{ ' · ⚫ F 동의' if m.status == 'F' }}</summary>
{% if is_leader %}<form method="post" action="{{ base }}/role/{{ m.id }}">
<label>역할</label><input type="text" name="role" value="{{ m.role }}"><label>역할 설명</label><input type="text" name="role_desc" value="{{ m.role_desc }}">
{% for g in m.goal_list %}<label>{{ loop.index }}주차 목표</label><input type="text" name="goal" value="{{ g }}">{% endfor %}
<button class="btn" style="margin-top:10px">저장</button></form>
{% if m.status == 'F' %}<form method="post" action="{{ base }}/unf/{{ m.id }}" style="margin-top:8px"><button class="btn gray">F 동의 되돌리기 (팀장)</button></form>{% endif %}
{% if m.email %}<form method="post" action="{{ base }}/unlink/{{ m.id }}" style="margin-top:8px"><button class="btn gray">계정 연결 해제 (팀장)</button> <span class="small">연결된 계정: {{ m.email }}</span></form>{% endif %}
{% else %}<p><b>{{ m.role }}</b> · {{ m.role_desc }}</p><ul>{% for g in m.goal_list %}<li>{{ loop.index }}주차: {{ g or '-' }}</li>{% endfor %}</ul>{% endif %}
</details>{% endfor %}
{% if is_leader %}<form method="post" action="{{ base }}/replan" style="margin-top:14px" onsubmit="return confirm('기존 역할·목표를 덮어씁니다. 계속할까요?')"><button class="btn ghost">🔁 AI로 역할 다시 설계</button></form>{% endif %}

{% elif tab == 'report' %}
<p class="small">주간 제출 기록·판정 점수·연장/F 이력을 종합해 교수님 제출용 기여도 보고서를 만듭니다.</p>
<form method="post" action="{{ base }}/report"><button class="btn full">📊 리포트 생성</button></form>
{% if report %}<p class="small">모드: {{ 'LLM' if report.mode == 'llm' else '규칙 기반' }}</p>
<div class="metrics">{% for c in report.contribution or [] %}<div class="metric" title="{{ c.basis }}"><div class="k">{{ c.name }}</div><div class="v">{{ c.percent }}%</div></div>{% endfor %}</div>
<div class="card"><pre class="code" style="max-height:none;background:#fff">{{ report.report_md }}</pre>
<a class="btn ghost" download="{{ team.code }}_report.md" href="data:text/markdown;charset=utf-8,{{ report.report_md|urlencode }}">보고서 .md 다운로드</a></div>
{% if report.peer_eval %}<h3>동료평가 초안</h3><ul>{% for p in report.peer_eval %}<li><b>{{ p.name }}</b> · {{ p.draft }}</li>{% endfor %}</ul>{% endif %}
{% if report.nudges %}<h3>팀장이 보낼 메시지 초안</h3>{% for n in report.nudges %}<pre class="code">[{{ n.name }}] {{ n.message }}</pre>{% endfor %}{% endif %}
{% endif %}

{% elif tab == 'logs' %}
<p class="small">이 팀에서 실행된 모든 AI 호출(시스템 프롬프트·입력·원문 응답)이 자동 기록됩니다. 제출용 '프롬프트 기록'으로 바로 내려받을 수 있습니다.</p>
{% if logs %}<a class="btn ghost" href="{{ base }}/logs.json">프롬프트 기록 JSON 다운로드</a>
{% for l in logs %}<details><summary>{{ (l.created_at or '')[:16] }} · {{ l.stage }} · {{ l.model }} · {{ l.elapsed_sec }}s</summary>
<b>System prompt</b><pre class="code">{{ l.system_prompt }}</pre><b>User prompt</b><pre class="code">{{ (l.user_prompt or '')[:4000] }}</pre><b>Response</b><pre class="code">{{ (l.raw_response or '')[:4000] }}</pre></details>{% endfor %}
{% else %}<div class="alert info">아직 AI 호출 기록이 없습니다. (규칙 기반 모드에서는 기록되지 않습니다. 상단 「AI 설정」에서 키를 넣어 주세요)</div>{% endif %}

{% elif tab == 'tools' %}
<div class="cols"><div class="card"><h3 style="margin-top:0">⏩ 데모용 시간 이동</h3><p class="small">심사·시연용. 팀 전체의 '오늘'을 옮겨 주차 마감을 지나게 할 수 있습니다.</p>
<div class="row">{% for d, lab in [(1,'+1일'),(7,'+7일'),(0,'초기화')] %}<form method="post" action="{{ base }}/time"><input type="hidden" name="delta" value="{{ d }}"><button class="btn gray">{{ lab }}</button></form>{% endfor %}</div>
<p class="small">현재 가상 날짜: {{ now_full }} (오프셋 {{ team.sim_offset_days }}일)</p></div>
<div class="card"><h3 style="margin-top:0">💾 데이터 백업</h3><a class="btn ghost" href="{{ base }}/export.json">팀 데이터 JSON 내보내기</a>
{% if is_leader or is_demo %}<form method="post" action="{{ base }}/import" enctype="multipart/form-data" style="margin-top:12px"><label>JSON 가져오기 (같은 코드의 팀을 덮어씀)</label><input type="file" name="file" accept=".json"><button class="btn gray" style="margin-top:8px">가져오기 실행</button></form>{% endif %}</div></div>
{% endif %}
{% endblock %}"""

OATH_DOC = r'''{% macro oath_doc(team, m, week, signed=False, signature=None, signed_name='', signed_at='') %}
<div class="oathdoc">
  <div class="od-title">학점 포기 동의 서약서</div>
  <table class="od-meta">
    <tr><th>수업</th><td>{{ team.course }}</td><th>팀</th><td>{{ team.name }}</td></tr>
    <tr><th>서약자</th><td>{{ m.name }}</td><th>역할</th><td>{{ m.role or '-' }}</td></tr>
    <tr><th>과제</th><td colspan="3">{{ team.assignment }}</td></tr>
  </table>
  <ol class="od-clauses">
    <li>본인은 {% if week %}{{ week }}주차{% else %}정해진 주차의{% endif %} 작업물을 마감까지 제출하지 않았으며, 이 팀 프로젝트에 더 이상 참여하지 않겠습니다.</li>
    <li>본인은 이 과제의 학점을 포기하고, <b>F 학점을 받는 것에 동의</b>합니다.</li>
    <li>이 사실을 팀이 <b>교수님께 따로 보고하는 것에 동의</b>합니다.</li>
    <li>본인의 이름은 팀 보드에서 흑백으로 표시되며, 서약 후에는 본인이 취소할 수 없습니다. (팀장만 되돌릴 수 있습니다)</li>
  </ol>
  <p class="od-pledge">위 내용을 충분히 읽고 이해하였으며, 본인의 자유로운 의사로 서약합니다.</p>
  {% if signed %}
  <div class="od-sign"><div><span class="small">서약일</span><br><b>{{ signed_at }}</b></div>
    <div><span class="small">서약자</span><br><b>{{ signed_name }}</b></div>
    <div class="od-sigbox">{% if signature %}<img src="{{ signature }}" alt="서명">{% endif %}<span class="od-seal">(서명)</span></div></div>
  {% endif %}
</div>
{% endmacro %}'''

OATH_PAGE = r'''{% extends "base.html" %}{% from "oathdoc.html" import oath_doc %}{% block title %}학점 포기 동의 서약서 · {{ m.name }}{% endblock %}{% block body %}
<div class="row noprint" style="justify-content:space-between"><a href="{{ base }}">← 팀 보드로</a><button class="btn gray" onclick="window.print()">인쇄 / PDF 저장</button></div>
{{ oath_doc(team, m, m.f_week, True, m.f_signature, m.f_signed_name or m.name, (m.f_agreed_at or '')[:16]|replace('T', ' ')) }}
{% endblock %}'''

SPLASH = r'''<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>팀플 서약</title>
<meta name="description" content="매주 작업물로 기여를 증명하는 무임승차 방지 팀플 플랫폼">
<link rel="icon" type="image/png" href="/icon-32.png"><link rel="apple-touch-icon" href="/icon-180.png">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{font-family:"Noto Sans KR",-apple-system,"Malgun Gothic",sans-serif;background:radial-gradient(circle at 50% 30%,#ffffff 0,#eef2ff 45%,#f6f7f9 100%);color:#111827;
display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;padding:24px 16px;text-align:center;overflow:hidden}
.brand{position:fixed;top:22px;left:26px;font-weight:900;letter-spacing:.05em;color:#111827}
.win{background:#fff;color:#111;border-radius:18px;width:min(460px,100%);padding:28px 26px;border:1px solid #e5e7eb;border-top:5px solid #4f46e5;box-shadow:0 24px 60px rgba(79,70,229,.18),0 4px 14px rgba(17,24,39,.06);animation:pop .55s .15s both cubic-bezier(.2,1.4,.4,1);text-align:left}
@keyframes pop{from{transform:scale(.7);opacity:0}}
.warn{font-size:.88rem;color:#b91c1c;font-weight:700}
.q{font-size:1.85rem;line-height:1.3;font-weight:900;margin:12px 0 8px}
.sub{color:#6b7280;font-size:.95rem}
.row{display:flex;gap:10px;margin-top:20px}
.row>*{flex:1;border:0;border-radius:11px;padding:14px;font:inherit;font-weight:800;text-align:center;text-decoration:none}
.yes{background:#f3f4f6;color:#9ca3af;cursor:not-allowed}
.no{background:#4f46e5;color:#fff;cursor:pointer;transition:transform .15s,box-shadow .15s}
.no:hover{transform:translateY(-2px);box-shadow:0 10px 24px rgba(79,70,229,.45)}
.yes-tip{display:none;margin-top:12px;font-size:.85rem;color:#b91c1c}
.hint{margin-top:22px;color:#6b7280;font-size:.9rem;line-height:1.7}
.hint b{color:#374151}
@media (max-width:480px){.q{font-size:1.5rem}.brand{left:16px}}
</style></head><body>
<div class="brand"><img src="/icon-180.png" alt="" width="30" height="30" style="border-radius:50%;vertical-align:-9px;margin-right:6px">팀플 서약</div>
<div class="win" role="dialog" aria-labelledby="q">
  <img src="/icon-180.png" alt="" width="66" height="66" style="border-radius:50%;display:block;margin-bottom:12px">
  <div class="warn">⚠️ 이번 주 작업물이 없습니다</div>
  <div class="q" id="q">팀플에 참여하지<br>않으시겠습니까?</div>
  <div class="sub">당신의 팀원 3명이 기다리고 있습니다.</div>
  <div class="row"><button class="yes" type="button" id="yes" aria-disabled="true">예</button><a class="no" href="/start">아니요, 참여할게요</a></div>
  <div class="yes-tip" id="tip">팀플 서약에서는 '예'를 고를 수 없어요. 함께해요 🙂</div>
</div>
<div class="hint">매주 작업물로 기여를 증명하는 팀플 플랫폼<br><b>AI가 역할을 나누고, 제출물을 검토하고, 기여도를 기록합니다.</b></div>
<script>document.getElementById('yes').onclick=function(){document.getElementById('tip').style.display='block';};</script>
</body></html>'''

ERROR = r"""{% extends "base.html" %}{% block body %}<h1>{{ title }}</h1><div class="alert error">{{ message }}</div><a href="/">← 처음으로</a>{% endblock %}"""

env = Environment(
    loader=DictLoader({"base.html": BASE, "auth.html": AUTH, "recovery.html": RECOVERY, "home.html": HOME, "join.html": JOIN,
                       "pick.html": PICK, "splash.html": SPLASH, "oathdoc.html": OATH_DOC, "oath.html": OATH_PAGE, "account.html": ACCOUNT, "settings.html": SETTINGS, "team.html": TEAM, "error.html": ERROR}),
    autoescape=select_autoescape(default=True),
)
