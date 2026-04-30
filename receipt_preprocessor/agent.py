import datetime
import uuid
from zoneinfo import ZoneInfo

from google.adk.agents import SequentialAgent
from google.adk.agents.callback_context import CallbackContext

from .sub_agents.geometry.geometry_agent import geometry_agent
from .sub_agents.packaging.packaging_agent import packaging_agent
from .sub_agents.quality.quality_agent import quality_gate_agent
from .sub_agents.validity.validity_agent import validity_gate_agent

_PIPELINE_STATE_KEYS = (
    "rejection_code",
    "rejection_message",
    "original_image_uri",
    "receipt_type",
    "store_category",
    "quality_score",
    "quality_issues",
    "corrected_image_uri",
    "geometry_corrected",
    "azure_payload",
)


def set_session(callback_context: CallbackContext) -> None:
    """Resets pipeline state and injects a fresh session_id and timestamp before each turn."""
    for key in _PIPELINE_STATE_KEYS:
        callback_context.state.pop(key, None)
    callback_context.state["session_id"] = str(uuid.uuid4())
    callback_context.state["timestamp"] = datetime.datetime.now(
        ZoneInfo("UTC")
    ).isoformat()


receipt_preprocessor = SequentialAgent(
    name="receipt_preprocessor",
    description=(
        "Pre-processes receipt images before Azure OCR: validates retail category, "
        "scores quality, corrects perspective distortion, and packages the result."
    ),
    sub_agents=[
        validity_gate_agent,
        quality_gate_agent,
        geometry_agent,
        packaging_agent,
    ],
    before_agent_callback=set_session,
)

root_agent = receipt_preprocessor
