"""存量 JSON 落在 data/stock/，不写入陌拜集合。"""
from __future__ import annotations

import json
import threading
from typing import Any

from ..config import DATA_DIR
from ..storage import new_id, now_iso

STOCK_DIR = DATA_DIR / "stock"
_lock = threading.RLock()

COLLECTIONS = (
    "records",
    "grants",
    "call_logs",
    "playbook_state",
    "settings",
    "audit",
)


def ensure_dir() -> None:
    STOCK_DIR.mkdir(parents=True, exist_ok=True)


def _path(name: str):
    return STOCK_DIR / f"{name}.json"


def read_collection(name: str, default: Any = None) -> Any:
    ensure_dir()
    path = _path(name)
    with _lock:
        if not path.exists():
            return [] if default is None else default
        return json.loads(path.read_text(encoding="utf-8"))


def write_collection(name: str, data: Any) -> None:
    ensure_dir()
    path = _path(name)
    tmp = path.with_suffix(".tmp")
    with _lock:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def list_items(name: str) -> list[dict]:
    data = read_collection(name, [])
    return data if isinstance(data, list) else []


def get_item(name: str, item_id: str) -> dict | None:
    for item in list_items(name):
        if item.get("id") == item_id:
            return item
    return None


def upsert_item(name: str, item: dict) -> dict:
    items = list_items(name)
    item_id = item.get("id") or new_id("ST")
    item["id"] = item_id
    item["updated_at"] = now_iso()
    if "created_at" not in item:
        item["created_at"] = item["updated_at"]
    replaced = False
    for index, existing in enumerate(items):
        if existing.get("id") == item_id:
            merged = {**existing, **item}
            items[index] = merged
            item = merged
            replaced = True
            break
    if not replaced:
        items.append(item)
    write_collection(name, items)
    return item


def read_object(name: str, default: dict | None = None) -> dict:
    data = read_collection(name, default or {})
    return data if isinstance(data, dict) else (default or {})


def write_object(name: str, data: dict) -> dict:
    payload = {**data, "updated_at": now_iso()}
    write_collection(name, payload)
    return payload


def disabled_playbooks() -> set[str]:
    state = read_object("playbook_state", {})
    return {key for key, value in state.items() if key != "updated_at" and isinstance(value, dict) and value.get("enabled") is False}


def set_playbook_enabled(playbook_id: str, enabled: bool) -> dict:
    state = read_object("playbook_state", {})
    state.pop("updated_at", None)
    current = state.get(playbook_id) if isinstance(state.get(playbook_id), dict) else {}
    state[playbook_id] = {**current, "enabled": enabled}
    return write_object("playbook_state", state)


def settings() -> dict:
    data = read_object("settings", {})
    return {
        "commission_rate": data.get("commission_rate", 8),
        "grant_hours": 36,
        "lock_days": 60,
    }


def save_settings(commission_rate: float) -> dict:
    rate = max(5, min(10, float(commission_rate)))
    current = read_object("settings", {})
    current["commission_rate"] = rate
    write_object("settings", current)
    return settings()


def append_audit(user: dict | None, method: str, path: str, status: int, target: str = "", action: str = "") -> None:
    if not action:
        return
    items = list_items("audit")
    who = user or {}
    items.append(
        {
            "id": new_id("SA"),
            "at": now_iso(),
            "username": who.get("username") or "",
            "display_name": who.get("display_name") or "",
            "department": who.get("department") or "",
            "role": who.get("stock_role") or who.get("role") or "",
            "method": method.upper(),
            "path": path,
            "action": action,
            "target": target[:80],
            "status": int(status),
        }
    )
    if len(items) > 8000:
        items = items[-8000:]
    write_collection("audit", items)
