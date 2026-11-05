"""SQLite 저장소. 팀 / 팀원 / 주간 제출 / 연장 / 프롬프트 로그.

Streamlit Cloud 처럼 디스크가 휘발성인 환경에서는 재시작 시 초기화될 수 있으므로
사이드바의 '데이터 백업(JSON)' 으로 내보내기/가져오기를 지원한다.
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import string
from datetime import date, datetime, time, timedelta
from typing import Optional

DB_PATH = os.environ.get("TEAMFAIR_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "teamfair.db"))
ACCEPTED = ("인정", "조건부 인정")


def conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS teams(
                id INTEGER PRIMARY KEY, code TEXT UNIQUE, course TEXT, name TEXT, assignment TEXT,
                start_date TEXT, weeks INTEGER, leader TEXT, sim_offset_days INTEGER DEFAULT 0,
                advice TEXT DEFAULT '', milestones_json TEXT DEFAULT '[]', created_at TEXT);
            CREATE TABLE IF NOT EXISTS members(
                id INTEGER PRIMARY KEY, team_id INTEGER, name TEXT, role TEXT DEFAULT '', role_desc TEXT DEFAULT '',
                goals_json TEXT DEFAULT '[]', status TEXT DEFAULT 'active', f_agreed_at TEXT);
            CREATE TABLE IF NOT EXISTS submissions(
                id INTEGER PRIMARY KEY, team_id INTEGER, member_id INTEGER, week INTEGER, text TEXT, link TEXT,
                filename TEXT, score INTEGER, verdict TEXT, review_json TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS extensions(
                id INTEGER PRIMARY KEY, team_id INTEGER, member_id INTEGER, week INTEGER, until TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS prompt_logs(
                id INTEGER PRIMARY KEY, team_id INTEGER, stage TEXT, model TEXT, base_url TEXT, system_prompt TEXT,
                user_prompt TEXT, raw_response TEXT, elapsed_sec REAL, created_at TEXT);
            """
        )


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


# ───────────── 팀 ─────────────

