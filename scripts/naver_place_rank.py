#!/usr/bin/env python3
"""네이버 검색·플레이스 노출/순위 점검 + 스크린샷 + 엑셀 리포트.

설치 (최초 1회):
  cd "학원홍보 AEO"
  source .venv/bin/activate
  pip install playwright pandas openpyxl
  # macOS 13(Ventura)에서는 Playwright 번들 Chromium 미지원.
  # → playwright install chromium 실패해도 OK. 설치된 Google Chrome 사용.

실행:
  .venv/bin/python scripts/naver_place_rank.py
  .venv/bin/python scripts/naver_place_rank.py --limit 5
  .venv/bin/python scripts/naver_place_rank.py --headed
  .venv/bin/python scripts/naver_place_rank.py --channel chromium  # 번들 브라우저 (mac14+)

주의:
  - 네이버 비공식 자동화입니다. IP 차단·캡차·DOM 변경 가능.
  - 주 1회 수동 실행·참고용으로만 사용하세요.
  - 순위는 '플레이스/업체형 블록'에서 브랜드명이 보이는 대략 순위입니다.
  - 텔레그램: .env에 TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID 후 --telegram
"""

from __future__ import annotations

import argparse
import random
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# 브랜드·키워드
# ---------------------------------------------------------------------------

BRAND_MAIN = "OMA실용음악학원"
BRAND_ALIASES = (
    "OMA실용음악학원",
    "오엠에이실용음악학원",
    "오엠에이 실용음악학원",
    "오엠에이",
    "OMA MUSIC",
    "OMAMUSIC",
    "OMA",
    "oma",
)

# 화정역 인근 — 검색 개인화 편차 줄이기
GEO_HWJEONG = {"latitude": 37.63455, "longitude": 126.83265}

KEYWORDS = [
    # 메인 및 지역 과목
    "화정보컬학원",
    "화정실용음악학원",
    "화정피아노학원",
    "화정기타학원",
    "화정드럼학원",
    "화정작곡학원",
    "화정미디작곡학원",
    "덕양구보컬학원",
    "덕양구실용음악학원",
    "고양시실용음악학원",
    "행신보컬학원",
    "행신실용음악학원",
    "행신기타학원",
    "행신베이스학원",
    "삼송보컬학원",
    "원흥보컬학원",
    # 입시
    "화정보컬입시",
    "화정실용음악입시",
    "화정기타입시",
    "화정베이스입시",
    "행신보컬입시",
    "행신기타입시",
    "행신베이스입시",
    # 목적/세부
    "화정성인보컬학원",
    "화정취미보컬",
    "화정축가레슨",
    "화정보컬1대1",
    "화정보컬피드백",
    "화정연습실대여",
    "화정합주실",
]

# 1타 N피 — 리포트 '권장그룹' 컬럼용 (새 글 양 줄이기)
KEYWORD_GROUPS: dict[str, str] = {
    "화정보컬학원": "G1_화정보컬클러스터",
    "화정성인보컬학원": "G1_화정보컬클러스터",
    "화정취미보컬": "G1_화정보컬클러스터",
    "화정보컬1대1": "G1_화정보컬클러스터",
    "화정보컬피드백": "G1_화정보컬클러스터",
    "화정보컬입시": "G2_화정보컬입시",
    "화정실용음악학원": "G3_화정실용",
    "화정실용음악입시": "G3_화정실용",
    "화정피아노학원": "G4_화정과목",
    "화정기타학원": "G4_화정과목",
    "화정드럼학원": "G4_화정과목",
    "화정작곡학원": "G4_화정과목",
    "화정미디작곡학원": "G4_화정과목",
    "화정기타입시": "G5_화정입시과목",
    "화정베이스입시": "G5_화정입시과목",
    "덕양구보컬학원": "G6_광역",
    "덕양구실용음악학원": "G6_광역",
    "고양시실용음악학원": "G6_광역",
    "행신보컬학원": "G7_행신",
    "행신실용음악학원": "G7_행신",
    "행신기타학원": "G7_행신",
    "행신베이스학원": "G7_행신",
    "행신보컬입시": "G8_행신입시",
    "행신기타입시": "G8_행신입시",
    "행신베이스입시": "G8_행신입시",
    "삼송보컬학원": "G9_인접",
    "원흥보컬학원": "G9_인접",
    "화정축가레슨": "G10_세부에피소드",
    "화정연습실대여": "G10_세부에피소드",
    "화정합주실": "G10_세부에피소드",
}

