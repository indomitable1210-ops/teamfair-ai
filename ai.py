"""Multi-AI 파이프라인 (OpenAI 호환 인터페이스).

역할 설계 AI → (제출 시) 검토 AI → 판정 AI → (주차/최종) 리포트 AI

모든 호출이 OpenAI Chat Completions 호환 형식이므로
교내 틸론(Tilon) GPU에서 vLLM / Ollama 로 띄운 로컬 모델(EXAONE, Qwen 등)도
base_url 만 바꾸면 그대로 연결된다.  API 키가 없으면 규칙 기반 모드로 동작한다.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Optional


def load_env_local() -> None:
    """로컬 개발용: 프로젝트 폴더의 .env.local (KEY=VALUE) 을 환경변수로 읽는다. 이미 있는 값은 덮어쓰지 않는다.
    배포(Vercel)에서는 프로젝트 Environment Variables 가 그대로 쓰이고, .env.local 은 업로드되지 않는다."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.local")
    if os.environ.get("TEAMFAIR_NO_ENV_LOCAL") or not os.path.exists(path):  # 테스트는 실제 키를 쓰지 않도록
        return
    for line in open(path, encoding="utf-8-sig"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env_local()

PROVIDERS = {
    "틸론 GPU 서버 (vLLM/Ollama · OpenAI 호환)": {
        "base_url": "http://localhost:8000/v1",
        "model": "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct",
        "key_env": "TILON_API_KEY",
        "help": "교내 틸론 GPU VM에서 vllm serve / ollama serve 로 띄운 주소(예: http://<틸론VM-IP>:8000/v1). API Key 칸에는 EMPTY 라고 입력하세요.",
    },
    "Groq (무료 티어)": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "key_env": "GROQ_API_KEY",
        "help": "console.groq.com 에서 무료 키 발급.",
    },
    "Google Gemini (무료 티어)": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.5-flash",
        "key_env": "GEMINI_API_KEY",
        "help": "aistudio.google.com 에서 무료 키 발급.",
    },
    "OpenAI": {
        "base_url": None,
        "model": os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        "key_env": "OPENAI_API_KEY",
        "help": "platform.openai.com 에서 발급한 키.",
    },
}

# ───────────────────────── 프롬프트 (PROMPT_LOG.md 와 동일) ─────────────────────────

PLANNER_SYSTEM = """당신은 대학 팀 프로젝트의 '역할 설계 AI'입니다.
과제 설명과 팀원 명단, 프로젝트 기간(주 단위)을 받아 **무임승차가 불가능하도록** 역할을 설계합니다.

설계 원칙
1. 모든 팀원에게 '매주 검증 가능한 산출물'이 하나 이상 있어야 합니다. (예: "시장조사 보고서 2쪽", "PPT 5~8장", "설문 문항 15개")
2. 업무량은 균등하게. 특정 팀원에게 '취합', '검토'처럼 산출물이 모호한 역할만 주지 마세요.
3. 주차별 목표는 그 주에 끝낼 수 있는 크기로, 전 주 결과물과 연결되게 설계합니다.
4. 마지막 주는 통합·리허설이 포함됩니다.
5. 반드시 아래 JSON 스키마로만 응답합니다. 설명 문장 금지.

{
  "members": [
    {"name": "이름", "role": "역할명 (8자 이내)", "role_desc": "역할 설명 1문장",
     "weekly_goals": ["1주차 산출물", "2주차 산출물", "..."]}
  ],
  "milestones": ["1주차 팀 마일스톤", "2주차 ...", "..."],
  "advice": "이 팀이 무임승차를 막기 위해 지킬 규칙 2가지"
}
weekly_goals 길이는 반드시 프로젝트 주차 수와 같아야 합니다."""

