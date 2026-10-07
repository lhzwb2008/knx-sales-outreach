"""上传后检索这家公司的新闻、招聘和公众号文章，再判断能否触达。

不靠词表放行。引用的链接必须来自检索接口，没有可引用结果时不送进可触达。
"""
from __future__ import annotations

import html
import json
import re
from typing import Any

import httpx

from .. import config, llm
from ..storage import now_iso
from . import engine, preview, storage

_SEARCH_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
EMPTY_LINE = "还没看到和组织、用人有关的公开动作。"


def lookup(record: dict[str, Any]) -> dict[str, Any]:
    if not llm.available():
        raise llm.LLMError("缺少 DASHSCOPE_API_KEY，无法检索公开动态")
    company = str(record.get("company") or "").strip()
    if not company:
        raise llm.LLMError("没有公司名称，无法检索")
    hits = _attach_excerpts(_search(company))
    if not hits:
        return normalize({"signal": "none", "summary": EMPTY_LINE, "items": []})
    industry = str(record.get("industry") or "")
    purchased = str(record.get("purchased_display") or record.get("purchased_scope") or "")
    system = (
        "你是肯耐珂萨的客户研究员。只能使用下面给出的检索结果，不要补充结果里没有的事实，不要编造链接。"
        "这些结果来自新闻、招聘网站和被搜索引擎收录的公众号。"
        "输出 JSON："
        "signal（confirm、leading、none 之一），"
        "summary（只写一句。这句要从检索结果里的事实说出经营或用人问题，并点出材料里的具体动作。"
        "看不出这类动作时，就写还没看到和组织、用人有关的公开动作，不要另编一套经营问题），"
        "actions（公司自己已经发生的组织、用人、招聘、培训、门店或工厂、外派动作，字符串数组），"
        "pressures（只有外部压力、还看不到公司动作的点，字符串数组），"
        "items（数组，元素含 title、url、date、fact，url 必须原样使用检索结果里的链接）。"
        "signal=confirm 表示结果里能看到这家公司已经在动；"
        "leading 表示主要是行业或政策压力；"
        "none 表示结果和组织发展无关，或只是同名公司、品牌广告。"
    )
    user = (
        f"公司：{company}\n"
        f"行业：{industry or '未知'}\n"
        f"已购原文：{purchased or '未填'}\n"
        f"检索结果：\n{json.dumps(hits, ensure_ascii=False)}"
    )
    data = llm.chat_json(
        system=system,
        user=user,
        model=config.DASHSCOPE_SEARCH_MODEL,
        temperature=0.2,
        max_tokens=1800,
        enable_thinking=False,
    )
    allowed = {item["url"] for item in hits}
    result = normalize(data)
    result["items"] = [item for item in result["items"] if item["url"] in allowed]
    if result["signal"] == "confirm" and not result["items"]:
        result["signal"] = "none"
        result["actions"] = []
        result["summary"] = EMPTY_LINE
        result["brief"] = EMPTY_LINE
    elif result["items"]:
        result["brief"] = _brief(result["summary"], result["items"])
    return result