# 대표 핵심 — 5위 밖이면 '즉시대응'
CORE_KEYWORDS = {
    "화정보컬학원",
    "화정실용음악학원",
    "화정기타학원",
    "행신보컬학원",
    "행신실용음악학원",
    "덕양구보컬학원",
    "고양시실용음악학원",
}

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
    "Mobile/15E148 Safari/604.1"
)

PLACE_ITEM_SELECTORS = [
    "a.XCvzh",
    "span.nuCTT",
    "a.place_bluelink",
    "a.LylZZ",
    "span.YwYLL",
    "span.TYaxT",
    "div.place_section li",
    "ul.list_place li",
    "#place-main-section-root li",
    "div.api_subject_bx li.bx",
    "a[href*='m.place.naver.com/place']",
    "a[href*='map.naver.com']",
]


def _normalize(s: str) -> str:
    return re.sub(r"\s+", "", (s or "")).lower().replace("·", "")


def brand_match(text: str) -> bool:
    n = _normalize(text)
    if not n:
        return False
    # 짧은 별칭(OMA)은 단독 영단어/학원명 맥락에서만
    for alias in BRAND_ALIASES:
        a = _normalize(alias)
        if len(a) >= 4 and a in n:
            return True
    if "oma" in n and ("실용" in n or "음악" in n or "학원" in n):
        return True
    if _normalize("오엠에이") in n and ("실용" in n or "음악" in n or "학원" in n or len(n) <= 12):
        return True
    if re.search(r"(^|[^a-z])oma([^a-z]|$)", n) and "학원" in n:
        return True
    return False


def recommend_action(keyword: str, rank: int | None, exposed: bool) -> str:
    """제미나이식 우선순위 → 리포트용 액션."""
    if exposed and rank is not None and rank <= 5:
        return "유지(리뉴얼만)"
    if keyword in CORE_KEYWORDS and (not exposed or rank is None or rank > 5):
        return "1순위_즉시대응"
    if not exposed or rank is None or rank > 10:
        group = KEYWORD_GROUPS.get(keyword, "")
        if group.endswith("세부에피소드") or keyword in {
            "화정축가레슨",
            "화정연습실대여",
            "화정합주실",
            "화정취미보컬",
        }:
            return "2순위_월1~2회"
        return "주간_2~3편후보"
    if rank and 6 <= rank <= 10:
        return "관찰_또는_리뉴얼"
    return "유지"


def safe_filename(keyword: str, index: int) -> str:
    safe = re.sub(r'[\\/:*?"<>|]+', "_", keyword)
    return f"{index:02d}_{safe}.png"


def _is_noise_name(t: str) -> bool:
    noise = {
        "더보기",
        "지도",
        "예약",
        "저장",
        "닫기",
        "광고",
        "플레이스",
        "검색",
        "길찾기",
        "공유",
        "전화",
        "영업중",
        "영업 종료",
        "운영 종료",
        "리뷰",
        "방문",
    }
    if t in noise:
        return True
    if len(t) < 2 or len(t) > 60:
        return True
    if t.isdigit():
        return True
    if re.fullmatch(r"\d+\s*/\s*\d+", t):
        return True
    if re.fullmatch(r"[\d.,]+\s*km", t, re.I):
        return True
    return False


