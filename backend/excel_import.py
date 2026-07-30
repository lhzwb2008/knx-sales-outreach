from __future__ import annotations

import io
import json
from typing import Any

from openpyxl import load_workbook

from . import llm, storage


def workbook_to_preview(content: bytes, max_rows: int = 40) -> dict[str, Any]:
    wb = load_workbook(io.BytesIO(content), data_only=True)
    sheet = wb.active
    rows: list[list[Any]] = []
    for i, row in enumerate(sheet.iter_rows(values_only=True)):
        if i >= max_rows:
            break
        rows.append([("" if c is None else str(c).strip()) for c in row])
    # drop fully empty rows
    rows = [r for r in rows if any(x for x in r)]
    headers = rows[0] if rows else []
    return {
        "sheet": sheet.title,
        "headers": headers,
        "row_count": len(rows) - 1 if rows else 0,
        "sample_rows": rows[:15],
        "all_rows": rows,
    }


def parse_leads_with_llm(content: bytes, filename: str = "upload.xlsx") -> dict[str, Any]:
    preview = workbook_to_preview(content)
    rows = preview["all_rows"]
    # Keep prompt size reasonable
    compact = rows[:80]
    system = (
        "你是肯耐珂萨（Kenexa）销售助理，负责把任意格式的客户 Excel 解析成标准线索。"
        "Excel 没有固定表头，请根据语义识别列：姓名/姓氏、电话/手机、公司/企业、职位、行业、备注等。"
        "输出 JSON：{leads:[{name,phone,company,title,industry,company_size,source,notes}], "
        "mapping_notes:string, skipped_rows:number}。"
        "name 可只保留姓或称呼；phone 尽量规范化为数字；company 必填，缺公司的行放入跳过。"
        "source 固定为「Excel导入」。不要编造电话或不存在的公司。"
    )
    user = (
        f"文件名：{filename}\n工作表：{preview['sheet']}\n"
        f"前若干行（含表头可能）：\n{json.dumps(compact, ensure_ascii=False)}\n"
        "请解析为线索 JSON。"
    )
    data = llm.chat_json(system=system, user=user, temperature=0.1, max_tokens=4000)
    leads_in = data.get("leads") or []
    saved = []
    for item in leads_in:
        company = str(item.get("company") or "").strip()
        phone = str(item.get("phone") or "").strip()
        if not company:
            continue
        lead = {
            "id": storage.new_id("L"),
            "name": str(item.get("name") or "").strip() or "客户",
            "phone": phone,
            "company": company,
            "title": str(item.get("title") or "").strip(),
            "industry": str(item.get("industry") or "").strip(),
            "company_size": str(item.get("company_size") or "").strip(),
            "source": "Excel导入",
            "notes": str(item.get("notes") or "").strip(),
            "status": "待分析",
            "workflow_step": 1,
        }
        saved.append(storage.upsert_item("leads", lead))
    return {
        "imported": len(saved),
        "skipped": int(data.get("skipped_rows") or 0),
        "mapping_notes": data.get("mapping_notes") or "",
        "preview": {
            "sheet": preview["sheet"],
            "headers": preview["headers"],
            "row_count": preview["row_count"],
            "sample_rows": preview["sample_rows"],
        },
        "leads": saved,
    }
