"""3단계 — 네이버 VIEW/스마트블록 Playwright 추출 (검증 후 구현).

현재 MVP는 **m.blog.naver.com 변환 + Jina Reader 폴백**을 사용합니다.
본문 추출이 비어 있거나 120자 미만이면 Jina를 시도하고, 그래도 실패하면 수동 URL을 확인하세요.
Playwright는 3단계(`core/template/playwright_naver.py`)로 보류합니다.
"""

from __future__ import annotations

from core.template.models import PostStructure


def extract_naver_view_post(url: str) -> PostStructure:
    raise NotImplementedError(
        "네이버 VIEW Playwright 추출은 3단계입니다. "
        "지금은 /generate에서 참고 URL을 직접 입력하거나, "
        "SerpAPI + requests 추출 결과를 확인하세요."
    )
