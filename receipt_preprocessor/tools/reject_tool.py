from typing import Literal

from google.adk.tools.tool_context import ToolContext

RejectionCode = Literal[
    "FILE_INVALID",
    "DUPLICATE",
    "REFUND_RECEIPT",
    "NON_RECEIPT",
    "OVERSEAS_RECEIPT",
    "NON_RETAIL",
    "QUALITY_LOW",
    "GEOMETRY_FAILED",
]


def reject_with_code(
    code: RejectionCode, user_message: str, tool_context: ToolContext
) -> dict:
    """Records rejection in session state and escalates to stop the pipeline."""
    tool_context.state["rejection_code"] = code
    tool_context.state["rejection_message"] = user_message
    tool_context.actions.escalate = True
    return {"rejected": True, "code": code, "message": user_message}
