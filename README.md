<div align="center">

# 🧭 RepoPilot

**Find the code. Follow the evidence. Trust the citation.**

Ask a local Python or Java repository a question and get an answer backed by source lines the agent actually saw.

![RepoPilot architecture](docs/figures/architecture.svg)

[Quick start](#quick-start) · [How it works](#how-it-works) · [Evaluation](#evaluation) · [API](#api)

</div>

## What you get

- **Hybrid code search:** code-aware BM25 and local embeddings combined with reciprocal rank fusion.
- **A bounded investigator:** three read-only tools, a tool-call budget, duplicate detection, and structured final answers.
- **Verified citations:** the server checks paths, line numbers, and whether each cited range was exposed by a tool.
- **Incremental indexing:** changed files are updated; identical chunks reuse cached vectors.
- **A working interface:** Streamlit UI, FastAPI endpoints, and a CLI.
- **Offline checks:** a deterministic embedder and a labelled fixture keep tests and retrieval evaluation free of model downloads and API charges.

## Quick start

Python **3.11 or 3.12** is required. From PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Put an Anthropic API key in `.env` for answers. The default model is `claude-haiku-4-5-20251001`, which Anthropic [lists as active](https://docs.anthropic.com/en/docs/about-claude/model-deprecations). You can set `REPOPILOT_MODEL` to another model supporting native tool use. The first production index downloads the BGE small ONNX model into `.cache/fastembed`.

In two terminals:

```powershell
uvicorn repopilot.api.main:app --reload --port 8000
streamlit run src/repopilot/ui/app.py
```

Open the Streamlit URL, enter the absolute path of a local repository, click **Index repository**, wait until its status is **ready**, then ask a question. You can also use the CLI:

```powershell
python -m repopilot.cli index C:\path\to\repo
python -m repopilot.cli ask C:\path\to\repo "Where is authentication checked?"
```

For free, offline retrieval experiments, set `REPOPILOT_EMBEDDER=hash` before indexing. Use the same embedder setting for queries against that index.

## How it works

1. The scanner reads `.py` and `.java` files. It skips build directories, large and binary files, generated files, and symlinks.
2. Python chunks come from `ast`; Java chunks use a lightweight declaration heuristic. Every chunk retains its true source line range.
3. BM25 and dense similarity rank chunks. Reciprocal rank fusion combines the top 50 from each list.
4. The model can search, read a numbered file range, or find symbol references. Each tool response is bounded and marked as untrusted repository content.
5. The model submits a structured answer. The server fills snippets from real files and rejects citations it cannot verify.

![Hybrid retrieval combines BM25 and dense rankings](docs/figures/retrieval.svg)

See [the architecture notes](docs/architecture.md) for the data flow and trust boundaries.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/repositories/index` | Start indexing a local directory |
| `GET` | `/repositories/{id}/status` | Check progress and errors |
| `POST` | `/query` | Ask a question with a retrieval mode and tool budget |
| `GET` | `/health` | Health check |

FastAPI exposes interactive schemas at `http://127.0.0.1:8000/docs`. A query response contains the answer, evidence status (`supported`, `inferred`, or `insufficient`), verified citations, tool trace, tool count, and latency.

## Evaluation

The committed [20-question fixture dataset](eval/dataset.jsonl) contains 16 answerable and 4 unanswerable questions about [a small sample repository](tests/fixtures/sample_repo). Its source ranges were checked against the files. Run the offline retrieval comparison with:

```powershell
$env:REPOPILOT_EMBEDDER = "hash"
python -m eval.run_eval --offline
```

The committed [retrieval results](eval/results/retrieval.json) from this fixture are:

| Mode | Recall@3 on 16 answerable questions |
| --- | ---: |
| Hybrid | 100% |
| BM25 | 100% |
| Dense | 100% |

This fixture is intentionally tiny, so these numbers are a functional smoke test, **not** evidence that hybrid retrieval is better. It also cannot measure answer correctness. To evaluate on a larger repository, [fetch the pinned FastAPI template snapshot](scripts/fetch_eval_repo.ps1), hand-label source ranges in a separate JSONL dataset, and pass `--repo` and `--dataset` to the runner. Add `--agent` to measure abstention, citation relevance, latency, and tool calls with a hosted key. The runner writes JSON to `eval/results/`. No hosted evaluation result is claimed here.

## Tests

```powershell
pytest -q -m "not integration"
```

Tests cover discovery, line preservation, tokenization, search, path traversal, provenance, references, and a scripted fake model. CI runs the same suite and offline evaluation on every push and pull request.

## Limits and design choices

- Java declaration parsing and references are heuristic; Python AST analysis is more reliable.
- Local BM25 ranks in memory; SQLite stores vectors as JSON per chunk. This favors readability and a few thousand chunks over maximum scale. A dedicated search engine becomes appropriate for very large repositories.
- Citation verification proves source provenance and range validity. It does not establish that the prose faithfully interprets the code.
- RepoPilot is intended to run locally. If you expose the API to other users, set `REPOPILOT_ALLOWED_ROOTS` and add authentication before accepting arbitrary paths.
- The production embedder downloads a model on first use, and hosted answers require an Anthropic key. Offline tests use a deterministic hash embedder.

## Repository map

```text
src/repopilot/   scanner, chunker, index, retrieval, agent, API, UI, CLI
eval/            labelled fixture and benchmark runner
tests/           offline tests and sample repository
docs/            architecture notes and figure
scripts/         pinned evaluation repository fetcher
```

MIT license. Built to keep code investigation inspectable, bounded, and honest about its evidence.
