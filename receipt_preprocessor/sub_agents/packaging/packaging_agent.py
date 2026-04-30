from google.adk.agents import Agent

from receipt_preprocessor import config

from .prompt import PACKAGING_PROMPT
from .tools.build_payload_tool import build_azure_payload

packaging_agent = Agent(
    name="packaging_agent",
    model=config.GENAI_MODEL,
    description="Assembles the final preprocessed payload for Azure OCR.",
    instruction=PACKAGING_PROMPT,
    output_key="azure_payload",
    tools=[build_azure_payload],
)
