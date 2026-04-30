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

    mock_client = MagicMock()
    mock_blob = MagicMock()
    mock_blob.download_as_bytes.return_value = b"image_data"
    mock_client.bucket.return_value.blob.return_value = mock_blob

    with patch(
        "receipt_preprocessor.tools.gcs_utils._get_storage_client",
        return_value=mock_client,
    ):
        result = download_from_gcs("gs://my-bucket/path/to/img.jpg")

    assert result == b"image_data"
    mock_client.bucket.assert_called_with("my-bucket")
    mock_client.bucket.return_value.blob.assert_called_with("path/to/img.jpg")


def test_upload_to_gcs():
    from receipt_preprocessor.tools.gcs_utils import upload_to_gcs

    mock_client = MagicMock()
    mock_blob = MagicMock()
    mock_client.bucket.return_value.blob.return_value = mock_blob

    with patch(
        "receipt_preprocessor.tools.gcs_utils._get_storage_client",
        return_value=mock_client,
    ):
        result = upload_to_gcs(b"image_data", "my-bucket", "20260430/abc/corrected.jpg")

    assert result == "gs://my-bucket/20260430/abc/corrected.jpg"
    mock_blob.upload_from_string.assert_called_once_with(
        b"image_data", content_type="image/jpeg"
    )


def test_download_invalid_uri_raises():
    from receipt_preprocessor.tools.gcs_utils import download_from_gcs

    with pytest.raises(ValueError, match="gs://"):
        download_from_gcs("my-bucket/path/img.jpg")


def test_download_gcs_api_error_raises():
    from google.api_core.exceptions import GoogleAPICallError

    from receipt_preprocessor.tools.gcs_utils import download_from_gcs

    mock_client = MagicMock()
    mock_client.bucket.return_value.blob.return_value.download_as_bytes.side_effect = (
        GoogleAPICallError("404 Not Found")
    )
    with patch(
        "receipt_preprocessor.tools.gcs_utils._get_storage_client",
        return_value=mock_client,
    ):
        with pytest.raises(GoogleAPICallError):
            download_from_gcs("gs://my-bucket/missing.jpg")


def test_make_image_part_uses_from_uri_for_gcs():
    from unittest.mock import patch as _patch

    from receipt_preprocessor.tools.gcs_utils import make_image_part

    with _patch("receipt_preprocessor.tools.gcs_utils.genai_types.Part") as mock_part:
        make_image_part("gs://bucket/img.jpg")
        mock_part.from_uri.assert_called_once_with(
            file_uri="gs://bucket/img.jpg", mime_type="image/jpeg"
        )


def test_make_image_part_reads_local_file(tmp_path):
    from receipt_preprocessor.tools.gcs_utils import make_image_part

    img_file = tmp_path / "receipt.jpg"
    img_file.write_bytes(b"\xff\xd8\xff" + b"\x00" * 10)

    with patch("receipt_preprocessor.tools.gcs_utils.genai_types.Part") as mock_part:
        make_image_part(str(img_file))
        mock_part.from_bytes.assert_called_once_with(
            data=img_file.read_bytes(), mime_type="image/jpeg"
        )


# --- skip_if_rejected callback ---


def test_skip_if_rejected_returns_none_when_no_rejection():
    from receipt_preprocessor.sub_agents.callbacks import skip_if_rejected

    ctx = MagicMock()
    ctx.state = {}

    result = skip_if_rejected(ctx)

    assert result is None


def test_skip_if_rejected_returns_content_when_rejection_code_set():
    from google.genai import types

    from receipt_preprocessor.sub_agents.callbacks import skip_if_rejected

    ctx = MagicMock()
    ctx.state = {"rejection_code": "NON_RECEIPT"}

    result = skip_if_rejected(ctx)

    assert result is not None
    assert isinstance(result, types.Content)
    assert result.role == "model"
