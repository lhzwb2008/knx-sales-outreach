from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import DATA_DIR

_lock = threading.RLock()

COLLECTIONS = (
    "leads",
    "profiles",
    "rules",
    "competitors",
    "scripts",
    "products",
    "outreach",
    "followups",
    "wechat_todos",
    "scoring",
    "settings",
)


def _path(name: str) -> Path:
    return DATA_DIR / f"{name}.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_collection(name: str, default: Any = None) -> Any:
    ensure_data_dir()
    path = _path(name)
    with _lock:
        if not path.exists():
            return [] if default is None else default
        return json.loads(path.read_text(encoding="utf-8"))


def write_collection(name: str, data: Any) -> None:
    ensure_data_dir()
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


def upsert_item(name: str, item: dict, *, id_field: str = "id") -> dict:
    items = list_items(name)
    item_id = item.get(id_field) or str(uuid4())
    item[id_field] = item_id
    item["updated_at"] = now_iso()
    if "created_at" not in item:
        item["created_at"] = item["updated_at"]
    replaced = False
    for i, existing in enumerate(items):
        if existing.get(id_field) == item_id:
            merged = {**existing, **item}
            items[i] = merged
            item = merged
            replaced = True
            break
    if not replaced:
        items.append(item)
    write_collection(name, items)
    return item


def delete_item(name: str, item_id: str) -> bool:
    items = list_items(name)
    new_items = [x for x in items if x.get("id") != item_id]
    if len(new_items) == len(items):
        return False
    write_collection(name, new_items)
    return True


def read_object(name: str, default: dict | None = None) -> dict:
    data = read_collection(name, default or {})
    return data if isinstance(data, dict) else (default or {})


def write_object(name: str, data: dict) -> dict:
    data = {**data, "updated_at": now_iso()}
    write_collection(name, data)
    return data


def new_id(prefix: str = "") -> str:
    raw = uuid4().hex[:10].upper()
    return f"{prefix}{raw}" if prefix else raw
