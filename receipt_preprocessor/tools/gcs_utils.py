from google.api_core.exceptions import GoogleAPICallError
from google.cloud import storage


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
