"""存量 Excel。表头按语义对应，不写入陌拜线索。"""
from __future__ import annotations

from typing import Any

from ..excel_import import workbook_to_preview

ALIASES: dict[str, tuple[str, ...]] = {
    "company": ("公司全称", "公司名称", "公司", "企业名称", "客户名称", "单位名称"),
    "phone": ("电话", "手机", "手机号", "联系电话", "联系方式"),
    "contact": ("联系人", "姓名", "客户姓名"),
    "role_name": ("默认角色", "角色", "职位", "职务"),
    "industry": ("行业", "所属行业"),
    "purchased_scope": ("已购经营范围", "已购产品", "已购", "购买产品", "成交产品", "历史采购"),
    "service_end": ("服务截止", "成交日期", "到期", "截止日期", "合同到期"),
    "unit_price": ("客单价", "金额", "单价", "合同额"),
    "signals_text": ("公开信号", "已知信号", "信号", "招聘信息", "动态"),
    "notes": ("备注", "说明"),
    "crm_id": ("CRM", "客户编号", "主键", "客户ID", "客户id"),
}


def _header_map(headers: list[str]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for index, header in enumerate(headers):
        title = str(header or "").strip().replace(" ", "")
        if not title:
            continue
        for field, aliases in ALIASES.items():
            if field in mapping:
                continue
            if any(alias.replace(" ", "") in title or title in alias for alias in aliases):
                mapping[field] = index
    return mapping


def parse_stock_rows(content: bytes) -> list[dict[str, str]]:
    preview = workbook_to_preview(content, max_rows=5000)
    rows = preview.get("all_rows") or []
    if len(rows) < 2:
        raise ValueError("表格至少需要表头和一行客户")
    mapping = _header_map(rows[0])
    if "company" not in mapping:
        raise ValueError("没有识别到公司全称列")
    parsed: list[dict[str, str]] = []
    for raw in rows[1:]:
        if not any(str(cell or "").strip() for cell in raw):
            continue
        item = {field: (raw[index] if index < len(raw) else "") for field, index in mapping.items()}
        company = str(item.get("company") or "").strip()
        if not company:
            continue
        item["company"] = company
        parsed.append(item)
    if not parsed:
        raise ValueError("没有可导入的客户行")
    return parsed
