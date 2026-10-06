"""规则定产品和状态之后，由模型写五线和话术。写完即用，不再按条目打回。"""
from __future__ import annotations

from typing import Any

from .. import llm
from .engine import soften_copy


def narrate(analysis: dict[str, Any]) -> dict[str, Any]:
    if not llm.available():
        raise llm.LLMError("缺少 DASHSCOPE_API_KEY，无法生成分析")
    products = "、".join(item["name"] for item in analysis.get("products") or []) or "无"
    system = (
        "你是肯耐珂萨存量客户顾问。根据下面已经确定的材料，自己写成销售能直接用的分析。"
        "输出 JSON，字段：lines（字符串数组，建议五条：停在哪、经营上发生什么、人的问题、为什么是现在、为什么是这些产品）、"
        "pitch（可照着打的电话稿）、supplement（补充观察，没有就空字符串）。"
        "写具体，引用材料里的事实。产品以给定名单为主，并列说明，不要只推一个。"
        "若确认信号还没成立，全文最多用一句轻声带过，例如「这几项事实还不够齐，电话里可以先核对情况」。"
        "不要写严禁、不得、禁止、不能对外、内部专用、硬性约束，也不要把提醒展开成推销禁令或免责声明。"
        "自称肯耐珂萨顾问。数字按材料原话转述。"
    )
    user = (
        f"公司：{analysis.get('company')}\n"
        f"联系人：{analysis.get('contact')} {analysis.get('role_name')}\n"
        f"已购原文：{analysis.get('purchased_display') or analysis.get('purchased_scope')}，截止 {analysis.get('service_end')}，客单价 {analysis.get('unit_price')}\n"
        f"分析用经营范围：{'、'.join(analysis.get('mapped_scopes') or []) or '无'}。"
        f"K米账户：{'有' if analysis.get('kmi_account') else '无'}。"
        f"咨询未细分：{'是' if analysis.get('consult_unspecified') else '否'}\n"
        "写到卡片上的已购沿用原文，不要改成经营范围名称。K米不要写成某一条产品线。\n"
        f"公开材料：{analysis.get('signals_text')}\n"
        f"行业：{(analysis.get('primary_industry') or {}).get('name') or '未命中'}\n"
        f"成熟度：{analysis.get('maturity_label')}\n"
        f"信号：{analysis.get('signal_level')}\n"
        f"确认：{'、'.join(analysis.get('confirm_hits') or [])}\n"
        f"并列产品：{products}\n"
        f"可转述：{analysis.get('speakable')}\n"
        "请直接写。"
    )
    data = llm.chat_json(system=system, user=user, temperature=0.4, max_tokens=8000)
    lines = data.get("lines")
    if isinstance(lines, str):
        lines = [lines]
    if not isinstance(lines, list):
        lines = []
    lines = [str(item).strip() for item in lines if str(item).strip()]
    lines, pitch, supplement = soften_copy(
        lines,
        str(data.get("pitch") or "").strip(),
        str(data.get("supplement") or "").strip(),
    )
    updated = dict(analysis)
    updated["lines"] = lines
    updated["pitch"] = pitch
    updated["supplement"] = supplement
    updated["copy_source"] = "model"
    return updated
