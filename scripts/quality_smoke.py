"""품질 스모크 테스트 — 샘플 입력으로 dual 생성 후 가드레일 점수 출력.

사용:
  .venv/bin/python scripts/quality_smoke.py
  .venv/bin/python scripts/quality_smoke.py --case vocal
  .venv/bin/python scripts/quality_smoke.py --case guitar
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from config.settings import load_settings
from core.dual_channel import optimize_dual_channels
from core.stt_music_review import prepare_theory_stt_snippets
from core.stt_topic import (
    append_topic_plan_to_source,
    detect_filler_phrases,
    detect_tistory_duplication,
    extract_stt_topic_plan,
    verify_key_point_coverage,
    verify_stt_contradictions,
    verify_topic_coverage,
)
from core.build_source import SttSnippet, build_source_from_stt_only
from core.keyword_rotation import build_keyword_plan
from core.lesson_subject import detect_lesson_subject, resolve_template_keyword


GUITAR_STT = """
자 그래서 우리 여기 있는 알파벳 음계를 조금 볼 수 있어야 되는데 기타 지판을
튜닝 할 때 각 줄들마다 무슨 음계가 나오는지. 6번 줄은 무슨 음으로 나오죠? E음으로 시작을 하죠.
5번 줄은 A에 맞추죠. 4번 줄 D. 3번 줄 G. 2번 줄은 B로. 1번 줄은 E. 6번 줄하고 1번 줄하고는 같은 음이에요.
B랑 C 사이는 반음 간격이라서 한 칸이에요. E랑 F 사이도 반음. 나머지는 두 칸씩.
12번 플랫은 한 옥타브 올라왔으니까 E로 다시 돌아가는거야.
가로로 수평으로 음을 볼 수 있게 먼저 연습. A플랫 음을 찾을거야.
카포 2번 프렛에 걸고 C 코드를 치면 D 코드가 되는 거거든.
C코드, G코드, A코드, E코드, D코드. 다섯 가지만 알고 있으면 모든 코드도 잡아줄 수 있다.
그걸 케이지드 시스템이라고 얘기합니다.
""".strip()


def _score_case(name: str, checks: list[tuple[str, bool, str]]) -> dict:
    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    print(f"\n===== {name} =====")
    for label, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    pct = round(100 * passed / total) if total else 0
    print(f"  → {passed}/{total} ({pct}%)")
    return {"name": name, "passed": passed, "total": total, "pct": pct}


def run_vocal(cfg) -> dict:
    sample = (ROOT / "samples" / "lesson_note.txt").read_text(encoding="utf-8")
    plan = build_keyword_plan(
        cfg.business,
        sample,
        lesson_title="고음 브릿지 레슨",
        target_keyword="",
    )
    topic = extract_stt_topic_plan(
        sample,
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
    )
    source = append_topic_plan_to_source(sample, topic) if topic else sample
    draft = optimize_dual_channels(
        source,
        cfg.business,
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        keyword_plan=plan,
        topic_plan=topic,
        lesson_title="고음 브릿지 레슨",
        target_keyword=resolve_template_keyword(plan, ""),
    )

    body = f"{draft.markdown}\n{draft.naver.body}"
    fillers = detect_filler_phrases(body)
    dupes = detect_tistory_duplication(draft.markdown, draft.naver.body)
    missing = draft.missing_topics or []
    missing_kp = draft.missing_key_points or []

    must = ["립트릴", "브릿지", "메트로놈"]
    hit = [w for w in must if w in body]
    subject = plan.lesson_subject

    checks = [
        ("과목 감지(보컬 계열)", "보컬" in subject or subject in ("보컬", "랩"), subject),
        ("STT 주제 추출", bool(topic and topic.topics), f"{len(topic.topics) if topic else 0} topics"),
        ("원문 핵심어 반영", len(hit) >= 2, f"hit={hit}"),
        ("티스토리 FAQ 존재", len(draft.tistory.faq) >= 2, f"faq={len(draft.tistory.faq)}"),
        ("네이버 본문 길이≥400", len(re.sub(r"\s+", "", draft.naver.body)) >= 400, str(len(re.sub(r"\s+", "", draft.naver.body)))),
        ("빈 서사 금지어 없음", len(fillers) == 0, ", ".join(fillers[:5])),
        ("네이버 복붙 적음", len(dupes) <= 1, f"dupes={len(dupes)}"),
        ("주제 누락 없음", len(missing) == 0, str(missing[:3])),
        ("세부 포인트 누락≤2", len(missing_kp) <= 2, f"{len(missing_kp)} missing"),
    ]
    return _score_case("vocal_memo", checks)


def run_guitar(cfg) -> dict:
    snippets = [SttSnippet(recording_id=1, title="기타 이론", text=GUITAR_STT)]
    subject = detect_lesson_subject(
        cfg.business,
        source_text=GUITAR_STT,
        lesson_title="지판·CAGED",
    )
    snippets, reviews, review_block = prepare_theory_stt_snippets(
        snippets,
        subject=subject,
        lesson_title="지판·CAGED",
        academy_profile=cfg.business,
    )
    source = build_source_from_stt_only(
        lesson_title="지판·CAGED",
        stt_snippets=snippets,
        academy_name=cfg.business.name,
    )
    if review_block:
        source = f"{source}\n\n{review_block}"

    plan = build_keyword_plan(
        cfg.business,
        source,
        lesson_title="지판·CAGED",
        target_keyword="",
    )
    topic = extract_stt_topic_plan(
        source,
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        stt_snippets=snippets,
    )
    if topic:
        source = append_topic_plan_to_source(source, topic)

    draft = optimize_dual_channels(
        source,
        cfg.business,
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        stt_snippets=snippets,
        keyword_plan=plan,
        topic_plan=topic,
        stt_review=reviews,
        lesson_title="지판·CAGED",
        target_keyword=resolve_template_keyword(plan, ""),
    )

    body = f"{draft.markdown}\n{draft.naver.body}"
    fillers = detect_filler_phrases(body)
    factual = verify_stt_contradictions(source, body)
    # 1번 줄 = E 정확성
    bad_string1 = bool(re.search(r"1번\s*줄[^.\n]{0,20}C", body))
    has_e = bool(re.search(r"1번\s*줄[^.\n]{0,20}E", body)) or ("1번 줄" in body and "E" in body)
    has_caged = "CAGED" in body.upper() or "케이지드" in body
    has_capo = "카포" in body
    tuning_ok = all(x in body for x in ["6번", "E"]) and ("5번" in body and "A" in body)

    checks = [
        ("과목 감지=기타", subject == "기타", subject),
        ("주제 추출≥4", bool(topic and len(topic.topics) >= 4), f"{len(topic.topics) if topic else 0}"),
        ("튜닝 E/A 반영", tuning_ok, ""),
        ("1번 줄≠C 오류 없음", not bad_string1, "1번 줄=C 검출됨" if bad_string1 else ""),
        ("1번 줄 E 또는 동음 언급", has_e, ""),
        ("CAGED 반영", has_caged, ""),
        ("카포 반영", has_capo, ""),
        ("STT 불일치 경고 없음", len(factual) == 0, "; ".join(factual[:2])),
        ("빈 서사 금지어 없음", len(fillers) == 0, ", ".join(fillers[:5])),
        ("주제 커버리지", len(draft.missing_topics or []) == 0, str(draft.missing_topics)),
    ]
    return _score_case("guitar_stt_fixture", checks)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=["all", "vocal", "guitar"], default="all")
    args = parser.parse_args()

    cfg = load_settings()
    if not cfg.openai_api_key:
        print("OPENAI_API_KEY가 없습니다.")
        return 1

    results = []
    if args.case in ("all", "vocal"):
        results.append(run_vocal(cfg))
    if args.case in ("all", "guitar"):
        results.append(run_guitar(cfg))

    print("\n===== SUMMARY =====")
    for r in results:
        print(f"  {r['name']}: {r['pct']}% ({r['passed']}/{r['total']})")
    avg = round(sum(r["pct"] for r in results) / len(results)) if results else 0
    print(f"  average: {avg}%")
    print(
        "\n해석: 80%+ 운영 가능, 60~79% 검수 필수, 60% 미만 파이프라인 손보기.\n"
        "이 점수는 가드레일/충실도이지 검색 순위 점수가 아닙니다."
    )
    return 0 if avg >= 60 else 2


if __name__ == "__main__":
    raise SystemExit(main())
