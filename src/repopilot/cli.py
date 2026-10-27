import argparse
import json
from pathlib import Path
from repopilot.agent.llm import configured_llm
from repopilot.agent.loop import investigate
from repopilot.agent.tools import InvestigationTools
from repopilot.config import data_dir
from repopilot.ingestion.embedder import configured_embedder
from repopilot.ingestion.indexer import index_repository,repo_id
from repopilot.retrieval.hybrid import HybridRetriever
from repopilot.retrieval.store import Store


def main():
    p = argparse.ArgumentParser(description="Index or investigate a repository")
    sub = p.add_subparsers(dest="command",required=True)
    ix = sub.add_parser("index"); ix.add_argument("repo")
    ask = sub.add_parser("ask"); ask.add_argument("repo"); ask.add_argument("question")
    args = p.parse_args()
    root = Path(args.repo).resolve()
    if args.command == "index":
        print(index_repository(root)); return
    store = Store(data_dir()/repo_id(root))
    if store.state().get("status") != "ready":
        p.error("Repository is not indexed. Run 'python -m repopilot.cli index <repo>' first.")
    retriever = HybridRetriever(store,configured_embedder())
    try:
        llm = configured_llm()
    except (RuntimeError, ValueError) as exc:
        p.error(str(exc))
    response = investigate(args.question,InvestigationTools(root,retriever),llm)
    print(json.dumps(response.model_dump(),indent=2))


if __name__ == "__main__": main()