def extract_place_names(page) -> list[dict]:
    """플레이스 업체 후보 [{name, is_ad}] — m.place 링크만 사용(노이즈 최소화)."""
    items: list[dict] = []
    seen: set[str] = set()

    def _clean_name(raw: str) -> str:
        t = re.sub(r"\s+", " ", (raw or "")).strip()
        t = re.sub(r"^광고\s*", "", t).strip()
        for cat in (
            "실용음악교육",
            "보컬트레이닝",
            "피아노",
            "댄스교육",
            "음악학원",
            "노래,발성,보컬교육",
        ):
            if t.endswith(cat) and len(t) > len(cat) + 2:
                t = t[: -len(cat)].strip()
        return t

    def _add(raw: str, is_ad: bool = False) -> None:
        t = _clean_name(raw)
        if _is_noise_name(t):
            return
        # 리뷰어·UI 찌꺼기
        if re.search(r"\*{2,}|\d+시간|\d{1,2}:\d{2}|운영|길찾기|전화|공유|저장", t):
            if not any(k in t for k in ("학원", "음악", "보컬", "피아노", "OMA", "오엠에이")):
                return
        if re.fullmatch(r"[a-z0-9*._-]{2,20}", t, re.I):
            return
        key = _normalize(t)
        if key in seen:
            return
        seen.add(key)
        items.append({"name": t, "is_ad": bool(is_ad)})

    try:
        js_items = page.evaluate(
            """() => {
              const out = [];
              const seen = new Set();
              const push = (name, ad) => {
                let t = (name || '').replace(/\\s+/g, ' ').trim().split('\\n')[0];
                if (!t || t.length < 2 || t.length > 50) return;
                if (seen.has(t)) return;
                seen.add(t);
                out.push({name: t, is_ad: !!ad});
              };
              document.querySelectorAll('a[href*="place.naver.com/place"]').forEach(a => {
                const href = a.href || '';
                // 플레이스 목록 항목만 (광고 포함)
                if (!/place\\.naver\\.com\\/place\\/\\d+/.test(href)) return;
                const ad = /PLACE_AD|n_ad_group|from=PLACE_AD/.test(href);
                const span = a.querySelector('span.nuCTT, span.YwYLL, span.TYaxT, span');
                let name = (span && (span.innerText||'').trim()) || '';
                if (!name) name = (a.innerText||'').trim().split('\\n')[0];
                // 카테고리만 있는 span 스킵을 위해 짧은 한글 카테고리 제외는 파이썬에서
                push(name, ad);
              });
              return out.slice(0, 25);
            }"""
        )
        if isinstance(js_items, list):
            for it in js_items:
                if isinstance(it, dict):
                    _add(str(it.get("name") or ""), bool(it.get("is_ad")))
    except Exception:
        pass

    # 보조: span.nuCTT (중복은 seen이 걸러줌)
    if len(items) < 3:
        for sel in ("span.nuCTT", "a.XCvzh", "a.place_bluelink"):
            try:
                locs = page.locator(sel)
                count = min(locs.count(), 30)
                for i in range(count):
                    try:
                        txt = locs.nth(i).inner_text(timeout=400)
                    except Exception:
                        continue
                    _add((txt or "").strip().splitlines()[0], False)
            except Exception:
                continue

    return items[:20]


def find_rank(items: list[dict], *, organic_only: bool = False) -> tuple[int | None, str, int | None]:
    """(표시순위, 매칭명, 광고제외순위). 최대 20위까지."""
    pool = [x for x in items if not (organic_only and x.get("is_ad"))] if organic_only else items
    pool = pool[:20]
    for i, it in enumerate(pool, start=1):
        name = str(it.get("name") or "")
        if brand_match(name):
            organic_rank = None
            org_i = 0
            for it2 in items:
                if it2.get("is_ad"):
                    continue
                org_i += 1
                if brand_match(str(it2.get("name") or "")):
                    organic_rank = org_i
                    break
            return i, name, organic_rank
    return None, "", None


def rank_label(rank: int | None) -> str:
    if rank is None:
        return "20위권외"
    if rank <= 20:
        return f"{rank}위"
    return "20위권외"


def prepare_place_view(page, keyword: str) -> None:
    """검색 결과에서 플레이스 영역이 보이도록 스크롤·탭 시도."""
    page.wait_for_timeout(900)
    # 플레이스 탭/더보기
    for label in ("플레이스", "지도", "관련 플레이스"):
        try:
            loc = page.get_by_role("tab", name=re.compile(label))
            if loc.count():
                loc.first.click(timeout=1200)
                page.wait_for_timeout(700)
                break
        except Exception:
            pass
        try:
            loc = page.get_by_text(label, exact=True)
            if loc.count():
                loc.first.click(timeout=1200)
                page.wait_for_timeout(700)
                break
        except Exception:
            pass
    for _ in range(3):
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(400)
    # 플레이스 더보기
    try:
        more = page.get_by_text(re.compile(r"플레이스.*더보기|더보기"))
        if more.count():
            more.first.click(timeout=1000)
            page.wait_for_timeout(800)
    except Exception:
        pass


