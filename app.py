"""팀플 서약 (TeamFair) — 무임승차 방지 팀 프로젝트 플랫폼

수업·팀·팀원 등록 → AI 역할 설계 → 매주 작업물 업로드(AI 검토·판정)
→ 미제출자에게 '평화를 부수겠습니까?' 팝업 → 하루 연장 또는 F 동의(이름 흑백 처리)
→ AI 기여도 리포트
"""
from __future__ import annotations

import html
import json
import os
from datetime import date, timedelta

import streamlit as st

import ai
import db

st.set_page_config(page_title="팀플 서약", page_icon="🤝", layout="wide")
db.init()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

st.markdown(
    """
<style>
.member-card{border:1px solid #e3e6ea;border-radius:14px;padding:14px 16px;margin-bottom:10px;background:#fff;}
.member-card .nm{font-size:1.15rem;font-weight:700;}
.member-card .rl{color:#4b5563;font-size:.9rem;margin-top:2px;}
.member-card .tag{display:inline-block;font-size:.75rem;padding:2px 8px;border-radius:999px;margin-left:6px;vertical-align:middle;}
.tag-leader{background:#eef2ff;color:#3730a3;} .tag-ok{background:#ecfdf5;color:#065f46;}
.tag-warn{background:#fffbeb;color:#92400e;} .tag-bad{background:#fef2f2;color:#991b1b;}
.member-card.f{filter:grayscale(100%);opacity:.55;background:#f3f4f6;}
.member-card.f .nm{text-decoration:line-through;color:#374151;}
.member-card.f .oath{font-size:.8rem;color:#111;margin-top:6px;font-style:italic;}
.grid{width:100%;border-collapse:collapse;font-size:.92rem;}
.grid th,.grid td{border-bottom:1px solid #eee;padding:8px 10px;text-align:center;}
.grid th{background:#f9fafb;} .grid td:first-child,.grid th:first-child{text-align:left;font-weight:600;}
.grid tr.f td{filter:grayscale(100%);opacity:.5;text-decoration:line-through;}
.peace{font-size:1.5rem;font-weight:800;text-align:center;margin:10px 0 18px;}
.small{color:#6b7280;font-size:.85rem;}
</style>
""",
    unsafe_allow_html=True,
)


# ───────────────────────── 공용 ─────────────────────────

def secret(k: str, default: str = "") -> str:
    try:
        v = st.secrets.get(k)  # type: ignore[attr-defined]
        if v:
            return str(v)
    except Exception:
        pass
    return os.getenv(k, default)


def get_llm() -> ai.LLM:
    s = st.session_state
    prov = ai.PROVIDERS[s.get("ai_provider", list(ai.PROVIDERS)[0])]
    base_url = s.get("ai_base_url", prov["base_url"] or "")
    key = s.get("ai_key") or secret(prov["key_env"])
    model = s.get("ai_model", prov["model"])
    return ai.LLM(base_url or None, key, model, enabled=s.get("ai_enabled", True))


def flush_logs(team_id: int, llm: ai.LLM) -> None:
    db.add_logs(team_id, llm.logs)
    llm.logs.clear()


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def go(team_code: str, me: str | None = None) -> None:
    st.session_state.team_code = team_code
    if me:
        st.session_state.me = me
    st.session_state.pop("pd_step", None)
    st.rerun()


# ───────────────────────── 사이드바 ─────────────────────────

