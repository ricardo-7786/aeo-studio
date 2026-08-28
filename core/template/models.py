"""AEO 템플릿 데이터 모델."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PostStructure(BaseModel):
    url: str
    title: str = ""
    headings: list[str] = Field(default_factory=list)
    char_count: int = 0
    qa_patterns: list[str] = Field(default_factory=list)
    excerpt: str = ""


class AeoTemplate(BaseModel):
    target_keyword: str
    channel: str = "naver"
    recommended_title_pattern: str
    section_structure: list[str] = Field(default_factory=list)
    target_word_count: int = 700
    qa_pairs: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    notes: str = ""

    def to_cache_dict(self) -> dict:
        return self.model_dump()

    @classmethod
    def from_cache_dict(cls, data: dict) -> AeoTemplate:
        return cls.model_validate(data)