def extract_from_map_fallback(page, keyword: str) -> list[dict]:
    """PC 검색에서 실패 시 지도 검색 폴백."""
    from urllib.parse import quote

    url = f"https://map.naver.com/p/search/{quote(keyword)}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2500)
        # 검색 패널 iframe
        frames = page.frames
        target = page
        for fr in frames:
            try:
                if "search" in (fr.url or "") or fr.locator("li").count() > 3:
                    target = fr
                    break
            except Exception:
                continue
        items = extract_place_names(target)
        if items:
            return items
        # iframe 본문 라인 기반
        try:
            text = target.inner_text("body")[:12000]
        except Exception:
            text = page.inner_text("body")[:12000]
        items = []
        seen: set[str] = set()
        for line in text.splitlines():
            t = line.strip()
            if _is_noise_name(t):
                continue
            if any(x in t for x in ("학원", "음악", "보컬", "피아노", "레슨", "트레이닝")):
                key = _normalize(t)
                if key in seen:
                    continue
                seen.add(key)
                items.append({"name": t, "is_ad": t.startswith("광고")})
            if len(items) >= 20:
                break
        return items
    except Exception:
        return []


def launch_browser(p, *, headed: bool, channel: str):
    """macOS 13은 번들 Chromium 미지원 → 기본은 시스템 Chrome."""
    launch_kwargs: dict = {"headless": not headed}
    try:
        if channel and channel != "chromium":
            launch_kwargs["channel"] = channel
            browser = p.chromium.launch(**launch_kwargs)
            print(f"브라우저: channel={channel}", flush=True)
            return browser
        browser = p.chromium.launch(headless=not headed)
        print("브라우저: Playwright Chromium", flush=True)
        return browser
    except Exception as exc:
        msg = str(exc)
        if "Executable doesn't exist" in msg or "does not support" in msg.lower():
            raise SystemExit(
                "Playwright 번들 Chromium을 쓸 수 없습니다 "
                "(macOS 13 Ventura 등에서 흔함).\n"
                "Google Chrome이 설치되어 있다면:\n"
                "  .venv/bin/python scripts/naver_place_rank.py --limit 3\n"
                "(기본값이 --channel chrome 입니다)\n"
                f"원본 오류: {msg[:300]}"
            ) from exc
        if channel == "chrome":
            raise SystemExit(
                "시스템 Google Chrome으로 실행하지 못했습니다.\n"
                "1) Chrome 설치: https://www.google.com/chrome/\n"
                "2) 또는 macOS 14+ 에서: playwright install chromium && "
                "--channel chromium\n"
                f"원본 오류: {msg[:300]}"
            ) from exc
        raise


