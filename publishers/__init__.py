"""발행 플랫폼 팩토리."""

from __future__ import annotations

from config.settings import Settings
from publishers.base import BasePublisher, PublishResult
from publishers.tistory import TistoryPublisher
from publishers.wordpress import WordPressPublisher


def get_publisher(settings: Settings) -> BasePublisher:
    platform = (settings.publish_platform or "wordpress").lower()
    if platform == "wordpress":
        return WordPressPublisher(settings)
    if platform == "tistory":
        return TistoryPublisher(settings)
    raise ValueError(
        f"지원하지 않는 PUBLISH_PLATFORM: {platform} (wordpress|tistory)"
    )


__all__ = [
    "BasePublisher",
    "PublishResult",
    "TistoryPublisher",
    "WordPressPublisher",
    "get_publisher",
]
