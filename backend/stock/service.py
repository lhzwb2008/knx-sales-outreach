"""存量名单的保存与展示。同一公司全称各存各的，不合并、不锁定来源。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..excel_import import normalize_phone
from ..storage import new_id, now_iso
from . import catalog, engine, preview, storage
from .playbooks import PLAYBOOKS, SHELF

INTENTS = ("有明确兴趣", "暂无需求", "需发资料", "号码失效")
PAIN = ("属实", "偏差")


def create_record(payload: dict[str, Any], *, source: str, owner: str, assigned_by: str = "") -> dict:
    record = {
        "id": new_id("ST"),
        "company": str(payload.get("company") or "").strip(),
        "phone": normalize_phone(str(payload.get("phone") or "")),
        "contact": str(payload.get("contact") or "").strip(),
        "role_name": str(payload.get("role_name") or payload.get("role") or "").strip(),
        "industry": str(payload.get("industry") or "").strip(),
        "purchased_scope": str(payload.get("purchased_scope") or "").strip(),
        "service_end": str(payload.get("service_end") or "").strip(),
        "unit_price": str(payload.get("unit_price") or "").strip(),
        "signals_text": str(payload.get("signals_text") or "").strip(),
        "notes": str(payload.get("notes") or "").strip(),
        "crm_id": str(payload.get("crm_id") or "").strip(),
        "source": source,
        "owner": owner,
        "assigned_by": assigned_by,
        "effective_on": str(payload.get("effective_on") or "").strip(),
        "grant_expires_at": "",
        "first_touch_at": "",
        "lock_until": "",
        "lock_label": "",
        "align_status": "aligned" if source != "self_upload" and str(payload.get("crm_id") or "").strip() else "unaligned",
    }
    if source == "admin_import" and record["crm_id"]:
        record["align_status"] = "aligned"
    record["analysis"] = engine.analyze(record, storage.disabled_playbooks())
    record["analysis"]["copy_source"] = "pending"
    record["status"] = engine.place_status(record["analysis"]["signal_level"], source, owner)
    return storage.upsert_item("records", record)


def reanalyze(record: dict) -> dict:
    record["analysis"] = engine.analyze(record, storage.disabled_playbooks())
    record["status"] = engine.place_status(record["analysis"]["signal_level"], record.get("source") or "", record.get("owner") or "")
    record["analysis"]["copy_source"] = "pending"
    return storage.upsert_item("records", record)


def ensure_model_copy(record: dict) -> dict:
    """规则决定产品和状态。五线、话术、补充观察只由模型写成。"""
    from . import narrate

    analysis = record.get("analysis") or {}
    if analysis.get("copy_source") == "model" and analysis.get("lines"):
        return record
    if not analysis.get("signal_level"):
        record = reanalyze(record)
        analysis = record["analysis"]
    record["analysis"] = narrate.narrate(analysis)
    return storage.upsert_item("records", record)


def present(record: dict, viewer: dict) -> dict:
    access = engine.phone_access(record, viewer)
    analysis = engine.public_analysis(
        record.get("analysis") or {},
        include_tension=False,
    )
    contacts = _public_contacts(record, access["visible"])
    preferred = next((item for item in contacts if item.get("preferred")), contacts[0] if contacts else {})
    data = dict(record)
    data["analysis"] = analysis
    data["contacts"] = contacts
    data["extra_contact_count"] = max(0, len(contacts) - 1)
    data["purchased_display"] = record.get("purchased_display") or record.get("purchased_scope") or ""
    data["phone"] = _preferred_number(preferred) if access["visible"] else ""
    data["phone_visible"] = access["visible"]
    data["phone_note"] = access["note"]
    if preferred:
        data["contact"] = preferred.get("name") or data.get("contact") or ""
        data["role_name"] = preferred.get("role") or data.get("role_name") or ""
    data["pain_recorded"] = bool(record.get("pain_match"))
    data["source_label"] = {
        "self_upload": "自有名单",
        "admin_assign": "管理员分配",
        "admin_import": "公海导入",
    }.get(record.get("source") or "", record.get("source") or "")
    return data


def can_read(record: dict, viewer: dict) -> bool:
    return True


def list_for(viewer: dict, status: str) -> list[dict]:
    rows = [present(item, viewer) for item in storage.list_items("records") if item.get("status") == status and can_read(item, viewer)]
    if status == "pool":
        rows.sort(key=lambda item: (0 if (item.get("analysis") or {}).get("signal_level") == "confirm" else 1, item.get("company") or ""))
    else:
        rows.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return rows


def assign_record(record_id: str, viewer: dict, body: dict[str, Any]) -> dict:
    record = storage.get_item("records", record_id)
    if not record:
        raise KeyError(record_id)
    if record.get("source") == "self_upload":
        raise ValueError("自有名单保持在原账号下，不并入分配")
    owner = str(body.get("owner") or "").strip()
    if not owner:
        raise ValueError("请选择部门账号")
    record["owner"] = owner
    record["source"] = "admin_assign"
    record["assigned_by"] = viewer.get("username") or ""
    record["effective_on"] = str(body.get("effective_on") or "").strip()
    if body.get("phone"):
        record["phone"] = normalize_phone(str(body.get("phone")))
    if body.get("role_name"):
        record["role_name"] = str(body.get("role_name")).strip()
    if body.get("crm_id"):
        record["crm_id"] = str(body.get("crm_id")).strip()
        record["align_status"] = "aligned"
    record["status"] = engine.place_status(
        (record.get("analysis") or {}).get("signal_level") or "none",
        "admin_assign",
        owner,
    )
    return storage.upsert_item("records", record)


def request_grant(record_id: str, viewer: dict) -> dict:
    record = storage.get_item("records", record_id)
    if not record or not can_read(record, viewer):
        raise KeyError(record_id)
    if record.get("source") == "self_upload":
        raise ValueError("号码来自本人上传，无需申请")
    if record.get("status") != "incubation":
        raise ValueError("只有孵化期需要申请外呼")
    grant = storage.upsert_item(
        "grants",
        {
            "id": new_id("SG"),
            "record_id": record_id,
            "owner": viewer.get("username") or "",
            "company": record.get("company") or "",
            "status": "pending",
            "expires_at": "",
            "approved_by": "",
        },
    )
    return grant


def approve_grant(grant_id: str, viewer: dict, approved: bool) -> dict:
    grant = storage.get_item("grants", grant_id)
    if not grant:
        raise KeyError(grant_id)
    record = storage.get_item("records", grant.get("record_id") or "")
    if not record:
        raise KeyError(grant_id)
    if approved:
        expires = engine.grant_expires_at()
        grant["status"] = "approved"
        grant["expires_at"] = expires
        grant["approved_by"] = viewer.get("username") or ""
        record["grant_expires_at"] = expires
        storage.upsert_item("records", record)
    else:
        grant["status"] = "rejected"
        grant["approved_by"] = viewer.get("username") or ""
    return storage.upsert_item("grants", grant)


def import_companies(companies: list[dict], *, destination: str, owner: str, assigned_by: str, acknowledge: bool, warning_count: int) -> list[dict]:
    if destination not in {"base", "pool", "assign"}:
        raise ValueError("请选择导入去向")
    if destination == "assign" and not owner.strip():
        raise ValueError("请选择部门账号")
    if warning_count and not acknowledge:
        raise ValueError("请先勾选已知晓警告")
    if not companies:
        raise ValueError("没有可导入的客户")
    today = datetime.now().astimezone().date().isoformat()
    created: list[dict] = []
    for company in companies:
        code = str(company.get("customer_code") or "").strip()
        name = str(company.get("company") or "").strip()
        if not code or not name:
            raise ValueError("客户编码和名称不完整，不能导入")
        industry_code = str(company.get("industry_code") or "").strip()
        industry = catalog.industry_by_code(industry_code)
        contacts = company.get("contacts") or []
        preferred = next((item for item in contacts if item.get("preferred")), contacts[0] if contacts else {})
        number = _preferred_number(preferred)
        unrecognized = [str(item) for item in company.get("unrecognized") or [] if str(item).strip()]
        record = {
            "id": new_id("ST"),
            "company": name,
            "customer_code": code,
            "phone": normalize_phone(number) or number,
            "contact": preferred.get("name") or "",
            "role_name": preferred.get("role") or "",
            "contacts": contacts,
            "industry": industry["name"] if industry else "",
            "industry_code": industry_code,
            "industry_tags": list(company.get("industry_tags") or []),
            "industry_status": "pending" if not industry else "confirmed",
            "entity_exception": bool(company.get("entity_exception")) or industry_code == "IND00",
            "purchased_scope": "、".join(company.get("scopes") or []),
            "purchased_display": str(company.get("purchased_display") or ""),
            "scopes": list(company.get("scopes") or []),
            "kmi_account": bool(company.get("kmi_account")),
            "consult_unspecified": bool(company.get("consult_unspecified")),
            "unrecognized": unrecognized,
            "service_end": "",
            "unit_price": "",
            "signals_text": str(company.get("signals_text") or ""),
            "notes": str(company.get("notes") or ""),
            "crm_id": code,
            "related": list(company.get("related") or []),
            "source": "admin_import",
            "owner": "",
            "assigned_by": "",
            "effective_on": "",
            "grant_expires_at": "",
            "first_touch_at": "",
            "lock_until": "",
            "lock_label": "",
            "align_status": "aligned",
            "import_profile": "business",
            "pain_match": "",
            "pain_note": "",
        }
        record["analysis"] = engine.analyze(record)
        record["analysis"]["copy_source"] = "pending"
        status = preview.place_company(record["analysis"]["signal_level"], destination, bool(unrecognized))
        record["status"] = status
        if destination == "assign" and status != "base":
            record["source"] = "admin_assign"
            record["owner"] = owner.strip()
            record["assigned_by"] = assigned_by
            record["effective_on"] = today
        created.append(storage.upsert_item("records", record))
    return created


def set_industry(record_id: str, industry_code: str) -> dict:
    record = storage.get_item("records", record_id)
    if not record:
        raise KeyError(record_id)
    industry = catalog.industry_by_code(industry_code)
    if not industry:
        raise ValueError("请选择业务行业")
    record["industry_code"] = industry["code"]
    record["industry"] = industry["name"]
    record["industry_status"] = "confirmed"
    record["entity_exception"] = industry["code"] == "IND00"
    record["import_profile"] = record.get("import_profile") or "business"
    record["analysis"] = engine.analyze(record)
    record["analysis"]["copy_source"] = "pending"
    return storage.upsert_item("records", record)


def deal_map_rows() -> list[dict]:
    data = storage.read_object("deal_map", {})
    rows = data.get("rows") if isinstance(data, dict) else []
    return rows if isinstance(rows, list) else []


def add_deal_rule(keyword: str, scope: str) -> list[dict]:
    keyword = keyword.strip()
    scope = scope.strip()
    if not keyword:
        raise ValueError("请填写成交原文里的关键词")
    if scope == "kmi":
        kind, saved = "kmi", ""
    elif scope == "consult":
        kind, saved = "consult", ""
    elif scope in SHELF:
        kind, saved = "scope", scope
    else:
        raise ValueError("请选择货架内的经营范围")
    data = storage.read_object("deal_map", {})
    rows = list(data.get("rows") or [])
    rows.append({"keyword": keyword, "kind": kind, "scope": saved})
    data["rows"] = rows
    storage.write_object("deal_map", data)
    return rows


def write_call(record_id: str, viewer: dict, body: dict[str, Any]) -> dict:
    record = storage.get_item("records", record_id)
    if not record or not can_read(record, viewer):
        raise KeyError(record_id)
    intention = str(body.get("intention") or "").strip()
    pain = str(body.get("pain_match") or "").strip()
    if intention not in INTENTS:
        raise ValueError("请选择意向")
    if record.get("pain_match"):
        pain = pain or str(record.get("pain_match"))
    elif pain not in PAIN:
        raise ValueError("请选择痛点是否属实")
    if pain and pain not in PAIN:
        raise ValueError("请选择痛点是否属实")
    access = engine.phone_access(record, viewer)
    if record.get("status") == "incubation" and record.get("source") != "self_upload" and not access["visible"]:
        raise ValueError("孵化期外呼尚未获准，或授权已超过 36 小时")
    now = now_iso()
    contact_id = str(body.get("contact_id") or "").strip()
    channel_number = str(body.get("channel_number") or "").strip()
    if intention == "号码失效" or body.get("invalidate"):
        _invalidate_channel(record, contact_id, channel_number)
    if pain:
        record["pain_match"] = pain
        note = str(body.get("pain_note") or "").strip()
        if note:
            record["pain_note"] = note
    if not record.get("first_touch_at"):
        record["first_touch_at"] = now
    if record.get("status") == "reachable" and record.get("source") == "admin_assign" and not record.get("lock_until"):
        record["lock_until"] = engine.lock_until(datetime.now().astimezone())
        record["lock_label"] = "存量挖掘系统"
    storage.upsert_item("records", record)
    settings = storage.settings()
    return storage.upsert_item(
        "call_logs",
        {
            "id": new_id("SC"),
            "record_id": record_id,
            "company": record.get("company") or "",
            "username": viewer.get("username") or "",
            "department": viewer.get("department") or "",
            "intention": intention,
            "pain_match": pain,
            "pain_note": str(body.get("pain_note") or "").strip(),
            "operator_note": str(body.get("operator_note") or "").strip(),
            "extension": str(body.get("extension") or "").strip(),
            "contact_id": contact_id,
            "channel_number": channel_number,
            "first_touch_at": record.get("first_touch_at") or now,
            "lock_label": record.get("lock_label") or "",
            "commission_rate": settings["commission_rate"] if record.get("lock_label") else None,
        },
    )


def align_record(record_id: str, crm_id: str) -> dict:
    record = storage.get_item("records", record_id)
    if not record:
        raise KeyError(record_id)
    record["crm_id"] = (crm_id or "").strip()
    record["align_status"] = "aligned" if record["crm_id"] else record.get("align_status") or "unaligned"
    if record.get("analysis"):
        gaps = [gap for gap in record["analysis"].get("gaps") or [] if gap != "未对齐 CRM"]
        if not record["crm_id"]:
            gaps.append("未对齐 CRM")
        record["analysis"]["gaps"] = gaps
    return storage.upsert_item("records", record)


def pending_subjects(viewer: dict) -> list[dict]:
    rows = [
        present(item, viewer)
        for item in storage.list_items("records")
        if item.get("align_status") == "unaligned" or item.get("industry_status") == "pending"
    ]
    rows.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return rows


def _preferred_number(contact: dict) -> str:
    channels = contact.get("channels") or []
    for channel in channels:
        if channel.get("kind") == "mobile" and not channel.get("invalid") and not channel.get("switchboard"):
            return str(channel.get("number") or "")
    for channel in channels:
        if not channel.get("invalid"):
            return str(channel.get("number") or "")
    return ""


def _public_contacts(record: dict, visible: bool) -> list[dict]:
    raw = record.get("contacts")
    if not isinstance(raw, list) or not raw:
        phone = "" if record.get("phone_invalid") else str(record.get("phone") or "")
        raw = [
            {
                "id": "primary",
                "name": record.get("contact") or "",
                "role": record.get("role_name") or "",
                "preferred": True,
                "weak_role": False,
                "channels": [{"kind": "mobile", "number": phone, "switchboard": False, "invalid": bool(record.get("phone_invalid"))}] if phone or record.get("phone_invalid") else [],
            }
        ]
    public: list[dict] = []
    for item in raw:
        channels = []
        for channel in item.get("channels") or []:
            number = str(channel.get("number") or "")
            channels.append(
                {
                    "kind": channel.get("kind") or "mobile",
                    "number": number if visible else "",
                    "switchboard": bool(channel.get("switchboard")),
                    "invalid": bool(channel.get("invalid")),
                }
            )
        public.append(
            {
                "id": item.get("id") or "",
                "name": item.get("name") or "",
                "role": item.get("role") or "",
                "preferred": bool(item.get("preferred")),
                "weak_role": bool(item.get("weak_role")),
                "channels": channels,
            }
        )
    if public and not any(item["preferred"] for item in public):
        public[0]["preferred"] = True
    return public


def _invalidate_channel(record: dict, contact_id: str, number: str) -> None:
    contacts = record.get("contacts")
    if not isinstance(contacts, list) or not contacts:
        record["phone_invalid"] = True
        return
    for contact in contacts:
        if contact_id and contact.get("id") != contact_id:
            continue
        for channel in contact.get("channels") or []:
            if number and channel.get("number") != number:
                continue
            channel["invalid"] = True
    record["contacts"] = contacts


def playbook_rows() -> list[dict]:
    disabled = storage.disabled_playbooks()
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "enabled": item["id"] not in disabled,
        }
        for item in PLAYBOOKS
    ]
