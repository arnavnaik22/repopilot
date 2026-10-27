import json
import os
import time
from types import SimpleNamespace

import httpx
from repopilot import config  # loads .env when python-dotenv is installed


class AnthropicLLM:
    def __init__(self):
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("Set ANTHROPIC_API_KEY in your environment")
        from anthropic import Anthropic
        self.client = Anthropic()
        self.model = os.getenv("REPOPILOT_ANTHROPIC_MODEL", os.getenv("REPOPILOT_MODEL", "claude-haiku-4-5-20251001"))

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


class GroqLLM:
    """Adapt Groq's OpenAI-compatible chat tools to the agent's block format."""

    def __init__(self, client: httpx.Client | None = None):
        self.key = os.getenv("GROQ_API_KEY", "")
        if not self.key:
            raise RuntimeError("Set GROQ_API_KEY in your environment or .env")
        self.client = client or httpx.Client(timeout=30)
        self.model = os.getenv("REPOPILOT_GROQ_MODEL", "openai/gpt-oss-20b")

    @staticmethod
    def _messages(system, messages):
        output = [{"role": "system", "content": system}]
        for message in messages:
            content = message["content"]
            if message["role"] == "user" and isinstance(content, str):
                output.append({"role": "user", "content": content})
            elif message["role"] == "user":
                for result in content:
                    output.append({"role": "tool", "tool_call_id": result["tool_use_id"], "content": result["content"]})
            else:
                calls = [block for block in content if getattr(block, "type", None) == "tool_use"]
                text = "\n".join(getattr(block, "text", "") for block in content if getattr(block, "type", None) == "text")
                item = {"role": "assistant", "content": text or None}
                if calls:
                    item["tool_calls"] = [{"id": block.id, "type": "function", "function": {"name": block.name, "arguments": json.dumps(block.input)}} for block in calls]
                output.append(item)
        return output

    def call(self, system, messages, tools, force_submit=False):
        functions = [{"type": "function", "function": {"name": tool["name"], "description": tool["description"], "parameters": tool["input_schema"]}} for tool in tools]
        body = {"model": self.model, "messages": self._messages(system, messages), "tools": functions,
                "tool_choice": {"type": "function", "function": {"name": tools[-1]["name"]}} if force_submit else "auto",
                "max_completion_tokens": 1600}
        for attempt in range(3):
            try:
                response = self.client.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {self.key}"}, json=body)
                response.raise_for_status()
                choice = response.json()["choices"][0]["message"]
                blocks = []
                if choice.get("content"):
                    blocks.append(SimpleNamespace(type="text", text=choice["content"]))
                for call in choice.get("tool_calls") or []:
                    try:
                        args = json.loads(call["function"]["arguments"])
                    except (KeyError, TypeError, json.JSONDecodeError):
                        args = {}
                    blocks.append(SimpleNamespace(type="tool_use", id=call["id"], name=call["function"]["name"], input=args))
                return SimpleNamespace(content=blocks)
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
                status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                if attempt == 2 or (status not in (429,500,502,503,504) and not isinstance(exc, httpx.TimeoutException)):
                    raise
                time.sleep(2 ** attempt)


def configured_llm():
    provider = os.getenv("REPOPILOT_PROVIDER", "groq").lower()
    if provider == "groq":
        return GroqLLM()
    if provider == "anthropic":
        return AnthropicLLM()
    raise ValueError("REPOPILOT_PROVIDER must be 'groq' or 'anthropic'")
