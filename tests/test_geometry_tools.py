import io
import sys
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image


@pytest.fixture(autouse=True)
def set_required_env(monkeypatch):
    monkeypatch.setenv("GCS_BUCKET_NAME", "test-bucket")
    sys.modules.pop("receipt_preprocessor.config", None)


def _make_jpeg_bytes(width: int = 200, height: int = 300) -> bytes:
    img = Image.new("RGB", (width, height), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# --- detect_corners_tool ---


def test_detect_corners_returns_four_points():
    from receipt_preprocessor.sub_agents.geometry.tools.detect_corners_tool import (
        detect_corners,
    )

    ctx = MagicMock()
    ctx.state = {"original_image_uri": "gs://bucket/tilted.jpg"}

    mock_response = MagicMock()
    mock_response.text = '{"corners": [[10, 10], [190, 5], [195, 295], [8, 290]]}'

    with patch(
        "receipt_preprocessor.sub_agents.geometry.tools.detect_corners_tool.genai.Client"
    ) as mock_cls:
        mock_cls.return_value.models.generate_content.return_value = mock_response
        result = detect_corners(ctx)

    assert result["corners"] is not None
    assert len(result["corners"]) == 4


def test_detect_corners_returns_null_when_undetermined():
    from receipt_preprocessor.sub_agents.geometry.tools.detect_corners_tool import (
        detect_corners,
    )

    ctx = MagicMock()
    ctx.state = {"original_image_uri": "gs://bucket/fullframe.jpg"}

    mock_response = MagicMock()
    mock_response.text = '{"corners": null}'

    with patch(
        "receipt_preprocessor.sub_agents.geometry.tools.detect_corners_tool.genai.Client"
    ) as mock_cls:
        mock_cls.return_value.models.generate_content.return_value = mock_response
        result = detect_corners(ctx)

    assert result["corners"] is None


# --- correct_perspective_tool ---


def test_correct_and_upload_with_valid_corners():
    from receipt_preprocessor.sub_agents.geometry.tools.correct_perspective_tool import (
        correct_and_upload,
    )

    ctx = MagicMock()
    ctx.state = {
        "original_image_uri": "gs://bucket/tilted.jpg",
        "session_id": "test-session-abc",
    }
    image_bytes = _make_jpeg_bytes()
    corners = [[10, 10], [190, 10], [190, 290], [10, 290]]

    with patch(
        "receipt_preprocessor.sub_agents.geometry.tools.correct_perspective_tool.download_from_gcs",
        return_value=image_bytes,
    ):
        with patch(
            "receipt_preprocessor.sub_agents.geometry.tools.correct_perspective_tool.upload_to_gcs",
            return_value="gs://bucket/20260430/test-session-abc/corrected.jpg",
        ):
            result = correct_and_upload(corners, ctx)

    assert result["corrected"] is True
    assert (
        result["corrected_image_uri"]
        == "gs://bucket/20260430/test-session-abc/corrected.jpg"
    )
    assert (
        ctx.state["corrected_image_uri"]
        == "gs://bucket/20260430/test-session-abc/corrected.jpg"
    )
    assert ctx.state["geometry_corrected"] is True


def test_correct_and_upload_passes_original_when_no_corners():
    from receipt_preprocessor.sub_agents.geometry.tools.correct_perspective_tool import (
        correct_and_upload,
    )

    ctx = MagicMock()
    ctx.state = {
        "original_image_uri": "gs://bucket/fullframe.jpg",
        "session_id": "test-session-xyz",
    }

    result = correct_and_upload(None, ctx)

    assert result["corrected"] is False
    assert result["corrected_image_uri"] == "gs://bucket/fullframe.jpg"
    assert ctx.state["corrected_image_uri"] == "gs://bucket/fullframe.jpg"
    assert ctx.state["geometry_corrected"] is False


def test_apply_perspective_produces_valid_jpeg():
    from receipt_preprocessor.sub_agents.geometry.tools.correct_perspective_tool import (
        _apply_perspective,
    )

    image_bytes = _make_jpeg_bytes(200, 300)
    corners = [[10, 10], [190, 10], [190, 290], [10, 290]]
    result = _apply_perspective(image_bytes, corners)

    assert isinstance(result, bytes)
    reopened = Image.open(io.BytesIO(result))
    assert reopened.format == "JPEG"
