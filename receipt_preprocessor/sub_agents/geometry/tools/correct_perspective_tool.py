import io
import logging
from datetime import date
from typing import Optional

import numpy as np
from google.adk.tools.tool_context import ToolContext
from PIL import Image

from receipt_preprocessor import config
from receipt_preprocessor.tools.gcs_utils import read_image_bytes, upload_to_gcs

logger = logging.getLogger(__name__)


def _compute_perspective_coeffs(src_corners: list, dst_corners: list) -> list:
    """Compute 8 Pillow PERSPECTIVE coefficients for the inverse transform (dst→src).

    Pillow's transform maps destination coords to source coords:
        x_src = (a·x + b·y + c) / (g·x + h·y + 1)
        y_src = (d·x + e·y + f) / (g·x + h·y + 1)
    We solve the resulting 8x8 linear system via least-squares.
    """
    A, b = [], []
    for (x, y), (X, Y) in zip(dst_corners, src_corners, strict=False):
        A.append([x, y, 1, 0, 0, 0, -x * X, -y * X])
        A.append([0, 0, 0, x, y, 1, -x * Y, -y * Y])
        b.extend([X, Y])
    coeffs, _, _, _ = np.linalg.lstsq(
        np.array(A, dtype=np.float64), np.array(b, dtype=np.float64), rcond=None
    )
    return coeffs.tolist()


def _apply_perspective(image_bytes: bytes, corners: list) -> bytes:
    """Applies a 4-point perspective transform (TL, TR, BR, BL) using Pillow."""
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    dst = [[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]]
    coeffs = _compute_perspective_coeffs(corners, dst)
    corrected = img.transform(
        (w, h), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC
    )
    output = io.BytesIO()
    corrected.save(output, format="JPEG", quality=95)
    return output.getvalue()


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
        image_bytes = read_image_bytes(image_uri)
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
