import mimetypes

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import storage
from google.genai import types as genai_types


def make_image_part(image_uri: str) -> genai_types.Part:
    """Returns a Gemini Part for a GCS URI, HTTPS URL, or local file path."""
    mime_type = mimetypes.guess_type(image_uri)[0] or "image/jpeg"
    if image_uri.startswith(("gs://", "http://", "https://")):
        return genai_types.Part.from_uri(file_uri=image_uri, mime_type=mime_type)
    with open(image_uri, "rb") as f:
        data = f.read()
    return genai_types.Part.from_bytes(data=data, mime_type=mime_type)


def download_from_gcs(gcs_uri: str) -> bytes:
    """Downloads bytes from a GCS URI (gs://bucket/path)."""
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Invalid GCS URI — expected gs:// prefix, got: {gcs_uri!r}")
    bucket_name, blob_path = gcs_uri.removeprefix("gs://").split("/", 1)
    try:
        return storage.Client().bucket(bucket_name).blob(blob_path).download_as_bytes()
    except GoogleAPICallError as exc:
        raise RuntimeError(f"GCS download failed for {gcs_uri!r}: {exc}") from exc


def upload_to_gcs(image_bytes: bytes, bucket_name: str, blob_path: str) -> str:
    """Uploads bytes to GCS and returns the gs:// URI. Always stores as JPEG."""
    try:
        blob = storage.Client().bucket(bucket_name).blob(blob_path)
        blob.upload_from_string(image_bytes, content_type="image/jpeg")
        return f"gs://{bucket_name}/{blob_path}"
    except GoogleAPICallError as exc:
        raise RuntimeError(
            f"GCS upload failed for gs://{bucket_name}/{blob_path!r}: {exc}"
        ) from exc
