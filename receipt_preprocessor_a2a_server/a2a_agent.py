from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

root_agent = RemoteA2aAgent(
    name="receipt_preprocessor",
    description="Pre-processes receipt images before Azure OCR.",
    agent_card="http://localhost:8001/a2a/receipt_preprocessor/.well-known/agent.json",
    timeout=120.0,
    httpx_client=None,
)
