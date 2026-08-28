"""티스토리 Open API 발행기."""

from __future__ import annotations

import requests

from config.settings import Settings
from publishers.base import BasePublisher, PublishResult

TISTORY_WRITE_URL = "https://www.tistory.com/apis/post/write"


class TistoryPublisher(BasePublisher):
    platform = "tistory"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.tistory_access_token:
            raise ValueError("TISTORY_ACCESS_TOKEN이 필요합니다.")
        if not settings.tistory_blog_name:
            raise ValueError("TISTORY_BLOG_NAME이 필요합니다.")

    def publish(
        self,
        *,
        title: str,
        html_content: str,
        markdown_content: str,
        tags: list[str] | None = None,
        meta_description: str | None = None,
    ) -> PublishResult:
        # 티스토리는 HTML content 권장. tag는 콤마 구분.
        tag_str = ",".join(tags or [])
        data = {
            "access_token": self.settings.tistory_access_token,
            "output": "json",
            "blogName": self.settings.tistory_blog_name,
            "title": title,
            "content": html_content,
            "visibility": str(self.settings.tistory_visibility),
            "tag": tag_str,
            "acceptComment": "1",
        }

        try:
            resp = requests.post(TISTORY_WRITE_URL, data=data, timeout=60)
        except requests.RequestException as exc:
            return PublishResult(
                success=False,
                platform=self.platform,
                url=None,
                post_id=None,
                message=f"티스토리 요청 실패: {exc}",
            )

        if resp.status_code != 200:
            return PublishResult(
                success=False,
                platform=self.platform,
                url=None,
                post_id=None,
                message=f"티스토리 HTTP {resp.status_code}: {resp.text[:500]}",
            )

        try:
            body = resp.json()
        except ValueError:
            return PublishResult(
                success=False,
                platform=self.platform,
                url=None,
                post_id=None,
                message=f"티스토리 응답 JSON 파싱 실패: {resp.text[:300]}",
            )

        # {"tistory": {"status": "200", "postId": "...", "url": "..."}}
        tistory = body.get("tistory") or body
        status = str(tistory.get("status", ""))
        if status not in {"200", "201"}:
            err = tistory.get("error_message") or tistory.get("message") or body
            return PublishResult(
                success=False,
                platform=self.platform,
                url=None,
                post_id=None,
                message=f"티스토리 API 오류: {err}",
            )

        return PublishResult(
            success=True,
            platform=self.platform,
            url=tistory.get("url"),
            post_id=str(tistory.get("postId", "")),
            message="티스토리 발행 성공",
        )
