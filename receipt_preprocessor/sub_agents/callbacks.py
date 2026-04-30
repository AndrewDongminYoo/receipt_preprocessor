from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.genai import types


def skip_if_rejected(callback_context: CallbackContext) -> Optional[types.Content]:
    """Skips this agent if an upstream gate already recorded a rejection_code in state."""
    if callback_context.state.get("rejection_code"):
        return types.Content(
            role="model",
            parts=[types.Part(text="Skipped: upstream rejection already recorded.")],
        )
    return None
