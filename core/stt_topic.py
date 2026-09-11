"""STT → 주제 구조 추출·본문 반영·누락 검증."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.build_source import SttSnippet
from core.openai_json import chat_json

_TOPIC_SYSTEM = """당신은 음악·예체능 레슨 STT를 분석해 블로그 글 구조를 만드는 편집자입니다.
원문에 없는 내용을 지어내지 마세요. STT·메모에 실제로 나온 연습명·기술명·곡명·질문만 추출합니다.
응답은 반드시 JSON 객체 하나만 출력합니다."""

_MIN_SOURCE_CHARS = 180
_LONG_STT_CHARS = 2500
_VERY_LONG_STT_CHARS = 4500


@dataclass
class SttTopic:
    heading: str
    key_points: list[str] = field(default_factory=list)


@dataclass
class SttTopicPlan:
    topics: list[SttTopic] = field(default_factory=list)
    faq_suggestions: list[str] = field(default_factory=list)
    total_stt_chars: int = 0
    suggest_split: bool = False
    split_hint: str = ""

    def heading_list(self) -> list[str]:
        return [t.heading.strip() for t in self.topics if t.heading.strip()]


def _stt_char_count(source_text: str, snippets: list[SttSnippet] | None) -> int:
    if snippets:
        return sum(len(s.text or "") for s in snippets)
    return len(re.sub(r"\s+", "", source_text or ""))


def _build_extraction_prompt(source_text: str, snippets: list[SttSnippet] | None) -> str:
    clip_block = ""
    if snippets:
        lines = []
        for i, s in enumerate(snippets, start=1):
            title = (s.title or f"녹음 #{s.recording_id}").strip()
            lines.append(f"--- 클립 {i}: {title} ---\n{(s.text or '').strip()}")
        clip_block = "\n\n[STT 클립별 원문]\n" + "\n\n".join(lines)

    return f"""아래 레슨 STT·메모에서 블로그 본문용 주제 구조를 추출하세요.

[레슨 원문]
{source_text.strip()}
{clip_block}

JSON 스키마:
{{
  "topics": [
    {{
      "heading": "## 소제목으로 쓸 짧은 제목 (연습명·기술명, 8~28자)",
      "key_points": ["반드시 본문에 넣을 사실 1", "사실 2", "..."]
    }}
  ],
  "faq_suggestions": ["STT·원문으로만 답 가능한 구체 질문", "..."]
}}

규칙:
1. topics는 STT에 실제로 다뤄진 주제 단위로 3~10개. 긴 STT(2,500자↑)는 세분화 필수.
   예) 튜닝·각 줄 시작음 / 반음·온음 간격 / 가로(수평) 지판 연습 / 코드 구성음 / 카포 / CAGED / 수직 연습
2. heading은 소설·후기형 금지. 기술명·연습명 중심.
3. key_points는 주제당 4~8개(STT 짧으면 2~4개). 줄 번호·프렛·음 이름·코드명·연습 지시를 STT 그대로 포함.
   예) "6번 줄 E로 시작", "5번 줄 A", "1번 줄 E(6번과 동일)", "B-C 사이만 반음(한 칸)", "12프렛=한 옥타브 E", "카포 2프렛 C→D"