with st.sidebar:
    st.markdown("## 🤝 팀플 서약")
    st.caption("무임승차 없는 팀 프로젝트 · 매주 작업물로 증명하기")

    with st.expander("🧠 AI 설정", expanded=False):
        names = list(ai.PROVIDERS)
        if "ai_provider" not in st.session_state:
            # 환경변수/Secrets 에 키가 있는 제공자를 기본 선택 (배포 환경에서 바로 AI 모드)
            st.session_state.ai_provider = next((n for n in names if secret(ai.PROVIDERS[n]["key_env"])), names[0])
            if secret("TILON_BASE_URL"):
                st.session_state.ai_base_url = secret("TILON_BASE_URL")
        prov_name = st.selectbox("LLM 제공자", names, key="ai_provider")
        prov = ai.PROVIDERS[prov_name]
        st.caption(prov["help"])
        if "_prov_last" not in st.session_state or st.session_state._prov_last != prov_name:
            st.session_state.ai_base_url = prov["base_url"] or ""
            st.session_state.ai_model = prov["model"]
            st.session_state._prov_last = prov_name
        st.text_input("Base URL (OpenAI 호환 엔드포인트)", key="ai_base_url")
        st.text_input("모델", key="ai_model")
        st.text_input("API Key", type="password", key="ai_key", help=f"비워두면 환경변수/Secrets 의 {prov['key_env']} 를 사용")
        st.toggle("AI 사용 (끄면 규칙 기반 모드)", value=True, key="ai_enabled")
        llm_probe = get_llm()
        if llm_probe.available:
            st.success(f"AI 모드 · {llm_probe.model}")
            if st.button("연결 테스트"):
                try:
                    st.info("응답: " + llm_probe.ping())
                except Exception as e:  # noqa: BLE001
                    st.error(f"연결 실패: {e}")
        else:
            st.warning("키가 없어 규칙 기반 모드로 동작합니다. (AI 설정에서 키 입력 또는 틸론 GPU 서버 주소 입력)")

    if st.session_state.get("team_code"):
        st.divider()
        _t = db.get_team(st.session_state.team_code)
        if _t:
            st.markdown(f"**{_t['course']} · {_t['name']}**  \n초대 코드 `{_t['code']}`")
            st.markdown(f"나: **{st.session_state.get('me', '미선택')}**")
            if st.button("팀 나가기 / 다른 팀", use_container_width=True):
                for k in ("team_code", "me", "pd_step"):
                    st.session_state.pop(k, None)
                st.rerun()
            with st.expander("⏩ 데모용 시간 이동", expanded=False):
                st.caption("심사·시연용. 팀 전체의 '오늘'을 옮겨 주차 마감을 지나게 할 수 있습니다.")
                c1, c2, c3 = st.columns(3)
                if c1.button("+1일"):
                    db.update_team(_t["id"], sim_offset_days=int(_t["sim_offset_days"]) + 1); st.rerun()
                if c2.button("+7일"):
                    db.update_team(_t["id"], sim_offset_days=int(_t["sim_offset_days"]) + 7); st.rerun()
                if c3.button("초기화"):
                    db.update_team(_t["id"], sim_offset_days=0); st.rerun()
                st.caption(f"현재 가상 날짜: {db.team_now(_t):%Y-%m-%d %H:%M} (오프셋 {_t['sim_offset_days']}일)")
            with st.expander("💾 데이터 백업", expanded=False):
                st.download_button("팀 데이터 JSON 내보내기", db.export_team(_t), file_name=f"teamfair_{_t['code']}.json", use_container_width=True)
                up = st.file_uploader("JSON 가져오기", type=["json"], key="import_json")
                if up and st.button("가져오기 실행"):
                    t2 = db.import_team(up.read().decode("utf-8"))
                    go(t2["code"])


# ───────────────────────── 랜딩 (팀 만들기 / 참여) ─────────────────────────

