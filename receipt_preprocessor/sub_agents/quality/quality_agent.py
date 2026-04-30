from google.adk.agents import Agent

from receipt_preprocessor import config
from receipt_preprocessor.sub_agents.callbacks import skip_if_rejected
from receipt_preprocessor.tools.reject_tool import reject_with_code

from .prompt import QUALITY_PROMPT
from .tools.score_quality_tool import score_image_quality

quality_gate_agent = Agent(
    name="quality_gate_agent",
    model=config.GENAI_MODEL,
    description="Scores receipt image quality and rejects images below the quality threshold.",
    instruction=QUALITY_PROMPT,
    tools=[score_image_quality, reject_with_code],
    before_agent_callback=skip_if_rejected,
)
