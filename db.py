"""저장소. 팀 / 팀원 / 주간 제출 / 연장 / 프롬프트 로그 / 사용자 계정 / 첨부 파일.

- `DATABASE_URL`(Postgres, 예: Neon·Supabase 무료 DB)이 있으면 **영구 저장소**로 Postgres 를 사용한다.
  Streamlit Cloud 처럼 디스크가 휘발성인 환경에서도 계정·팀·제출물이 재시작 후 그대로 남는다.
- 없으면 로컬 SQLite 파일(`TEAMFAIR_DB`, 기본 teamfair.db)을 사용한다.

두 DB 모두 같은 SQL(`?` 플레이스홀더)로 다루기 위해 얇은 커넥션 래퍼(_Conn)를 둔다.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import random
import secrets as pysecrets
import sqlite3
import string
import threading
from datetime import date, datetime, time, timedelta
from typing import Optional

DB_PATH = os.environ.get("TEAMFAIR_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "teamfair.db"))
ACCEPTED = ("인정", "조건부 인정")
SESSION_DAYS = 30
MAX_FILE_BYTES = 8 * 1024 * 1024


_BOM = "\ufeff"  # 윈도우 파이프로 넣은 값 앞에 붙는 보이지 않는 문자


def _database_url() -> str:
    """환경변수 → st.secrets 순으로 DATABASE_URL 을 찾는다. (st 가 없으면 환경변수만)"""
    if os.environ.get("TEAMFAIR_FORCE_SQLITE"):  # 테스트용: secrets/환경변수와 무관하게 로컬 SQLite 강제
        return ""
    url = os.environ.get("DATABASE_URL", "").strip().lstrip(_BOM)  # Streamlit 은 secrets.toml 값을 환경변수로도 내보낸다
    if not url:
        try:
            import streamlit as st  # noqa: WPS433
            url = str(st.secrets.get("DATABASE_URL", "") or "")  # type: ignore[attr-defined]
        except Exception:
            url = ""
    return url.strip().lstrip(_BOM)


# ───────────── 커넥션 래퍼 ─────────────

class _Conn:
    """sqlite3 와 psycopg(Postgres) 를 같은 인터페이스로 감싼다.

    - execute(sql, params): `?` 플레이스홀더 공용. 결과 row 는 dict 처럼 접근 가능.
    - insert(sql, params): INSERT 후 새 id 반환 (sqlite: lastrowid / pg: RETURNING id).
    - with 블록 종료 시 commit(예외면 rollback).
    """

    def __init__(self, raw, pg: bool):
        self.raw, self.pg = raw, pg

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.pg else sql

    def execute(self, sql: str, params=()):
        if self.pg:
            from psycopg.rows import dict_row
            cur = self.raw.cursor(row_factory=dict_row)
            cur.execute(self._sql(sql), tuple(params))
            return cur
        return self.raw.execute(sql, tuple(params))

    def executemany(self, sql: str, seq) -> None:
        if self.pg:
            with self.raw.cursor() as cur:
                cur.executemany(self._sql(sql), [tuple(p) for p in seq])
        else:
            self.raw.executemany(sql, seq)

    def insert(self, sql: str, params=()) -> int:
        if self.pg:
            cur = self.execute(sql + " RETURNING id", params)
            return int(cur.fetchone()["id"])
        return int(self.raw.execute(sql, tuple(params)).lastrowid)

    def __enter__(self):
        if self.pg:
            _PG_LOCK.acquire()
        return self

    def __exit__(self, et, ev, tb):
        try:
            if et is None:
                self.raw.commit()
            else:
                self.raw.rollback()
        finally:
            if self.pg:
                _PG_LOCK.release()
            else:
                self.raw.close()
        return False


_PG_LOCK = threading.RLock()
_PG_CONN = None


def _pg_conn():
    """Postgres 는 접속 비용이 커서 모듈 전역 커넥션 하나를 재사용한다(끊기면 재접속)."""
    global _PG_CONN
    import psycopg
    with _PG_LOCK:
        if _PG_CONN is not None and not _PG_CONN.closed:
            try:
                with _PG_CONN.cursor() as cur:
                    cur.execute("SELECT 1")
                _PG_CONN.rollback()
                return _PG_CONN
            except Exception:
                try:
                    _PG_CONN.close()
                except Exception:
                    pass
        _PG_CONN = psycopg.connect(_database_url(), connect_timeout=15, autocommit=False)
        return _PG_CONN


def using_postgres() -> bool:
    return bool(_database_url())


def conn() -> _Conn:
    if using_postgres():
        return _Conn(_pg_conn(), pg=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return _Conn(c, pg=False)


def storage_label() -> str:
    return "Postgres (영구 저장)" if using_postgres() else "SQLite (로컬 파일)"


# ───────────── 스키마 ─────────────

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS teams(
        id {PK}, code TEXT UNIQUE, course TEXT, name TEXT, assignment TEXT,
        start_date TEXT, weeks INTEGER, leader TEXT, sim_offset_days INTEGER DEFAULT 0,
        advice TEXT DEFAULT '', milestones_json TEXT DEFAULT '[]', created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS members(
        id {PK}, team_id INTEGER, name TEXT, role TEXT DEFAULT '', role_desc TEXT DEFAULT '',
        goals_json TEXT DEFAULT '[]', status TEXT DEFAULT 'active', f_agreed_at TEXT, email TEXT)""",
    """CREATE TABLE IF NOT EXISTS submissions(
        id {PK}, team_id INTEGER, member_id INTEGER, week INTEGER, text TEXT, link TEXT,
        filename TEXT, score INTEGER, verdict TEXT, review_json TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS extensions(
        id {PK}, team_id INTEGER, member_id INTEGER, week INTEGER, until TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS prompt_logs(
        id {PK}, team_id INTEGER, stage TEXT, model TEXT, base_url TEXT, system_prompt TEXT,
        user_prompt TEXT, raw_response TEXT, elapsed_sec REAL, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS briefings(
        id {PK}, team_id INTEGER, week INTEGER, content_json TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS users(
        id {PK}, email TEXT UNIQUE, name TEXT, pw_hash TEXT, salt TEXT, created_at TEXT, last_login_at TEXT,
        recovery_hash TEXT, recovery_salt TEXT, failed_count INTEGER DEFAULT 0, locked_until TEXT)""",
    """CREATE TABLE IF NOT EXISTS sessions(
        id {PK}, token TEXT UNIQUE, email TEXT, created_at TEXT, expires_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS attachments(
        id {PK}, team_id INTEGER, filename TEXT UNIQUE, size INTEGER, data {BLOB}, created_at TEXT)""",
]

