from google.adk.agents import Agent

from receipt_preprocessor import config
from receipt_preprocessor.tools.reject_tool import reject_with_code

from .prompt import VALIDITY_PROMPT
from .tools.classify_receipt_tool import classify_receipt

validity_gate_agent = Agent(
    name="validity_gate_agent",
    model=config.GENAI_MODEL,
    description="Validates that the uploaded image is a domestic Korean retail receipt.",
    instruction=VALIDITY_PROMPT,
    tools=[classify_receipt, reject_with_code],
)