def landing() -> None:
    st.title("🤝 팀플 서약")
    st.markdown("##### 팀플 시작 전에 팀을 등록하고, **매주 작업물로 기여를 증명**하세요. 올리지 않으면… 팝업이 묻습니다.")
    st.caption("AI가 역할을 설계하고, 제출물이 '진짜 작업물'인지 검토·판정하며, 학기 말 기여도 리포트를 만들어 줍니다.")

    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("① 팀 만들기")
        with st.form("create_team"):
            course = st.text_input("팀플 수업 이름", placeholder="예: 경영정보시스템")
            tname = st.text_input("팀 이름", placeholder="예: 3조")
            members_raw = st.text_area("구성원 이름 (한 줄에 한 명, 첫 번째가 팀장)", placeholder="김민수\n이서연\n박지훈\n최유진", height=110)
            assignment = st.text_area("이 수업에서 함께 해야 하는 과제", placeholder="예: 국내 편의점 3사 앱 UX 비교 분석 보고서(10쪽) + 발표(10분)", height=90)
            c1, c2 = st.columns(2)
            weeks = c1.number_input("프로젝트 기간 (주)", 1, 16, 4)
            sdate = c2.date_input("시작일 (매주 이 요일이 마감)", value=date.today())
            use_ai = st.checkbox("AI로 역할·주차별 목표 자동 설계", value=True)
            ok = st.form_submit_button("팀 만들기 🚀", use_container_width=True)
        if ok:
            members = [m.strip() for m in members_raw.replace(",", "\n").split("\n") if m.strip()]
            if not course or not tname or len(members) < 2 or not assignment:
                st.error("수업 이름, 팀 이름, 구성원 2명 이상, 과제 내용을 모두 입력해 주세요.")
            elif len(set(members)) != len(members):
                st.error("구성원 이름이 중복됩니다.")
            else:
                team = db.create_team(course=course, name=tname, assignment=assignment, start_date=sdate,
                                      weeks=int(weeks), leader=members[0], members=members)
                llm = get_llm()
                with st.spinner("AI가 역할과 주차별 목표를 설계하는 중…" if (use_ai and llm.available) else "역할 템플릿 생성 중…"):
                    try:
                        plan = ai.plan_roles(llm if use_ai else ai.LLM(None, "", "", enabled=False), course, assignment, members, int(weeks))
                    except Exception as e:  # noqa: BLE001
                        st.warning(f"AI 설계 실패로 템플릿을 사용합니다: {e}")
                        plan = ai.plan_roles(ai.LLM(None, "", "", enabled=False), course, assignment, members, int(weeks))
                    db.save_plan(team["id"], plan)
                    flush_logs(team["id"], llm)
                st.success(f"팀이 만들어졌습니다! 초대 코드 **{team['code']}** 를 팀원에게 공유하세요.")
                go(team["code"], members[0])

    with right:
        st.subheader("② 팀 참여하기")
        code = st.text_input("초대 코드", placeholder="예: DEMO01").strip().upper()
        if code:
            team = db.get_team(code)
            if not team:
                st.error("해당 코드의 팀이 없습니다.")
            else:
                st.info(f"{team['course']} · {team['name']} · {team['weeks']}주 과제")
                me = st.selectbox("내 이름", [m["name"] for m in db.list_members(team["id"])])
                if st.button("입장하기", use_container_width=True):
                    go(code, me)
        st.divider()
        st.subheader("🎬 바로 체험 (데모 팀)")
        st.caption("4명 · 3주 과제 · 현재 3주차. **박지훈**은 한 번도 올리지 않았습니다. 박지훈으로 입장하면 팝업을 볼 수 있어요.")
        if st.button("데모 팀 생성하고 입장", use_container_width=True):
            llm = ai.LLM(None, "", "", enabled=False)  # 데모 시드는 즉시 생성(규칙 기반 검토)
            team = db.seed_demo(lambda **kw: ai.review_submission(llm, **kw))
            go(team["code"], "박지훈")


# ───────────────────────── 평화 팝업 ─────────────────────────

