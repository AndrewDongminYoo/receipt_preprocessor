import logging
from datetime import date
from typing import Optional

import cv2
import numpy as np
from google.adk.tools.tool_context import ToolContext

from receipt_preprocessor import config
from receipt_preprocessor.tools.gcs_utils import download_from_gcs, upload_to_gcs

logger = logging.getLogger(__name__)


def _apply_perspective(image_bytes: bytes, corners: list) -> bytes:
    """Applies a 4-point perspective transform (TL, TR, BR, BL) using OpenCV."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")

    h, w = img.shape[:2]
    src = np.float32(corners)
    dst = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])

    M = cv2.getPerspectiveTransform(src, dst)
    corrected = cv2.warpPerspective(img, M, (w, h))

    success, buffer = cv2.imencode(".jpg", corrected, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not success:
        raise ValueError("Could not encode corrected image")
    return buffer.tobytes()


def correct_and_upload(corners: Optional[list], tool_context: ToolContext) -> dict:
    """Applies perspective correction and uploads the result to GCS.

    Soft gate: on any failure, falls back to original_image_uri without escalating.
    Writes corrected_image_uri and geometry_corrected to session state.
    """
    image_uri = tool_context.state.get("original_image_uri")
    session_id = tool_context.state.get("session_id")

    if not corners:
        tool_context.state["corrected_image_uri"] = image_uri
        tool_context.state["geometry_corrected"] = False
        return {"corrected_image_uri": image_uri, "corrected": False}

    try:
        image_bytes = download_from_gcs(image_uri)
        corrected_bytes = _apply_perspective(image_bytes, corners)
        date_str = date.today().strftime("%Y%m%d")
        blob_path = f"{date_str}/{session_id}/corrected.jpg"
        corrected_uri = upload_to_gcs(
            corrected_bytes, config.GCS_BUCKET_NAME, blob_path
        )
        tool_context.state["corrected_image_uri"] = corrected_uri
        tool_context.state["geometry_corrected"] = True
        return {"corrected_image_uri": corrected_uri, "corrected": True}
    except Exception as exc:
        # GEOMETRY_FAILED is a soft failure per spec — log and pass original through
        logger.warning("Perspective correction failed (GEOMETRY_FAILED): %s", exc)
        tool_context.state["corrected_image_uri"] = image_uri
        tool_context.state["geometry_corrected"] = False
        return {
            "corrected_image_uri": image_uri,
            "corrected": False,
            "error": "GEOMETRY_FAILED",
        }
