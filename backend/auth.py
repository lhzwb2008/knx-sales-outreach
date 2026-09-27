"""登录会话与操作审计。不改动业务集合，账户和日志单独落在 data/。"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import unquote

from fastapi import Request
from starlette.responses import JSONResponse, Response

from . import storage
from .config import DATA_DIR

COOKIE = "knx_session"
SESSION_DAYS = 14
USERS_FILE = "users"
AUDIT_FILE = "audit"
AUDIT_LIMIT = 8000
PUBLIC_API = {"/api/health", "/api/auth/login"}

# 仅在 users.json 不存在时写入。改这里不会覆盖已经登录过的线上账户。
SEED_USERS = (
    {"username": "admin", "password": "Admin@knx2026", "display_name": "管理员", "department": "管理", "role": "admin"},
    {"username": "a", "password": "BuA@knx2026", "display_name": "事业部A", "department": "事业部A", "role": "user"},
    {"username": "b", "password": "BuB@knx2026", "display_name": "事业部B", "department": "事业部B", "role": "user"},
    {"username": "c1", "password": "BuC1@knx2026", "display_name": "事业部C1", "department": "事业部C1", "role": "user"},
    {"username": "c2", "password": "BuC2@knx2026", "display_name": "事业部C2", "department": "事业部C2", "role": "user"},
    {"username": "c3", "password": "BuC3@knx2026", "display_name": "事业部C3", "department": "事业部C3", "role": "user"},
)

# 仅补缺，不覆盖已有账号密码。存量账号和陌拜账号互不进入对方工作台。
STOCK_SEED_USERS = (
    {
        "username": "stock-admin",
        "password": "StockAdmin@knx2026",
        "display_name": "存量管理员",
        "department": "存量管理",
        "role": "admin",
        "module": "stock",
        "stock_role": "admin",
    },
    {
        "username": "stock-a",
        "password": "StockA@knx2026",
        "display_name": "存量部门A",
        "department": "存量部门A",
        "role": "user",
        "module": "stock",
        "stock_role": "frontline",
    },
    {
        "username": "stock-ro",
        "password": "StockRo@knx2026",
        "display_name": "存量只读",
        "department": "存量只读",
        "role": "user",
        "module": "stock",
        "stock_role": "readonly",
    },
)

_ACTION_RULES: tuple[tuple[str, str, str], ...] = (
    ("POST", "/api/import/excel", "导入名单"),
    ("POST", "/api/import/overwrite", "覆盖导入"),
    ("POST", "/api/leads", "新增客户"),
    ("PUT", "/api/leads/", "修改客户"),
    ("DELETE", "/api/leads/", "删除客户"),
    ("POST", "/api/ai/analyze-need", "智能分析"),
    ("POST", "/api/ai/enrich-profile", "补充画像"),
    ("POST", "/api/ai/generate-script", "生成话术"),
    ("POST", "/api/ai/experience-to-rule", "经验转规则"),
    ("POST", "/api/leads/", "分析客户"),
    ("POST", "/api/profiles", "保存画像"),
    ("POST", "/api/rules", "保存规则"),
    ("DELETE", "/api/rules/", "删除规则"),
    ("POST", "/api/scripts", "保存话术"),
    ("DELETE", "/api/scripts/", "删除话术"),
    ("POST", "/api/competitors", "保存市场方案"),
    ("DELETE", "/api/competitors/", "删除市场方案"),
    ("PUT", "/api/scoring", "更新评分"),
    ("POST", "/api/outreach", "保存触达记录"),
    ("POST", "/api/wechat-todos", "新建微信待办"),
    ("POST", "/api/wechat-todos/", "完成微信待办"),
    ("POST", "/api/followups/", "完成跟进"),
    ("GET", "/api/export/data.zip", "导出数据"),
    ("POST", "/api/seed/reset", "重置演示数据"),
    ("POST", "/api/help/generate-image", "生成帮助图"),
    ("POST", "/api/auth/logout", "退出登录"),
)


def _secret() -> bytes:
    path = DATA_DIR / ".auth_secret"
    if path.exists():
        raw = path.read_text(encoding="utf-8").strip()
        if raw:
            return raw.encode()
    storage.ensure_data_dir()
    raw = secrets.token_hex(32)
    path.write_text(raw, encoding="utf-8")
    return raw.encode()


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_hex, digest_hex = stored.split("$", 2)
        if algo != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def public_user(user: dict) -> dict:
    module = user.get("module") or "outreach"
    data = {
        "username": user.get("username") or "",
        "display_name": user.get("display_name") or "",
        "department": user.get("department") or "",
        "role": user.get("role") or "user",
        "module": module,
    }
    if module == "stock":
        data["stock_role"] = user.get("stock_role") or "frontline"
    return data


def _materialize_user(item: dict, now: str) -> dict:
    row = {
        "username": item["username"],
        "password_hash": hash_password(item["password"]),
        "display_name": item["display_name"],
        "department": item["department"],
        "role": item["role"],
        "module": item.get("module") or "outreach",
        "created_at": now,
    }
    if item.get("stock_role"):
        row["stock_role"] = item["stock_role"]
    return row


def ensure_users() -> None:
    """只在还没有账户文件时初始化。已有 users.json 一律不改，避免覆盖线上正在使用的账号。"""
    path = DATA_DIR / f"{USERS_FILE}.json"
    if path.exists():
        return
    now = storage.now_iso()
    users = [_materialize_user(item, now) for item in (*SEED_USERS, *STOCK_SEED_USERS)]
    storage.write_collection(USERS_FILE, users)


def list_users() -> list[dict]:
    data = storage.read_collection(USERS_FILE, [])
    return data if isinstance(data, list) else []


def find_user(username: str) -> dict | None:
    key = (username or "").strip()
    for user in list_users():
        if user.get("username") == key:
            return user
    return None


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def issue_token(username: str) -> str:
    exp = int((datetime.now().astimezone() + timedelta(days=SESSION_DAYS)).timestamp())
    payload = f"{username}|{exp}"
    return f"{payload}|{_sign(payload)}"


def user_from_token(token: str) -> dict | None:
    try:
        username, exp_s, sig = token.split("|", 2)
        payload = f"{username}|{exp_s}"
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        if int(exp_s) < int(datetime.now().timestamp()):
            return None
    except (ValueError, TypeError):
        return None
    user = find_user(username)
    return public_user(user) if user else None


def user_from_request(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE, "")
    return user_from_token(token) if token else None


def set_session_cookie(response: Response, token: str, request: Request) -> None:
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"
    response.set_cookie(
        COOKIE,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


def _json_body(raw: bytes, content_type: str) -> dict:
    if "application/json" not in (content_type or "") or not raw or len(raw) > 65536:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _path_match(path: str, prefix: str) -> bool:
    if path == prefix:
        return True
    return prefix.endswith("/") and path.startswith(prefix)


def describe_action(method: str, path: str) -> str | None:
    method = method.upper()
    if method == "POST" and path.rstrip("/").endswith("/contacts"):
        return "新增联系人"
    for rule_method, prefix, label in _ACTION_RULES:
        if method == rule_method and _path_match(path, prefix):
            return label
    if method in {"POST", "PUT", "PATCH", "DELETE"} and path.startswith("/api/"):
        return f"{method} {path}"
    return None


def _target_from(path: str, body: dict) -> str:
    for key in ("company", "name", "lead_id", "existing_id", "id"):
        value = body.get(key)
        if value:
            return str(value)[:80]
    parts = [unquote(p) for p in path.split("/") if p]
    if len(parts) >= 3 and parts[0] == "api":
        return parts[-1][:80]
    return ""


def append_audit(user: dict | None, method: str, path: str, status: int, target: str = "", action: str | None = None) -> None:
    label = action or describe_action(method, path)
    if not label:
        return
    items = storage.read_collection(AUDIT_FILE, [])
    if not isinstance(items, list):
        items = []
    who = user or {}
    items.append(
        {
            "id": storage.new_id("AU"),
            "at": storage.now_iso(),
            "username": who.get("username") or "",
            "display_name": who.get("display_name") or "",
            "department": who.get("department") or "",
            "role": who.get("role") or "",
            "method": method.upper(),
            "path": path,
            "action": label,
            "target": target,
            "status": int(status),
        }
    )
    if len(items) > AUDIT_LIMIT:
        items = items[-AUDIT_LIMIT:]
    storage.write_collection(AUDIT_FILE, items)


def audit_stats(range_key: str) -> dict:
    now = datetime.now().astimezone()
    if range_key == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        range_key = "7d"
        start = now - timedelta(days=7)
    logs = storage.read_collection(AUDIT_FILE, [])
    if not isinstance(logs, list):
        logs = []
    buckets: dict[str, dict[str, Any]] = {}
    for user in list_users():
        if user.get("role") == "admin":
            continue
        buckets[user["username"]] = {
            **public_user(user),
            "login_count": 0,
            "last_active": "",
            "operation_count": 0,
            "by_action": {},
        }
    for row in logs:
        username = row.get("username") or ""
        bucket = buckets.get(username)
        if not bucket:
            continue
        at = str(row.get("at") or "")
        if at > (bucket["last_active"] or ""):
            bucket["last_active"] = at
        try:
            when = datetime.fromisoformat(at)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.astimezone()
        if when < start:
            continue
        action = row.get("action") or ""
        status = int(row.get("status") or 0)
        if action == "登录" and status < 400:
            bucket["login_count"] += 1
            continue
        if action in {"登录", "退出登录"}:
            continue
        if status >= 400:
            continue
        bucket["operation_count"] += 1
        counts = bucket["by_action"]
        counts[action] = counts.get(action, 0) + 1
    users = list(buckets.values())
    users.sort(key=lambda item: (-item["operation_count"], item["department"]))
    return {"range": range_key, "users": users}


def is_public_api(path: str) -> bool:
    return path in PUBLIC_API or not path.startswith("/api/")


def module_block(user: dict, path: str, method: str) -> str | None:
    """登录只用于审计。已登录账号可以同时使用增量和存量。"""
    return None


async def guard(request: Request, call_next):
    path = request.url.path
    if is_public_api(path):
        return await call_next(request)
    user = user_from_request(request)
    if not user:
        return JSONResponse({"detail": "请先登录"}, status_code=401)
    request.state.user = user
    raw = await request.body()
    body = _json_body(raw, request.headers.get("content-type", ""))
    response = await call_next(request)
    if path != "/api/auth/logout":
        append_audit(user, request.method, path, response.status_code, _target_from(path, body))
    return response