@st.dialog("⚠️ 이번 주 작업물이 없습니다")
def peace_dialog(team: dict, me: dict, alert: dict) -> None:
    week = alert["week"]
    step = st.session_state.get("pd_step", "ask")

    if step == "ask":
        st.markdown(f"**{me['name']}** 님, **{week}주차** 작업물을 마감({db.week_deadline(team, week):%m/%d %H:%M})까지 올리지 않으셨습니다.")
        st.markdown(f"<div class='small'>이번 주 목표: {esc((me['goals'] or ['-'] * week)[week - 1])}</div>", unsafe_allow_html=True)
        st.markdown("<div class='peace'>팀의 평화를 부수겠습니까?</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("예", use_container_width=True, key="pd_yes"):
            st.session_state.pd_step = "confirm"
            st.rerun(scope="fragment")
        if alert.get("ext_used"):
            c2.button("아니요 (연장 기회 소진)", use_container_width=True, disabled=True, key="pd_no_d")
            st.caption("이미 하루 연장을 사용했습니다. 지금 바로 '작업물 올리기' 탭에서 제출하면 팝업이 사라집니다.")
            if st.button("지금 올리러 가기", use_container_width=True, key="pd_upload"):
                st.session_state.force_tab_upload = True
                st.session_state.pd_snooze = True
                st.rerun()
        else:
            if c2.button("아니요", use_container_width=True, key="pd_no"):
                until = db.team_now(team) + timedelta(days=1)
                db.grant_extension(team["id"], me["id"], week, until)
                st.session_state.pop("pd_step", None)
                st.session_state.toast = f"기회를 드립니다. {week}주차 마감이 하루 연장되었습니다 ({until:%m/%d %H:%M}까지)."
                st.rerun()

    elif step == "confirm":
        st.markdown("<div class='peace'>혼자 F를 받는 것에 동의한다는 건가요?</div>", unsafe_allow_html=True)
        st.caption("'예'를 누르면 되돌릴 수 없으며, 팀 보드에서 이름이 흑백으로 표시되고 교수님께 별도 보고됩니다.")
        c1, c2 = st.columns(2)
        if c1.button("예", use_container_width=True, key="pd_yes2"):
            db.mark_f(me["id"], True)
            st.session_state.pd_step = "done"
            st.rerun(scope="fragment")
        if c2.button("뒤로가기", use_container_width=True, key="pd_back"):
            st.session_state.pd_step = "ask"
            st.rerun(scope="fragment")

    else:  # done
        st.markdown("<div class='peace'>F를 받는데 동의하셨습니다.</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='member-card f'><div class='nm'>{esc(me['name'])}</div>"
            f"<div class='oath'>“F를 받겠습니다. 교수님께 따로 말씀드리는 것에 동의합니다.”</div></div>",
            unsafe_allow_html=True,
        )
        if st.button("확인", use_container_width=True, key="pd_done"):
            st.session_state.pop("pd_step", None)
            st.rerun()


# ───────────────────────── 팀 화면 ─────────────────────────

def member_card(m: dict, team: dict, status_label: str) -> str:
    cls = "member-card f" if m["status"] == "F" else "member-card"
    tags = ""
    if m["name"] == team["leader"]:
        tags += "<span class='tag tag-leader'>팀장</span>"
    oath = "<div class='oath'>“F를 받겠습니다. 교수님께 따로 말씀드리는 것에 동의합니다.”</div>" if m["status"] == "F" else ""
    return (f"<div class='{cls}'><div class='nm'>{esc(m['name'])}{tags}</div>"
            f"<div class='rl'>{esc(m['role'] or '역할 미정')} · {esc(m['role_desc'])}</div>"
            f"<div class='small' style='margin-top:4px'>{status_label}</div>{oath}</div>")


def team_page(team: dict) -> None:
    members = db.list_members(team["id"])
    subs = db.list_submissions(team["id"])
    exts = db.list_extensions(team["id"])
    me_name = st.session_state.get("me")
    me = db.get_member(team["id"], me_name) if me_name else None
    cur_w = db.current_week(team)
    now = db.team_now(team)

    _toast = st.session_state.pop("toast", None)
    if _toast:
        st.toast(_toast, icon="⏰")
        st.info(_toast)
    if "toast_msg" in st.session_state:
        st.success(st.session_state.pop("toast_msg"))

    if not me:
        st.title(f"{team['course']} · {team['name']}")
        me_sel = st.selectbox("내 이름을 선택하세요", [m["name"] for m in members])
        if st.button("입장"):
            go(team["code"], me_sel)
        return

    # 팝업 트리거
    alert = db.pending_alert(team, me, subs, exts)
    if alert and not st.session_state.get("pd_snooze"):
        peace_dialog(team, me, alert)
    st.session_state.pop("pd_snooze", None)

    # 헤더
    deadline = db.week_deadline(team, cur_w)
    dleft = (deadline - now)
    dd = f"D-{dleft.days}" if dleft.days >= 0 else f"D+{-dleft.days}"
    st.title(f"{team['course']} · {team['name']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("현재 주차", f"{cur_w} / {team['weeks']}주")
    c2.metric("이번 주 마감", f"{deadline:%m/%d}", dd)
    done_cnt = sum(1 for m in members if db.week_status(team, m, cur_w, subs, exts)["status"] in ("done", "conditional"))
    c3.metric("이번 주 제출", f"{done_cnt} / {len(members)}명")
    c4.metric("가상 오늘", f"{now:%m/%d}")

    tabs = ["🏠 팀 보드", "📤 작업물 올리기", "🧭 역할·주차 목표", "📊 AI 기여도 리포트", "🧾 프롬프트 기록"]
    t_board, t_up, t_role, t_rep, t_log = st.tabs(tabs)

    # ── 팀 보드
    with t_board:
        st.markdown(f"**과제** · {esc(team['assignment'])}", unsafe_allow_html=True)
        if team.get("advice"):
            st.info("🛡️ 팀 규칙 · " + team["advice"])
        cols = st.columns(min(4, len(members)))
        for i, m in enumerate(members):
            stt = db.week_status(team, m, cur_w, subs, exts)
            cols[i % len(cols)].markdown(member_card(m, team, f"{cur_w}주차: {stt['label']}"), unsafe_allow_html=True)

        st.markdown("#### 주차별 제출 현황")
        head = "".join(f"<th>{w}주차<br><span class='small'>~{db.week_deadline(team, w):%m/%d}</span></th>" for w in range(1, team["weeks"] + 1))
        rows = ""
        for m in members:
            cells = "".join(f"<td>{db.week_status(team, m, w, subs, exts)['label']}</td>" for w in range(1, team["weeks"] + 1))
            rows += f"<tr class='{'f' if m['status'] == 'F' else ''}'><td>{esc(m['name'])}</td>{cells}</tr>"
        st.markdown(f"<table class='grid'><tr><th>팀원</th>{head}</tr>{rows}</table>", unsafe_allow_html=True)
        st.caption("✅ 인정 · 🟡 조건부 인정 · ⏳ 진행 중 · ⏰ 하루 연장 중 · ❌ 미제출/미인정 · ⚫ F 동의")

        if subs:
            st.markdown("#### 최근 제출물")
            for s in sorted(subs, key=lambda x: x["created_at"], reverse=True)[:6]:
                with st.expander(f"{s['week']}주차 · {s['member']} · {s['verdict']} {s['score']}점 · {s['created_at'][:16]}"):
                    st.write(s["text"])
                    if s["link"]:
                        st.markdown(f"🔗 {s['link']}")
                    if s["filename"]:
                        st.markdown(f"📎 {s['filename']}")
                    rv = s["review"].get("review", {})
                    if rv:
                        st.caption("AI 검토 · " + rv.get("summary", ""))

    # ── 작업물 올리기
    with t_up:
        if me["status"] == "F":
            st.error("F 동의 상태에서는 제출할 수 없습니다. 팀장이 '역할·주차 목표' 탭에서 되돌릴 수 있습니다.")
        else:
            weeks_sel = [w for w in range(1, team["weeks"] + 1)
                         if db.week_status(team, me, w, subs, exts)["status"] in ("open", "extended", "missed")]
            if not weeks_sel:
                st.success("제출할 주차가 없습니다. 모든 주차가 처리되었어요 👏")
            else:
                default_idx = weeks_sel.index(cur_w) if cur_w in weeks_sel else 0
                w = st.selectbox("제출 주차", weeks_sel, index=default_idx, format_func=lambda x: f"{x}주차")
                goal = (me["goals"][w - 1] if len(me["goals"]) >= w else "(목표 미설정)")
                stt = db.week_status(team, me, w, subs, exts)
                st.markdown(f"**내 역할** {esc(me['role'])} · **{w}주차 목표** {esc(goal)}", unsafe_allow_html=True)
                st.caption(f"상태: {stt['label']}" + (f" · 마감 {stt['deadline']:%m/%d %H:%M}" if stt.get("deadline") else ""))
                with st.form("upload"):
                    text = st.text_area("이번 주에 한 일 (무엇을 · 얼마나 · 어떻게, 3줄 이상 권장)", height=160,
                                        placeholder="예: 설문 문항 15개 초안 작성. 인구통계 4 + 이용행태 6 + 만족도 5 문항, 5점 척도. 구글폼 링크 첨부.")
                    link = st.text_input("결과물 링크 (노션/드라이브/깃허브 등)")
                    f = st.file_uploader("파일 첨부 (선택)")
                    sub = st.form_submit_button("제출하고 AI 검토 받기", use_container_width=True)
                if sub:
                    if not text.strip() and not link and not f:
                        st.error("내용, 링크, 파일 중 하나는 있어야 합니다.")
                    else:
                        fname = ""
                        if f is not None:
                            safe = os.path.basename(f.name).replace(" ", "_")
                            fname = f"{team['code']}_w{w}_{me['name']}_{safe}"
                            with open(os.path.join(UPLOAD_DIR, fname), "wb") as fp:
                                fp.write(f.getbuffer())
                        llm = get_llm()
                        with st.spinner("검토 AI → 판정 AI 가 제출물을 확인하는 중…" if llm.available else "규칙 기반 검토 중…"):
                            try:
                                res = ai.review_submission(llm, member=me["name"], role=me["role"], goal=goal, week=w,
                                                           text=text, link=link, filename=fname)
                            except Exception as e:  # noqa: BLE001
                                st.warning(f"AI 검토 실패 → 규칙 기반으로 대체: {e}")
                                res = ai.review_submission(ai.LLM(None, "", "", enabled=False), member=me["name"], role=me["role"],
                                                           goal=goal, week=w, text=text, link=link, filename=fname)
                            flush_logs(team["id"], llm)
                        v, rv = res["verdict"], res["review"]
                        db.add_submission(team["id"], me["id"], w, text=text, link=link, filename=fname,
                                          score=int(v.get("score", 0)), verdict=v.get("verdict", "미인정"), review=res)
                        icon = {"인정": "✅", "조건부 인정": "🟡"}.get(v.get("verdict"), "❌")
                        st.markdown(f"### {icon} 판정: **{v.get('verdict')}** · {v.get('score')}점")
                        st.write(v.get("reason", ""))
                        if v.get("required_fix") and v.get("required_fix") != "없음":
                            st.warning("보완 요구: " + v["required_fix"])
                        m1, m2, m3, m4 = st.columns(4)
                        m1.metric("관련성", rv.get("relevance", 0)); m2.metric("완성도", rv.get("completeness", 0))
                        m3.metric("노력", rv.get("effort", 0)); m4.metric("명확성", rv.get("clarity", 0))
                        if rv.get("strengths"):
                            st.markdown("**잘한 점** · " + " / ".join(rv["strengths"]))
                        if rv.get("improvements"):
                            st.markdown("**보완점** · " + " / ".join(rv["improvements"]))
                        if rv.get("next_week_tip"):
                            st.caption("💡 " + rv["next_week_tip"])
                        if v.get("verdict") == "미인정":
                            st.error("미인정 제출은 제출로 집계되지 않습니다. 보완해서 다시 올려주세요.")
                        if st.button("팀 보드로 새로고침"):
                            st.rerun()

    # ── 역할·주차 목표
    with t_role:
        is_leader = me["name"] == team["leader"]
        st.caption("AI가 설계한 역할과 주차별 산출물 목표입니다. 팀장은 수정할 수 있습니다.")
        ms = team.get("milestones_json")
        try:
            milestones = json.loads(ms or "[]")
        except Exception:
            milestones = []
        if milestones:
            st.markdown("**팀 마일스톤** · " + " → ".join(f"{i + 1}주 {m}" for i, m in enumerate(milestones)))
        for m in members:
            with st.expander(f"{m['name']} · {m['role'] or '역할 미정'}" + (" · ⚫ F 동의" if m["status"] == "F" else ""), expanded=(m["id"] == me["id"])):
                if is_leader:
                    role = st.text_input("역할", m["role"], key=f"role_{m['id']}")
                    rdesc = st.text_input("역할 설명", m["role_desc"], key=f"rdesc_{m['id']}")
                    goals = []
                    for w in range(1, team["weeks"] + 1):
                        g = m["goals"][w - 1] if len(m["goals"]) >= w else ""
                        goals.append(st.text_input(f"{w}주차 목표", g, key=f"goal_{m['id']}_{w}"))
                    c1, c2 = st.columns(2)
                    if c1.button("저장", key=f"save_{m['id']}"):
                        db.update_member(m["id"], role=role, role_desc=rdesc, goals=goals)
                        st.session_state.toast_msg = f"{m['name']} 역할을 저장했습니다."
                        st.rerun()
                    if m["status"] == "F" and c2.button("F 동의 되돌리기 (팀장)", key=f"unf_{m['id']}"):
                        db.mark_f(m["id"], False)
                        st.rerun()
                else:
                    st.markdown(f"**{m['role']}** · {m['role_desc']}")
                    for w in range(1, team["weeks"] + 1):
                        g = m["goals"][w - 1] if len(m["goals"]) >= w else "-"
                        st.markdown(f"- {w}주차: {g}")
        if is_leader:
            st.divider()
            if st.button("🔁 AI로 역할 다시 설계", help="기존 역할·목표를 덮어씁니다."):
                llm = get_llm()
                with st.spinner("역할 설계 AI 실행 중…"):
                    try:
                        plan = ai.plan_roles(llm, team["course"], team["assignment"], [m["name"] for m in members], int(team["weeks"]))
                        db.save_plan(team["id"], plan)
                        flush_logs(team["id"], llm)
                        st.rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"실패: {e}")

    # ── 리포트
    with t_rep:
        st.caption("주간 제출 기록·판정 점수·연장/F 이력을 종합해 교수님 제출용 기여도 보고서를 만듭니다.")
        if st.button("📊 리포트 생성", use_container_width=True):
            llm = get_llm()
            with st.spinner("리포트 AI 작성 중…" if llm.available else "규칙 기반 집계 중…"):
                slim = [{"member": s["member"], "week": s["week"], "verdict": s["verdict"], "score": s["score"],
                         "summary": (s["review"].get("review", {}) or {}).get("summary", ""), "text": (s["text"] or "")[:200]} for s in subs]
                exslim = [{"member": e["member"], "week": e["week"], "until": e["until"]} for e in exts]
                try:
                    rep = ai.build_report(llm, team={**team, "current_week": cur_w}, members=members, submissions=slim, extensions=exslim)
                except Exception as e:  # noqa: BLE001
                    st.warning(f"AI 리포트 실패 → 규칙 기반으로 대체: {e}")
                    rep = ai.build_report(ai.LLM(None, "", "", enabled=False), team={**team, "current_week": cur_w}, members=members, submissions=slim, extensions=exslim)
                flush_logs(team["id"], llm)
                st.session_state.report = rep
        rep = st.session_state.get("report")
        if rep:
            st.markdown(f"<span class='small'>모드: {'LLM' if rep.get('mode') == 'llm' else '규칙 기반'}</span>", unsafe_allow_html=True)
            cols = st.columns(len(rep.get("contribution", [])) or 1)
            for i, c in enumerate(rep.get("contribution", [])):
                cols[i].metric(c["name"], f"{c['percent']}%", help=c.get("basis", ""))
            st.markdown(rep.get("report_md", ""))
            st.download_button("보고서 .md 다운로드", rep.get("report_md", ""), file_name=f"{team['code']}_report.md")
            if rep.get("peer_eval"):
                st.markdown("#### 동료평가 초안")
                for p in rep["peer_eval"]:
                    st.markdown(f"- **{p['name']}** · {p['draft']}")
            if rep.get("nudges"):
                st.markdown("#### 팀장이 보낼 메시지 초안")
                for n in rep["nudges"]:
                    st.code(f"[{n['name']}] {n['message']}", language=None)

    # ── 프롬프트 기록
    with t_log:
        logs = db.list_logs(team["id"])
        st.caption("이 팀에서 실행된 모든 AI 호출(시스템 프롬프트·입력·원문 응답)이 자동 기록됩니다. 제출용 '프롬프트 기록'으로 바로 내려받을 수 있습니다.")
        if logs:
            st.download_button("프롬프트 기록 JSON 다운로드", json.dumps(logs, ensure_ascii=False, indent=2),
                               file_name=f"{team['code']}_prompt_log.json")
            for l in logs[:30]:
                with st.expander(f"{l['created_at'][:16]} · {l['stage']} · {l['model']} · {l['elapsed_sec']}s"):
                    st.markdown("**System prompt**"); st.code(l["system_prompt"], language=None)
                    st.markdown("**User prompt**"); st.code(l["user_prompt"][:4000], language=None)
                    st.markdown("**Response**"); st.code(l["raw_response"][:4000], language="json")
        else:
            st.info("아직 AI 호출 기록이 없습니다. (규칙 기반 모드에서는 기록되지 않습니다 — 사이드바 AI 설정에서 키를 넣어 주세요)")


# ───────────────────────── 라우팅 ─────────────────────────

if st.session_state.get("team_code"):
    _team = db.get_team(st.session_state.team_code)
    if _team:
        team_page(_team)
    else:
        st.session_state.pop("team_code", None)
        landing()
else:
    landing()
