import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from repopilot.agent.loop import investigate
from repopilot.agent.path_guard import guarded_path
from repopilot.agent.tools import InvestigationTools
from repopilot.agent.verifier import verify
from repopilot.ingestion.chunker import chunk
from repopilot.ingestion.embedder import HashEmbedder
from repopilot.ingestion.indexer import index_repository
from repopilot.ingestion.scanner import scan
from repopilot.retrieval.hybrid import HybridRetriever
from repopilot.retrieval.store import Store
from repopilot.retrieval.tokenizer import tokenize

ROOT = Path(__file__).parent / "fixtures" / "sample_repo"


def test_scanner_and_chunk_line_invariant(tmp_path):
    assert {p for p,_,_ in scan(ROOT)} >= {"auth.py","Service.java"}
    for path,source,_ in scan(ROOT):
        lines=source.splitlines()
        for c in chunk(path,source):
            assert "\n".join(lines[c.start_line-1:c.end_line]) == c.text
    assert any(c.symbol_name=="authenticate_user" for c in chunk("auth.py",(ROOT/"auth.py").read_text()))


def test_tokenizer_and_retrieval(tmp_path,monkeypatch):
    monkeypatch.setenv("REPOPILOT_DATA_DIR",str(tmp_path))
    rid=index_repository(ROOT,embedder=HashEmbedder())
    store=Store(tmp_path/rid)
    retriever=HybridRetriever(store,HashEmbedder())
    assert "greetuser" in tokenize("greetUser") and "greet" in tokenize("greetUser")
    for mode in ("hybrid","bm25","dense"):
        assert retriever.search("authenticate_user",3,mode)
    assert any(x.path=="auth.py" for x in retriever.search("authenticate_user",3))
    assert Store(tmp_path/index_repository(ROOT,embedder=HashEmbedder())).state()["status"]=="ready"


def test_path_guard_and_provenance():
    for bad in ("../auth.py",r"C:\Windows\system.ini",r"..\..\secret",r"\\server\share\file"):
        with pytest.raises(ValueError): guarded_path(ROOT,bad)
    assert guarded_path(ROOT,"auth.py").name=="auth.py"
    claim={"path":"auth.py","start_line":14,"end_line":18}
    assert not verify(ROOT,[claim],{})
    assert verify(ROOT,[claim],{"auth.py":[(14,18)]})[0].verified


def test_tools_and_agent_budget(tmp_path,monkeypatch):
    monkeypatch.setenv("REPOPILOT_DATA_DIR",str(tmp_path))
    rid=index_repository(ROOT,embedder=HashEmbedder())
    tools=InvestigationTools(ROOT,HybridRetriever(Store(tmp_path/rid),HashEmbedder()))
    assert "definition (exact)" in tools.find_references("authenticate_user")
    assert "14:" in tools.read_file("auth.py",14,18)
    class Fake:
        def __init__(self): self.n=0
        def call(self,system,messages,schemas,force_submit=False):
            self.n+=1
            name="search_code" if self.n==1 else "submit_answer"
            args={"query":"authenticate_user"} if self.n==1 else {"answer":"Active users pass.","evidence_status":"supported","citations":[{"path":"auth.py","start_line":14,"end_line":18}]}
            return SimpleNamespace(content=[SimpleNamespace(type="tool_use",name=name,input=args,id=str(self.n))])
    result=investigate("How is auth checked?",tools,Fake(),max_calls=2)
    assert result.evidence_status=="supported" and result.citations and result.tool_calls_used==1


def test_duplicate_and_budget_are_bounded(tmp_path,monkeypatch):
    monkeypatch.setenv("REPOPILOT_DATA_DIR",str(tmp_path))
    rid=index_repository(ROOT,embedder=HashEmbedder())
    tools=InvestigationTools(ROOT,HybridRetriever(Store(tmp_path/rid),HashEmbedder()))
    class Fake:
        def __init__(self): self.n=0
        def call(self,system,messages,schemas,force_submit=False):
            self.n+=1
            if force_submit:
                name,args="submit_answer",{"answer":"Not enough evidence.","evidence_status":"insufficient","citations":[]}
            else:
                name,args="search_code",{"query":"authenticate_user"}
            return SimpleNamespace(content=[SimpleNamespace(type="tool_use",name=name,input=args,id=str(self.n))])
    result=investigate("What happened?",tools,Fake(),max_calls=2)
    assert result.tool_calls_used==2 and result.budget_exhausted
    assert result.trace[1].duplicate


def test_incremental_removes_deleted_file(tmp_path,monkeypatch):
    monkeypatch.setenv("REPOPILOT_DATA_DIR",str(tmp_path/"index"))
    repo=tmp_path/"repo"; repo.mkdir()
    (repo/"one.py").write_text("def one():\n    return 1\n")
    (repo/"two.py").write_text("def two():\n    return 2\n")
    rid=index_repository(repo,embedder=HashEmbedder())
    (repo/"two.py").unlink()
    index_repository(repo,embedder=HashEmbedder())
    store=Store(tmp_path/"index"/rid)
    assert list(store.files())==["one.py"]


def test_request_validation():
    from pydantic import ValidationError
    from repopilot.schemas import QueryRequest
    with pytest.raises(ValidationError):
        QueryRequest(repository_id="abc",question="hi",top_k=21)


def test_answer_judge_schema_with_fake_model():
    from eval.judge import judge_answer
    class Fake:
        def call(self,system,messages,tools,force_submit=False):
            assert force_submit and tools[0]["name"]=="submit_grade"
            return SimpleNamespace(content=[SimpleNamespace(type="tool_use",name="submit_grade",input={"score":1,"reason":"Covers the facts"})])
    grade=judge_answer({"question":"Where?","reference_answer":"Here","key_facts":["Here"]},"Here",Fake())
    assert grade["score"]==1
