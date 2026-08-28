"""AEO 앱 웹 UI — FastAPI + Jinja2."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from config.industry import INDUSTRIES, INDUSTRY_META  # noqa: E402
from db.business_repo import BusinessRepo, BusinessRow  # noqa: E402
from db.connection import is_db_configured  # noqa: E402
from db.draft_repo import get_draft, list_drafts  # noqa: E402
from db.post_repo import list_published_posts, register_published_post  # noqa: E402
from services.content_service import generate_dual_draft  # noqa: E402
from web.audio_upload import cleanup_temp_audio_files, save_uploaded_audio_files  # noqa: E402

app = FastAPI(title="AEO Studio", version="0.2.0")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


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
        "industries": INDUSTRIES,
        "industry_meta": INDUSTRY_META,
    }
    base.update(extra)
    return base


def _render(request: Request, name: str, *, status_code: int = 200, **extra):
    return templates.TemplateResponse(
        request,
        name,
        _ctx(request, **extra),
        status_code=status_code,
    )


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
    )
    BusinessRepo().upsert(row)
    return RedirectResponse(url="/businesses", status_code=303)


@app.get("/generate", response_class=HTMLResponse)
async def generate_form(request: Request, business_key: str = ""):
    businesses = BusinessRepo().list_all() if is_db_configured() else []
    default_key = business_key or os.getenv("DEFAULT_BUSINESS_KEY", "")
    return _render(request, "generate.html", businesses=businesses, default_key=default_key)


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
):
    key = business_key.strip() or None
    temp_paths: list = []
    try:
        temp_paths = await save_uploaded_audio_files(audio_files)
        result = generate_dual_draft(
            source_text=source_text,
            audio_paths=temp_paths or None,
            lesson_title=lesson_title.strip() or "현장 기록",
            business_key=key,
            save_to_db=save_draft == "on" and is_db_configured(),
            use_template=use_template == "on",
            target_keyword=target_keyword,
            template_channel=template_channel,
            manual_reference_urls=manual_reference_urls,
            force_template_refresh=force_template_refresh == "on",
        )
    except Exception as exc:  # noqa: BLE001
        businesses = BusinessRepo().list_all() if is_db_configured() else []
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