def run_check(
    *,
    keywords: list[str],
    out_dir: Path,
    headed: bool,
    delay_min: float,
    delay_max: float,
    channel: str = "chrome",
) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "playwright가 없습니다. pip install playwright pandas openpyxl"
        ) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    with sync_playwright() as p:
        browser = launch_browser(p, headed=headed, channel=channel)
        # 모바일 검색이 플레이스 목록 DOM이 더 안정적
        context = browser.new_context(
            user_agent=MOBILE_UA,
            locale="ko-KR",
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True,
            geolocation=GEO_HWJEONG,
            permissions=["geolocation"],
        )
        page = context.new_page()

        for idx, keyword in enumerate(keywords, start=1):
            from urllib.parse import quote

            url = f"https://m.search.naver.com/search.naver?query={quote(keyword)}"
            print(f"[{idx}/{len(keywords)}] {keyword} …", flush=True)
            rank: int | None = None
            organic_rank: int | None = None
            matched = ""
            items: list[dict] = []
            source = "m_search"
            confidence = "low"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(1200)
                for _ in range(3):
                    page.mouse.wheel(0, 1200)
                    page.wait_for_timeout(450)

                items = extract_place_names(page)
                rank, matched, organic_rank = find_rank(items)

                # 모바일에서 실패 시 PC 검색 → 지도 폴백
                if rank is None:
                    pc = browser.new_context(
                        user_agent=USER_AGENT,
                        locale="ko-KR",
                        viewport={"width": 1400, "height": 900},
                        geolocation=GEO_HWJEONG,
                        permissions=["geolocation"],
                    )
                    try:
                        pp = pc.new_page()
                        pp.goto(
                            f"https://search.naver.com/search.naver?query={quote(keyword)}",
                            wait_until="domcontentloaded",
                            timeout=45000,
                        )
                        prepare_place_view(pp, keyword)
                        items2 = extract_place_names(pp)
                        if items2:
                            items = items2
                            source = "pc_search"
                            rank, matched, organic_rank = find_rank(items)
                        if rank is None:
                            fb = extract_from_map_fallback(pp, keyword)
                            if fb:
                                items = fb
                                source = "map"
                                rank, matched, organic_rank = find_rank(items)
                        shot = out_dir / safe_filename(keyword, idx)
                        pp.screenshot(path=str(shot), full_page=True)
                    finally:
                        pc.close()
                else:
                    shot = out_dir / safe_filename(keyword, idx)
                    page.screenshot(path=str(shot), full_page=True)

                use_rank = rank if rank is not None else organic_rank
                try:
                    body_hit = brand_match(page.inner_text("body")[:12000])
                except Exception:
                    body_hit = False
                exposed = use_rank is not None
                page_mention = body_hit and not exposed

                if exposed and matched:
                    confidence = "high"
                elif page_mention:
                    confidence = "medium"
                else:
                    confidence = "low"

                action = recommend_action(keyword, use_rank, exposed)
                names = [str(x.get("name") or "") for x in items]
                ad_n = sum(1 for x in items if x.get("is_ad"))
                results.append(
                    {
                        "no": idx,
                        "keyword": keyword,
                        "group": KEYWORD_GROUPS.get(keyword, ""),
                        "exposed": "O" if exposed else "X",
                        "rank": rank_label(use_rank),
                        "rank_num": use_rank,
                        "organic_rank": rank_label(organic_rank) if organic_rank else "",
                        "matched_name": matched,
                        "page_mention": "O" if page_mention else "X",
                        "confidence": confidence,
                        "source": source,
                        "top10_sample": " | ".join(names[:8]),
                        "ad_count": ad_n,
                        "action": action,
                        "screenshot": str(shot.relative_to(ROOT)) if shot.is_relative_to(ROOT) else str(shot),
                        "error": "",
                    }
                )
                status = rank_label(use_rank)
                print(
                    f"    → {status} / 노출={'O' if exposed else 'X'} / "
                    f"신뢰={confidence} / {source} / {action}",
                    flush=True,
                )
                if names[:5]:
                    print(f"       감지: {' | '.join(names[:5])}", flush=True)
            except Exception as exc:  # noqa: BLE001
                error = str(exc)[:200]
                print(f"    ! 실패: {error}", flush=True)
                results.append(
                    {
                        "no": idx,
                        "keyword": keyword,
                        "group": KEYWORD_GROUPS.get(keyword, ""),
                        "exposed": "X",
                        "rank": "오류",
                        "rank_num": None,
                        "organic_rank": "",
                        "matched_name": "",
                        "page_mention": "X",
                        "confidence": "low",
                        "source": "",
                        "top10_sample": "",
                        "ad_count": 0,
                        "action": "재실행",
                        "screenshot": "",
                        "error": error,
                    }
                )

            if idx < len(keywords):
                time.sleep(random.uniform(delay_min, delay_max))

        context.close()
        browser.close()

    return results


