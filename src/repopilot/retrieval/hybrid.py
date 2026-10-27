import json
import math
from collections import Counter
from dataclasses import dataclass
from repopilot.retrieval.tokenizer import tokenize


@dataclass
class RetrievedChunk:
    path: str
    start_line: int
    end_line: int
    snippet: str
    score: float
    bm25_rank: int | None
    dense_rank: int | None


class HybridRetriever:
    def __init__(self, store, embedder):
        self.rows = store.chunks()
        self.embedder = embedder
        self.docs = [tokenize(r["path"] + " " + r["symbol_name"] + " " + r["text"]) for r in self.rows]
        self.df = Counter(t for doc in self.docs for t in set(doc))
        self.avg_len = sum(map(len, self.docs)) / max(len(self.docs), 1)

    def search(self, query: str, k=8, mode="hybrid") -> list[RetrievedChunk]:
        if not self.rows:
            return []
        terms = tokenize(query)
        n = len(self.rows)
        bm = []
        for doc in self.docs:
            counts = Counter(doc)
            score = 0.0
            for t in terms:
                df = self.df[t]
                idf = math.log(1 + (n - df + .5) / (df + .5))
                tf = counts[t]
                score += idf * tf * 2.2 / (tf + 1.2 * (.25 + .75 * len(doc) / (self.avg_len or 1))) if tf else 0
            bm.append(score)
        qv = self.embedder.embed([query])[0]
        dense = [sum(a*b for a,b in zip(qv,json.loads(r["vector"]))) for r in self.rows]
        br = sorted(range(n), key=lambda i: (-bm[i], i))[:50]
        dr = sorted(range(n), key=lambda i: (-dense[i], i))[:50]
        ranks_b, ranks_d = {i:j+1 for j,i in enumerate(br)}, {i:j+1 for j,i in enumerate(dr)}
        def score(i):
            if mode == "bm25": return bm[i]
            if mode == "dense": return dense[i]
            s = (1/(60+ranks_b[i]) if i in ranks_b else 0) + (1/(60+ranks_d[i]) if i in ranks_d else 0)
            if self.rows[i]["symbol_name"].lower() in terms: s += .02
            return s
        order = sorted(range(n), key=lambda i: (-score(i), i))[:k]
        return [RetrievedChunk(r["path"],r["start_line"],r["end_line"],r["text"],score(i),ranks_b.get(i),ranks_d.get(i)) for i in order if (mode != "bm25" or bm[i] > 0) for r in [self.rows[i]]]
