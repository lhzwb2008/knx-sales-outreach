from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import httpx

from . import config


class ImageError(RuntimeError):
    pass


def available() -> bool:
    return bool(config.AIHUBMIX_API_KEY)


HELP_PROMPT = """Create a clean horizontal business workflow infographic for Chinese B2B sales users.
Landscape 16:9. Match KNX 智拓 product UI colors exactly:
- Background: cool light blue-gray gradient (#EEF3F8 to #E8EEF6), subtle soft cyan radial glow top-right (rgba cyan, very faint)
- Primary accent cyan: #00A8D8
- Glow accent: #00DDFF
- Deep navy ink: #0D1526 / #1A2438
- Soft orange CTA accent: #FF9C00 (use sparingly for step titles or number rings)
- Cards: pure white (#FFFFFF), soft blue-gray shadow, rounded ~16px
NO logos, NO watermarks, NO English except step numbers 1-5.
NO purple, NO teal/green Kenexa look, NO warm cream/beige background, NO terracotta/coral.

Title at top center in clear bold Chinese navy (exact text):
「KNX 智拓 · 使用流程」

Subtitle under title in muted blue-gray (exact):
「智能拓客 · 需求洞察 · 话术触达 · 促成交」

Draw FIVE numbered rounded white cards in a single left-to-right flow with thick cyan (#00A8D8) arrows between them.
Each card: large cyan/orange number circle, simple flat cyan line-icon, EXACT Chinese labels:

Step 1 title: 上传名单
Step 1 body: 导入Excel客户表
（系统自动识别字段）

Step 2 title: 需求分析
Step 2 body: 结合公开信息
判断客户可能需求

Step 3 title: 生成话术
Step 3 body: 按需求定制电话开场
有的放矢再外呼

Step 4 title: 记录过程
Step 4 body: 填写通话细节与结果
沉淀可复用经验

Step 5 title: 微信待办
Step 5 body: 对方同意加微后
提醒跟进发资料

Bottom footer line in muted gray (exact Chinese):
「作者 Ira · 供肯耐珂萨销售同事日常陌拜使用」

Typography: all Chinese characters sharp, large, high-contrast, perfectly legible, no typos, no missing strokes, no garbled glyphs.
Flat modern SaaS infographic, generous spacing, no clutter, no 3D, no neon purple glow.
"""


def generate_image(prompt: str, *, size: str | None = None, quality: str | None = None) -> bytes:
    if not available():
        raise ImageError("缺少生图配置")
    url = f"{config.AIHUBMIX_BASE_URL}/images/generations"
    body: dict[str, Any] = {
        "model": config.AIHUBMIX_IMAGE_MODEL,
        "prompt": prompt,
        "n": 1,
        "size": size or config.AIHUBMIX_IMAGE_SIZE,
        "quality": quality or config.AIHUBMIX_IMAGE_QUALITY,
    }
    headers = {
        "Authorization": f"Bearer {config.AIHUBMIX_API_KEY}",
        "Content-Type": "application/json",
    }
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            with httpx.Client(timeout=config.AIHUBMIX_IMAGE_TIMEOUT) as client:
                resp = client.post(url, headers=headers, json=body)
                if resp.status_code >= 400:
                    raise ImageError(f"生图失败 HTTP {resp.status_code}: {resp.text[:400]}")
                data = resp.json()
                item = (data.get("data") or [{}])[0]
                b64 = item.get("b64_json")
                if b64:
                    return base64.b64decode(b64)
                img_url = item.get("url")
                if img_url:
                    r2 = client.get(img_url)
                    r2.raise_for_status()
                    return r2.content
                raise ImageError(f"生图无图片数据: {str(data)[:300]}")
        except (httpx.HTTPError, ImageError) as e:
            last_err = e
            time.sleep(1.5 * attempt)
    raise ImageError(f"生图重试耗尽: {last_err}")


def ensure_help_image(force: bool = False) -> Path:
    path = config.HELP_IMAGE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 1000 and not force:
        return path
    raw = generate_image(HELP_PROMPT)
    path.write_bytes(raw)
    return path
