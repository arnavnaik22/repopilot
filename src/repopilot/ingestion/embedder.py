"""Local ONNX embeddings in production, deterministic vectors for offline tests."""
import hashlib
import math
import os
from repopilot.retrieval.tokenizer import tokenize


class HashEmbedder:
    dimension = 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = []
        for text in texts:
            v = [0.0] * self.dimension
            for token in tokenize(text):
                digest = hashlib.sha256(token.encode()).digest()
                index = int.from_bytes(digest[:2], "big") % self.dimension
                v[index] += 1 if digest[2] % 2 else -1
            norm = math.sqrt(sum(x * x for x in v)) or 1
            result.append([x / norm for x in v])
        return result


class FastEmbedder:
    def __init__(self):
        from fastembed import TextEmbedding
        self.model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", cache_dir=".cache/fastembed")

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self.model.embed(texts)]


def configured_embedder():
    return HashEmbedder() if os.getenv("REPOPILOT_EMBEDDER", "fastembed") == "hash" else FastEmbedder()
