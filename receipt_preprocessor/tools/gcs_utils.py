from google.cloud import storage


def download_from_gcs(gcs_uri: str) -> bytes:
    """Downloads bytes from a GCS URI (gs://bucket/path)."""
    path = gcs_uri.replace("gs://", "")
    bucket_name, blob_path = path.split("/", 1)
    client = storage.Client()
    return client.bucket(bucket_name).blob(blob_path).download_as_bytes()


def upload_to_gcs(image_bytes: bytes, bucket_name: str, blob_path: str) -> str:
    """Uploads bytes to GCS and returns the gs:// URI."""
    client = storage.Client()
    blob = client.bucket(bucket_name).blob(blob_path)
    blob.upload_from_string(image_bytes, content_type="image/jpeg")
    return f"gs://{bucket_name}/{blob_path}"