def create_team(*, course: str, name: str, assignment: str, start_date: date, weeks: int, leader: str,
                members: list[str], code: Optional[str] = None) -> dict:
    with conn() as c:
        code = code or _code()
        while c.execute("SELECT 1 FROM teams WHERE code=?", (code,)).fetchone():
            code = _code()
        cur = c.execute(
            "INSERT INTO teams(code,course,name,assignment,start_date,weeks,leader,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (code, course, name, assignment, start_date.isoformat(), weeks, leader, _now_iso()))
        tid = cur.lastrowid
        for m in members:
            c.execute("INSERT INTO members(team_id,name) VALUES(?,?)", (tid, m))
    return get_team(code)


def get_team(code: str) -> Optional[dict]:
    with conn() as c:
        r = c.execute("SELECT * FROM teams WHERE code=?", (code.strip().upper(),)).fetchone()
    return dict(r) if r else None


def update_team(team_id: int, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE teams SET {cols} WHERE id=?", (*fields.values(), team_id))


def delete_team(team_id: int) -> None:
    with conn() as c:
        for t in ("members", "submissions", "extensions", "prompt_logs"):
            c.execute(f"DELETE FROM {t} WHERE team_id=?", (team_id,))
        c.execute("DELETE FROM teams WHERE id=?", (team_id,))


# ───────────── 팀원 ─────────────

def list_members(team_id: int) -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM members WHERE team_id=? ORDER BY id", (team_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["goals"] = json.loads(d.get("goals_json") or "[]")
        out.append(d)
    return out


def get_member(team_id: int, name: str) -> Optional[dict]:
    for m in list_members(team_id):
        if m["name"] == name:
            return m
    return None


def update_member(member_id: int, **fields) -> None:
    if "goals" in fields:
        fields["goals_json"] = json.dumps(fields.pop("goals"), ensure_ascii=False)
    cols = ", ".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE members SET {cols} WHERE id=?", (*fields.values(), member_id))


def mark_f(member_id: int, agreed: bool = True) -> None:
    update_member(member_id, status="F" if agreed else "active", f_agreed_at=_now_iso() if agreed else None)


def save_plan(team_id: int, plan: dict) -> None:
    members = {m["name"]: m for m in list_members(team_id)}
    for p in plan.get("members", []):
        m = members.get(p.get("name"))
        if m:
            update_member(m["id"], role=p.get("role", ""), role_desc=p.get("role_desc", ""), goals=p.get("weekly_goals", []))
    update_team(team_id, advice=plan.get("advice", ""), milestones_json=json.dumps(plan.get("milestones", []), ensure_ascii=False))


# ───────────── 제출 / 연장 ─────────────

def add_submission(team_id: int, member_id: int, week: int, *, text: str, link: str, filename: str,
                   score: int, verdict: str, review: dict) -> int:
    with conn() as c:
        cur = c.execute(
            "INSERT INTO submissions(team_id,member_id,week,text,link,filename,score,verdict,review_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (team_id, member_id, week, text, link, filename, score, verdict, json.dumps(review, ensure_ascii=False), _now_iso()))
        return cur.lastrowid


def list_submissions(team_id: int) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT s.*, m.name AS member FROM submissions s JOIN members m ON m.id=s.member_id WHERE s.team_id=? ORDER BY s.week, s.created_at",
            (team_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["review"] = json.loads(d.get("review_json") or "{}")
        out.append(d)
    return out


def grant_extension(team_id: int, member_id: int, week: int, until: datetime) -> None:
    with conn() as c:
        c.execute("INSERT INTO extensions(team_id,member_id,week,until,created_at) VALUES(?,?,?,?,?)",
                  (team_id, member_id, week, until.isoformat(timespec="seconds"), _now_iso()))


def list_extensions(team_id: int) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT e.*, m.name AS member FROM extensions e JOIN members m ON m.id=e.member_id WHERE e.team_id=? ORDER BY e.id",
            (team_id,)).fetchall()
    return [dict(r) for r in rows]


# ───────────── 프롬프트 로그 ─────────────

def add_logs(team_id: int, logs: list[dict]) -> None:
    if not logs:
        return
    with conn() as c:
        c.executemany(
            "INSERT INTO prompt_logs(team_id,stage,model,base_url,system_prompt,user_prompt,raw_response,elapsed_sec,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            [(team_id, l["stage"], l["model"], l.get("base_url"), l["system_prompt"], l["user_prompt"], l["raw_response"],
              l.get("elapsed_sec"), _now_iso()) for l in logs])


def list_logs(team_id: int) -> list[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM prompt_logs WHERE team_id=? ORDER BY id DESC", (team_id,)).fetchall()
    return [dict(r) for r in rows]


# ───────────── 시간 / 주차 계산 ─────────────

def team_now(team: dict) -> datetime:
    """데모용 가상 시간: 실제 현재 + sim_offset_days."""
    return datetime.now() + timedelta(days=int(team.get("sim_offset_days") or 0))


def start_date(team: dict) -> date:
    return date.fromisoformat(team["start_date"])


def week_deadline(team: dict, week: int) -> datetime:
    """w주차 마감 = 시작일 + 7w 일의 23:59."""
    return datetime.combine(start_date(team) + timedelta(days=7 * week), time(23, 59))


def current_week(team: dict) -> int:
    now = team_now(team)
    w = (now.date() - start_date(team)).days // 7 + 1
    return max(1, min(int(team["weeks"]), w))


def week_status(team: dict, member: dict, week: int, submissions: list[dict], extensions: list[dict]) -> dict:
    """한 팀원의 w주차 상태.
    status: done | conditional | open | extended | missed | F
    """
    if member.get("status") == "F":
        return {"status": "F", "label": "⚫ F 동의"}
    now = team_now(team)
    subs = [s for s in submissions if s["member_id"] == member["id"] and s["week"] == week]
    acc = [s for s in subs if s["verdict"] in ACCEPTED]
    if acc:
        best = max(acc, key=lambda s: s["score"] or 0)
        if best["verdict"] == "인정":
            return {"status": "done", "label": f"✅ {best['score']}점", "sub": best}
        return {"status": "conditional", "label": f"🟡 조건부 {best['score']}점", "sub": best}
    exts = [e for e in extensions if e["member_id"] == member["id"] and e["week"] == week]
    deadline = week_deadline(team, week)
    if now <= deadline:
        return {"status": "open", "label": "⏳ 진행 중", "deadline": deadline}
    for e in exts:
        until = datetime.fromisoformat(e["until"])
        if now <= until:
            return {"status": "extended", "label": "⏰ 연장 중", "deadline": until, "ext": e}
    return {"status": "missed", "label": "❌ 미제출" if not subs else "❌ 미인정", "ext_used": bool(exts)}


def pending_alert(team: dict, member: dict, submissions: list[dict], extensions: list[dict]) -> Optional[dict]:
    """팝업을 띄워야 할 가장 이른 '미제출' 주차 정보. 없으면 None."""
    if member.get("status") == "F":
        return None
    for w in range(1, int(team["weeks"]) + 1):
        st = week_status(team, member, w, submissions, extensions)
        if st["status"] == "missed":
            return {"week": w, **st}
    return None


# ───────────── 백업 ─────────────

def export_team(team: dict) -> str:
    return json.dumps({
        "team": team, "members": list_members(team["id"]), "submissions": list_submissions(team["id"]),
        "extensions": list_extensions(team["id"]), "logs": list_logs(team["id"]),
    }, ensure_ascii=False, indent=2, default=str)


def import_team(payload: str) -> dict:
    d = json.loads(payload)
    t = d["team"]
    old = get_team(t["code"])
    if old:
        delete_team(old["id"])
    with conn() as c:
        cur = c.execute(
            "INSERT INTO teams(code,course,name,assignment,start_date,weeks,leader,sim_offset_days,advice,milestones_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (t["code"], t["course"], t["name"], t["assignment"], t["start_date"], t["weeks"], t["leader"],
             t.get("sim_offset_days", 0), t.get("advice", ""), t.get("milestones_json", "[]"), t.get("created_at") or _now_iso()))
        tid = cur.lastrowid
        idmap = {}
        for m in d["members"]:
            cur = c.execute("INSERT INTO members(team_id,name,role,role_desc,goals_json,status,f_agreed_at) VALUES(?,?,?,?,?,?,?)",
                            (tid, m["name"], m.get("role", ""), m.get("role_desc", ""), m.get("goals_json", "[]"), m.get("status", "active"), m.get("f_agreed_at")))
            idmap[m["id"]] = cur.lastrowid
        for s in d.get("submissions", []):
            c.execute("INSERT INTO submissions(team_id,member_id,week,text,link,filename,score,verdict,review_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (tid, idmap.get(s["member_id"]), s["week"], s.get("text"), s.get("link"), s.get("filename"), s.get("score"), s.get("verdict"), s.get("review_json", "{}"), s.get("created_at")))
        for e in d.get("extensions", []):
            c.execute("INSERT INTO extensions(team_id,member_id,week,until,created_at) VALUES(?,?,?,?,?)",
                      (tid, idmap.get(e["member_id"]), e["week"], e["until"], e.get("created_at")))
        for l in d.get("logs", []):
            c.execute("INSERT INTO prompt_logs(team_id,stage,model,base_url,system_prompt,user_prompt,raw_response,elapsed_sec,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                      (tid, l["stage"], l["model"], l.get("base_url"), l["system_prompt"], l["user_prompt"], l["raw_response"], l.get("elapsed_sec"), l.get("created_at")))
    return get_team(t["code"])


# ───────────── 데모 팀 ─────────────

DEMO_CODE = "DEMO01"


def seed_demo(review_fn) -> dict:
    """심사용 데모 팀. 4명 · 3주 과제, 시작일은 15일 전 → 현재 3주차, 1·2주차 마감 경과.
    박지훈은 한 번도 제출하지 않아 로그인 시 '평화를 부수겠습니까?' 팝업이 뜬다."""
    old = get_team(DEMO_CODE)
    if old:
        delete_team(old["id"])
    members = ["김민수", "이서연", "박지훈", "최유진"]
    team = create_team(
        course="경영정보시스템", name="3조", leader="김민수", members=members, code=DEMO_CODE,
        assignment="국내 편의점 3사의 모바일 앱 UX를 비교 분석하고, 개선안을 담은 보고서(10쪽)와 발표(10분)를 완성한다.",
        start_date=date.today() - timedelta(days=15), weeks=3)
    plan = {
        "members": [
            {"name": "김민수", "role": "총괄·보고서", "role_desc": "구조 설계와 보고서 통합", "weekly_goals": ["보고서 목차·분석 프레임 1쪽", "1~2장 초안 4쪽", "최종 보고서 10쪽 통합"]},
            {"name": "이서연", "role": "UX 분석", "role_desc": "3사 앱 휴리스틱 평가", "weekly_goals": ["휴리스틱 평가표 설계", "3사 앱 평가 결과표+스크린샷 15장", "분석 장 작성 3쪽"]},
            {"name": "박지훈", "role": "사용자 설문", "role_desc": "설문 설계·수집·분석", "weekly_goals": ["설문 문항 15개 초안", "응답 50부 수집·기초 통계", "설문 결과 장 2쪽"]},
            {"name": "최유진", "role": "발표자료", "role_desc": "PPT 제작·리허설", "weekly_goals": ["디자인 템플릿·스토리라인", "PPT 1~8장", "PPT 완성 15장+리허설"]},
        ],
        "milestones": ["분석 프레임 확정", "데이터 수집 완료", "최종본 제출·리허설"],
        "advice": "① 매주 일요일 21시까지 작업물 업로드 ② 링크만 말고 '무엇을 얼마나'를 3줄 이상 적기",
    }
    save_plan(team["id"], plan)
    ms = {m["name"]: m for m in list_members(team["id"])}
    demo_subs = {
        ("김민수", 1): ("보고서 목차 7개 장으로 확정했습니다. 분석 프레임은 닐슨 10대 휴리스틱 + 과업 성공률로 잡았고, 각 장별 담당·분량 표를 넣었습니다. 노션 링크 참고.", "https://notion.so/demo/outline"),
        ("김민수", 2): ("1장 서론(1.5쪽) 2장 선행연구(2.5쪽) 초안 완성. 참고문헌 12건 정리, 편의점 앱 MAU 통계(2026.09 기준) 표 2개 추가.", "https://docs.google.com/demo/draft"),
        ("이서연", 1): ("휴리스틱 평가표를 10개 항목 × 5점 척도로 설계했고, 평가 시나리오(로그인→상품검색→결제) 3개를 정의했습니다. 평가표 시트 공유합니다.", "https://docs.google.com/demo/sheet"),
        ("이서연", 2): ("GS25·CU·세븐일레븐 앱 평가 완료. 항목별 점수표와 스크린샷 18장, 주요 문제점 12건을 정리했습니다. 세븐일레븐 결제 단계가 가장 길었습니다(7단계).", "https://drive.google.com/demo/screens"),
        ("최유진", 1): ("발표 스토리라인 10슬라이드 구성안과 디자인 템플릿(브랜드 컬러 3종) 초안을 만들었습니다. 피그마 링크.", "https://figma.com/demo/template"),
        ("최유진", 2): ("PPT 1~8장 제작 완료(표지·목차·문제정의·분석 프레임·3사 개요). 서연님 스크린샷 반영했습니다.", "https://figma.com/demo/slides"),
    }
    for (name, week), (text, link) in demo_subs.items():
        m = ms[name]
        goal = m["goals"][week - 1]
        res = review_fn(member=name, role=m["role"], goal=goal, week=week, text=text, link=link, filename="")
        add_submission(team["id"], m["id"], week, text=text, link=link, filename="",
                       score=int(res["verdict"].get("score", 0)), verdict=res["verdict"].get("verdict", "인정"), review=res)
    return get_team(DEMO_CODE)
