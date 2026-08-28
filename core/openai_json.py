"""OpenAI JSON mode 공통 클라이언트."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI


def chat_json(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.4,
) -> dict[str, Any]:
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 필요합니다.")

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw = completion.choices[0].message.content or "{}"
    return json.loads(raw)
