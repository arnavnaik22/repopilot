import re


def tokenize(text: str) -> list[str]:
    out = []
    for word in re.findall(r"[A-Za-z][A-Za-z0-9_]*|\d+", text):
        out.append(word.lower())
        split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", word).replace("_", " ")
        out.extend(x.lower() for x in split.split() if x.lower() != word.lower())
    return out
