import hashlib
from datetime import datetime, timezone
from pathlib import Path
from repopilot.config import allowed_repo, data_dir
from repopilot.ingestion.chunker import chunk
from repopilot.ingestion.embedder import configured_embedder
from repopilot.ingestion.scanner import scan
from repopilot.retrieval.store import Store


def repo_id(root: Path) -> str:
    return hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:12]


def index_repository(root: Path, force: bool = False, embedder=None) -> str:
    root = root.resolve()
    if not root.is_dir() or not allowed_repo(root):
        raise ValueError("Repository directory is invalid or outside REPOPILOT_ALLOWED_ROOTS")
    rid = repo_id(root)
    store = Store(data_dir() / rid)
    previous_embedder = store.state().get("embedder")
    store.set_state(root=str(root), status="indexing", error=None, files_total=0, files_indexed=0, files_skipped=0)
    try:
        old = store.files()
        seen = set()
        embedder = embedder or configured_embedder()
        embedder_name = type(embedder).__name__
        if previous_embedder != embedder_name:
            force = True
        cache = store.cached_vectors() if previous_embedder == embedder_name else {}
        changed = 0
        for path, source, sha in scan(root):
            seen.add(path)
            if not force and old.get(path) == sha:
                continue
            parts = chunk(path, source)
            missing = list(dict.fromkeys(c.content_hash for c in parts if c.content_hash not in cache))
            if missing:
                texts = [f"# path: {next(c.path for c in parts if c.content_hash == h)} | symbol: {next(c.symbol_name for c in parts if c.content_hash == h)}\n{next(c.text for c in parts if c.content_hash == h)}" for h in missing]
                cache.update(zip(missing, embedder.embed(texts)))
            store.replace_file(path, sha, parts, [cache[c.content_hash] for c in parts])
            changed += 1
            store.set_state(files_indexed=changed)
        for path in old.keys() - seen:
            store.remove_file(path)
        store.set_state(status="ready", embedder=embedder_name, files_total=len(seen), files_skipped=0, chunks=len(store.chunks()), last_indexed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        store.set_state(status="failed", error=str(exc))
        raise
    return rid
