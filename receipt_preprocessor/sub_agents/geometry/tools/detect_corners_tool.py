import json

import google.genai as genai
from google.adk.tools.tool_context import ToolContext

from receipt_preprocessor import config
from receipt_preprocessor.tools.gcs_utils import make_image_part
from receipt_preprocessor.tools.json_utils import extract_json


def detect_corners(tool_context: ToolContext) -> dict:
    """Detects the 4 corner coordinates of the receipt in the image.

    Reads original_image_uri from session state.
    Returns {"corners": [[x,y]x4]} or {"corners": null}.
    """
    image_uri = tool_context.state.get("original_image_uri")
    if not image_uri:
        return {"corners": None}

    client = genai.Client()
    response = client.models.generate_content(
        model=config.GENAI_MODEL,
        contents=[
            make_image_part(image_uri),
            """Identify the 4 corner pixel coordinates of the receipt document in this image.

Coordinate origin (0,0) is at the top-left of the image.

Respond ONLY with valid JSON, no markdown:
{"corners": [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]}
Order: top-left, top-right, bottom-right, bottom-left.

If the receipt fills the entire frame OR corners cannot be reliably determined, respond:
{"corners": null}""",
        ],
    )

    try:
        return extract_json(response.text)
    except (json.JSONDecodeError, AttributeError):
        return {"corners": None}