def save_excel(results: list[dict], path: Path) -> None:
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("pandas/openpyxl 필요: pip install pandas openpyxl") from exc

    df = pd.DataFrame(results)
    df = df.rename(
        columns={
            "no": "No",
            "keyword": "키워드",
            "group": "권장그룹(1타N피)",
            "exposed": "상단노출",
            "rank": "순위",
            "rank_num": "순위숫자",
            "organic_rank": "광고제외순위",
            "matched_name": "매칭업체명",
            "page_mention": "페이지내브랜드언급",
            "confidence": "신뢰도",
            "source": "수집출처",
            "top10_sample": "상위샘플",
            "ad_count": "광고수",
            "action": "권장액션",
            "screenshot": "캡처경로",
            "error": "오류",
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def print_summary(results: list[dict]) -> None:
    exposed = [r for r in results if r["exposed"] == "O"]
    out = [r for r in results if r["exposed"] == "X"]
    urgent = [r for r in results if r["action"] == "1순위_즉시대응"]
    weekly = [r for r in results if r["action"] == "주간_2~3편후보"]

    print("\n========== 요약 ==========")
    print(f"전체: {len(results)} | 노출 O: {len(exposed)} | 노출 X: {len(out)}")
    print(f"즉시대응: {len(urgent)} | 주간후보: {len(weekly)}")
    print(
        "\n{:<4} {:<18} {:<6} {:<10} {:<8} {}".format(
            "No", "키워드", "노출", "순위", "신뢰", "액션"
        )
    )
    print("-" * 78)
    for r in results:
        print(
            f"{r['no']:<4} {r['keyword']:<18} {r['exposed']:<6} "
            f"{str(r['rank']):<10} {r.get('confidence', ''):<8} {r['action']}"
        )
    if urgent:
        print("\n[즉시 대응 권장]")
        for r in urgent:
            print(f"  - {r['keyword']} ({r['rank']})")
    if weekly:
        print("\n[주간 2~3편 후보 — 그룹으로 묶어서 1편 권장]")
        for r in weekly[:12]:
            print(f"  - {r['keyword']} / {r['group']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="네이버 플레이스/검색 노출 점검")
    parser.add_argument("--limit", type=int, default=0, help="앞에서 N개만 (테스트용)")
    parser.add_argument("--headed", action="store_true", help="브라우저 표시")
    parser.add_argument("--out-dir", type=str, default="", help="캡처 폴더")
    parser.add_argument("--delay-min", type=float, default=2.0)
    parser.add_argument("--delay-max", type=float, default=4.0)
    parser.add_argument(
        "--channel",
        type=str,
        default="chrome",
        choices=("chrome", "chromium", "msedge"),
        help="브라우저 채널 (macOS 13은 chrome 권장, 기본값)",
    )
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="점검 후 텔레그램 요약 전송 (.env 토큰 필요)",
    )
    parser.add_argument(
        "--telegram-test",
        action="store_true",
        help="점검 없이 텔레그램 연결만 테스트",
    )
    args = parser.parse_args()

    if args.telegram_test:
        from core.telegram_notify import send_telegram_message, telegram_enabled

        if not telegram_enabled():
            print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 를 .env에 넣어 주세요.")
            return 1
        out = send_telegram_message("✅ AEO 순위 알림 테스트 — 연결 OK")
        if out.get("ok"):
            print("텔레그램 테스트 전송 성공")
            return 0
        print(f"텔레그램 실패: {out.get('error')}")
        return 1

    today = date.today().isoformat()
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "captures" / today
    keywords = KEYWORDS[: args.limit] if args.limit > 0 else list(KEYWORDS)

    print(f"브랜드: {BRAND_MAIN} / aliases={BRAND_ALIASES[:3]}…")
    print(f"키워드 {len(keywords)}개 → 캡처: {out_dir}")

    results = run_check(
        keywords=keywords,
        out_dir=out_dir,
        headed=args.headed,
        delay_min=args.delay_min,
        delay_max=max(args.delay_min, args.delay_max),
        channel=args.channel,
    )

    xlsx = ROOT / f"rank_result_{today}.xlsx"
    save_excel(results, xlsx)
    print_summary(results)
    print(f"\n엑셀 저장: {xlsx}")
    print(f"캡처 폴더: {out_dir}")

    if args.telegram:
        from core.telegram_notify import notify_rank_results, telegram_enabled

        if not telegram_enabled():
            print("텔레그램 스킵: .env에 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 없음")
        else:
            out = notify_rank_results(
                results, excel_name=xlsx.name, brand=BRAND_MAIN
            )
            if out.get("ok"):
                print("텔레그램 알림 전송 완료")
            else:
                print(f"텔레그램 실패: {out.get('error')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
