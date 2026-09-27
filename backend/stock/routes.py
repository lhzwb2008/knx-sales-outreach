from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from . import narrate, service, storage
from .engine import soften_copy
from .importer import parse_stock_rows
from .. import llm

router = APIRouter(prefix="/api/stock")


class AssignIn(BaseModel):
    owner: str
    phone: str = ""
    role_name: str = ""
    crm_id: str = ""
    effective_on: str = ""


class AlignIn(BaseModel):
    crm_id: str = ""


class CallIn(BaseModel):
    record_id: str
    intention: str
    pain_match: str
    pain_note: str = ""
    operator_note: str = ""
    extension: str = ""


class ToggleIn(BaseModel):
    enabled: bool


class SettingsIn(BaseModel):
    commission_rate: float = Field(ge=5, le=10)


def _user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "请先登录")
    return user


def _require(request: Request, *_roles: str) -> dict:
    return _user(request)


def _record_or_404(record_id: str, viewer: dict) -> dict:
    record = storage.get_item("records", record_id)
    if not record or not service.can_read(record, viewer):
        raise HTTPException(404, "客户不存在")
    return record


def _call(action):
    try:
        return action()
    except KeyError:
        raise HTTPException(404, "记录不存在")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/reachable")
def reachable(request: Request) -> list[dict]:
    return service.list_for(_require(request, "frontline", "admin", "readonly"), "reachable")


@router.get("/incubation")
def incubation(request: Request) -> list[dict]:
    return service.list_for(_require(request, "frontline", "admin", "readonly"), "incubation")


@router.get("/trials")
def trials(request: Request) -> list[dict]:
    return service.list_for(_require(request, "frontline", "admin", "readonly"), "trial")


@router.get("/admin/base")
def admin_base(request: Request) -> list[dict]:
    return service.list_for(_require(request, "admin", "readonly"), "base")


@router.get("/admin/pool")
def admin_pool(request: Request) -> list[dict]:
    return service.list_for(_require(request, "admin", "readonly"), "pool")


@router.get("/admin/align")
def admin_align(request: Request) -> list[dict]:
    viewer = _require(request, "admin", "readonly")
    rows = [
        service.present(item, viewer)
        for item in storage.list_items("records")
        if item.get("align_status") == "unaligned"
    ]
    rows.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return rows


@router.get("/admin/grants")
def admin_grants(request: Request) -> list[dict]:
    _require(request, "admin", "readonly")
    rows = [item for item in storage.list_items("grants") if item.get("status") == "pending"]
    rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return rows


@router.get("/admin/playbooks")
def admin_playbooks(request: Request) -> list[dict]:
    _require(request, "admin", "readonly")
    return service.playbook_rows()


@router.post("/admin/playbooks/{playbook_id}")
def admin_playbook_toggle(playbook_id: str, body: ToggleIn, request: Request) -> dict:
    _require(request, "admin")
    if playbook_id not in {item["id"] for item in service.PLAYBOOKS}:
        raise HTTPException(404, "行业条目不存在")
    storage.set_playbook_enabled(playbook_id, body.enabled)
    return {"id": playbook_id, "enabled": body.enabled}


@router.get("/admin/accounts")
def admin_accounts(request: Request) -> list[dict]:
    _require(request, "admin")
    from .. import auth

    return [auth.public_user(user) for user in auth.list_users()]


@router.get("/admin/settings")
def admin_settings(request: Request) -> dict:
    _require(request, "admin", "readonly")
    return storage.settings()


@router.put("/admin/settings")
def admin_save_settings(body: SettingsIn, request: Request) -> dict:
    _require(request, "admin")
    return storage.save_settings(body.commission_rate)


@router.post("/admin/imports")
async def admin_import(request: Request, file: UploadFile = File(...)) -> dict:
    user = _require(request, "admin")
    rows = _rows(await file.read())
    created = [service.present(_with_model(service.create_record(row, source="admin_import", owner="")), user) for row in rows]
    return {"count": len(created), "records": created}


@router.post("/admin/assign/{record_id}")
def admin_assign(record_id: str, body: AssignIn, request: Request) -> dict:
    user = _require(request, "admin")
    saved = _call(lambda: service.assign_record(record_id, user, body.model_dump()))
    return service.present(saved, user)


@router.post("/admin/align/{record_id}")
def admin_align_one(record_id: str, body: AlignIn, request: Request) -> dict:
    user = _require(request, "admin")
    saved = _call(lambda: service.align_record(record_id, body.crm_id))
    return service.present(saved, user)


@router.post("/admin/grants/{grant_id}")
def admin_grant(grant_id: str, request: Request, approved: bool = True) -> dict:
    user = _require(request, "admin")
    return _call(lambda: service.approve_grant(grant_id, user, approved))


@router.post("/uploads")
async def uploads(request: Request, file: UploadFile = File(...)) -> dict:
    user = _require(request, "frontline")
    rows = _rows(await file.read())
    created = [
        service.present(_with_model(service.create_record(row, source="self_upload", owner=user["username"])), user)
        for row in rows
    ]
    return {"count": len(created), "records": created}


@router.get("/cards/{record_id}")
def card(record_id: str, request: Request) -> dict:
    user = _require(request, "frontline", "admin", "readonly")
    record = _with_model(_record_or_404(record_id, user))
    return _card_payload(service.present(record, user))


@router.post("/cards/{record_id}/narrate")
def card_narrate(record_id: str, request: Request) -> dict:
    user = _require(request, "frontline", "admin")
    record = _record_or_404(record_id, user)
    analysis = dict(record.get("analysis") or {})
    analysis["copy_source"] = "pending"
    try:
        record["analysis"] = narrate.narrate(analysis)
    except llm.LLMError as exc:
        raise HTTPException(502, "分析生成失败，请稍后重试") from exc
    saved = storage.upsert_item("records", record)
    return _card_payload(service.present(saved, user))


@router.post("/calls")
def calls(body: CallIn, request: Request) -> dict:
    user = _require(request, "frontline", "admin")
    return _call(lambda: service.write_call(body.record_id, user, body.model_dump()))


@router.post("/incubation/{record_id}/call-requests")
def call_request(record_id: str, request: Request) -> dict:
    user = _require(request, "frontline")
    return _call(lambda: service.request_grant(record_id, user))


def _with_model(record: dict) -> dict:
    try:
        return service.ensure_model_copy(record)
    except llm.LLMError as exc:
        raise HTTPException(502, f"分析生成失败：{exc}") from exc


def _rows(content: bytes) -> list[dict[str, str]]:
    try:
        return parse_stock_rows(content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _card_payload(shown: dict) -> dict:
    analysis = shown["analysis"]
    lines, pitch, supplement = soften_copy(
        analysis.get("lines") or [],
        analysis.get("pitch") or "",
        analysis.get("supplement") or "",
    )
    return {
        "record": shown,
        "lines": lines,
        "pitch": pitch,
        "supplement": supplement,
        "products": analysis.get("products") or [],
        "incubation_notice": shown.get("status") == "incubation",
    }
