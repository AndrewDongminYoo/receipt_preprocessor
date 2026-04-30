import os

from dotenv import load_dotenv

load_dotenv()

GCS_BUCKET_NAME: str = os.environ.get("GCS_BUCKET_NAME", "")
QUALITY_THRESHOLD: int = int(os.getenv("QUALITY_THRESHOLD", "6"))
GENAI_MODEL: str = os.getenv("GENAI_MODEL", "gemini-2.5-flash")
GCS_IMAGE_TTL_DAYS: int = int(os.getenv("GCS_IMAGE_TTL_DAYS", "7"))