_INIT_DONE = False


def init() -> None:
    global _INIT_DONE
    if _INIT_DONE:
        return
    pg = using_postgres()
    pk = "SERIAL PRIMARY KEY" if pg else "INTEGER PRIMARY KEY"
    blob = "BYTEA" if pg else "BLOB"
    with conn() as c:
        for stmt in _SCHEMA:
            c.execute(stmt.replace("{PK}", pk).replace("{BLOB}", blob))
        # 구버전 DB 마이그레이션 (없는 컬럼만 추가)
        for table, col, typ in (("members", "email", "TEXT"), ("users", "recovery_hash", "TEXT"), ("users", "recovery_salt", "TEXT"),
                                ("users", "failed_count", "INTEGER DEFAULT 0"), ("users", "locked_until", "TEXT")):
            if pg:
                c.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {typ}")
            else:
                cols = [r["name"] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
                if col not in cols:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    _INIT_DONE = True


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _norm_email(email: str) -> str:
    return (email or "").strip().lower()


# ───────────── 사용자 계정 / 로그인 ─────────────
# 비밀번호·복구 코드는 PBKDF2-SHA256(20만 회) 해시로만 저장. 로그인 5회 실패 시 5분 잠금.

PW_MIN = 6
LOCK_AFTER, LOCK_MINUTES = 5, 5


def _hash_pw(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()


def _new_recovery_code() -> str:
    """사람이 적어둘 수 있는 복구 코드. 헷갈리는 글자(0/O/1/I)는 제외. 예: 7KQF-M3PX"""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(pysecrets.choice(alphabet) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def _norm_code(code: str) -> str:
    return (code or "").strip().upper().replace(" ", "").replace("-", "")


def _check_password(pw: str) -> None:
    if len(pw or "") < PW_MIN:
        raise ValueError(f"비밀번호는 {PW_MIN}자 이상이어야 합니다.")
    if pw.strip() != pw:
        raise ValueError("비밀번호 앞뒤에 공백은 쓸 수 없습니다.")


def _check_email(email: str) -> str:
    email = _norm_email(email)
    local, _, domain = email.partition("@")
    if not local or "." not in domain or " " in email or len(email) > 254:
        raise ValueError("올바른 이메일 주소를 입력해 주세요.")
    return email


def _set_secret(c, user_id: int, *, password: Optional[str] = None, recovery: Optional[str] = None) -> None:
    """비밀번호 / 복구 코드 중 넘어온 것만 새 salt 로 다시 해시해 저장."""
    if password is not None:
        salt = pysecrets.token_hex(16)
        c.execute("UPDATE users SET pw_hash=?, salt=?, failed_count=0, locked_until=NULL WHERE id=?", (_hash_pw(password, salt), salt, user_id))
    if recovery is not None:
        rsalt = pysecrets.token_hex(16)
        c.execute("UPDATE users SET recovery_hash=?, recovery_salt=? WHERE id=?", (_hash_pw(_norm_code(recovery), rsalt), rsalt, user_id))


def register_user(email: str, name: str, password: str) -> dict:
    """가입. 반환 dict 에 1회만 보여줄 'recovery_code' 가 포함된다."""
    email = _check_email(email)
    _check_password(password)
    if not (name or "").strip():
        raise ValueError("이름을 입력해 주세요.")
    if len(name.strip()) > 30:
        raise ValueError("이름은 30자 이하로 입력해 주세요.")
    if get_user(email):
        raise ValueError("이미 가입된 이메일입니다. 로그인해 주세요.")
    code = _new_recovery_code()
    with conn() as c:
        uid = c.insert("INSERT INTO users(email,name,pw_hash,salt,created_at,failed_count) VALUES(?,?,?,?,?,0)",
                       (email, name.strip(), "", "", _now_iso()))
        _set_secret(c, uid, password=password, recovery=code)
    u = get_user(email)
    u["recovery_code"] = code
    return u


def get_user(email: str) -> Optional[dict]:
    with conn() as c:
        r = c.execute("SELECT id,email,name,created_at,last_login_at FROM users WHERE email=?", (_norm_email(email),)).fetchone()
    return dict(r) if r else None


def _raw_user(c, email: str) -> Optional[dict]:
    r = c.execute("SELECT * FROM users WHERE email=?", (_norm_email(email),)).fetchone()
    return dict(r) if r else None


def login_lock_remaining(email: str) -> int:
    """잠금 상태면 남은 초, 아니면 0."""
    with conn() as c:
        r = _raw_user(c, email)
    if not r or not r.get("locked_until"):
        return 0
    left = (datetime.fromisoformat(r["locked_until"]) - datetime.now()).total_seconds()
    return max(0, int(left))


def verify_login(email: str, password: str) -> Optional[dict]:
    """성공 시 사용자 dict, 실패 시 None. 실패가 LOCK_AFTER 회 쌓이면 LOCK_MINUTES 분 잠금 (잠금 중엔 맞아도 거부)."""
    email = _norm_email(email)
    with conn() as c:
        r = _raw_user(c, email)
        if not r:
            return None
        if r.get("locked_until") and r["locked_until"] > _now_iso():
            return None
        if not r["pw_hash"] or not hmac.compare_digest(_hash_pw(password, r["salt"]), r["pw_hash"]):
            n = int(r.get("failed_count") or 0) + 1
            until = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds") if n >= LOCK_AFTER else None
            c.execute("UPDATE users SET failed_count=?, locked_until=? WHERE id=?", (0 if until else n, until, r["id"]))
            return None
        c.execute("UPDATE users SET last_login_at=?, failed_count=0, locked_until=NULL WHERE id=?", (_now_iso(), r["id"]))
    return get_user(email)


def change_password(email: str, current: str, new: str) -> None:
    _check_password(new)
    if current == new:
        raise ValueError("새 비밀번호가 현재 비밀번호와 같습니다.")
    if not verify_login(email, current):
        raise ValueError("현재 비밀번호가 올바르지 않습니다.")
    with conn() as c:
        r = _raw_user(c, email)
        _set_secret(c, r["id"], password=new)


def reset_password_with_code(email: str, code: str, new: str) -> str:
    """비밀번호 찾기: 이메일 + 복구 코드로 새 비밀번호 설정. 새 복구 코드를 발급해 돌려준다(이전 코드는 폐기)."""
    _check_password(new)
    with conn() as c:
        r = _raw_user(c, email)
        if not r or not r.get("recovery_hash") or not hmac.compare_digest(_hash_pw(_norm_code(code), r["recovery_salt"]), r["recovery_hash"]):
            raise ValueError("이메일 또는 복구 코드가 올바르지 않습니다.")
        new_code = _new_recovery_code()
        _set_secret(c, r["id"], password=new, recovery=new_code)
        c.execute("DELETE FROM sessions WHERE email=?", (_norm_email(email),))  # 다른 기기 세션 모두 종료
    return new_code


def regenerate_recovery_code(email: str, password: str) -> str:
    if not verify_login(email, password):
        raise ValueError("비밀번호가 올바르지 않습니다.")
    code = _new_recovery_code()
    with conn() as c:
        r = _raw_user(c, email)
        _set_secret(c, r["id"], recovery=code)
    return code


def rename_user(email: str, name: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("이름을 입력해 주세요.")
    if len(name) > 30:
        raise ValueError("이름은 30자 이하로 입력해 주세요.")
    with conn() as c:
        c.execute("UPDATE users SET name=? WHERE email=?", (name, _norm_email(email)))
    return get_user(email)


def delete_user(email: str, password: str) -> int:
    """회원 탈퇴. 비밀번호 확인 후 계정·세션 삭제. 팀 기록은 남기되 팀원-계정 연결만 해제한다.
    반환: 연결 해제된 팀원 수."""
    if not verify_login(email, password):
        raise ValueError("비밀번호가 올바르지 않습니다.")
    email = _norm_email(email)
    with conn() as c:
        n = len(c.execute("SELECT id FROM members WHERE email=?", (email,)).fetchall())
        c.execute("UPDATE members SET email=NULL WHERE email=?", (email,))
        c.execute("DELETE FROM sessions WHERE email=?", (email,))
        c.execute("DELETE FROM users WHERE email=?", (email,))
    return n


def create_session(email: str) -> str:
    token = pysecrets.token_urlsafe(32)
    now = datetime.now()
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE expires_at < ?", (now.isoformat(timespec="seconds"),))
        c.execute("INSERT INTO sessions(token,email,created_at,expires_at) VALUES(?,?,?,?)",
                  (token, _norm_email(email), now.isoformat(timespec="seconds"),
                   (now + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")))
    return token


def user_by_session(token: str) -> Optional[dict]:
    if not token:
        return None
    with conn() as c:
        r = c.execute("SELECT email, expires_at FROM sessions WHERE token=?", (token,)).fetchone()
    if not r or r["expires_at"] < _now_iso():
        return None
    return get_user(r["email"])


def delete_session(token: str) -> None:
    if not token:
        return
    with conn() as c:
        c.execute("DELETE FROM sessions WHERE token=?", (token,))


def delete_all_sessions(email: str) -> int:
    """모든 기기에서 로그아웃. 반환: 지운 세션 수."""
    with conn() as c:
        n = len(c.execute("SELECT id FROM sessions WHERE email=?", (_norm_email(email),)).fetchall())
        c.execute("DELETE FROM sessions WHERE email=?", (_norm_email(email),))
    return n


def count_sessions(email: str) -> int:
    with conn() as c:
        return len(c.execute("SELECT id FROM sessions WHERE email=? AND expires_at >= ?", (_norm_email(email), _now_iso())).fetchall())


# ───────────── 팀 ─────────────

def create_team(*, course: str, name: str, assignment: str, start_date: date, weeks: int, leader: str,
                members: list[str], code: Optional[str] = None, emails: Optional[dict] = None) -> dict:
    """members: 이름 목록. emails: {이름: 이메일} (선택) — 해당 이메일로 로그인한 사용자가 자동 매칭된다."""
    emails = {k: _norm_email(v) for k, v in (emails or {}).items() if v}
    with conn() as c:
        code = code or _code()
        while c.execute("SELECT 1 FROM teams WHERE code=?", (code,)).fetchone():
            code = _code()
        tid = c.insert(
            "INSERT INTO teams(code,course,name,assignment,start_date,weeks,leader,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (code, course, name, assignment, start_date.isoformat(), weeks, leader, _now_iso()))
        for m in members:
            c.execute("INSERT INTO members(team_id,name,email) VALUES(?,?,?)", (tid, m, emails.get(m) or None))
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
        for t in ("members", "submissions", "extensions", "prompt_logs", "briefings", "attachments"):
            c.execute(f"DELETE FROM {t} WHERE team_id=?", (team_id,))
        c.execute("DELETE FROM teams WHERE id=?", (team_id,))


def teams_for_email(email: str) -> list[dict]:
    """이 이메일이 팀원으로 연결된 팀 목록 (+ 내 이름)."""
    email = _norm_email(email)
    if not email:
        return []
    with conn() as c:
        rows = c.execute(
            "SELECT t.*, m.name AS my_name, m.status AS my_status FROM members m JOIN teams t ON t.id=m.team_id "
            "WHERE m.email=? ORDER BY t.id DESC", (email,)).fetchall()
    return [dict(r) for r in rows]


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


def member_by_email(team_id: int, email: str) -> Optional[dict]:
    email = _norm_email(email)
    if not email:
        return None
    for m in list_members(team_id):
        if _norm_email(m.get("email") or "") == email:
            return m
    return None


def claim_member(team_id: int, name: str, email: str) -> dict:
    """팀원 이름을 로그인 이메일과 연결한다. 이미 다른 이메일과 연결된 이름이면 거부."""
    email = _norm_email(email)
    m = get_member(team_id, name)
    if not m:
        raise ValueError("팀원 명단에 없는 이름입니다.")
    cur = _norm_email(m.get("email") or "")
    if cur and cur != email:
        raise ValueError(f"'{name}' 은(는) 이미 다른 계정과 연결되어 있습니다. 팀장에게 확인해 주세요.")
    other = member_by_email(team_id, email)
    if other and other["id"] != m["id"]:
        raise ValueError(f"이 계정은 이미 '{other['name']}' 으로 연결되어 있습니다.")
    update_member(m["id"], email=email)
    return get_member(team_id, name)


def update_member(member_id: int, **fields) -> None:
    if "goals" in fields:
        fields["goals_json"] = json.dumps(fields.pop("goals"), ensure_ascii=False)
    if "email" in fields:
        fields["email"] = _norm_email(fields["email"]) or None
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
        return c.insert(
            "INSERT INTO submissions(team_id,member_id,week,text,link,filename,score,verdict,review_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (team_id, member_id, week, text, link, filename, score, verdict, json.dumps(review, ensure_ascii=False), _now_iso()))


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


# ───────────── 첨부 파일 (DB 에 저장 → 재시작 후에도 유지) ─────────────

def save_file(team_id: int, filename: str, data: bytes) -> str:
    """파일 바이트를 DB 에 저장하고, 저장된(고유) 파일명을 돌려준다."""
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"파일은 {MAX_FILE_BYTES // (1024 * 1024)}MB 이하만 첨부할 수 있습니다.")
    with conn() as c:
        name = filename
        n = 1
        while c.execute("SELECT 1 FROM attachments WHERE filename=?", (name,)).fetchone():
            n += 1
            root, ext = os.path.splitext(filename)
            name = f"{root}({n}){ext}"
        c.execute("INSERT INTO attachments(team_id,filename,size,data,created_at) VALUES(?,?,?,?,?)",
                  (team_id, name, len(data), data, _now_iso()))
    return name


def get_file(filename: str) -> Optional[bytes]:
    if not filename:
        return None
    with conn() as c:
        r = c.execute("SELECT data FROM attachments WHERE filename=?", (filename,)).fetchone()
    if not r:
        return None
    d = r["data"]
    return bytes(d) if d is not None else None


# ───────────── 브리핑 ─────────────

def save_briefing(team_id: int, week: int, content: dict) -> None:
    with conn() as c:
        c.execute("INSERT INTO briefings(team_id,week,content_json,created_at) VALUES(?,?,?,?)",
                  (team_id, week, json.dumps(content, ensure_ascii=False), _now_iso()))


def get_briefing(team_id: int, week: int) -> Optional[dict]:
    with conn() as c:
        r = c.execute("SELECT * FROM briefings WHERE team_id=? AND week=? ORDER BY id DESC LIMIT 1", (team_id, week)).fetchone()
    if not r:
        return None
    d = json.loads(r["content_json"])
    d["_created_at"] = r["created_at"]
    return d


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
        tid = c.insert(
            "INSERT INTO teams(code,course,name,assignment,start_date,weeks,leader,sim_offset_days,advice,milestones_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (t["code"], t["course"], t["name"], t["assignment"], t["start_date"], t["weeks"], t["leader"],
             t.get("sim_offset_days", 0), t.get("advice", ""), t.get("milestones_json", "[]"), t.get("created_at") or _now_iso()))
        idmap = {}
        for m in d["members"]:
            mid = c.insert("INSERT INTO members(team_id,name,role,role_desc,goals_json,status,f_agreed_at,email) VALUES(?,?,?,?,?,?,?,?)",
                           (tid, m["name"], m.get("role", ""), m.get("role_desc", ""), m.get("goals_json", "[]"), m.get("status", "active"),
                            m.get("f_agreed_at"), _norm_email(m.get("email") or "") or None))
            idmap[m["id"]] = mid
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
