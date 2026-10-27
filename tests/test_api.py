from fastapi.testclient import TestClient
from pathlib import Path
from types import SimpleNamespace
from repopilot.api.main import app


def test_health_and_validation():
    client=TestClient(app)
    assert client.get("/health").json()=={"status":"ok"}
    assert client.post("/query",json={"repository_id":"bad","question":"hi"}).status_code==422
    assert client.get("/repositories/invalid/status").status_code==404


def test_index_and_query_flow(tmp_path,monkeypatch):
    monkeypatch.setenv("REPOPILOT_DATA_DIR",str(tmp_path))
    monkeypatch.setenv("REPOPILOT_EMBEDDER","hash")
    root=Path(__file__).parent/"fixtures"/"sample_repo"
    class Fake:
        def __init__(self): self.n=0
        def call(self,system,messages,tools,force_submit=False):
            self.n+=1
            name="search_code" if self.n==1 else "submit_answer"
            payload={"query":"authenticate_user"} if self.n==1 else {"answer":"The function rejects inactive users.","evidence_status":"supported","citations":[{"path":"auth.py","start_line":15,"end_line":20}]}
            return SimpleNamespace(content=[SimpleNamespace(type="tool_use",name=name,input=payload,id=str(self.n))])
    monkeypatch.setattr("repopilot.api.main.configured_llm",Fake)
    client=TestClient(app)
    indexed=client.post("/repositories/index",json={"repo_path":str(root)})
    assert indexed.status_code==200
    rid=indexed.json()["repository_id"]
    assert client.get(f"/repositories/{rid}/status").json()["status"]=="ready"
    response=client.post("/query",json={"repository_id":rid,"question":"How are inactive users rejected?"})
    assert response.status_code==200
    body=response.json()
    assert body["evidence_status"]=="supported" and body["citations"][0]["verified"]
