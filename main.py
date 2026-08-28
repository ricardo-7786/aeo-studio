"""
학원 AEO 블로그 파이프라인
========================
레슨 기록 / 포인트 녹음 STT / 상담 메모 → 티스토리(AEO) + 네이버(SEO) 동시 생성
→ Schema.org JSON-LD → WordPress 또는 티스토리 자동 발행

사용 예:
  python main.py --file ./samples/lesson_note.txt --dual
  python main.py --audio rec1.m4a --audio rec2.m4a --lesson-title "그겨울 발음" --dual
  python main.py --text "오늘 보컬 레슨 요약..." --dual --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import markdown

from config.settings import Settings, load_settings
from core.aeo_optimizer import AEOArticle, article_to_markdown, optimize_to_aeo
from core.build_source import SttSnippet
from core.draft_generator import generate_draft_from_audio_files, generate_draft_from_source_text
from core.dual_channel import DualDraftResult
from core.input_parser import resolve_input
from core.naver_optimizer import naver_article_to_plain
from core.schema_builder import build_json_ld, json_ld_script_tag
from core.stt import load_audio
from publishers import PublishResult, get_publisher


def markdown_to_html(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["extra", "sane_lists", "nl2br"],
    )


def assemble_html(article: AEOArticle, json_ld_tag: str) -> str:
    md = article_to_markdown(article)
    body_md = re.sub(r"^# .+\n+", "", md, count=1).strip()
    body_html = markdown_to_html(body_md)
    return f"{body_html}\n\n{json_ld_tag}\n"


def save_artifacts_tistory(
    output_dir: Path,
    article: AEOArticle,
    json_ld: dict,
    html: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = re.sub(r"[^\w가-힣\-]+", "_", article.title)[:40] or "post"
    base = output_dir / f"{stamp}_{safe_title}"

    md_path = base.with_suffix(".md")
    html_path = Path(str(base) + ".html")
    json_path = Path(str(base) + ".jsonld.json")
    meta_path = Path(str(base) + ".meta.json")

    md_path.write_text(article_to_markdown(article), encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    json_path.write_text(json.dumps(json_ld, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_path.write_text(article.model_dump_json(indent=2), encoding="utf-8")
    return md_path


def save_dual_artifacts(output_dir: Path, draft: DualDraftResult) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w가-힣\-]+", "_", draft.tistory.title)[:36] or "draft"
    base = output_dir / f"{stamp}_{safe}"

    tistory_md = base.with_name(base.name + "_tistory.md")
    naver_txt = base.with_name(base.name + "_naver.txt")
    naver_meta = base.with_name(base.name + "_naver.meta.json")
    source_txt = base.with_name(base.name + "_source.txt")
    dual_json = base.with_name(base.name + "_dual.json")

    json_ld_tag = json_ld_script_tag(draft.json_ld)
    html = assemble_html(draft.tistory, json_ld_tag)

    tistory_md.write_text(draft.markdown, encoding="utf-8")
    Path(str(base) + "_tistory.html").write_text(html, encoding="utf-8")
    Path(str(base) + ".jsonld.json").write_text(
        json.dumps(draft.json_ld, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    naver_txt.write_text(draft.naver_plain, encoding="utf-8")
    naver_meta.write_text(
        json.dumps(
            {
                "title": draft.naver.title,
                "keywords": draft.naver.keywords,
                "meta_description": draft.naver.meta_description,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    source_txt.write_text(draft.source_text, encoding="utf-8")
    dual_json.write_text(
        json.dumps(
            {
                "generated_at": draft.generated_at,
                "stt_count": len(draft.stt_snippets),
                "tistory_title": draft.tistory.title,
                "naver_title": draft.naver.title,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return tistory_md


def print_result(result: PublishResult, dry_run: bool = False) -> None:
    print()
    print("=" * 60)
    if dry_run:
        print("[DRY-RUN] 발행을 건너뛰었습니다. 로컬 산출물만 저장했습니다.")
        print("=" * 60)
        return

    status = "SUCCESS" if result.success else "FAILED"
    print(f"[{status}] platform={result.platform}")
    print(f"message : {result.message}")
    if result.post_id:
        print(f"post_id : {result.post_id}")
    if result.url:
        print(f"URL     : {result.url}")
    else:
        print("URL     : (없음)")
    print("=" * 60)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="실용음악학원 AEO 블로그 자동 변환·발행 파이프라인",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", type=str, help="원본 텍스트 (레슨/상담 요약)")
    src.add_argument("--file", type=str, help="원본 텍스트 파일 경로")
    src.add_argument("--url", type=str, help="네이버 블로그 URL")
    src.add_argument(
        "--audio",
        action="append",
        dest="audios",
        help="포인트 녹음 파일 (여러 번 지정 가능, 시간순 STT → 한 글)",
    )

    p.add_argument("--lesson-title", type=str, default="", help="레슨 제목 (--audio 사용 시)")
    p.add_argument(
        "--coaching-points",
        type=str,
        default="",
        help="핵심 코칭 포인트 텍스트",
    )
    p.add_argument(
        "--dual",
        action="store_true",
        help="티스토리(AEO) + 네이버(SEO) 동시 생성 (권장)",
    )
    p.add_argument(
        "--platform",
        choices=["wordpress", "tistory"],
        help="발행 플랫폼 (.env PUBLISH_PLATFORM 덮어쓰기)",
    )
    p.add_argument("--dry-run", action="store_true", help="API 발행 없이 산출물만 생성")
    p.add_argument("--model", type=str, help="OpenAI 모델 (.env OPENAI_MODEL 덮어쓰기)")
    p.add_argument(
        "--business-key",
        type=str,
        help="DB 업체 키 (businesses.business_key). 미설정 시 DEFAULT_BUSINESS_KEY 또는 .env",
    )
    p.add_argument(
        "--industry",
        type=str,
        choices=["education", "restaurant", "clinic", "fitness", "beauty", "general"],
        help="업종 (이번 실행만 덮어쓰기)",
    )
    p.add_argument(
        "--save-draft",
        action="store_true",
        help="DATABASE_URL 있을 때 aeo_drafts 테이블에 초안 저장",
    )
    return p


def run(settings: Settings, args: argparse.Namespace) -> int:
    overrides: dict = {}
    if args.platform:
        overrides["publish_platform"] = args.platform
    if args.model:
        overrides["openai_model"] = args.model
    if overrides:
        settings = replace(settings, **overrides)

    biz = settings.business
    print(f"[업체] {biz.name} (key={biz.business_key}, industry={biz.industry})")

    dry_run = args.dry_run or settings.dry_run
    use_dual = args.dual or bool(args.audios)

    print("[1/5] 입력 수집 중...")
    source_text = ""
    lesson_title = args.lesson_title or "레슨 기록"

    if args.audios:
        print(f"  - STT clips: {len(args.audios)}개")
        for a in args.audios:
            print(f"    · {a}")
    elif args.text or args.file or args.url:
        source = resolve_input(text=args.text, file_path=args.file, url=args.url)
        source_text = source.body
        lesson_title = source.title
        print(f"  - type : {source.source_type}")
        print(f"  - title: {source.title[:60]}")
        print(f"  - chars: {len(source.body)}")

    print(f"[2/5] {'Dual(AEO+네이버)' if use_dual else 'AEO'} 변환 중 (model={settings.openai_model})...")

    if use_dual and args.audios:
        draft = generate_draft_from_audio_files(
            audio_paths=args.audios,
            lesson_title=lesson_title,
            academy=settings.academy,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            whisper_model=settings.whisper_model,
            whisper_language=settings.whisper_language,
            key_coaching_points=args.coaching_points,
        )
        article = draft.tistory
        print(f"  - STT OK: {len(draft.stt_snippets)} clips")
        print(f"  - tistory: {draft.tistory.title}")
        print(f"  - naver  : {draft.naver.title}")
    elif use_dual:
        if args.text or args.file or args.url:
            draft = generate_draft_from_source_text(
                source_text,
                settings.academy,
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
        else:
            raise ValueError("--dual requires --text, --file, --url, or --audio")
        article = draft.tistory
        print(f"  - tistory: {draft.tistory.title}")
        print(f"  - naver  : {draft.naver.title}")
    elif args.audios:
        source = load_audio(
            args.audios[0],
            api_key=settings.openai_api_key,
            model=settings.whisper_model,
            language=settings.whisper_language,
        )
        source_text = source.body
        article = optimize_to_aeo(
            source,
            settings.academy,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        draft = None
        print(f"  - title: {article.title}")
    else:
        source = resolve_input(text=args.text, file_path=args.file, url=args.url)
        article = optimize_to_aeo(
            source,
            settings.academy,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        draft = None
        print(f"  - title: {article.title}")

    print("[3/5] Schema.org JSON-LD 생성 중...")
    json_ld = draft.json_ld if draft else build_json_ld(settings.academy, article)
    json_ld_tag = json_ld_script_tag(json_ld)
    html = assemble_html(article, json_ld_tag)

    print("[4/5] 산출물 저장...")
    if draft:
        md_path = save_dual_artifacts(settings.output_dir, draft)
        print(f"  - tistory md: {md_path}")
        print(f"  - naver txt : {md_path.with_name(md_path.name.replace('_tistory.md', '_naver.txt'))}")
    else:
        md_path = save_artifacts_tistory(settings.output_dir, article, json_ld, html)
        print(f"  - saved: {md_path}")

    if args.save_draft:
        try:
            from db.connection import is_db_configured
            from db.draft_repo import save_aeo_draft

            if not is_db_configured():
                print("  ! --save-draft: DATABASE_URL 없음, DB 저장 건너뜀")
            elif draft:
                stt_payload = [
                    {"recording_id": s.recording_id, "title": s.title, "text": s.text}
                    for s in draft.stt_snippets
                ]
                draft_id = save_aeo_draft(
                    business_key=biz.business_key,
                    lesson_title=lesson_title,
                    source_text=draft.source_text,
                    tistory_markdown=draft.markdown,
                    json_ld=draft.json_ld,
                    naver_title=draft.naver.title,
                    naver_body=draft.naver_plain,
                    naver_keywords=draft.naver.keywords,
                    stt_snippets=stt_payload,
                )
                print(f"  - DB draft id: {draft_id}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ! DB 저장 실패: {exc}", file=sys.stderr)

    if dry_run:
        print_result(
            PublishResult(success=True, platform=settings.publish_platform, url=None, post_id=None, message="dry-run"),
            dry_run=True,
        )
        return 0

    print(f"[5/5] {settings.publish_platform} 발행 중 (티스토리/AEO 본문)...")
    publisher = get_publisher(settings)
    result = publisher.publish(
        title=article.title,
        html_content=html,
        markdown_content=article_to_markdown(article),
        tags=article.keywords,
        meta_description=article.meta_description,
    )
    print_result(result)
    if draft:
        print("\n[참고] 네이버 초안은 output/*_naver.txt — 복사 후 blog.naver.com 에 붙여넣기")
    return 0 if result.success else 1


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        settings = load_settings(
            business_key=args.business_key,
            industry_override=args.industry,
        )
        code = run(settings, args)
    except KeyboardInterrupt:
        print("\n중단되었습니다.", file=sys.stderr)
        code = 130
    except Exception as exc:  # noqa: BLE001
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        code = 1
    sys.exit(code)


if __name__ == "__main__":
    main()
