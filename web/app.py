"""AEO 앱 웹 UI — FastAPI + Jinja2."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from config.industry import INDUSTRIES, INDUSTRY_META  # noqa: E402
from config.settings import load_settings  # noqa: E402
from core.keyword_rotation import build_keyword_plan  # noqa: E402
from db.business_repo import BusinessRepo, BusinessRow  # noqa: E402
from db.connection import is_db_configured  # noqa: E402
from db.draft_repo import get_draft, list_drafts  # noqa: E402
from db.post_repo import list_published_posts, register_published_post  # noqa: E402
from services.content_service import generate_dual_draft  # noqa: E402
from db.coda_connection import is_coda_db_configured  # noqa: E402
from db.coda_repo import get_lesson_bundle, list_lessons  # noqa: E402
from services.coda_service import (  # noqa: E402
    generate_from_coda_json,
    generate_from_coda_lesson_id,
    generate_from_coda_recording_urls,
    parse_coda_json_text,
)
from web.api_v1 import router as api_v1_router  # noqa: E402
from web.audio_upload import cleanup_temp_audio_files, save_uploaded_audio_files  # noqa: E402

app = FastAPI(title="AEO Studio", version="0.2.0")
_coda_origins = [
    o.strip()
    for o in os.getenv("CODA_ALLOWED_ORIGINS", "http://localhost:5000,http://127.0.0.1:5000").split(",")
    if o.strip()
]
if _coda_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_coda_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(api_v1_router)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
_captures_dir = ROOT / "captures"
_captures_dir.mkdir(parents=True, exist_ok=True)
app.mount("/captures", StaticFiles(directory=str(_captures_dir)), name="captures")


def _db_required() -> None:
    if not is_db_configured():
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL이 설정되지 않았습니다. .env를 확인하세요.",
        )


def _ctx(request: Request, **extra):
    base = {
        "request": request,
        "db_ok": is_db_configured(),
        "coda_db_ok": is_coda_db_configured(),
        "industries": INDUSTRIES,
        "industry_meta": INDUSTRY_META,
    }
    base.update(extra)
    return base


def _render(request: Request, name: str, *, status_code: int = 200, **extra):
    if name == "ranks.html":
        extra.setdefault("telegram_ok", _telegram_configured())
        extra.setdefault("telegram_msg", None)
        extra.setdefault("schedule", _rank_schedule_status())
    return templates.TemplateResponse(
        request,
        name,
        _ctx(request, **extra),
        status_code=status_code,
    )


def _telegram_configured() -> bool:
    try:
        from core.telegram_notify import telegram_enabled

        return telegram_enabled()
    except Exception:
        return False


def _rank_schedule_status() -> dict:
    """launchd 스케줄 상태 (표시용)."""
    import os
    from pathlib import Path

    weekday_raw = (os.getenv("RANK_SCHEDULE_WEEKDAY") or "mon").strip().lower()
    labels = {
        "sun": "일",
        "0": "일",
        "mon": "월",
        "1": "월",
        "tue": "화",
        "2": "화",
        "wed": "수",
        "3": "수",
        "thu": "목",
        "4": "목",
        "fri": "금",
        "5": "금",
        "sat": "토",
        "6": "토",
    }
    hour = int(os.getenv("RANK_SCHEDULE_HOUR", "9") or 9)
    minute = int(os.getenv("RANK_SCHEDULE_MINUTE", "0") or 0)
    limit = (os.getenv("RANK_SCHEDULE_LIMIT") or "0").strip()
    plist = Path.home() / "Library" / "LaunchAgents" / "com.aeo.rank-weekly.plist"
    return {
        "installed": plist.is_file(),
        "weekday_label": labels.get(weekday_raw, weekday_raw),
        "hour": f"{hour:02d}",
        "minute": minute,
        "time_label": f"{hour:02d}:{minute:02d}",
        "limit_label": "전체" if not limit or limit == "0" else f"{limit}개",
        "log_hint": str(ROOT / "logs" / "rank_weekly.out.log"),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    businesses = []
    drafts_count = 0
    posts_count = 0
    if is_db_configured():
        businesses = BusinessRepo().list_all(limit=20)
        drafts_count = len(list_drafts(limit=100))
        posts_count = len(list_published_posts(limit=100))
    return _render(
        request,
        "index.html",
        businesses=businesses,
        drafts_count=drafts_count,
        posts_count=posts_count,
    )


def _list_rank_excels(limit: int = 10) -> list[str]:
    files = sorted(ROOT.glob("rank_result_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.name for p in files[:limit]]


def _shot_url(screenshot: str) -> str:
    """captures/... 상대경로 → /captures/... URL."""
    if not screenshot:
        return ""
    p = Path(screenshot)
    try:
        rel = p.resolve().relative_to((ROOT / "captures").resolve())
        return f"/captures/{rel.as_posix()}"
    except ValueError:
        s = screenshot.replace("\\", "/")
        if "captures/" in s:
            return "/" + s[s.index("captures/") :]
        return ""


@app.get("/ranks", response_class=HTMLResponse)
async def ranks_page(request: Request):
    from scripts.naver_place_rank import KEYWORDS

    return _render(
        request,
        "ranks.html",
        results=None,
        summary=None,
        urgent_list=None,
        excel_name=None,
        error=None,
        renewal=None,
        keywords=KEYWORDS,
        recent_excels=_list_rank_excels(),
    )


@app.post("/ranks/run", response_class=HTMLResponse)
async def ranks_run(
    request: Request,
    limit: int = Form(10),
    channel: str = Form("chrome"),
    notify_telegram: str = Form(""),
):
    import asyncio
    from datetime import date

    from scripts.naver_place_rank import BRAND_MAIN, KEYWORDS, run_check, save_excel

    limit = max(1, min(int(limit or 10), len(KEYWORDS)))
    channel = (channel or "chrome").strip()
    if channel not in {"chrome", "chromium", "msedge"}:
        channel = "chrome"

    today = date.today().isoformat()
    out_dir = ROOT / "captures" / today

    def _job():
        return run_check(
            keywords=KEYWORDS[:limit],
            out_dir=out_dir,
            headed=False,
            delay_min=2.0,
            delay_max=4.0,
            channel=channel,
        )

    try:
        results = await asyncio.to_thread(_job)
    except SystemExit as exc:
        return _render(
            request,
            "ranks.html",
            status_code=400,
            results=None,
            summary=None,
            urgent_list=None,
            excel_name=None,
            renewal=None,
            keywords=KEYWORDS,
            error=str(exc) or "브라우저 실행에 실패했습니다.",
            recent_excels=_list_rank_excels(),
            telegram_ok=_telegram_configured(),
        )
    except Exception as exc:  # noqa: BLE001
        return _render(
            request,
            "ranks.html",
            status_code=400,
            results=None,
            summary=None,
            urgent_list=None,
            excel_name=None,
            renewal=None,
            keywords=KEYWORDS,
            error=f"점검 실패: {exc}",
            recent_excels=_list_rank_excels(),
            telegram_ok=_telegram_configured(),
        )

    excel_name = f"rank_result_{today}.xlsx"
    save_excel(results, ROOT / excel_name)

    for r in results:
        r["shot_url"] = _shot_url(str(r.get("screenshot") or ""))

    summary = {
        "total": len(results),
        "exposed": sum(1 for r in results if r.get("exposed") == "O"),
        "hidden": sum(1 for r in results if r.get("exposed") == "X"),
        "urgent": sum(1 for r in results if r.get("action") == "1순위_즉시대응"),
        "weekly": sum(1 for r in results if r.get("action") == "주간_2~3편후보"),
    }
    urgent_list = [r for r in results if r.get("action") == "1순위_즉시대응"]

    telegram_msg = None
    want_tg = str(notify_telegram or "").strip().lower() in {"1", "on", "true", "yes", "y"}
    if want_tg:
        from core.telegram_notify import notify_rank_results, telegram_enabled

        if not telegram_enabled():
            telegram_msg = "텔레그램 미설정 — .env에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 필요"
        else:
            out = notify_rank_results(
                results, excel_name=excel_name, brand=BRAND_MAIN
            )
            telegram_msg = (
                "텔레그램 알림 전송 완료"
                if out.get("ok")
                else f"텔레그램 실패: {out.get('error')}"
            )

    return _render(
        request,
        "ranks.html",
        results=results,
        summary=summary,
        urgent_list=urgent_list,
        excel_name=excel_name,
        renewal=None,
        keywords=KEYWORDS,
        error=None,
        recent_excels=_list_rank_excels(),
        telegram_ok=_telegram_configured(),
        telegram_msg=telegram_msg,
    )


@app.post("/ranks/renewal", response_class=HTMLResponse)
async def ranks_renewal(
    request: Request,
    keyword: str = Form(...),
    group: str = Form(""),
    rank_note: str = Form(""),
    lesson_memo: str = Form(""),
    source_url: str = Form(""),
):
    from scripts.naver_place_rank import KEYWORD_GROUPS, KEYWORDS
    from core.renewal_draft import generate_renewal_draft, related_keywords_for

    kw = (keyword or "").strip()
    if not kw:
        return _render(
            request,
            "ranks.html",
            status_code=400,
            results=None,
            summary=None,
            urgent_list=None,
            excel_name=None,
            renewal=None,
            keywords=KEYWORDS,
            error="키워드를 선택하세요.",
            recent_excels=_list_rank_excels(),
        )

    cfg = load_settings()
    if not cfg.openai_api_key:
        return _render(
            request,
            "ranks.html",
            status_code=400,
            results=None,
            summary=None,
            urgent_list=None,
            excel_name=None,
            renewal=None,
            keywords=KEYWORDS,
            error="OPENAI_API_KEY가 없습니다.",
            recent_excels=_list_rank_excels(),
        )

    grp = (group or "").strip() or KEYWORD_GROUPS.get(kw, "")
    related = related_keywords_for(kw, grp, KEYWORDS, KEYWORD_GROUPS)
    url = (source_url or "").strip()

    try:
        renewal = generate_renewal_draft(
            keyword=kw,
            academy=cfg.business,
            api_key=cfg.openai_api_key,
            model=cfg.openai_model,
            group=grp,
            related_keywords=related,
            rank_note=rank_note,
            lesson_memo=lesson_memo,
            source_url=url,
        )
    except Exception as exc:  # noqa: BLE001
        return _render(
            request,
            "ranks.html",
            status_code=400,
            results=None,
            summary=None,
            urgent_list=None,
            excel_name=None,
            renewal=None,
            keywords=KEYWORDS,
            error=f"리뉴얼 초안 실패: {exc}",
            recent_excels=_list_rank_excels(),
        )

    return _render(
        request,
        "ranks.html",
        results=None,
        summary=None,
        urgent_list=None,
        excel_name=None,
        renewal=renewal,
        keywords=KEYWORDS,
        error=None,
        recent_excels=_list_rank_excels(),
    )


@app.get("/ranks/download/{filename}")
async def ranks_download(filename: str):
    name = Path(filename).name
    if not name.startswith("rank_result_") or not name.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="잘못된 파일명입니다.")
    path = ROOT / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(
        path,
        filename=name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/businesses", response_class=HTMLResponse)
async def businesses_list(request: Request):
    _db_required()
    rows = BusinessRepo().list_all()
    return _render(request, "businesses.html", businesses=rows)


@app.get("/businesses/new", response_class=HTMLResponse)
async def business_new_form(request: Request):
    return _render(request, "business_form.html", business=None, mode="new")


@app.get("/businesses/{business_key}/edit", response_class=HTMLResponse)
async def business_edit_form(request: Request, business_key: str):
    _db_required()
    row = BusinessRepo().get(business_key)
    if not row:
        raise HTTPException(status_code=404, detail="업체를 찾을 수 없습니다.")
    return _render(request, "business_form.html", business=row, mode="edit")


@app.post("/businesses/save")
async def business_save(
    business_key: str = Form(...),
    industry: str = Form("general"),
    name: str = Form(...),
    location: str = Form(""),
    address: str = Form(""),
    phone: str = Form(""),
    url: str = Form(""),
    services: str = Form(""),
    evidence: str = Form(""),
    adjacent_areas: str = Form(""),
    geo_lat: str = Form(""),
    geo_lng: str = Form(""),
    price_range: str = Form("$$"),
    opening_hours: str = Form(""),
):
    _db_required()
    row = BusinessRow(
        business_key=business_key.strip(),
        industry=industry.strip(),
        name=name.strip(),
        location=location.strip(),
        address=address.strip(),
        phone=phone.strip(),
        url=url.strip(),
        services=services.strip(),
        evidence=evidence.strip(),
        geo_lat=geo_lat.strip() or None,
        geo_lng=geo_lng.strip() or None,
        price_range=price_range.strip() or "$$",
        opening_hours=opening_hours.strip(),
        adjacent_areas=adjacent_areas.strip(),
    )
    BusinessRepo().upsert(row)
    return RedirectResponse(url="/businesses", status_code=303)


def _load_coda_lessons_safe() -> list:
    if not is_coda_db_configured():
        return []
    teacher = os.getenv("CODA_TEACHER_NAME", "전창영").strip()
    try:
        return list_lessons(teacher_name=teacher, limit=40)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! CODA 레슨 목록 로드 실패: {exc}")
        return []


@app.get("/generate", response_class=HTMLResponse)
async def generate_form(request: Request, business_key: str = ""):
    businesses = BusinessRepo().list_all() if is_db_configured() else []
    default_key = business_key or os.getenv("DEFAULT_BUSINESS_KEY", "")
    preview_plan = None
    try:
        preview_plan = build_keyword_plan(
            load_settings(business_key=default_key or None).business,
            "",
        )
    except Exception:  # noqa: BLE001
        preview_plan = None
    coda_teacher = os.getenv("CODA_TEACHER_NAME", "전창영").strip()
    return _render(
        request,
        "generate.html",
        businesses=businesses,
        default_key=default_key,
        preview_plan=preview_plan,
        default_target_keyword="",
        coda_db_ok=is_coda_db_configured(),
        coda_teacher_name=coda_teacher,
        coda_lessons=_load_coda_lessons_safe(),
    )


@app.post("/generate", response_class=HTMLResponse)
async def generate_submit(
    request: Request,
    business_key: str = Form(""),
    lesson_title: str = Form("현장 기록"),
    source_text: str = Form(""),
    save_draft: str = Form("on"),
    audio_files: list[UploadFile] = File(default=[]),
    use_template: str = Form(""),
    target_keyword: str = Form(""),
    template_channel: str = Form("naver"),
    manual_reference_urls: str = Form(""),
    force_template_refresh: str = Form(""),
    focus_area: str = Form(""),
    coda_recording_urls: str = Form(""),
    coda_json: str = Form(""),
    coda_teacher_name: str = Form(""),
    coda_include_stt: str = Form("on"),
    coda_lesson_id: str = Form(""),
):
    key = business_key.strip() or None
    temp_paths: list = []
    gen_kwargs = dict(
        business_key=key,
        save_to_db=save_draft == "on" and is_db_configured(),
        use_template=use_template == "on",
        target_keyword=target_keyword,
        template_channel=template_channel,
        manual_reference_urls=manual_reference_urls,
        force_template_refresh=force_template_refresh == "on",
        focus_area=focus_area.strip() or None,
    )
    try:
        temp_paths = await save_uploaded_audio_files(audio_files)
        coda_json_text = coda_json.strip()
        coda_urls_text = coda_recording_urls.strip()
        coda_lesson = coda_lesson_id.strip()

        if coda_lesson.isdigit():
            bundle = get_lesson_bundle(int(coda_lesson))
            if bundle:
                if not lesson_title.strip() or lesson_title.strip() == "현장 기록":
                    lesson_title = bundle.lesson.title or lesson_title
                if not coda_teacher_name.strip():
                    coda_teacher_name = bundle.lesson.teacher_name
            result = generate_from_coda_lesson_id(
                int(coda_lesson),
                extra_coaching=source_text.strip(),
                **gen_kwargs,
            )
        elif coda_json_text:
            payload = parse_coda_json_text(coda_json_text)
            if lesson_title.strip() and lesson_title.strip() != "현장 기록":
                payload.setdefault("lessonTitle", lesson_title.strip())
            if source_text.strip():
                existing = payload.get("keyCoachingPoints") or payload.get("key_coaching_points") or ""
                payload["keyCoachingPoints"] = (
                    f"{existing}\n{source_text.strip()}".strip() if existing else source_text.strip()
                )
            result = generate_from_coda_json(payload, **gen_kwargs)
        elif coda_urls_text:
            result = generate_from_coda_recording_urls(
                recording_lines=coda_urls_text,
                lesson_title=lesson_title.strip() or "현장 기록",
                key_coaching_points=source_text.strip(),
                teacher_name=coda_teacher_name.strip(),
                include_stt=coda_include_stt == "on",
                **gen_kwargs,
            )
        else:
            result = generate_dual_draft(
                source_text=source_text,
                audio_paths=temp_paths or None,
                lesson_title=lesson_title.strip() or "현장 기록",
                **gen_kwargs,
            )
    except Exception as exc:  # noqa: BLE001
        businesses = BusinessRepo().list_all() if is_db_configured() else []
        preview_plan = None
        try:
            preview_plan = build_keyword_plan(
                load_settings(business_key=key).business,
                source_text,
                focus_area_override=focus_area.strip() or None,
            )
        except Exception:  # noqa: BLE001
            pass
        return _render(
            request,
            "generate.html",
            status_code=400,
            businesses=businesses,
            default_key=business_key,
            error=str(exc),
            lesson_title=lesson_title,
            source_text=source_text,
            use_template=use_template == "on",
            target_keyword=target_keyword,
            template_channel=template_channel,
            manual_reference_urls=manual_reference_urls,
            focus_area=focus_area,
            force_template_refresh=force_template_refresh == "on",
            preview_plan=preview_plan,
            default_target_keyword="",
            coda_recording_urls=coda_recording_urls,
            coda_json=coda_json,
            coda_teacher_name=coda_teacher_name or os.getenv("CODA_TEACHER_NAME", "전창영"),
            coda_include_stt=coda_include_stt == "on",
            coda_lesson_id=coda_lesson_id,
            coda_db_ok=is_coda_db_configured(),
            coda_lessons=_load_coda_lessons_safe(),
        )
    finally:
        cleanup_temp_audio_files(temp_paths)

    draft = result.draft
    return _render(
        request,
        "generate_result.html",
        result=result,
        tistory_title=draft.tistory.title,
        tistory_markdown=draft.markdown,
        naver_title=draft.naver.title,
        naver_body=draft.naver_plain,
        naver_keywords=", ".join(draft.naver.keywords),
        json_ld=draft.json_ld,
        stt_snippets=draft.stt_snippets,
        template=result.template,
        keyword_plan=result.keyword_plan,
        topic_plan=draft.topic_plan,
        missing_topics=draft.missing_topics,
        missing_key_points=draft.missing_key_points,
        filler_phrases=draft.filler_phrases,
        factual_warnings=draft.factual_warnings,
        duplicated_paragraphs=draft.duplicated_paragraphs,
        stt_review=draft.stt_review,
    )


@app.get("/drafts", response_class=HTMLResponse)
async def drafts_list(request: Request, business_key: str = ""):
    _db_required()
    rows = list_drafts(business_key=business_key or None, limit=50)
    businesses = BusinessRepo().list_all()
    return _render(
        request,
        "drafts.html",
        drafts=rows,
        businesses=businesses,
        filter_key=business_key,
    )


@app.get("/drafts/{draft_id}", response_class=HTMLResponse)
async def draft_detail(request: Request, draft_id: str):
    _db_required()
    row = get_draft(draft_id)
    if not row:
        raise HTTPException(status_code=404, detail="초안을 찾을 수 없습니다.")
    return _render(request, "draft_detail.html", draft=row)


@app.get("/posts", response_class=HTMLResponse)
async def posts_list(request: Request, business_key: str = ""):
    _db_required()
    rows = list_published_posts(business_key=business_key or None, limit=100)
    businesses = BusinessRepo().list_all()
    return _render(
        request,
        "posts.html",
        posts=rows,
        businesses=businesses,
        filter_key=business_key,
    )


@app.get("/posts/register", response_class=HTMLResponse)
async def register_form(
    request: Request,
    business_key: str = "",
    draft_id: str = "",
):
    _db_required()
    businesses = BusinessRepo().list_all()
    return _render(
        request,
        "register_post.html",
        businesses=businesses,
        default_key=business_key,
        default_draft_id=draft_id,
    )


@app.post("/posts/register")
async def register_submit(
    business_key: str = Form(...),
    channel: str = Form(...),
    published_url: str = Form(...),
    target_keyword: str = Form(""),
    target_engine: str = Form("naver"),
    draft_id: str = Form(""),
    is_monitored: str = Form("on"),
):
    _db_required()
    try:
        register_published_post(
            business_key=business_key,
            channel=channel,
            published_url=published_url,
            target_keyword=target_keyword,
            target_engine=target_engine,
            draft_id=draft_id.strip() or None,
            is_monitored=is_monitored == "on",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/posts", status_code=303)


def main() -> None:
    import uvicorn

    host = os.getenv("WEB_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_PORT", "8787"))
    uvicorn.run("web.app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
