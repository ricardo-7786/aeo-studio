"""블로그 발행기 공통 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PublishResult:
    success: bool
    platform: str
    url: str | None
    post_id: str | None
    message: str


class BasePublisher(ABC):
    platform: str = "base"

    @abstractmethod
    def publish(
        self,
        *,
        title: str,
        html_content: str,
        markdown_content: str,
        tags: list[str] | None = None,
        meta_description: str | None = None,
    ) -> PublishResult:
        raise NotImplementedError
