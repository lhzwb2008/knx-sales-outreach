from __future__ import annotations

import io
import json
import re
from typing import Any

from openpyxl import load_workbook

from . import llm, storage

OVERWRITE_FIELDS = (
    "name",
    "phone",
    "company",
    "title",
    "industry",
    "company_size",
    "notes",
    "source",
)


def normalize_company(company: str) -> str:
    return re.sub(r"\s+", "", str(company or "")).casefold()


_THREE_DIGIT_AREAS = {"010", "020", "021", "022", "023", "024", "025", "027", "028", "029"}


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if digits.startswith("00") and len(digits) > 11:
        digits = digits[2:]
    if digits.startswith("86") and len(digits) >= 13:
        rest = digits[2:]
        if len(rest) == 11 and rest.startswith("1"):
            digits = rest
    return digits


def callable_phone(phone: str) -> bool:
    """手机 11 位（1 开头）；座机为区号加 7 或 8 位。"""
    digits = normalize_phone(phone)
    if re.fullmatch(r"1[3-9]\d{9}", digits):
        return True
    if not digits.startswith("0"):
        return False
    if digits[:3] in _THREE_DIGIT_AREAS:
        local = digits[3:]
    else:
        local = digits[4:]
    return len(local) in (7, 8) and local.isdigit()


def lead_has_callable_phone(lead: dict[str, Any]) -> bool:
    phones = [lead.get("phone") or ""]
    phones.extend(contact.get("phone") or "" for contact in contacts_of(lead))
    return any(callable_phone(phone) for phone in phones)


