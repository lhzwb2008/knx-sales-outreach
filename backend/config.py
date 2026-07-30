from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
FRONTEND_DIR = ROOT / "frontend"
ASSETS_DIR = FRONTEND_DIR / "assets"
HELP_IMAGE_PATH = ASSETS_DIR / "help-workflow.png"

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
).rstrip("/")
DASHSCOPE_MODEL = os.getenv("DASHSCOPE_MODEL", "deepseek-v4-pro").strip()
DASHSCOPE_ENABLE_THINKING = (
    os.getenv("DASHSCOPE_ENABLE_THINKING", "false").strip().lower() in ("1", "true", "yes")
)
DASHSCOPE_TIMEOUT = float(os.getenv("DASHSCOPE_TIMEOUT", "120"))
DASHSCOPE_MAX_RETRIES = int(os.getenv("DASHSCOPE_MAX_RETRIES", "3"))

AIHUBMIX_API_KEY = os.getenv("AIHUBMIX_API_KEY", "").strip()
AIHUBMIX_BASE_URL = os.getenv("AIHUBMIX_BASE_URL", "https://api.inferera.com/v1").rstrip("/")
AIHUBMIX_IMAGE_MODEL = os.getenv("AIHUBMIX_IMAGE_MODEL", "gpt-image-2").strip()
AIHUBMIX_IMAGE_SIZE = os.getenv("AIHUBMIX_IMAGE_SIZE", "1536x1024").strip()
AIHUBMIX_IMAGE_QUALITY = os.getenv("AIHUBMIX_IMAGE_QUALITY", "high").strip()
AIHUBMIX_IMAGE_TIMEOUT = float(os.getenv("AIHUBMIX_IMAGE_TIMEOUT", "300"))

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8765"))
