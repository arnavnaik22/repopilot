import os
import re


def redact(message: object) -> str:
    text = str(message)
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if key:
        text = text.replace(key, "[REDACTED]")
    return re.sub(r"sk-ant-[A-Za-z0-9_-]+", "[REDACTED]", text)
