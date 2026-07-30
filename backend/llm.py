from __future__ import annotations

import json
import time
from typing import Any

import httpx

from . import config


class LLMError(RuntimeError):
    pass


def available() -> bool:
    return bool(config.DASHSCOPE_API_KEY)


def chat_complete(
    *,
    system: str,
    user: str,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 2048,
    response_format_json: bool = False,
    enable_thinking: bool | None = None,
) -> str:
    if not available():
        raise LLMError("缺少 DASHSCOPE_API_KEY，请检查 .env")

    url = f"{config.DASHSCOPE_BASE_URL}/chat/completions"
    body: dict[str, Any] = {
        "model": model or config.DASHSCOPE_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    thinking = config.DASHSCOPE_ENABLE_THINKING if enable_thinking is None else enable_thinking
    body["enable_thinking"] = thinking
    if response_format_json:
        body["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {config.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }

    last_err: Exception | None = None
    for attempt in range(1, config.DASHSCOPE_MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=config.DASHSCOPE_TIMEOUT) as client:
                resp = client.post(url, headers=headers, json=body)
                if resp.status_code in (408, 425, 429, 500, 502, 503, 504):
                    last_err = LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                    time.sleep(1.5 * attempt)
                    continue
                if resp.status_code >= 400:
                    raise LLMError(f"百炼 API HTTP {resp.status_code}: {resp.text[:500]}")
                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    raise LLMError(f"返回无 choices: {json.dumps(data)[:300]}")
                msg = choices[0].get("message") or {}
                content = msg.get("content")
                if isinstance(content, list):
                    content = "".join(
                        p.get("text", "") for p in content if isinstance(p, dict)
                    )
                if not isinstance(content, str) or not content.strip():
                    # deepseek thinking 模式可能把正文放在 reasoning_content 外的空 content
                    raise LLMError(f"返回 content 为空: {json.dumps(data)[:400]}")
                return content.strip()
        except httpx.HTTPError as e:
            last_err = e
            if attempt < config.DASHSCOPE_MAX_RETRIES:
                time.sleep(1.5 * attempt)
                continue
            raise LLMError(f"网络失败: {e}") from e
    raise LLMError(f"重试耗尽: {last_err}")


def chat_json(**kwargs: Any) -> dict:
    text = chat_complete(response_format_json=True, **kwargs)
    # 兼容模型偶尔包 markdown 代码块
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise LLMError(f"JSON 解析失败: {e}; raw={cleaned[:400]}") from e
