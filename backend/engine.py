from __future__ import annotations

import re
from typing import Any

from . import storage


def _split_keywords(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[/｜|,，;；\n]+", raw)
    return [p.strip() for p in parts if p.strip()]


def _text_blob(profile: dict, lead: dict | None = None) -> str:
    chunks: list[str] = []
    if lead:
        chunks.append(f"企业:{lead.get('company','')}")
        chunks.append(f"联系人:{lead.get('name','')}")
        chunks.append(f"备注:{lead.get('notes','')}")
    for key in (
        "summary",
        "industry",
        "stage",
        "recruiting_text",
        "news_text",
        "review_text",
        "website_text",
        "contact_notes",
        "raw_signals",
    ):
        val = profile.get(key)
        if isinstance(val, list):
            chunks.append(" ".join(str(x) for x in val))
        elif val:
            chunks.append(str(val))
    jobs = profile.get("jobs") or []
    for job in jobs:
        if isinstance(job, dict):
            chunks.append(f"{job.get('title','')} {job.get('desc','')}")
        else:
            chunks.append(str(job))
    return "\n".join(chunks)


def match_competitors(text: str, competitors: list[dict]) -> list[dict]:
    hits = []
    lower = text.lower()
    for c in competitors:
        if not c.get("enabled", True):
            continue
        kws = _split_keywords(c.get("keywords", ""))
        aliases = _split_keywords(c.get("aliases", ""))
        found = []
        for kw in kws + aliases + [c.get("name", "")]:
            if not kw:
                continue
            if kw.lower() in lower or kw in text:
                found.append(kw)
        if found:
            hits.append(
                {
                    "id": c["id"],
                    "name": c["name"],
                    "tier": c.get("tier", "medium"),
                    "category": c.get("category", ""),
                    "strategy": c.get("strategy", ""),
                    "matched_keywords": list(dict.fromkeys(found)),
                }
            )
    return hits


def match_rules(text: str, rules: list[dict], competitors_hits: list[dict]) -> list[dict]:
    results = []
    for rule in rules:
        if rule.get("status") == "已验证无效":
            continue
        if rule.get("enabled") is False:
            continue
        kws = _split_keywords(rule.get("signal_keywords", ""))
        if not kws:
            continue
        matched = [kw for kw in kws if kw.lower() in text.lower() or kw in text]
        if not matched:
            continue

        confidence = float(rule.get("confidence", 50))
        strength = float(rule.get("signal_strength", 3))

        # 补充条件：简单关键词加成
        bonus_note = ""
        extra = rule.get("extra_condition") or ""
        m = re.search(r"[「\"“]?([^」\"”]+)[」\"”]?.{0,8}置信度\s*\+?\s*(\d+)", extra)
        if m:
            trigger, bonus = m.group(1).strip(), int(m.group(2))
            if trigger and (trigger in text or trigger.lower() in text.lower()):
                confidence = min(100, confidence + bonus)
                bonus_note = f"补充条件命中「{trigger}」+{bonus}%"

        # 反例：命中则降权
        exception = rule.get("exception") or ""
        exception_hit = False
        for token in _split_keywords(exception.replace("如果", "").replace("则", "/")):
            if len(token) >= 2 and token in text:
                confidence = max(5, confidence * 0.55)
                exception_hit = True
                break

        score = round(confidence * (0.6 + 0.08 * strength), 2)
        results.append(
            {
                "rule_id": rule["id"],
                "signal_type": rule.get("signal_type"),
                "matched_keywords": matched,
                "need": rule.get("need"),
                "products": rule.get("products"),
                "confidence": round(confidence, 1),
                "signal_strength": strength,
                "score": score,
                "script_id": rule.get("script_id"),
                "bonus_note": bonus_note,
                "exception_hit": exception_hit,
                "validation_status": rule.get("validation_status") or rule.get("status"),
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    # 竞品策略提示
    if competitors_hits:
        strong = [c for c in competitors_hits if c.get("tier") == "strong"]
        weak = [c for c in competitors_hits if c.get("tier") == "weak"]
        for r in results:
            if strong:
                r["competitor_strategy"] = "互补方案（竞品强势绑定）"
            elif weak:
                r["competitor_strategy"] = "替换方案（竞品体验窗口）"
            else:
                r["competitor_strategy"] = "差异化切入"
    return results


def score_lead(
    lead: dict,
    profile: dict,
    rule_hits: list[dict],
    competitor_hits: list[dict],
    weights: dict,
) -> dict:
    w = {
        "urgency": float(weights.get("urgency", 0.30)),
        "budget": float(weights.get("budget", 0.25)),
        "decision": float(weights.get("decision", 0.20)),
        "competitor_window": float(weights.get("competitor_window", 0.15)),
        "industry_fit": float(weights.get("industry_fit", 0.10)),
    }

    top_conf = rule_hits[0]["confidence"] if rule_hits else 0
    urgency = min(100, top_conf * 0.9 + (15 if profile.get("recent_change") else 0))

    size = str(profile.get("company_size") or lead.get("company_size") or "")
    financing = str(profile.get("financing") or "")
    budget = 40
    if any(x in size for x in ("500", "1000", "万人", "大型")):
        budget = 85
    elif any(x in size for x in ("200", "300", "中型")):
        budget = 70
    elif any(x in size for x in ("100", "50", "小型")):
        budget = 45
    if any(x in financing for x in ("融资", "上市", "IPO", "A轮", "B轮", "C轮")):
        budget = min(100, budget + 20)

    title = str(lead.get("title") or profile.get("contact_title") or "")
    decision = 35
    if any(x in title for x in ("CHRO", "HRD", "人力资源总监", "CHO", "VP", "副总裁")):
        decision = 90
    elif any(x in title for x in ("经理", "主管", "BP", "负责人")):
        decision = 65
    elif any(x in title for x in ("专员", "助理")):
        decision = 30

    competitor_window = 55
    if any(c.get("tier") == "weak" for c in competitor_hits):
        competitor_window = 85
    elif any(c.get("tier") == "strong" for c in competitor_hits):
        competitor_window = 40
    elif not competitor_hits:
        competitor_window = 70  # 空白市场

    industry = str(profile.get("industry") or lead.get("industry") or "")
    preferred = weights.get("preferred_industries") or [
        "互联网",
        "制造",
        "零售",
        "消费",
        "金融",
        "医药",
        "教育",
    ]
    industry_fit = 50
    for p in preferred:
        if p in industry:
            industry_fit = 80
            break

    total = (
        urgency * w["urgency"]
        + budget * w["budget"]
        + decision * w["decision"]
        + competitor_window * w["competitor_window"]
        + industry_fit * w["industry_fit"]
    )
    total = round(total, 1)
    if total >= 75:
        tier = "P0-立即电话"
    elif total >= 55:
        tier = "P1-优先跟进"
    elif total >= 35:
        tier = "P2-短信/邮件预热"
    else:
        tier = "P3-长期培育"

    return {
        "total": total,
        "tier": tier,
        "dimensions": {
            "urgency": round(urgency, 1),
            "budget": round(budget, 1),
            "decision": round(decision, 1),
            "competitor_window": round(competitor_window, 1),
            "industry_fit": round(industry_fit, 1),
        },
        "weights": w,
    }


def analyze_lead(lead_id: str) -> dict[str, Any]:
    lead = storage.get_item("leads", lead_id)
    if not lead:
        raise ValueError("线索不存在")

    profile = None
    for p in storage.list_items("profiles"):
        if p.get("lead_id") == lead_id:
            profile = p
            break
    if not profile:
        profile = {
            "id": storage.new_id("PF"),
            "lead_id": lead_id,
            "company": lead.get("company"),
            "summary": lead.get("notes") or "尚未构建详细画像，仅基于线索备注与规则匹配。",
            "jobs": [],
            "recruiting_text": lead.get("notes", ""),
            "news_text": "",
            "review_text": "",
        }

    text = _text_blob(profile, lead)
    rules = storage.list_items("rules")
    competitors = storage.list_items("competitors")
    scoring = storage.read_object("scoring", {})
    weights = scoring.get("weights") or {}

    competitor_hits = match_competitors(text, competitors)
    rule_hits = match_rules(text, rules, competitor_hits)
    priority = score_lead(lead, profile, rule_hits, competitor_hits, weights)

    # 更新规则命中统计
    for hit in rule_hits:
        rule = storage.get_item("rules", hit["rule_id"])
        if rule:
            rule["hit_count"] = int(rule.get("hit_count") or 0) + 1
            hc = rule["hit_count"]
            deals = int(rule.get("deal_count") or 0)
            rule["accuracy"] = round(deals / hc * 100, 1) if hc else 0
            storage.upsert_item("rules", rule)

    scripts = {s["id"]: s for s in storage.list_items("scripts")}
    recommended_scripts = []
    for hit in rule_hits[:3]:
        sid = hit.get("script_id")
        if sid and sid in scripts:
            recommended_scripts.append(scripts[sid])

    result = {
        "lead": lead,
        "profile": profile,
        "rule_hits": rule_hits,
        "competitor_hits": competitor_hits,
        "priority": priority,
        "scripts": recommended_scripts,
        "analyzed_at": storage.now_iso(),
    }

    lead["last_score"] = priority["total"]
    lead["last_tier"] = priority["tier"]
    lead["last_analyzed_at"] = result["analyzed_at"]
    lead["status"] = lead.get("status") or "已分析"
    storage.upsert_item("leads", lead)
    return result
