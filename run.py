#!/usr/bin/env python3
"""启动陌拜智推本地服务。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import uvicorn

from backend.config import HOST, PORT

if __name__ == "__main__":
    # 默认关闭 reload，避免后台启动/频繁改文件时进程被 WatchFiles 拉挂
    # 开发热重载：RELOAD=1 python run.py
    reload = os.getenv("RELOAD", "0").strip().lower() in ("1", "true", "yes")
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=reload)
