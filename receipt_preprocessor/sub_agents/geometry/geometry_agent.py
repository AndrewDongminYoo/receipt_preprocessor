from google.adk.agents import Agent

from receipt_preprocessor import config

from .prompt import GEOMETRY_PROMPT
from .tools.correct_perspective_tool import correct_and_upload
from .tools.detect_corners_tool import detect_corners

geometry_agent = Agent(
    name="geometry_agent",
    model=config.GENAI_MODEL,
    description="Detects and corrects perspective distortion in receipt images.",
    instruction=GEOMETRY_PROMPT,
    tools=[detect_corners, correct_and_upload],
)
