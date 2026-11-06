"""팀플 서약 — Vercel 배포용 웹 서버 (FastAPI).

Streamlit 화면(streamlit_app.py)과 같은 저장소(db.py)·AI 파이프라인(ai.py)을 그대로 쓰고,
화면만 서버 렌더링 HTML 로 다시 만든 것. Vercel Python 런타임이 ASGI `app` 을 실행한다.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
from datetime import date, timedelta

os.environ.setdefault("TZ", "Asia/Seoul")  # 마감 계산을 한국 시간 기준으로
try:
    time.tzset()
except AttributeError:  # Windows 로컬 실행
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from fastapi import FastAPI, File, Form, Request, UploadFile  # noqa: E402
from fastapi.responses import HTMLResponse, RedirectResponse, Response  # noqa: E402

import ai  # noqa: E402
import db  # noqa: E402
from web_templates import env  # noqa: E402
import icon_data  # noqa: E402
import base64  # noqa: E402

app = FastAPI(title="팀플 서약", docs_url=None, redoc_url=None, openapi_url=None)
MAX_UPLOAD = 4 * 1024 * 1024  # Vercel 요청 본문 한도(4.5MB) 안쪽
TABS = [("board", "🏠 팀 보드"), ("upload", "📤 작업물 올리기"), ("roles", "🧭 역할·주차 목표"),
        ("report", "📊 AI 기여도 리포트"), ("logs", "🧾 프롬프트 기록"), ("tools", "🛠️ 시연 도구")]

_DB_READY = False


def ensure_db() -> None:
    global _DB_READY
    if not _DB_READY:
        db.init()
        _DB_READY = True


# ───────────── 공용: 쿠키 · 플래시 · 렌더 ─────────────

def is_https(req: Request) -> bool:
    return req.headers.get("x-forwarded-proto", req.url.scheme) == "https"


def set_cookie(resp: Response, req: Request, key: str, value: str, max_age: int | None = None) -> None:
    resp.set_cookie(key, value, max_age=max_age, httponly=True, samesite="lax", secure=is_https(req), path="/")


def go(req: Request, url: str, flash: str | None = None, kind: str = "success") -> RedirectResponse:
    r = RedirectResponse(url, status_code=303)
    if flash:
        set_cookie(r, req, "flash", urllib.parse.quote(json.dumps([kind, flash], ensure_ascii=False)), 60)
    return r


def current_user(req: Request) -> dict | None:
    if not hasattr(req.state, "user"):
        req.state.user = db.user_by_session(req.cookies.get("s", ""))
    return req.state.user


def llm_config(req: Request) -> dict:
    c = req.cookies
    names = list(ai.PROVIDERS)
    prov = urllib.parse.unquote(c.get("ai_p", ""))
    if prov not in ai.PROVIDERS:
        prov = next((n for n in names if os.getenv(ai.PROVIDERS[n]["key_env"])), names[0])
    p = ai.PROVIDERS[prov]
    base_custom = urllib.parse.unquote(c.get("ai_u", ""))
    model_custom = urllib.parse.unquote(c.get("ai_m", ""))
    base = base_custom or (os.getenv("TILON_BASE_URL") if p["key_env"] == "TILON_API_KEY" and os.getenv("TILON_BASE_URL") else p["base_url"])
    key = urllib.parse.unquote(c.get("ai_k", "")) or os.getenv(p["key_env"], "")
    return {"provider": prov, "base_url": base, "model": model_custom or p["model"], "key": key,
            "enabled": c.get("ai_off") != "1", "base_url_custom": base_custom, "model_custom": model_custom,
            "has_cookie_key": bool(c.get("ai_k"))}


def get_llm(req: Request) -> ai.LLM:
    cfg = llm_config(req)
    return ai.LLM(cfg["base_url"] or None, cfg["key"], cfg["model"], enabled=cfg["enabled"])


def rule_llm() -> ai.LLM:
    return ai.LLM(None, "", "", enabled=False)


def render(req: Request, name: str, status: int = 200, **ctx) -> HTMLResponse:
    flash = None
    raw = req.cookies.get("flash")
    if raw:
        try:
            flash = json.loads(urllib.parse.unquote(raw))
        except Exception:
            flash = None
    probe = get_llm(req)
    ctx.setdefault("user", current_user(req))
    ctx.setdefault("form", {})
    html = env.get_template(name).render(
        flash=flash, storage=db.storage_label(), pw_min=db.PW_MIN,
        ai_status=(f"AI 모드 · {probe.model}" if probe.available else "규칙 기반 모드 (AI 키 없음)"), **ctx)
    resp = HTMLResponse(html, status_code=status)
    if raw:
        resp.delete_cookie("flash", path="/")
    return resp


def error_page(req: Request, title: str, message: str, status: int = 400) -> HTMLResponse:
    return render(req, "error.html", status=status, title=title, message=message)


@app.middleware("http")
async def db_guard(request: Request, call_next):
    try:
        ensure_db()
    except Exception as e:  # noqa: BLE001
        # 예외 메시지에 접속 주소(비밀번호)가 들어갈 수 있어 화면에는 절대 출력하지 않고 서버 로그에만 남긴다.
        print(f"[db_guard] DB init failed: {type(e).__name__}", file=sys.stderr)
        return HTMLResponse("<h1>데이터베이스에 연결할 수 없습니다</h1><p>잠시 후 다시 시도해 주세요.</p>", status_code=503)
    return await call_next(request)


# ───────────── 로그인 / 회원가입 / 비밀번호 찾기 ─────────────

def login_response(req: Request, user: dict, url: str = "/", flash: str | None = None, recovery: str | None = None) -> RedirectResponse:
    r = go(req, url, flash)
    set_cookie(r, req, "s", db.create_session(user["email"]), db.SESSION_DAYS * 86400)
    if recovery:
        set_cookie(r, req, "rc", recovery, 3600)
    return r


@app.get("/", response_class=HTMLResponse)
def home(req: Request, tab: str = ""):
    user = current_user(req)
    if not user:
        # 로그인하지 않은 방문자가 첫 주소(/)로 들어오면 항상 시작화면부터 보여 준다 (로그아웃·오류 안내로 돌아온 경우는 제외)
        if not tab and not req.cookies.get("flash"):
            return HTMLResponse(env.get_template("splash.html").render())
        return render(req, "auth.html", tab=tab if tab in ("login", "signup", "reset") else "login")
    return render(req, "home.html", my_teams=db.teams_for_email(user["email"]), today=date.today().isoformat(),
                  recovery_code=req.cookies.get("rc"))


@app.get("/start")
def start(req: Request):
    """시작화면의 「아니요, 참여할게요」 → 로그인/회원가입/데모 화면으로."""
    return RedirectResponse("/?tab=login", status_code=303)


@app.get("/intro", response_class=HTMLResponse)
def intro():
    """시작화면 다시 보기 (시연용)."""
    return HTMLResponse(env.get_template("splash.html").render())


@app.post("/login")
def do_login(req: Request, email: str = Form(""), pw: str = Form("")):
    left = db.login_lock_remaining(email)
    if left:
        return render(req, "auth.html", tab="login", form={"email": email},
                      error=f"로그인 {db.LOCK_AFTER}회 실패로 잠겨 있습니다. {left // 60}분 {left % 60}초 후 다시 시도하거나 「비밀번호 찾기」를 이용하세요.")
    u = db.verify_login(email, pw)
    if not u:
        msg = (f"{db.LOCK_AFTER}회 연속 실패로 {db.LOCK_MINUTES}분간 로그인이 잠겼습니다. 「비밀번호 찾기」로 재설정할 수 있습니다."
               if db.login_lock_remaining(email) else "이메일 또는 비밀번호가 올바르지 않습니다.")
        return render(req, "auth.html", tab="login", form={"email": email}, error=msg)
    return login_response(req, u)


@app.post("/signup")
def do_signup(req: Request, name: str = Form(""), email: str = Form(""), pw1: str = Form(""), pw2: str = Form("")):
    form = {"name": name, "email": email}
    if pw1 != pw2:
        return render(req, "auth.html", tab="signup", form=form, error="비밀번호 확인이 일치하지 않습니다.")
    try:
        u = db.register_user(email, name, pw1)
    except ValueError as e:
        return render(req, "auth.html", tab="signup", form=form, error=str(e))
    return login_response(req, u, flash="가입 완료! 바로 로그인되었습니다.", recovery=u["recovery_code"])


@app.post("/reset")
def do_reset(req: Request, email: str = Form(""), code: str = Form(""), pw1: str = Form(""), pw2: str = Form("")):
    if pw1 != pw2:
        return render(req, "auth.html", tab="reset", form={"email": email}, error="새 비밀번호 확인이 일치하지 않습니다.")
    try:
        new_code = db.reset_password_with_code(email, code, pw1)
    except ValueError as e:
        return render(req, "auth.html", tab="reset", form={"email": email}, error=str(e))
    u = db.verify_login(email, pw1)
    return login_response(req, u, flash="비밀번호를 재설정하고 로그인했습니다.", recovery=new_code)


@app.post("/ack-recovery")
def ack_recovery(req: Request):
    r = go(req, req.headers.get("referer") or "/")
    r.delete_cookie("rc", path="/")
    return r


@app.post("/logout")
def do_logout(req: Request):
    db.delete_session(req.cookies.get("s", ""))
    r = go(req, "/", "로그아웃되었습니다.")
    for k in ("s", "rc"):
        r.delete_cookie(k, path="/")
    return r


# ───────────── 내 계정 ─────────────

def need_user(req: Request):
    u = current_user(req)
    return u, (None if u else go(req, "/", "로그인이 필요합니다.", "error"))


def account_page(req: Request, error: str | None = None, status: int = 200):
    u = current_user(req)
    return render(req, "account.html", status=status, error=error, n_sessions=db.count_sessions(u["email"]),
                  recovery_code=req.cookies.get("rc"))


@app.get("/account", response_class=HTMLResponse)
def account(req: Request):
    u, bad = need_user(req)
    return bad or account_page(req)


@app.post("/account/name")
def account_name(req: Request, name: str = Form("")):
    u, bad = need_user(req)
    if bad:
        return bad
    try:
        db.rename_user(u["email"], name)
    except ValueError as e:
        return account_page(req, str(e), 400)
    return go(req, "/account", "이름을 변경했습니다.")


@app.post("/account/password")
def account_password(req: Request, cur: str = Form(""), n1: str = Form(""), n2: str = Form("")):
    u, bad = need_user(req)
    if bad:
        return bad
    if n1 != n2:
        return account_page(req, "새 비밀번호 확인이 일치하지 않습니다.", 400)
    try:
        db.change_password(u["email"], cur, n1)
    except ValueError as e:
        return account_page(req, str(e), 400)
    return go(req, "/account", "비밀번호를 변경했습니다.")


@app.post("/account/recovery")
def account_recovery(req: Request, pw: str = Form("")):
    u, bad = need_user(req)
    if bad:
        return bad
    try:
        code = db.regenerate_recovery_code(u["email"], pw)
    except ValueError as e:
        return account_page(req, str(e), 400)
    r = go(req, "/account", "새 복구 코드를 발급했습니다. 이전 코드는 더 이상 쓸 수 없습니다.")
    set_cookie(r, req, "rc", code, 3600)
    return r


@app.post("/account/logout-all")
def account_logout_all(req: Request):
    u, bad = need_user(req)
    if bad:
        return bad
    db.delete_all_sessions(u["email"])
    r = go(req, "/", "모든 기기에서 로그아웃되었습니다.")
    r.delete_cookie("s", path="/")
    return r


@app.post("/account/delete")
def account_delete(req: Request, pw: str = Form(""), sure: str = Form("")):
    u, bad = need_user(req)
    if bad:
        return bad
    if not sure:
        return account_page(req, "탈퇴하려면 동의 체크가 필요합니다.", 400)
    try:
        db.delete_user(u["email"], pw)
    except ValueError as e:
        return account_page(req, str(e), 400)
    r = go(req, "/", "탈퇴가 완료되었습니다. 그동안 이용해 주셔서 감사합니다.")
    for k in ("s", "rc"):
        r.delete_cookie(k, path="/")
    return r


# ───────────── AI 설정 ─────────────

def settings_page(req: Request, ping=None):
    cfg = llm_config(req)
    return render(req, "settings.html", cfg=cfg, providers=list(ai.PROVIDERS), provider_items=list(ai.PROVIDERS.items()),
                  llm_available=get_llm(req).available, ping=ping)


@app.get("/settings", response_class=HTMLResponse)
def settings(req: Request):
    return settings_page(req)


@app.post("/settings")
def settings_save(req: Request, provider: str = Form(""), base_url: str = Form(""), model: str = Form(""),
                  key: str = Form(""), enabled: str = Form(""), clear: str = Form("")):
    r = go(req, "/settings", "AI 설정을 저장했습니다." if not clear else "브라우저에 저장된 AI 설정을 지웠습니다.")
    if clear:
        for k in ("ai_p", "ai_u", "ai_m", "ai_k", "ai_off"):
            r.delete_cookie(k, path="/")
        return r
    age = 90 * 86400
    set_cookie(r, req, "ai_p", urllib.parse.quote(provider), age)
    set_cookie(r, req, "ai_u", urllib.parse.quote(base_url.strip()), age)
    set_cookie(r, req, "ai_m", urllib.parse.quote(model.strip()), age)
    if key.strip():
        set_cookie(r, req, "ai_k", urllib.parse.quote(key.strip()), age)
    set_cookie(r, req, "ai_off", "" if enabled else "1", age)
    return r


@app.post("/settings/ping", response_class=HTMLResponse)
def settings_ping(req: Request):
    llm = get_llm(req)
    try:
        return settings_page(req, ("success", "응답: " + llm.ping()))
    except Exception as e:  # noqa: BLE001
        return settings_page(req, ("error", f"연결 실패: {e}"))


# ───────────── 팀 만들기 / 참여 / 데모 ─────────────

def parse_members(raw: str) -> tuple[list[str], dict]:
    names, emails = [], {}
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.replace("\t", ",").replace(" ", ",").split(",") if p.strip()]
        names.append(parts[0])
        em = next((p for p in parts[1:] if "@" in p), "")
        if em:
            emails[parts[0]] = em
    return names, emails


@app.post("/teams")
def create_team(req: Request, course: str = Form(""), tname: str = Form(""), members: str = Form(""), assignment: str = Form(""),
                weeks: int = Form(4), sdate: str = Form(""), use_ai: str = Form("")):
    u, bad = need_user(req)
    if bad:
        return bad
    form = {"course": course, "tname": tname, "members": members, "assignment": assignment, "weeks": weeks, "sdate": sdate}
    names, emails = parse_members(members)

    def fail(msg):
        return render(req, "home.html", status=400, my_teams=db.teams_for_email(u["email"]), today=date.today().isoformat(), form=form, error=msg)

    if not course.strip() or not tname.strip() or len(names) < 2 or not assignment.strip():
        return fail("수업 이름, 팀 이름, 구성원 2명 이상, 과제 내용을 모두 입력해 주세요.")
    if len(set(names)) != len(names):
        return fail("구성원 이름이 중복됩니다.")
    if len(set(emails.values())) != len(emails):
        return fail("같은 이메일이 두 명에게 적혀 있습니다.")
    weeks = max(1, min(16, int(weeks or 4)))
    try:
        start = date.fromisoformat(sdate) if sdate else date.today()
    except ValueError:
        return fail("시작일 형식이 올바르지 않습니다.")
    my_name = next((n for n in names if emails.get(n, "").lower() == u["email"]), None)
    if not my_name:
        my_name = u["name"] if u["name"] in names else names[0]
        emails[my_name] = u["email"]
    team = db.create_team(course=course.strip(), name=tname.strip(), assignment=assignment.strip(), start_date=start,
                          weeks=weeks, leader=names[0], members=names, emails=emails)
    llm = get_llm(req) if use_ai else rule_llm()
    note = ""
    try:
        plan = ai.plan_roles(llm, team["course"], team["assignment"], names, weeks)
    except Exception as e:  # noqa: BLE001
        note = f" (AI 설계 실패로 템플릿 사용: {e})"
        plan = ai.plan_roles(rule_llm(), team["course"], team["assignment"], names, weeks)
    db.save_plan(team["id"], plan)
    db.add_logs(team["id"], llm.logs)
    return go(req, f"/t/{team['code']}", f"팀이 만들어졌습니다! 초대 코드 {team['code']} 를 팀원에게 공유하세요.{note}")


@app.get("/join", response_class=HTMLResponse)
def join(req: Request, code: str = ""):
    u, bad = need_user(req)
    if bad:
        return bad
    team = db.get_team(code or "")
    if not team:
        return go(req, "/", "해당 코드의 팀이 없습니다.", "error")
    if team["code"] == db.DEMO_CODE:
        return go(req, f"/t/{team['code']}")
    free = [m["name"] for m in db.list_members(team["id"]) if not m.get("email")]
    return render(req, "join.html", team=team, mine=db.member_by_email(team["id"], u["email"]), free=free)


@app.post("/t/{code}/claim")
def claim(req: Request, code: str, name: str = Form("")):
    u, bad = need_user(req)
    if bad:
        return bad
    team = db.get_team(code)
    if not team:
        return go(req, "/", "해당 코드의 팀이 없습니다.", "error")
    try:
        db.claim_member(team["id"], name, u["email"])
    except ValueError as e:
        free = [m["name"] for m in db.list_members(team["id"]) if not m.get("email")]
        return render(req, "join.html", status=400, team=team, mine=None, free=free, error=str(e))
    return go(req, f"/t/{team['code']}", f"{name} 으로 연결되었습니다.")


@app.post("/demo")
def demo(req: Request):
    off = rule_llm()
    team = db.seed_demo(lambda **kw: ai.review_submission(off, **kw))
    r = go(req, f"/t/{team['code']}", "데모 팀을 새로 만들었습니다. 박지훈으로 입장합니다.")
    set_cookie(r, req, "gme", urllib.parse.quote("박지훈"), 86400)
    return r


@app.post("/t/{code}/as")
def demo_as(req: Request, code: str, name: str = Form("")):
    team = db.get_team(code)
    if not team or team["code"] != db.DEMO_CODE or not db.get_member(team["id"], name):
        return go(req, "/", "데모 팀에서만 팀원을 바꿔 볼 수 있습니다.", "error")
    r = go(req, f"/t/{team['code']}")
    set_cookie(r, req, "gme", urllib.parse.quote(name), 86400)
    return r


# ───────────── 팀 접근 제어 ─────────────

def team_access(req: Request, code: str):
    """(team, me, 오류 응답). 데모 팀은 쿠키로 고른 팀원, 그 외는 로그인 계정과 연결된 팀원만."""
    team = db.get_team(code or "")
    if not team:
        return None, None, go(req, "/", "해당 코드의 팀이 없습니다.", "error")
    if team["code"] == db.DEMO_CODE:
        name = urllib.parse.unquote(req.cookies.get("gme", ""))
        me = db.get_member(team["id"], name) if name else None
        if not me:
            return team, None, render(req, "pick.html", team=team, members=db.list_members(team["id"]))
        return team, me, None
    u = current_user(req)
    if not u:
        return team, None, go(req, "/", "이 팀에 들어가려면 로그인이 필요합니다.", "error")
    me = db.member_by_email(team["id"], u["email"])
    if not me:
        return team, None, go(req, f"/join?code={team['code']}")
    return team, me, None


def base_url(team: dict) -> str:
    return f"/t/{team['code']}"


# ───────────── 팀 화면 ─────────────

def team_page(req: Request, team: dict, me: dict, tab: str = "board", report: dict | None = None, result_id: int | None = None,
              pd: str = "", snooze: bool = False, bw: int | None = None):
    members = db.list_members(team["id"])
    subs = db.list_submissions(team["id"])
    exts = db.list_extensions(team["id"])
    cur_w = db.current_week(team)
    now = db.team_now(team)
    deadline = db.week_deadline(team, cur_w)
    dleft = deadline - now
    nweeks = int(team["weeks"])
    for m in members:
        m["labels"] = [db.week_status(team, m, w, subs, exts)["label"] for w in range(1, nweeks + 1)]
        m["cur_label"] = m["labels"][cur_w - 1]
        m["goal_list"] = [(m["goals"][w - 1] if len(m["goals"]) >= w else "") for w in range(1, nweeks + 1)]
    done_cnt = sum(1 for m in members if db.week_status(team, m, cur_w, subs, exts)["status"] in ("done", "conditional"))

    modal = None
    if pd == "done" and me.get("status") == "F":
        modal = {"step": "done"}
    else:
        alert = db.pending_alert(team, me, subs, exts)
        if alert and not snooze:
            w = alert["week"]
            goals = me["goals"] or []
            modal = {"step": pd if pd in ("confirm", "sign") else "ask", "week": w,
                     "deadline": f"{db.week_deadline(team, w):%m/%d %H:%M}",
                     "goal": goals[w - 1] if len(goals) >= w else "-", "ext_used": alert.get("ext_used")}

    brief_w = max(1, min(cur_w, bw or cur_w))
    upload_weeks = []
    for w in range(1, nweeks + 1):
        stt = db.week_status(team, me, w, subs, exts)
        if stt["status"] in ("open", "extended", "missed"):
            upload_weeks.append({"n": w, "label": stt["label"], "goal": me["goals"][w - 1] if len(me["goals"]) >= w else "(목표 미설정)"})
    upload_default = cur_w if any(x["n"] == cur_w for x in upload_weeks) else (upload_weeks[0]["n"] if upload_weeks else None)

    recent = []
    for s in sorted(subs, key=lambda x: x["created_at"] or "", reverse=True)[:6]:
        recent.append({**s, "summary": ((s["review"].get("review") or {}).get("summary", ""))})
    result = None
    if result_id:
        result = next((s for s in subs if s["id"] == result_id and s["member_id"] == me["id"]), None)
    try:
        milestones = json.loads(team.get("milestones_json") or "[]")
    except Exception:
        milestones = []

    return render(
        req, "team.html", team=team, me=me, members=members, base=base_url(team), tab=tab, tabs=TABS,
        is_leader=me["name"] == team["leader"], is_demo=team["code"] == db.DEMO_CODE, modal=modal,
        cur_w=cur_w, deadline_str=f"{deadline:%m/%d}", dday=(f"D-{dleft.days}" if dleft.days >= 0 else f"D+{-dleft.days}"),
        done_cnt=done_cnt, now_str=f"{now:%m/%d}", now_full=f"{now:%Y-%m-%d %H:%M}",
        weeks=[{"n": w, "deadline": f"{db.week_deadline(team, w):%m/%d}"} for w in range(1, nweeks + 1)],
        brief_w=brief_w, briefing=db.get_briefing(team["id"], brief_w), recent=recent,
        upload_weeks=upload_weeks, upload_default=upload_default, result=result, milestones=milestones,
        report=report, logs=db.list_logs(team["id"])[:30] if tab == "logs" else [],
    )


@app.get("/t/{code}", response_class=HTMLResponse)
def team_view(req: Request, code: str, tab: str = "board", result: int | None = None, pd: str = "", snooze: int = 0, bw: int | None = None):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    if tab not in dict(TABS):
        tab = "board"
    return team_page(req, team, me, tab=tab, result_id=result, pd=pd, snooze=bool(snooze), bw=bw)


@app.post("/t/{code}/peace/no")
def peace_no(req: Request, code: str):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    alert = db.pending_alert(team, me, db.list_submissions(team["id"]), db.list_extensions(team["id"]))
    if not alert or alert.get("ext_used"):
        return go(req, base_url(team))
    until = db.team_now(team) + timedelta(days=1)
    db.grant_extension(team["id"], me["id"], alert["week"], until)
    return go(req, base_url(team), f"기회를 드립니다. {alert['week']}주차 마감이 하루 연장되었습니다 ({until:%m/%d %H:%M}까지).", "info")


@app.post("/t/{code}/peace/agree")
def peace_agree(req: Request, code: str, signed_name: str = Form(""), signature: str = Form(""), agree: str = Form(""), week: int = Form(0)):
    """학점 포기 동의 서약서 제출: 본인 이름 입력 + 자필 서명 + 동의 체크가 모두 있어야 F 처리."""
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    back = f"{base_url(team)}?pd=sign"
    if signed_name.strip() != me["name"]:
        return go(req, back, f"서약서의 이름 칸에 본인 이름({me['name']})을 정확히 적어 주세요.", "error")
    if not db.valid_signature(signature):
        return go(req, back, "서명란에 자필 서명을 해 주세요.", "error")
    if not agree:
        return go(req, back, "서약 내용 동의에 체크해 주세요.", "error")
    db.mark_f(me["id"], True, signature=signature, signed_name=signed_name.strip(), week=week or None)
    return go(req, f"{base_url(team)}?pd=done")


@app.get("/t/{code}/oath/{member_id}", response_class=HTMLResponse)
def oath_view(req: Request, code: str, member_id: int):
    """서명된 학점 포기 동의 서약서 (팀원 누구나 열람·인쇄)."""
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    m = next((x for x in db.list_members(team["id"]) if x["id"] == member_id), None)
    if not m or m["status"] != "F":
        return error_page(req, "서약서 없음", "이 팀원은 학점 포기 서약을 하지 않았습니다.", 404)
    return render(req, "oath.html", team=team, m=m, base=base_url(team))


@app.post("/t/{code}/briefing")
def briefing(req: Request, code: str, week: int = Form(1)):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    members = db.list_members(team["id"])
    subs, exts = db.list_submissions(team["id"]), db.list_extensions(team["id"])
    week = max(1, min(db.current_week(team), int(week)))
    rows = []
    for m in members:
        stt = db.week_status(team, m, week, subs, exts)
        sb = stt.get("sub")
        rows.append({"name": m["name"], "role": m["role"], "status_label": stt["label"],
                     "goal": m["goals"][week - 1] if len(m["goals"]) >= week else "",
                     "next_goal": m["goals"][week] if len(m["goals"]) > week else "",
                     "verdict": sb["verdict"] if sb else None, "score": sb["score"] if sb else None,
                     "summary": ((sb["review"].get("review", {}) or {}).get("summary", "") if sb else ""),
                     "text": (sb["text"] or "")[:300] if sb else ""})
    llm = get_llm(req)
    note = None
    try:
        b = ai.weekly_briefing(llm, team=team, week=week, members=members, week_rows=rows)
    except Exception as e:  # noqa: BLE001
        note = f"AI 브리핑 실패 → 규칙 기반으로 대체: {e}"
        b = ai.weekly_briefing(rule_llm(), team=team, week=week, members=members, week_rows=rows)
    db.add_logs(team["id"], llm.logs)
    db.save_briefing(team["id"], week, b)
    return go(req, f"{base_url(team)}?bw={week}&snooze=1", note or f"{week}주차 브리핑을 만들었습니다.", "warn" if note else "success")


@app.post("/t/{code}/submit")
async def submit(req: Request, code: str, week: int = Form(...), text: str = Form(""), link: str = Form(""), file: UploadFile | None = File(None)):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    if me["status"] == "F":
        return go(req, f"{base_url(team)}?tab=upload", "F 동의 상태에서는 제출할 수 없습니다.", "error")
    subs, exts = db.list_submissions(team["id"]), db.list_extensions(team["id"])
    if db.week_status(team, me, week, subs, exts)["status"] not in ("open", "extended", "missed"):
        return go(req, f"{base_url(team)}?tab=upload&snooze=1", "이 주차는 이미 처리되었습니다.", "error")
    fname = ""
    if file is not None and file.filename:
        data = await file.read()
        if len(data) > MAX_UPLOAD:
            return go(req, f"{base_url(team)}?tab=upload&snooze=1", "파일은 4MB 이하만 첨부할 수 있습니다.", "error")
        if data:
            safe = os.path.basename(file.filename).replace(" ", "_")
            fname = db.save_file(team["id"], f"{team['code']}_w{week}_{me['name']}_{safe}", data)
    if not text.strip() and not link.strip() and not fname:
        return go(req, f"{base_url(team)}?tab=upload&snooze=1", "내용, 링크, 파일 중 하나는 있어야 합니다.", "error")
    goal = me["goals"][week - 1] if len(me["goals"]) >= week else "(목표 미설정)"
    prior = [{"member": s["member"], "week": s["week"], "text": s["text"] or "", "link": s["link"] or ""} for s in subs]
    llm = get_llm(req)
    note = None
    try:
        res = ai.review_submission(llm, member=me["name"], role=me["role"], goal=goal, week=week, text=text, link=link.strip(), filename=fname, prior=prior)
    except Exception as e:  # noqa: BLE001
        note = f"AI 검토 실패 → 규칙 기반으로 대체: {e}"
        res = ai.review_submission(rule_llm(), member=me["name"], role=me["role"], goal=goal, week=week, text=text, link=link.strip(), filename=fname, prior=prior)
    db.add_logs(team["id"], llm.logs)
    v = res["verdict"]
    sid = db.add_submission(team["id"], me["id"], week, text=text, link=link.strip(), filename=fname,
                            score=int(v.get("score", 0)), verdict=v.get("verdict", "미인정"), review=res)
    return go(req, f"{base_url(team)}?tab=upload&result={sid}&snooze=1", note, "warn") if note else go(req, f"{base_url(team)}?tab=upload&result={sid}&snooze=1")


@app.post("/t/{code}/role/{member_id}")
async def save_role(req: Request, code: str, member_id: int):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    if me["name"] != team["leader"]:
        return go(req, f"{base_url(team)}?tab=roles", "팀장만 수정할 수 있습니다.", "error")
    form = await req.form()
    target = next((m for m in db.list_members(team["id"]) if m["id"] == member_id), None)
    if not target:
        return go(req, f"{base_url(team)}?tab=roles", "팀원을 찾을 수 없습니다.", "error")
    db.update_member(member_id, role=str(form.get("role", "")), role_desc=str(form.get("role_desc", "")),
                     goals=[str(g) for g in form.getlist("goal")])
    return go(req, f"{base_url(team)}?tab=roles&snooze=1", f"{target['name']} 역할을 저장했습니다.")


@app.post("/t/{code}/unf/{member_id}")
def undo_f(req: Request, code: str, member_id: int):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    if me["name"] != team["leader"] or not any(m["id"] == member_id for m in db.list_members(team["id"])):
        return go(req, f"{base_url(team)}?tab=roles", "팀장만 되돌릴 수 있습니다.", "error")
    db.mark_f(member_id, False)
    return go(req, f"{base_url(team)}?tab=roles&snooze=1", "F 동의를 되돌렸습니다.")


@app.post("/t/{code}/unlink/{member_id}")
def unlink(req: Request, code: str, member_id: int):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    target = next((m for m in db.list_members(team["id"]) if m["id"] == member_id), None)
    if me["name"] != team["leader"] or not target:
        return go(req, f"{base_url(team)}?tab=roles", "팀장만 연결을 해제할 수 있습니다.", "error")
    if target["id"] == me["id"]:
        return go(req, f"{base_url(team)}?tab=roles", "팀장 본인의 연결은 해제할 수 없습니다.", "error")
    db.update_member(member_id, email="")
    return go(req, f"{base_url(team)}?tab=roles&snooze=1", f"{target['name']} 의 계정 연결을 해제했습니다. 새 계정으로 다시 연결할 수 있습니다.")


@app.post("/t/{code}/replan")
def replan(req: Request, code: str):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    if me["name"] != team["leader"]:
        return go(req, f"{base_url(team)}?tab=roles", "팀장만 다시 설계할 수 있습니다.", "error")
    llm = get_llm(req)
    try:
        plan = ai.plan_roles(llm, team["course"], team["assignment"], [m["name"] for m in db.list_members(team["id"])], int(team["weeks"]))
    except Exception as e:  # noqa: BLE001
        return go(req, f"{base_url(team)}?tab=roles", f"실패: {e}", "error")
    db.save_plan(team["id"], plan)
    db.add_logs(team["id"], llm.logs)
    return go(req, f"{base_url(team)}?tab=roles&snooze=1", "AI가 역할과 주차별 목표를 다시 설계했습니다.")


@app.post("/t/{code}/report", response_class=HTMLResponse)
def report(req: Request, code: str):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    members = db.list_members(team["id"])
    subs, exts = db.list_submissions(team["id"]), db.list_extensions(team["id"])
    cur_w = db.current_week(team)
    slim = [{"member": s["member"], "week": s["week"], "verdict": s["verdict"], "score": s["score"],
             "summary": (s["review"].get("review", {}) or {}).get("summary", ""), "text": (s["text"] or "")[:200]} for s in subs]
    exslim = [{"member": e["member"], "week": e["week"], "until": e["until"]} for e in exts]
    llm = get_llm(req)
    try:
        rep = ai.build_report(llm, team={**team, "current_week": cur_w}, members=members, submissions=slim, extensions=exslim)
    except Exception:  # noqa: BLE001
        rep = ai.build_report(rule_llm(), team={**team, "current_week": cur_w}, members=members, submissions=slim, extensions=exslim)
    db.add_logs(team["id"], llm.logs)
    return team_page(req, team, me, tab="report", report=rep, snooze=True)


@app.get("/t/{code}/logs.json")
def logs_json(req: Request, code: str):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    body = json.dumps(db.list_logs(team["id"]), ensure_ascii=False, indent=2, default=str)
    return Response(body, media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename={team['code']}_prompt_log.json"})


@app.get("/t/{code}/export.json")
def export_json(req: Request, code: str):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    return Response(db.export_team(team), media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename=teamfair_{team['code']}.json"})


@app.post("/t/{code}/import")
async def import_json(req: Request, code: str, file: UploadFile = File(...)):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    if me["name"] != team["leader"] and team["code"] != db.DEMO_CODE:
        return go(req, f"{base_url(team)}?tab=tools", "팀장만 가져올 수 있습니다.", "error")
    try:
        payload = (await file.read()).decode("utf-8")
        if json.loads(payload)["team"]["code"] != team["code"]:
            return go(req, f"{base_url(team)}?tab=tools", "다른 팀의 백업 파일입니다.", "error")
        t2 = db.import_team(payload)
    except Exception as e:  # noqa: BLE001
        return go(req, f"{base_url(team)}?tab=tools", f"가져오기 실패: {e}", "error")
    return go(req, base_url(t2), "백업을 가져왔습니다.")


@app.post("/t/{code}/time")
def time_shift(req: Request, code: str, delta: int = Form(0)):
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    off = 0 if delta == 0 else int(team["sim_offset_days"] or 0) + int(delta)
    db.update_team(team["id"], sim_offset_days=off)
    return go(req, f"{base_url(team)}?tab=tools", f"가상 날짜를 옮겼습니다 (오프셋 {off}일).")


@app.get("/file/{name:path}")
def file_download(req: Request, name: str):
    code = name.split("_", 1)[0]
    team, me, bad = team_access(req, code)
    if bad:
        return bad
    data = db.get_file(name)
    if data is None:
        return error_page(req, "파일 없음", "첨부 파일을 찾을 수 없습니다.", 404)
    original = name.split("_", 3)[-1]
    return Response(data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(original)}"})


_ICONS = {"/icon-32.png": ("ICON_32", "image/png"), "/icon-180.png": ("ICON_180", "image/png"),
          "/favicon.ico": ("ICON_ICO", "image/x-icon"), "/apple-touch-icon.png": ("ICON_180", "image/png")}


def _icon_route(path: str):
    attr, mime = _ICONS[path]
    data = base64.b64decode(getattr(icon_data, attr))
    return lambda: Response(data, media_type=mime, headers={"Cache-Control": "public, max-age=3600"})


for _p in _ICONS:
    app.add_api_route(_p, _icon_route(_p), methods=["GET"], include_in_schema=False)


@app.get("/healthz")
def healthz():
    return {"ok": True, "storage": db.storage_label()}



@app.exception_handler(404)
async def not_found(request: Request, exc):
    return error_page(request, "페이지를 찾을 수 없습니다", "주소를 다시 확인해 주세요.", 404)