REVIEWER_SYSTEM = """당신은 팀 프로젝트 주간 제출물을 검토하는 '검토 AI'입니다.
팀원의 역할, 이번 주 목표, 그리고 제출한 작업물(텍스트/링크 설명/파일명)을 보고 **구체적이고 공정하게** 검토합니다.

검토 기준 (각 0~100)
- relevance: 이번 주 목표와 얼마나 관련 있는가
- completeness: 목표 대비 완성도
- effort: 실제 투입 노력의 흔적 (구체적 수치·출처·구조·분량)
- clarity: 팀원이 바로 이어받아 쓸 수 있을 만큼 명확한가

주의
- 칭찬만 하지 마세요. 부족한 점은 구체적으로 지적하되 정중하게.
- "열심히 했습니다", "다음 주에 올릴게요" 같은 내용 없는 제출은 모든 점수를 20 이하로 주세요.
- 링크만 있고 설명이 없으면 completeness 를 50 이하로 하고 '설명 보강'을 요구하세요.
반드시 아래 JSON 으로만 응답합니다.

{
  "relevance": 0, "completeness": 0, "effort": 0, "clarity": 0,
  "summary": "제출물 2문장 요약",
  "strengths": ["강점1", "강점2"],
  "improvements": ["보완점1", "보완점2"],
  "next_week_tip": "다음 주를 위한 조언 1문장"
}"""

GATEKEEPER_SYSTEM = """당신은 제출물 인정 여부를 최종 판정하는 '판정 AI'입니다.
검토 AI 의 채점 결과와 원문 제출물을 함께 보고, 이것이 **'실질적인 작업물'인지, 아니면 제출 흉내만 낸 것인지** 판정합니다.

판정 규칙
1. 네 항목 평균이 40 미만이면 원칙적으로 "미인정".
2. 제출 텍스트가 50자 미만이고 링크·파일도 없으면 "미인정".
3. 목표와 전혀 다른 내용(예: 목표는 설문 설계인데 제출은 일기)이면 "미인정".
4. 애매하면 "조건부 인정"으로 하고, 48시간 내 보완할 항목을 명시합니다.
5. 판정 이유는 팀원이 납득할 수 있도록 근거 중심으로 2~3문장.
6. [유사도 검사 결과]에 '재탕'(본인의 이전 제출과 80% 이상 동일) 또는 '복붙'(다른 팀원 제출과 80% 이상 동일)이 있으면
   내용이 아무리 좋아도 "미인정"으로 판정하고 flags 에 넣습니다. 60~80% 유사('유사')는 "조건부 인정" 이하로 하고 무엇이 새로운지 설명을 요구합니다.
7. 설명은 이전과 같고 링크만 바뀐 제출('링크만 변경')은 "미인정".
반드시 아래 JSON 으로만 응답합니다.

{
  "verdict": "인정|조건부 인정|미인정",
  "score": 0,
  "reason": "판정 이유",
  "required_fix": "보완 요구사항 또는 '없음'",
  "flags": ["재탕|복붙|링크만 변경|형식적 제출|목표 불일치 중 해당 항목. 없으면 빈 배열"]
}
score 는 0~100 정수로, 검토 점수를 종합하되 판정과 모순되지 않게 조정합니다."""

BRIEFING_SYSTEM = """당신은 팀 프로젝트의 '주간 브리핑 AI'입니다. 이번 주 팀원들의 제출물·판정 결과·미제출 상태를 보고,
팀장이 회의 시작 때 그대로 읽을 수 있는 짧은 브리핑을 씁니다.

작성 원칙
1. 기록에 있는 사실만. 제출물 요약은 실제 내용(수치·분량·산출물명)을 인용합니다.
2. '누가 누구를 기다리고 있는지'(의존 관계)를 역할과 다음 주 목표에서 찾아냅니다. 예: PPT 담당은 분석 담당의 결과표를 기다림.
3. 위험 신호는 구체적으로: 미제출자, 조건부 인정으로 보완이 필요한 사람, 다음 주 목표가 이번 주 결과물에 막히는 경우.
4. 비난 금지. 중립적이고 실용적인 톤. 각 항목은 한 줄.
반드시 아래 JSON 으로만 응답합니다.

{
  "headline": "이번 주 팀 상태 한 줄 (예: '3/4 제출, 설문 파트 지연으로 다음 주 분석 일정 위험')",
  "done": ["이번 주 팀이 실제로 해낸 일 (최대 4개)"],
  "risks": ["위험 신호 (최대 3개)"],
  "waiting_on": [{"who": "기다리는 사람", "for_whom": "기다리게 하는 사람", "what": "무엇을"}],
  "next_week_focus": ["다음 주 팀이 집중할 것 (최대 3개)"],
  "message_for_team": "팀 단톡방에 그대로 올릴 수 있는 3~4문장 공지"
}"""

