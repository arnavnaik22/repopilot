from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class IndexRequest(BaseModel):
    repo_path: str
    force_reindex: bool = False


class IndexResponse(BaseModel):
    repository_id: str
    status: Literal["indexing", "ready", "failed"]


class IndexStatus(IndexResponse):
    files_total: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    chunks: int = 0
    last_indexed_at: datetime | None = None
    error: str | None = None


class QueryRequest(BaseModel):
    repository_id: str
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(8, ge=1, le=20)
    max_tool_calls: int = Field(5, ge=1, le=10)
    retrieval_mode: Literal["hybrid", "bm25", "dense"] = "hybrid"


class Citation(BaseModel):
    path: str
    start_line: int
    end_line: int
    snippet: str = ""
    verified: bool = False


class ToolTrace(BaseModel):
    step: int
    tool: str
    args: dict
    summary: str
    ok: bool
    duplicate: bool = False


class QueryResponse(BaseModel):
    answer: str
    evidence_status: Literal["supported", "inferred", "insufficient"]
    citations: list[Citation] = []
    trace: list[ToolTrace] = []
    tool_calls_used: int = 0
    budget_exhausted: bool = False
    latency_ms: int = 0
    error: str | None = None