def _search(company: str) -> list[dict[str, str]]:
    query = (
        f"检索「{company}」最近的新闻、招聘网站岗位、微信公众号文章。"
        "关注组织调整、用人、干部、培训、门店、工厂、外派。只依据检索结果。"
    )
    body = {
        "model": config.DASHSCOPE_SEARCH_MODEL,
        "input": {"messages": [{"role": "user", "content": query}]},
        "parameters": {
            "enable_search": True,
            "result_format": "message",
            "search_options": {
                "forced_search": True,
                "enable_source": True,
                "search_strategy": "max",
            },
        },
    }
    headers = {
        "Authorization": f"Bearer {config.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=config.DASHSCOPE_TIMEOUT) as client:
            resp = client.post(_SEARCH_URL, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise llm.LLMError(f"检索网络失败: {exc}") from exc
    if resp.status_code >= 400:
        raise llm.LLMError(f"检索 HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    if data.get("code"):
        raise llm.LLMError(f"检索失败: {data.get('code')} {str(data.get('message') or '')[:200]}")
    raw_results = ((data.get("output") or {}).get("search_info") or {}).get("search_results") or []
    hits: list[dict[str, str]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if not url or not title:
            continue
        snippet = ""
        for key in ("snippet", "summary", "content", "description"):
            if item.get(key):
                snippet = str(item[key]).strip()
                break
        hits.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
                "site": str(item.get("site_name") or "").strip(),
            }
        )
        if len(hits) >= 8:
            break
    return hits


def _attach_excerpts(hits: list[dict[str, str]]) -> list[dict[str, str]]:
    from concurrent.futures import ThreadPoolExecutor

    if not hits:
        return []

    def read(hit: dict[str, str]) -> dict[str, str]:
        copied = dict(hit)
        copied["excerpt"] = _read_page(hit["url"])
        return copied

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(read, hits))


def _read_page(url: str) -> str:
    try:
        with httpx.Client(timeout=12, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
    except httpx.HTTPError:
        return ""
    if resp.status_code >= 400:
        return ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", resp.text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1600]


def normalize(data: dict[str, Any]) -> dict[str, Any]:
    signal = str(data.get("signal") or "none").strip().lower()
    if signal not in {"confirm", "leading", "none"}:
        signal = "none"
    items = []
    for raw in data.get("items") or []:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        fact = str(raw.get("fact") or "").strip()
        url = str(raw.get("url") or "").strip()
        if not title or not (fact or url):
            continue
        if "未检索到" in title and not url:
            continue
        items.append(
            {
                "title": title,
                "url": url,
                "date": str(raw.get("date") or "").strip(),
                "fact": fact,
            }
        )
    actions = _strings(data.get("actions"))
    pressures = _strings(data.get("pressures"))
    summary = _one_sentence(str(data.get("summary") or "").strip())
    if not items:
        summary = EMPTY_LINE
    if signal == "confirm" and not items:
        signal = "none"
        actions = []
        summary = EMPTY_LINE
    return {
        "signal": signal,
        "summary": summary,
        "actions": actions,
        "pressures": pressures,
        "items": items,
        "brief": _brief(summary, items),
    }


def _brief(summary: str, items: list[dict[str, str]]) -> str:
    lines = [summary] if summary else []
    for item in items:
        when = f"{item['date']} " if item.get("date") else ""
        line = f"{when}{item['title']}：{item.get('fact') or ''}".strip("：")
        if item.get("url"):
            line = f"{line} {item['url']}"
        lines.append(line)
    return "\n".join(line for line in lines if line).strip()


def apply(record: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    signal = result["signal"]
    record["signals_text"] = result["brief"]
    record["research"] = {
        "at": now_iso(),
        "signal_level": signal,
        "summary": result["summary"],
        "sources": result["items"],
    }
    record.pop("research_error", None)
    analysis = dict(record.get("analysis") or {})
    analysis["signals_text"] = record["signals_text"]
    analysis["signal_level"] = signal
    analysis["confirm_hits"] = result["actions"]
    analysis["leading_hits"] = result["pressures"]
    analysis["research_summary"] = result["summary"]
    analysis["speakable"] = result["summary"]
    gaps = [gap for gap in analysis.get("gaps") or [] if "公开动态" not in gap and "先导或确认信号" not in gap]
    if signal == "none":
        gaps.append("未检索到和组织发展相关的公开动态")
    analysis["gaps"] = gaps
    record["analysis"] = analysis
    if record.get("import_profile") == "business":
        destination = str(record.get("import_destination") or "pool")
        record["status"] = preview.place_company(signal, destination, bool(record.get("unrecognized")))
    else:
        record["status"] = engine.place_status(signal, record.get("source") or "self_upload", record.get("owner") or "")
    return storage.upsert_item("records", record)


def refresh_line(record: dict[str, Any]) -> dict[str, Any]:
    """用已经保存的依据重写一句说明，不再重新检索。"""
    research = dict(record.get("research") or {})
    sources = research.get("sources") or []
    if not sources:
        sentence = EMPTY_LINE
    else:
        sentence = _sentence_from_sources(str(record.get("company") or ""), sources)
    research["summary"] = sentence
    record["research"] = research
    analysis = dict(record.get("analysis") or {})
    analysis["speakable"] = sentence
    analysis["research_summary"] = sentence
    record["analysis"] = analysis
    return storage.upsert_item("records", record)


def _sentence_from_sources(company: str, sources: list[dict[str, Any]]) -> str:
    packed = [
        {
            "title": item.get("title") or "",
            "fact": item.get("fact") or "",
            "date": item.get("date") or "",
        }
        for item in sources
        if isinstance(item, dict)
    ]
    data = llm.chat_json(
        system=(
            "根据给出的公开材料，只写一句中文。"
            "这句要说这些材料指向什么经营或用人问题，并点出材料里的具体事实。"
            "材料里看不出组织、用人、培训、门店工厂或外派动作时，"
            "就写还没看到和组织、用人有关的公开动作，不要另编经营问题。"
            "输出 JSON：sentence。"
        ),
        user=f"公司：{company}\n材料：{json.dumps(packed, ensure_ascii=False)}",
        model=config.DASHSCOPE_SEARCH_MODEL,
        temperature=0.2,
        max_tokens=300,
        enable_thinking=False,
    )
    return _one_sentence(str(data.get("sentence") or "").strip()) or EMPTY_LINE


def _one_sentence(text: str) -> str:
    text = " ".join(text.split())
    if not text:
        return ""
    for mark in ("。", "！", "？"):
        if mark in text:
            return text.split(mark, 1)[0] + mark
    return text


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