REPORTER_SYSTEM = """당신은 팀 프로젝트 '기여도 리포트 AI'입니다. 교수·조교에게 제출할 공식 보고서를 작성합니다.
입력: 팀 정보, 팀원별 역할, 주차별 제출 기록(판정·점수), 연장 사용 기록, F 동의 기록.

작성 원칙
1. 사실만 적습니다. 기록에 없는 활동을 추정해 쓰지 않습니다.
2. 기여도 %는 팀원 합이 100이 되게 하며, 인정된 제출 수·점수·연장/미제출 이력을 종합합니다.
3. F 에 동의한 팀원은 '본인 동의로 개별 평가 요청' 사실을 중립적으로 명시합니다.
4. 감정적·비난 표현 금지.
반드시 아래 JSON 으로만 응답합니다.

{
  "contribution": [{"name": "이름", "percent": 0, "basis": "산정 근거 1문장"}],
  "report_md": "마크다운 보고서 (제목, 개요, 팀원별 기여 표, 특이사항, 종합 의견). 400~700자",
  "peer_eval": [{"name": "이름", "draft": "동료평가 초안 2문장"}],
  "nudges": [{"name": "이름", "message": "참여가 저조한 팀원에게 팀장이 보낼 정중한 메시지. 없으면 빈 배열"}]
}"""

# ───────────────────────── 유틸 ─────────────────────────


def extract_json(text: str) -> dict:
    if not text:
        raise ValueError("빈 응답")
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except Exception:
        pass
    s, e = t.find("{"), t.rfind("}")
    if s != -1 and e > s:
        return json.loads(t[s:e + 1])
    raise ValueError("JSON 파싱 실패: " + t[:200])


class LLM:
    """OpenAI 호환 클라이언트 래퍼. client 가 None 이면 규칙 기반 모드."""

    def __init__(self, base_url: Optional[str], api_key: str, model: str, enabled: bool = True):
        self.model = model
        self.base_url = base_url
        self.client = None
        self.logs: list[dict] = []
        if enabled and api_key:
            try:
                from openai import OpenAI
                kw = {"api_key": api_key or "EMPTY"}
                if base_url:
                    kw["base_url"] = base_url
                self.client = OpenAI(**kw)
            except Exception:
                self.client = None

    @property
    def available(self) -> bool:
        return self.client is not None

    @property
    def _new_api(self) -> bool:
        """gpt-5·o 계열은 max_tokens 대신 max_completion_tokens 를 쓰고(추론 토큰 포함), temperature 를 고정값만 허용한다."""
        m = (self.model or "").lower()
        return m.startswith(("gpt-5", "o1", "o3", "o4"))

    def _create(self, msgs: list, *, temperature: float, max_tokens: int, json_mode: bool):
        kw = {"model": self.model, "messages": msgs}
        if self._new_api:
            kw["max_completion_tokens"] = max(max_tokens * 2, 2000)  # 추론 토큰 몫까지 여유
        else:
            kw["max_tokens"] = max_tokens
            kw["temperature"] = temperature
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        return self.client.chat.completions.create(**kw)

    def ping(self) -> str:
        r = self._create([{"role": "user", "content": "한국어로 '연결 성공'이라고만 답하세요."}], temperature=0, max_tokens=20, json_mode=False)
        return (r.choices[0].message.content or "").strip()

    def chat_json(self, stage: str, system: str, user: str, temperature=0.2, max_tokens=3000) -> dict:
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        t0 = time.time()
        try:
            r = self._create(msgs, temperature=temperature, max_tokens=max_tokens, json_mode=True)
        except Exception:
            r = self._create(msgs, temperature=temperature, max_tokens=max_tokens, json_mode=False)
        raw = r.choices[0].message.content or ""
        self.logs.append({"stage": stage, "model": self.model, "base_url": self.base_url or "https://api.openai.com/v1",
                          "system_prompt": system, "user_prompt": user, "raw_response": raw,
                          "elapsed_sec": round(time.time() - t0, 1)})
        return extract_json(raw)


# ───────────────────────── 1) 역할 설계 ─────────────────────────