4. faq_suggestions는 2~5개. 학원 일반 FAQ 금지. STT에 답이 있는 질문만.
5. 원문에 없는 주제·FAQ를 만들지 말 것.
6. 「N번 줄」(현 줄)과 「N번 플랫」(프렛 번호)을 구분할 것. STT에서 "1번 플랫=C"와 "1번 줄=E"는 다른 개념."""


def extract_stt_topic_plan(
    source_text: str,
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
    stt_snippets: list[SttSnippet] | None = None,
) -> SttTopicPlan | None:
    """STT·메모에서 주제 구조를 LLM으로 추출. 짧은 입력은 None."""
    text = (source_text or "").strip()
    if len(text.replace(" ", "")) < _MIN_SOURCE_CHARS:
        return None

    parsed = chat_json(
        api_key=api_key,
        model=model,
        system=_TOPIC_SYSTEM,
        user=_build_extraction_prompt(text, stt_snippets),
        temperature=0.2,
    )

    topics: list[SttTopic] = []
    for item in parsed.get("topics") or []:
        if not isinstance(item, dict):
            continue
        heading = str(item.get("heading") or "").strip()
        if not heading:
            continue
        heading = re.sub(r"^#+\s*", "", heading).strip()
        raw_points = item.get("key_points") or item.get("keyPoints") or []
        points = [str(p).strip() for p in raw_points if str(p).strip()] if isinstance(raw_points, list) else []
        max_pts = 10 if len(text.replace(" ", "")) >= _LONG_STT_CHARS else 6
        topics.append(SttTopic(heading=heading, key_points=points[:max_pts]))

    faq_raw = parsed.get("faq_suggestions") or parsed.get("faqSuggestions") or []
    faq = [str(q).strip() for q in faq_raw if str(q).strip()] if isinstance(faq_raw, list) else []

    if not topics:
        return None

    stt_chars = _stt_char_count(text, stt_snippets)
    suggest_split = stt_chars >= _LONG_STT_CHARS and len(topics) >= 4
    split_hint = ""
    if suggest_split:
        split_hint = (
            f"STT가 약 {stt_chars:,}자로 깁니다. 주제가 {len(topics)}개이므로 "
            "1편에 모두 담거나, 튜닝·이론 / 연습법처럼 2편으로 나누는 것도 고려하세요."
        )

    return SttTopicPlan(
        topics=topics,
        faq_suggestions=faq[:5],
        total_stt_chars=stt_chars,
        suggest_split=suggest_split,
        split_hint=split_hint,
    )


def append_topic_plan_to_source(source_text: str, plan: SttTopicPlan | None) -> str:
    """source_text 끝에 [STT 주제 구조] 블록 추가."""
    if not plan or not plan.topics:
        return source_text
    block = topic_plan_prompt_block(plan, for_source=True)
    base = source_text.rstrip()
    return f"{base}\n\n{block}" if base else block


def topic_plan_prompt_block(plan: SttTopicPlan, *, for_source: bool = False) -> str:
    """LLM 프롬프트 또는 source_text에 주입할 주제 구조 블록."""
    lines = ["[STT 주제 구조 — 아래 주제를 본문 ## 소제목·단락으로 빠짐없이 반영]"]
    if plan.suggest_split and plan.split_hint:
        lines.append(f"※ 분량 참고: {plan.split_hint}")

    for i, topic in enumerate(plan.topics, start=1):
        lines.append(f"{i}. {topic.heading}")
        for point in topic.key_points:
            lines.append(f"   - {point}")

    if plan.faq_suggestions:
        lines.append("")
        lines.append("[FAQ 후보 — 위 원문·STT로만 답할 수 있는 질문. 학원 일반 FAQ 금지]")
        for q in plan.faq_suggestions:
            lines.append(f"- {q}")

    lines.append("")
    lines.append(
        "[필수 체크리스트 — 생성 후 스스로 확인]"
        + "".join(f"\n☐ {t.heading}" for t in plan.topics)
    )

    if not for_source:
        lines.append(
            "\n위 [STT 주제 구조]의 각 heading을 markdown_body ## 소제목(또는 네이버 단락 제목)으로 사용하거나 "
            "동일한 기술명을 유지하세요."
        )
        lines.append(
            "각 key_points는 반드시 별도 문장으로 본문에 포함(한 줄 요약·개요문으로 뭉개기 금지). "
            "주제당 key_points 수만큼 최소 문장을 쓸 것."
        )
        lines.append("체크리스트 항목·key_points가 하나라도 빠지면 안 됩니다.")
    return "\n".join(lines)


def resolve_content_lengths(
    plan: SttTopicPlan | None,
    *,
    template_guide: str | None = None,
) -> tuple[int, str]:
    """STT 길이·주제 수에 따라 네이버 목표 글자 수와 AEO 분량 힌트."""
    from core.template.prompt_block import resolve_naver_target_chars

    naver = resolve_naver_target_chars(template_guide)
    if not plan:
        return naver, ""

    topic_count = len(plan.topics)
    stt_chars = plan.total_stt_chars

    if stt_chars >= _VERY_LONG_STT_CHARS or topic_count >= 6:
        naver = max(naver, 2200)
        aeo_hint = "markdown_body 공백 제외 1,800자 이상. 주제마다 ## 소제목 + 4문장 이상."
    elif stt_chars >= _LONG_STT_CHARS or topic_count >= 4:
        naver = max(naver, 1800)
        aeo_hint = "markdown_body 공백 제외 1,200자 이상. 주제마다 ## 소제목 + 3문장 이상."
    elif topic_count >= 3:
        naver = max(naver, 1200)
        aeo_hint = "STT 주제 3개 이상 — 각 주제별 ## 소제목 필수."
    else:
        aeo_hint = ""

    if plan.suggest_split:
        aeo_hint = (aeo_hint + " " if aeo_hint else "") + plan.split_hint

    return naver, aeo_hint.strip()


def _topic_terms(topic: SttTopic) -> list[str]:
    terms: list[str] = []
    heading = re.sub(r"[^\w가-힣]+", " ", topic.heading)
    for word in heading.split():
        if len(word) >= 2:
            terms.append(word.lower())
    for point in topic.key_points:
        for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", point):
            if len(token) >= 2:
                terms.append(token.lower())
    return list(dict.fromkeys(terms))


def verify_topic_coverage(
    plan: SttTopicPlan | None,
    *,
    tistory_text: str = "",
    naver_text: str = "",
) -> list[str]:
    """생성본에 주제가 반영됐는지 검사. 누락된 heading 목록 반환."""
    if not plan or not plan.topics:
        return []

    combined = f"{tistory_text}\n{naver_text}".lower()
    missing: list[str] = []

    for topic in plan.topics:
        terms = _topic_terms(topic)
        if not terms:
            continue
        hits = sum(1 for t in terms[:8] if t in combined)
        threshold = 1 if len(terms) <= 2 else 2
        if hits < threshold:
            missing.append(topic.heading)

    return missing


def _point_terms(point: str) -> list[str]:
    """key_point에서 검증용 핵심 토큰 추출."""
    terms: list[str] = []
    for m in re.finditer(r"\d+번(?:\s*줄)?|\d+프렛|\d+플랫", point):
        terms.append(m.group(0).replace(" ", ""))
    for m in re.finditer(r"[A-G][#b♭♯]?|카포|CAGED|케이지드|반음|온음|옥타브", point, re.I):
        terms.append(m.group(0).lower())
    for m in re.finditer(r"[가-힣]{2,}", point):
        w = m.group(0)
        if w not in ("그래서", "그러면", "이렇게", "예를", "들어서", "선생님", "수강생"):
            terms.append(w)
    return list(dict.fromkeys(terms))[:6]


def verify_key_point_coverage(
    plan: SttTopicPlan | None,
    *,
    tistory_text: str = "",
    naver_text: str = "",
) -> list[str]:
    """생성본에 key_point 핵심 내용이 반영됐는지 검사."""
    if not plan or not plan.topics:
        return []

    combined = f"{tistory_text}\n{naver_text}".lower()
    missing: list[str] = []

    for topic in plan.topics:
        for point in topic.key_points:
            terms = _point_terms(point)
            if not terms:
                continue
            hits = sum(1 for t in terms if t.lower() in combined)
            if hits < max(1, len(terms) // 3):
                missing.append(f"[{topic.heading}] {point}")

    return missing


def detect_filler_phrases(text: str) -> list[str]:
    """생성본에서 금지·빈 서사 패턴 탐지."""
    from core.prompts import STRICT_NEGATIVE_PHRASES

    found: list[str] = []
    for phrase in STRICT_NEGATIVE_PHRASES:
        if phrase in text:
            found.append(phrase)
    return found


def verify_stt_contradictions(source_text: str, generated_text: str) -> list[str]:
    """생성본이 STT와 모순되는 흔한 오류 탐지."""
    warnings: list[str] = []
    src = source_text or ""
    gen = (generated_text or "").replace(" ", "")

    # 1번 줄 = E (6번과 동일) — STT에 명시된 경우
    if re.search(r"1번\s*줄.*E|6번\s*줄.*1번\s*줄|1번\s*줄.*6번", src, re.I):
        if re.search(r"1번줄.*[Cc]로|1번줄은[Cc]", gen):
            warnings.append("1번 줄: STT는 E(6번 줄과 동일)인데 C로 기술됨 — 「1번 플랫」과 혼동 가능")

    # STT에 F# 없는데 D코드 F# 언급
    if "f#" not in src.lower() and "f샵" not in src and "파샵" not in src:
        if "f#" in generated_text.lower() or "F#" in generated_text:
            warnings.append("D코드 F#: STT 원문에 없는 내용 — 일반 지식으로 채운 것으로 보임")

    return warnings


def detect_tistory_duplication(tistory_text: str, naver_text: str, *, min_chars: int = 40) -> list[str]:
    """네이버 본문이 티스토리 문장을 그대로 복사했는지 탐지."""
    dupes: list[str] = []
    for para in re.split(r"\n+", tistory_text or ""):
        p = para.strip()
        if len(p) < min_chars or p.startswith("#"):
            continue
        normalized = re.sub(r"\s+", "", p)
        if normalized and normalized in re.sub(r"\s+", "", naver_text or ""):
            dupes.append(p[:60] + ("…" if len(p) > 60 else ""))
    return dupes[:5]
