import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(f"Required environment variable '{key}' is not set.")
    return value


def _int_env(key: str, default: int) -> int:
    raw = os.getenv(key, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise EnvironmentError(
            f"Environment variable '{key}' must be an integer, got: {raw!r}"
        ) from exc


GCS_BUCKET_NAME: str = _require("GCS_BUCKET_NAME")
QUALITY_THRESHOLD: int = _int_env("QUALITY_THRESHOLD", 6)
GENAI_MODEL: str = os.getenv("GENAI_MODEL", "gemini-2.5-flash")
GCS_IMAGE_TTL_DAYS: int = _int_env("GCS_IMAGE_TTL_DAYS", 7)
