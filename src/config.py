"""Configuration module using environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Application settings
APP_ENV: str = os.getenv("APP_ENV", "development")
DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

# Database settings
DATABASE_PATH: str = os.getenv(
    "DATABASE_PATH",
    str(BASE_DIR / "data" / "returns_records.db")
)

# Storage settings
IMAGE_STORAGE_PATH: str = os.getenv(
    "IMAGE_STORAGE_PATH",
    str(BASE_DIR / "data" / "images")
)

# Multi-tenant settings
ALLOWED_ORGS: list[str] = [
    org.strip() for org in os.getenv("ALLOWED_ORGS", "org_demo_alpha,org_demo_bravo").split(",") if org.strip()
]

# API Security
API_KEY: str = os.getenv("API_KEY", "")

# Gemini Model settings (for Phase 2+)
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
