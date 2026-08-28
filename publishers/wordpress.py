"""WordPress REST API 발행기 (Application Password)."""

from __future__ import annotations

import requests
from requests.auth import HTTPBasicAuth

from config.settings import Settings
from publishers.base import BasePublisher, PublishResult


class WordPressPublisher(BasePublisher):
    platform = "wordpress"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.wp_site_url:
            raise ValueError("WP_SITE_URL이 필요합니다.")
        if not settings.wp_username or not settings.wp_app_password:
            raise ValueError("WP_USERNAME / WP_APP_PASSWORD가 필요합니다.")

        self.endpoint = f"{settings.wp_site_url}/wp-json/wp/v2/posts"
        self.auth = HTTPBasicAuth(
            settings.wp_username,
            settings.wp_app_password.replace(" ", ""),
        )

    def publish(
        self,
        *,
        title: str,
        html_content: str,
        markdown_content: str,
        tags: list[str] | None = None,
        meta_description: str | None = None,
    ) -> PublishResult:
        payload: dict = {
            "title": title,
            "content": html_content,
            "status": self.settings.wp_status or "publish",
            "excerpt": meta_description or "",
        }
        if self.settings.wp_categories:
            payload["categories"] = self.settings.wp_categories
        if self.settings.wp_tags:
            payload["tags"] = self.settings.wp_tags

        try:
            resp = requests.post(
                self.endpoint,
                json=payload,
                auth=self.auth,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
        except requests.RequestException as exc:
            return PublishResult(
                success=False,
                platform=self.platform,
                url=None,
                post_id=None,
                message=f"WordPress 요청 실패: {exc}",
            )

        if resp.status_code not in (200, 201):
            return PublishResult(
                success=False,
                platform=self.platform,
                url=None,
                post_id=None,
                message=f"WordPress HTTP {resp.status_code}: {resp.text[:500]}",
            )

        data = resp.json()
        link = data.get("link") or data.get("guid", {}).get("rendered")
        post_id = str(data.get("id", ""))
        return PublishResult(
            success=True,
            platform=self.platform,
            url=link,
            post_id=post_id,
            message="WordPress 발행 성공",
        )
