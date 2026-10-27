from pathlib import Path
from fastapi import BackgroundTasks, FastAPI, HTTPException
from repopilot.agent.llm import AnthropicLLM
from repopilot.agent.redact import redact
from repopilot.agent.loop import investigate
from repopilot.agent.tools import InvestigationTools
from repopilot.config import allowed_repo, data_dir
from repopilot.ingestion.embedder import configured_embedder
from repopilot.ingestion.indexer import index_repository, repo_id
from repopilot.retrieval.hybrid import HybridRetriever
from repopilot.retrieval.store import Store
from repopilot.schemas import IndexRequest, IndexResponse, IndexStatus, QueryRequest, QueryResponse

app = FastAPI(title="RepoPilot", version="0.1.0")


@app.get("/health")
def health():
    return {"status":"ok"}


@app.post("/repositories/index", response_model=IndexResponse)
def start_index(request: IndexRequest, tasks: BackgroundTasks):
    root = Path(request.repo_path).resolve()
    if not root.is_dir() or not allowed_repo(root):
        raise HTTPException(400,"Invalid or disallowed repository directory")
    rid = repo_id(root)
    Store(data_dir()/rid).set_state(root=str(root),status="indexing",files_total=0,files_indexed=0,files_skipped=0,chunks=0,error=None)
    tasks.add_task(index_repository,root,request.force_reindex)
    return IndexResponse(repository_id=rid,status="indexing")


@app.get("/repositories/{repository_id}/status", response_model=IndexStatus)
def status(repository_id: str):
    if not repository_id.isalnum() or len(repository_id) != 12:
        raise HTTPException(404,"Repository not found")
    db = data_dir()/repository_id/"meta.sqlite"
    if not db.exists():
        raise HTTPException(404,"Repository not found")
    state = Store(data_dir()/repository_id).state()
    return IndexStatus(repository_id=repository_id,**{k:v for k,v in state.items() if k in IndexStatus.model_fields})


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    if not request.repository_id.isalnum() or len(request.repository_id) != 12:
        raise HTTPException(404,"Repository not found")
    db = data_dir()/request.repository_id/"meta.sqlite"
    if not db.exists():
        raise HTTPException(404,"Repository not found")
    store = Store(data_dir()/request.repository_id)
    state = store.state()
    if state.get("status") != "ready":
        raise HTTPException(409,"Repository is not ready")
    root = Path(state["root"])
    if not root.is_dir() or not allowed_repo(root):
        raise HTTPException(400,"Repository directory is unavailable")
    try:
        retriever = HybridRetriever(store,configured_embedder())
        tools = InvestigationTools(root,retriever,request.top_k,request.retrieval_mode)
        return investigate(request.question,tools,AnthropicLLM(),request.max_tool_calls)
    except Exception as exc:
        return QueryResponse(answer="Unable to complete the investigation.",evidence_status="insufficient",error=redact(exc))
