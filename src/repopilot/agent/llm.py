import os
import time
from repopilot import config  # loads .env when python-dotenv is installed


class AnthropicLLM:
    def __init__(self):
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("Set ANTHROPIC_API_KEY in your environment")
        from anthropic import Anthropic
        self.client = Anthropic()
        self.model = os.getenv("REPOPILOT_MODEL", "claude-haiku-4-5-20251001")

    def call(self, system, messages, tools, force_submit=False):
        for attempt in range(3):
            try:
                return self.client.messages.create(model=self.model, max_tokens=1600, system=system, messages=messages, tools=tools,
                    tool_choice={"type":"tool","name":tools[-1]["name"]} if force_submit else {"type":"auto"}, timeout=30)
            except Exception as exc:
                status = getattr(exc,"status_code",None)
                if attempt == 2 or (status not in (429,500,502,503,504) and "timeout" not in type(exc).__name__.lower()):
                    raise
                time.sleep(2 ** attempt)
