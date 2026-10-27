"""Reproducible retrieval benchmark; optional hosted agent measurements."""
import argparse
import json
import statistics
import time
from pathlib import Path
from repopilot.agent.llm import AnthropicLLM
from repopilot.agent.loop import investigate
from repopilot.agent.tools import InvestigationTools
from repopilot.config import data_dir
from repopilot.ingestion.embedder import HashEmbedder, configured_embedder
from repopilot.ingestion.indexer import index_repository
from repopilot.retrieval.hybrid import HybridRetriever
from repopilot.retrieval.store import Store


def overlaps(hit, gold):
    return hit.path == gold["path"] and hit.start_line <= gold["end_line"] and hit.end_line >= gold["start_line"]


def run(repo, dataset, modes, agent=False, offline=False):
    embedder = HashEmbedder() if offline else configured_embedder()
    rid = index_repository(repo,embedder=embedder)
    retriever = HybridRetriever(Store(data_dir()/rid),embedder)
    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    report = {"repository":str(repo),"dataset":str(dataset),"embedder":"hash" if offline else "fastembed","questions":len(cases),"modes":{}}
    for mode in modes:
        rows=[]
        for case in cases:
            start=time.monotonic()
            hits=retriever.search(case["question"],3,mode)
            row={"id":case["id"],"answerable":case["answerable"],"recall_at_3":any(overlaps(h,g) for h in hits for g in case["gold_locations"]) if case["answerable"] else None,"retrieval_ms":round((time.monotonic()-start)*1000,2)}
            if agent:
                result=investigate(case["question"],InvestigationTools(repo,retriever,mode=mode),AnthropicLLM())
                citations=result.citations
                row.update({"evidence_status":result.evidence_status,"citation_validity":all(c.verified for c in citations) if citations else None,"citation_relevance":sum(any(overlaps(c,g) for g in case["gold_locations"]) for c in citations)/len(citations) if citations else None,"latency_ms":result.latency_ms,"tool_calls":result.tool_calls_used,"error":result.error})
            rows.append(row)
        answerable=[r for r in rows if r["answerable"]]
        summary={"recall_at_3":round(sum(r["recall_at_3"] for r in answerable)/len(answerable),3),"median_retrieval_ms":round(statistics.median(r["retrieval_ms"] for r in rows),2)}
        if agent:
            summary.update({"abstention_unanswerable":sum(r["evidence_status"]=="insufficient" for r in rows if not r["answerable"])/max(1,sum(not r["answerable"] for r in rows)),"wrong_abstention_answerable":sum(r["evidence_status"]=="insufficient" for r in answerable)/len(answerable),"median_latency_ms":round(statistics.median(r["latency_ms"] for r in rows),2),"mean_tool_calls":round(statistics.mean(r["tool_calls"] for r in rows),2)})
        report["modes"][mode]={"summary":summary,"cases":rows}
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,default=Path("tests/fixtures/sample_repo"))
    p.add_argument("--dataset",type=Path,default=Path("eval/dataset.jsonl"))
    p.add_argument("--modes",nargs="+",choices=["hybrid","bm25","dense"],default=["hybrid","bm25","dense"])
    p.add_argument("--out",type=Path,default=Path("eval/results"))
    p.add_argument("--agent",action="store_true")
    p.add_argument("--offline",action="store_true")
    args=p.parse_args()
    report=run(args.repo,args.dataset,args.modes,args.agent,args.offline)
    args.out.mkdir(parents=True,exist_ok=True)
    target=args.out/("agent.json" if args.agent else "retrieval.json")
    target.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({m:x["summary"] for m,x in report["modes"].items()},indent=2))
    print(target)


if __name__=="__main__": main()