def plan_roles(llm: LLM, course: str, assignment: str, members: list[str], weeks: int) -> dict:
    if llm.available:
        user = (f"[수업] {course}\n[과제]\n{assignment}\n[팀원] {', '.join(members)} (총 {len(members)}명)\n"
                f"[기간] {weeks}주 (weekly_goals 는 정확히 {weeks}개)")
        data = llm.chat_json("역할 설계 AI (Planner)", PLANNER_SYSTEM, user, temperature=0.3, max_tokens=3500)
        # 길이 보정
        for m in data.get("members", []):
            g = list(m.get("weekly_goals", []))[:weeks]
            while len(g) < weeks:
                g.append(f"{len(g) + 1}주차 산출물 (팀장이 구체화)")
            m["weekly_goals"] = g
        return data
    # 규칙 기반
    base_roles = ["자료조사·분석", "문서/보고서 작성", "발표자료(PPT) 제작", "설문/데이터·검증", "일정관리·통합"]
    out = []
    for i, n in enumerate(members):
        role = base_roles[i % len(base_roles)]
        goals = [f"{w}주차: {role} 파트 산출물 (분량·범위를 팀에서 명시)" for w in range(1, weeks + 1)]
        goals[-1] = f"{weeks}주차: 담당 파트 최종본 + 통합 리허설"
        out.append({"name": n, "role": role, "role_desc": f"{role} 담당", "weekly_goals": goals})
    return {"members": out, "milestones": [f"{w}주차 마일스톤" for w in range(1, weeks + 1)],
            "advice": "① 매주 같은 요일 같은 시간에 작업물을 올린다 ② 링크만 올리지 말고 무엇을 했는지 3줄 이상 적는다",
            "_mode": "rule"}


# ───────────────────────── 2) 제출 검토 → 판정 ─────────────────────────


def _norm(t: str) -> str:
    return re.sub(r"[\s\W_]+", "", (t or "").lower())


def similarity_check(*, member: str, week: int, text: str, link: str, prior: list[dict]) -> list[dict]:
    """재탕·복붙·링크만 변경 감지 (결정적 계산, LLM 없이 수행).
    prior: [{"member","week","text","link"}] — 이 팀의 기존 제출물.
    반환: [{"kind": "재탕|복붙|유사|링크만 변경", "against": "이서연 2주차", "ratio": 0.87}]
    """
    import difflib
    a = _norm(text)
    out: list[dict] = []
    if len(a) < 30:
        return out
    for p in prior:
        if p.get("member") == member and p.get("week") == week:
            continue  # 같은 주차 재제출(보완)은 비교 대상에서 제외
        b = _norm(p.get("text", ""))
        if len(b) < 30:
            continue
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        against = f"{'본인' if p.get('member') == member else p.get('member')} {p.get('week')}주차"
        if ratio >= 0.8:
            kind = "재탕" if p.get("member") == member else "복붙"
            if p.get("member") == member and (link or "") != (p.get("link") or "") and ratio >= 0.95:
                kind = "링크만 변경"
            out.append({"kind": kind, "against": against, "ratio": round(ratio, 2)})
        elif ratio >= 0.6:
            out.append({"kind": "유사", "against": against, "ratio": round(ratio, 2)})
    out.sort(key=lambda x: -x["ratio"])
    return out[:3]