def contacts_of(lead: dict[str, Any]) -> list[dict[str, str]]:
    raw = lead.get("contacts")
    contacts: list[dict[str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            phone = str(item.get("phone") or "").strip()
            title = str(item.get("title") or "").strip()
            notes = str(item.get("notes") or "").strip()
            if not any((name, phone, title, notes)):
                continue
            contacts.append(
                {
                    "id": str(item.get("id") or storage.new_id("C")),
                    "name": name or "客户",
                    "phone": phone,
                    "title": title,
                    "notes": notes,
                }
            )
    if contacts:
        return contacts
    name = str(lead.get("name") or "").strip()
    phone = str(lead.get("phone") or "").strip()
    title = str(lead.get("title") or "").strip()
    notes = str(lead.get("notes") or "").strip()
    if not any((name, phone, title, notes)):
        return []
    return [
        {
            "id": str(lead.get("primary_contact_id") or "primary"),
            "name": name or "客户",
            "phone": phone,
            "title": title,
            "notes": notes,
        }
    ]


def sync_primary_contact(lead: dict[str, Any]) -> dict[str, Any]:
    contacts = contacts_of(lead)
    lead["contacts"] = contacts
    primary = contacts[0] if contacts else {}
    lead["name"] = primary.get("name") or lead.get("name") or "客户"
    lead["phone"] = primary.get("phone") or ""
    lead["title"] = primary.get("title") or ""
    lead["notes"] = primary.get("notes") if contacts else (lead.get("notes") or "")
    if primary.get("id"):
        lead["primary_contact_id"] = primary["id"]
    return lead


def present_lead(lead: dict[str, Any]) -> dict[str, Any]:
    item = dict(lead)
    item["contacts"] = contacts_of(lead)
    return item


def _contact_from_incoming(item: dict[str, Any]) -> dict[str, str]:
    return {
        "id": storage.new_id("C"),
        "name": str(item.get("name") or "").strip() or "客户",
        "phone": str(item.get("phone") or "").strip(),
        "title": str(item.get("title") or "").strip(),
        "notes": str(item.get("notes") or "").strip(),
    }


def _incoming_from_row(item: dict[str, Any]) -> dict[str, str] | None:
    company = str(item.get("company") or "").strip()
    if not company:
        return None
    return {
        "name": str(item.get("name") or "").strip() or "客户",
        "phone": str(item.get("phone") or "").strip(),
        "company": company,
        "title": str(item.get("title") or "").strip(),
        "industry": str(item.get("industry") or "").strip(),
        "company_size": str(item.get("company_size") or "").strip(),
        "source": "Excel导入",
        "notes": str(item.get("notes") or "").strip(),
    }


def _lead_index_by_phone(leads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for lead in leads:
        phones = [lead.get("phone") or ""]
        phones.extend(c.get("phone") or "" for c in contacts_of(lead))
        for phone in phones:
            key = normalize_phone(phone)
            if not key:
                continue
            prev = index.get(key)
            if prev is None or str(lead.get("updated_at") or "") >= str(prev.get("updated_at") or ""):
                index[key] = lead
    return index


def _lead_index_by_company(leads: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for lead in leads:
        key = normalize_company(lead.get("company") or "")
        if not key:
            continue
        prev = index.get(key)
        if prev is None or str(lead.get("updated_at") or "") >= str(prev.get("updated_at") or ""):
            index[key] = lead
    return index


def _public_existing(lead: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": lead.get("id"),
        "name": lead.get("name") or "",
        "phone": lead.get("phone") or "",
        "company": lead.get("company") or "",
        "title": lead.get("title") or "",
        "industry": lead.get("industry") or "",
        "notes": lead.get("notes") or "",
        "status": lead.get("status") or "",
        "last_tier": lead.get("last_tier") or "",
    }


def apply_overwrite(existing_id: str, incoming: dict[str, Any]) -> dict[str, Any]:
    existing = storage.get_item("leads", existing_id)
    if not existing:
        raise ValueError("线索不存在")
    incoming_phone = normalize_phone(incoming.get("phone") or "")
    existing_phone = normalize_phone(existing.get("phone") or "")
    if incoming_phone and existing_phone and incoming_phone != existing_phone:
        raise ValueError("手机号与已有客户不一致，无法覆盖")
    updated = {**existing}
    for field in OVERWRITE_FIELDS:
        if field in incoming:
            value = incoming.get(field)
            updated[field] = "" if value is None else str(value).strip()
    if not updated.get("name"):
        updated["name"] = "客户"
    if not updated.get("company"):
        raise ValueError("公司名称不能为空")
    contacts = contacts_of(updated)
    replaced = False
    for contact in contacts:
        if incoming_phone and normalize_phone(contact.get("phone") or "") == incoming_phone:
            contact["name"] = updated.get("name") or contact["name"]
            contact["phone"] = updated.get("phone") or contact["phone"]
            contact["title"] = updated.get("title") or ""
            contact["notes"] = updated.get("notes") or ""
            replaced = True
            break
    if not replaced:
        contacts.insert(0, _contact_from_incoming(updated))
    updated["contacts"] = contacts
    sync_primary_contact(updated)
    updated["id"] = existing_id
    updated["source"] = updated.get("source") or "Excel导入"
    return storage.upsert_item("leads", updated)


def workbook_to_preview(content: bytes, max_rows: int = 40) -> dict[str, Any]:
    wb = load_workbook(io.BytesIO(content), data_only=True)
    sheet = wb.active
    rows: list[list[Any]] = []
    for i, row in enumerate(sheet.iter_rows(values_only=True)):
        if i >= max_rows:
            break
        rows.append([("" if c is None else str(c).strip()) for c in row])
    rows = [r for r in rows if any(x for x in r)]
    headers = rows[0] if rows else []
    return {
        "sheet": sheet.title,
        "headers": headers,
        "row_count": len(rows) - 1 if rows else 0,
        "sample_rows": rows[:15],
        "all_rows": rows,
    }


def parse_leads_with_llm(
    content: bytes,
    filename: str = "upload.xlsx",
    owner: str = "",
    see_all: bool = True,
) -> dict[str, Any]:
    preview = workbook_to_preview(content)
    rows = preview["all_rows"]
    compact = rows[:80]
    system = (
        "你是肯耐珂萨（Kenexa）销售助理，负责把任意格式的客户 Excel 解析成标准线索。"
        "Excel 没有固定表头，请根据语义识别列：姓名/姓氏、电话/手机、公司/企业、职位、行业、备注等。"
        "输出 JSON：{leads:[{name,phone,company,title,industry,company_size,source,notes}], "
        "mapping_notes:string, skipped_rows:number}。"
        "同一公司有多位联系人时，每人单独输出一条，不要合并。"
        "name 可只保留姓或称呼；phone 尽量规范化为数字；company 必填，缺公司的行放入跳过。"
        "电话不是 11 位手机、也不是区号加 7 到 8 位座机的行放入跳过，不要编造成合法号码。"
        "source 固定为「Excel导入」。不要编造电话或不存在的公司。"
    )
    user = (
        f"文件名：{filename}\n工作表：{preview['sheet']}\n"
        f"前若干行（含表头可能）：\n{json.dumps(compact, ensure_ascii=False)}\n"
        "请解析为线索 JSON。"
    )
    data = llm.chat_json(system=system, user=user, temperature=0.1, max_tokens=4000)
    leads_in = data.get("leads") or []

    incoming_rows: list[dict[str, str]] = []
    file_dupes = 0
    seen_in_file: dict[str, int] = {}
    for item in leads_in:
        incoming = _incoming_from_row(item)
        if not incoming:
            continue
        key = normalize_phone(incoming["phone"])
        if key:
            if key in seen_in_file:
                file_dupes += 1
                incoming_rows[seen_in_file[key]] = incoming
                continue
            seen_in_file[key] = len(incoming_rows)
        incoming_rows.append(incoming)

    invalid_phones = 0
    callable_rows: list[dict[str, str]] = []
    for incoming in incoming_rows:
        if not callable_phone(incoming["phone"]):
            invalid_phones += 1
            continue
        callable_rows.append(incoming)
    incoming_rows = callable_rows

    grouped: dict[str, list[dict[str, str]]] = {}
    group_order: list[str] = []
    for incoming in incoming_rows:
        company_key = normalize_company(incoming["company"])
        if company_key not in grouped:
            grouped[company_key] = []
            group_order.append(company_key)
        grouped[company_key].append(incoming)

    existing_leads = storage.list_items("leads")
    if not see_all:
        existing_leads = [item for item in existing_leads if (item.get("owner") or "") == owner]
    existing_by_phone = _lead_index_by_phone(existing_leads)
    existing_by_company = _lead_index_by_company(existing_leads)
    saved: list[dict[str, Any]] = []
    created = 0
    merged = 0
    conflicts: list[dict[str, Any]] = []
    for company_key in group_order:
        rows = grouped[company_key]
        company_lead = existing_by_company.get(company_key)
        fresh_rows: list[dict[str, str]] = []
        for incoming in rows:
            phone_key = normalize_phone(incoming["phone"])
            matched = existing_by_phone.get(phone_key) if phone_key else None
            if matched and (not company_lead or matched.get("id") != company_lead.get("id")):
                conflicts.append(
                    {
                        "phone": incoming["phone"] or matched.get("phone") or "",
                        "phone_key": phone_key,
                        "existing": _public_existing(matched),
                        "incoming": incoming,
                    }
                )
                continue
            fresh_rows.append(incoming)
        if not fresh_rows:
            continue
        if company_lead:
            contacts = contacts_of(company_lead)
            by_phone = {
                normalize_phone(c.get("phone") or ""): c
                for c in contacts
                if normalize_phone(c.get("phone") or "")
            }
            added = 0
            for incoming in fresh_rows:
                phone_key = normalize_phone(incoming["phone"])
                current = by_phone.get(phone_key) if phone_key else None
                if current:
                    current["name"] = incoming["name"] or current["name"]
                    current["title"] = incoming["title"]
                    current["notes"] = incoming["notes"]
                    continue
                contact = _contact_from_incoming(incoming)
                contacts.append(contact)
                if phone_key:
                    by_phone[phone_key] = contact
                    existing_by_phone[phone_key] = company_lead
                added += 1
            company_lead["contacts"] = contacts
            for field in ("industry", "company_size"):
                if not company_lead.get(field):
                    company_lead[field] = next((row[field] for row in fresh_rows if row.get(field)), "")
            sync_primary_contact(company_lead)
            saved_lead = storage.upsert_item("leads", company_lead)
            existing_by_company[company_key] = saved_lead
            saved.append(saved_lead)
            merged += added
            continue
        contacts = [_contact_from_incoming(row) for row in fresh_rows]
        lead = {
            "id": storage.new_id("L"),
            "status": "待分析",
            "workflow_step": 1,
            "company": fresh_rows[0]["company"],
            "industry": next((row["industry"] for row in fresh_rows if row.get("industry")), ""),
            "company_size": next((row["company_size"] for row in fresh_rows if row.get("company_size")), ""),
            "source": "Excel导入",
            "owner": owner,
            "contacts": contacts,
        }
        sync_primary_contact(lead)
        saved_lead = storage.upsert_item("leads", lead)
        saved.append(saved_lead)
        created += 1
        existing_by_company[company_key] = saved_lead
        for contact in contacts:
            phone_key = normalize_phone(contact.get("phone") or "")
            if phone_key:
                existing_by_phone[phone_key] = saved_lead

    notes = str(data.get("mapping_notes") or "").strip()
    extras = []
    if invalid_phones:
        extras.append(f"电话不符合要求已跳过 {invalid_phones} 行（手机需 11 位，座机需区号加 7 到 8 位）")
    if file_dupes:
        extras.append(f"同一文件内重复手机号已合并 {file_dupes} 条（保留后出现的一行）")
    if merged:
        extras.append(f"已有公司并入联系人 {merged} 位")
    if conflicts:
        extras.append(f"发现 {len(conflicts)} 个已有手机号属于其他公司，请确认是否覆盖")
    mapping_notes = "；".join([p for p in (notes, *extras) if p])

    return {
        "imported": created,
        "merged": merged,
        "companies": len(saved),
        "skipped": int(data.get("skipped_rows") or 0) + file_dupes + invalid_phones,
        "conflicts": conflicts,
        "mapping_notes": mapping_notes,
        "preview": {
            "sheet": preview["sheet"],
            "headers": preview["headers"],
            "row_count": preview["row_count"],
            "sample_rows": preview["sample_rows"],
        },
        "leads": saved,
    }
