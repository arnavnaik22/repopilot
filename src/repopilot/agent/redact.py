import os
import re


def redact(message: object) -> str:
    text = str(message)
    for name in ("ANTHROPIC_API_KEY", "GROQ_API_KEY"):
        key = os.getenv(name, "")
        if key:
            text = text.replace(key, "[REDACTED]")
    return re.sub(r"(?:sk-ant-|gsk_)[A-Za-z0-9_-]+", "[REDACTED]", text)