def review_submission(llm: LLM, *, member: str, role: str, goal: str, week: int, text: str, link: str, filename: str,
                      prior: Optional[list[dict]] = None) -> dict:
    payload = (f"[팀원] {member}  [역할] {role}\n[이번 주({week}주차) 목표] {goal}\n"
               f"[제출 텍스트]\n{text.strip() or '(없음)'}\n[링크] {link or '(없음)'}\n[첨부파일] {filename or '(없음)'}")
    sims = similarity_check(member=member, week=week, text=text, link=link, prior=prior or [])
    sim_txt = "\n".join(f"- {s['kind']}: {s['against']} 제출과 {int(s['ratio'] * 100)}% 동일" for s in sims) or "- 이상 없음"
    hard = [s for s in sims if s["kind"] in ("재탕", "복붙", "링크만 변경")]
    if llm.available:
        review = llm.chat_json("검토 AI (Reviewer)", REVIEWER_SYSTEM, payload, temperature=0.2, max_tokens=1500)
        verdict = llm.chat_json(
            "판정 AI (Gatekeeper)", GATEKEEPER_SYSTEM,
            payload + "\n\n[검토 AI 결과]\n" + json.dumps(review, ensure_ascii=False) + f"\n\n[유사도 검사 결과]\n{sim_txt}",
            temperature=0.1, max_tokens=800)
        verdict.setdefault("flags", [])
        if hard and verdict.get("verdict") != "미인정":  # 모델이 놓쳐도 규칙으로 강제
            verdict["verdict"] = "미인정"
            verdict["flags"] = list(dict.fromkeys(verdict["flags"] + [h["kind"] for h in hard]))
            verdict["reason"] = f"{hard[0]['against']} 제출과 {int(hard[0]['ratio'] * 100)}% 동일한 내용입니다. " + verdict.get("reason", "")
        return {"review": review, "verdict": verdict, "similarity": sims, "mode": "llm"}
    # 규칙 기반
    n = len(text.strip())
    has_ref = bool(link or filename)
    base = min(100, 30 + n // 6 + (25 if has_ref else 0))
    rel = base if any(k in text for k in goal.replace(",", " ").split()[:3]) or has_ref else max(10, base - 25)
    review = {"relevance": rel, "completeness": base, "effort": min(100, base + 5), "clarity": min(100, 40 + n // 8),
              "summary": f"텍스트 {n}자" + (", 링크/파일 첨부" if has_ref else ", 첨부 없음") + " 제출.",
              "strengths": ["제출 기한 준수"] if n else [],
              "improvements": ["무엇을·얼마나 했는지 수치로 적기", "결과물 링크나 파일 첨부"] if not has_ref else ["다음 주 계획 1줄 추가"],
              "next_week_tip": "목표 문장의 핵심 단어가 제출 내용에 드러나게 작성하세요."}
    avg = (review["relevance"] + review["completeness"] + review["effort"] + review["clarity"]) / 4
    if hard:
        h = hard[0]
        v = {"verdict": "미인정", "score": min(int(avg), 30), "reason": f"{h['against']} 제출과 {int(h['ratio'] * 100)}% 동일한 내용입니다 ({h['kind']}).",
             "required_fix": "이번 주에 새로 한 작업만 구체적으로 작성해 다시 올려주세요.", "flags": [h["kind"]]}
    elif sims:  # 유사(60~80%)
        s = sims[0]
        v = {"verdict": "조건부 인정", "score": min(int(avg), 54), "reason": f"{s['against']} 제출과 {int(s['ratio'] * 100)}% 유사합니다. 새로 추가된 부분을 명확히 해주세요.",
             "required_fix": "48시간 내 이번 주에 새로 한 부분을 구분해 보강하세요.", "flags": ["유사"]}
    elif n < 50 and not has_ref:
        v = {"verdict": "미인정", "score": int(avg), "reason": "제출 내용이 50자 미만이고 첨부가 없습니다.", "required_fix": "작업 내용을 구체적으로 작성하고 결과물을 첨부하세요.", "flags": ["형식적 제출"]}
    elif avg < 40:
        v = {"verdict": "미인정", "score": int(avg), "reason": "검토 평균 점수가 40 미만입니다.", "required_fix": "목표와 관련된 실제 산출물을 올려주세요.", "flags": ["형식적 제출"]}
    elif avg < 55:
        v = {"verdict": "조건부 인정", "score": int(avg), "reason": "실질 작업은 있으나 완성도 보강이 필요합니다.", "required_fix": "48시간 내 분량·근거를 보강하세요.", "flags": []}
    else:
        v = {"verdict": "인정", "score": int(avg), "reason": "목표와 관련된 실질적 산출물로 판단됩니다.", "required_fix": "없음", "flags": []}
    return {"review": review, "verdict": v, "similarity": sims, "mode": "rule"}


# ───────────────────────── 2.5) 주간 브리핑 ─────────────────────────


def weekly_briefing(llm: LLM, *, team: dict, week: int, members: list[dict], week_rows: list[dict]) -> dict:
    """week_rows: [{"name","role","status_label","goal","next_goal","verdict","score","summary","text"}]"""
    if llm.available:
        user = (f"[수업] {team['course']}  [팀] {team['name']}  [과제] {team['assignment']}\n"
                f"[주차] {week}/{team['weeks']}주차\n\n[팀원별 이번 주 상태]\n{json.dumps(week_rows, ensure_ascii=False)}")
        return llm.chat_json("주간 브리핑 AI (Briefing)", BRIEFING_SYSTEM, user, temperature=0.3, max_tokens=1800) | {"mode": "llm"}
    done = [f"{r['name']}: {(r.get('summary') or r.get('text') or '')[:60]}" for r in week_rows if r.get("verdict") in ("인정", "조건부 인정")]
    missing = [r["name"] for r in week_rows if r.get("verdict") not in ("인정", "조건부 인정") and r.get("status_label", "").startswith(("❌", "⏰"))]
    cond = [r["name"] for r in week_rows if r.get("verdict") == "조건부 인정"]
    risks = ([f"미제출: {', '.join(missing)}"] if missing else []) + ([f"조건부 인정(보완 필요): {', '.join(cond)}"] if cond else [])
    waiting = []
    if missing:
        for r in week_rows:
            if r["name"] not in missing and r.get("next_goal"):
                waiting.append({"who": r["name"], "for_whom": missing[0], "what": f"{missing[0]}의 {week}주차 산출물"})
                break
    return {"headline": f"{len(done)}/{len(week_rows)} 제출" + (f", {', '.join(missing)} 미제출" if missing else ", 전원 제출"),
            "done": done[:4], "risks": risks[:3], "waiting_on": waiting,
            "next_week_focus": [f"{r['name']}: {r['next_goal']}" for r in week_rows if r.get("next_goal")][:3],
            "message_for_team": f"{week}주차 결과 공유합니다. {len(done)}명 제출 완료" + (f", {', '.join(missing)}님은 이번 주 안에 올려주세요." if missing else ". 모두 고생했어요!") + " 다음 주 목표는 역할 탭을 확인해주세요.",
            "mode": "rule"}


# ───────────────────────── 3) 기여도 리포트 ─────────────────────────


def build_report(llm: LLM, *, team: dict, members: list[dict], submissions: list[dict], extensions: list[dict]) -> dict:
    if llm.available:
        user = (f"[수업] {team['course']}  [팀] {team['name']}\n[과제] {team['assignment']}\n"
                f"[기간] {team['weeks']}주, 현재 {team.get('current_week')}주차\n\n"
                f"[팀원·역할]\n{json.dumps([{k: m.get(k) for k in ('name', 'role', 'status', 'f_agreed_at')} for m in members], ensure_ascii=False)}\n\n"
                f"[제출 기록]\n{json.dumps(submissions, ensure_ascii=False)}\n\n[연장 사용]\n{json.dumps(extensions, ensure_ascii=False)}")
        return llm.chat_json("리포트 AI (Reporter)", REPORTER_SYSTEM, user, temperature=0.3, max_tokens=3000) | {"mode": "llm"}
    # 규칙 기반
    pts = {m["name"]: 0.0 for m in members}
    for s in submissions:
        if s.get("verdict") == "인정":
            pts[s["member"]] += s.get("score", 60)
        elif s.get("verdict") == "조건부 인정":
            pts[s["member"]] += s.get("score", 40) * 0.6
    total = sum(pts.values()) or 1
    contribution = [{"name": n, "percent": round(p / total * 100), "basis": f"인정 제출 점수 합 {int(p)}"} for n, p in pts.items()]
    rows = "\n".join(f"| {c['name']} | {c['percent']}% | {c['basis']} |" for c in contribution)
    f_names = [m["name"] for m in members if m.get("status") == "F"]
    report = (f"## {team['course']} · {team['name']} 기여도 보고서 (규칙 기반)\n\n**과제**: {team['assignment'][:80]}\n\n"
              f"| 팀원 | 기여도 | 근거 |\n|---|---|---|\n{rows}\n\n"
              + (f"**특이사항**: {', '.join(f_names)} 팀원은 본인 동의로 개별 평가(F)를 요청했습니다.\n\n" if f_names else "")
              + "본 보고서는 주간 제출 기록만으로 자동 산출되었습니다.")
    low = [c["name"] for c in contribution if c["percent"] < 100 / max(1, len(members)) * 0.6]
    return {"contribution": contribution, "report_md": report,
            "peer_eval": [{"name": c["name"], "draft": f"{c['name']} 팀원의 기여도는 제출 기록 기준 {c['percent']}%입니다."} for c in contribution],
            "nudges": [{"name": n, "message": f"{n}님, 이번 주 작업물 공유 부탁드려요. 막히는 부분 있으면 같이 봐요!"} for n in low],
            "mode": "rule"}
