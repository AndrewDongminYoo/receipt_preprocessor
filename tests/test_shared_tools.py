from unittest.mock import MagicMock, patch

import pytest

# --- reject_tool ---


def test_reject_with_code_sets_state_and_escalates():
    from receipt_preprocessor.tools.reject_tool import reject_with_code

    ctx = MagicMock()
    ctx.state = {}
    ctx.actions = MagicMock()

    result = reject_with_code("NON_RECEIPT", "영수증 이미지를 다시 촬영해 주세요.", ctx)

    assert result == {
        "rejected": True,
        "code": "NON_RECEIPT",
        "message": "영수증 이미지를 다시 촬영해 주세요.",
    }
    assert ctx.state["rejection_code"] == "NON_RECEIPT"
    assert ctx.state["rejection_message"] == "영수증 이미지를 다시 촬영해 주세요."
    assert ctx.actions.escalate is True


# --- gcs_utils ---


def test_download_from_gcs():
    from receipt_preprocessor.tools.gcs_utils import download_from_gcs

    with patch("receipt_preprocessor.tools.gcs_utils.storage.Client") as mock_cls:
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"image_data"
        mock_cls.return_value.bucket.return_value.blob.return_value = mock_blob

        result = download_from_gcs("gs://my-bucket/path/to/img.jpg")

    assert result == b"image_data"
    mock_cls.return_value.bucket.assert_called_with("my-bucket")
    mock_cls.return_value.bucket.return_value.blob.assert_called_with("path/to/img.jpg")


def test_upload_to_gcs():
    from receipt_preprocessor.tools.gcs_utils import upload_to_gcs

    with patch("receipt_preprocessor.tools.gcs_utils.storage.Client") as mock_cls:
        mock_blob = MagicMock()
        mock_cls.return_value.bucket.return_value.blob.return_value = mock_blob

        result = upload_to_gcs(b"image_data", "my-bucket", "20260430/abc/corrected.jpg")

    assert result == "gs://my-bucket/20260430/abc/corrected.jpg"
    mock_blob.upload_from_string.assert_called_once_with(
        b"image_data", content_type="image/jpeg"
    )


def test_download_invalid_uri_raises():
    from receipt_preprocessor.tools.gcs_utils import download_from_gcs

    with pytest.raises(ValueError, match="gs://"):
        download_from_gcs("my-bucket/path/img.jpg")


def test_download_gcs_api_error_raises_runtime():
    from google.api_core.exceptions import GoogleAPICallError

    from receipt_preprocessor.tools.gcs_utils import download_from_gcs

    with patch("receipt_preprocessor.tools.gcs_utils.storage.Client") as mock_cls:
        mock_cls.return_value.bucket.return_value.blob.return_value.download_as_bytes.side_effect = GoogleAPICallError(
            "404 Not Found"
        )
        with pytest.raises(RuntimeError, match="GCS download failed"):
            download_from_gcs("gs://my-bucket/missing.jpg")
