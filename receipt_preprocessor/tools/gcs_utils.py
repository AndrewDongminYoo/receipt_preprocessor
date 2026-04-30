import mimetypes
from typing import Optional

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import storage
from google.genai import types as genai_types

_storage_client: Optional[storage.Client] = None


def _get_storage_client() -> storage.Client:
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client


def make_image_part(image_uri: str) -> genai_types.Part:
    """Returns a Gemini Part for a GCS URI, HTTPS URL, or local file path."""
    mime_type = mimetypes.guess_type(image_uri)[0] or "image/jpeg"
    if image_uri.startswith(("gs://", "http://", "https://")):
        return genai_types.Part.from_uri(file_uri=image_uri, mime_type=mime_type)
    with open(image_uri, "rb") as f:
        data = f.read()
    return genai_types.Part.from_bytes(data=data, mime_type=mime_type)


def read_image_bytes(image_uri: str) -> bytes:
    """Reads image bytes from a GCS URI (gs://) or a local file path."""
    if image_uri.startswith("gs://"):
        return download_from_gcs(image_uri)
    with open(image_uri, "rb") as f:
        return f.read()


def download_from_gcs(gcs_uri: str) -> bytes:
    """Downloads bytes from a GCS URI (gs://bucket/path)."""
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI — expected gs:// prefix, got: {gcs_uri!r}")
    bucket_name, blob_path = gcs_uri.removeprefix("gs://").split("/", 1)
    try:
        return (
            _get_storage_client()
            .bucket(bucket_name)
            .blob(blob_path)
            .download_as_bytes()
        )
    except GoogleAPICallError as exc:
        exc.add_note(f"GCS URI: {gcs_uri!r}")
        raise


def upload_to_gcs(image_bytes: bytes, bucket_name: str, blob_path: str) -> str:
    """Uploads bytes to GCS and returns the gs:// URI. Always stores as JPEG."""
    try:
        blob = _get_storage_client().bucket(bucket_name).blob(blob_path)
        blob.upload_from_string(image_bytes, content_type="image/jpeg")
        return f"gs://{bucket_name}/{blob_path}"
    except GoogleAPICallError as exc:
        exc.add_note(f"GCS URI: gs://{bucket_name}/{blob_path}")
        raise
