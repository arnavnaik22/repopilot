"""Conservative source discovery. Repository content is always treated as data."""
import hashlib
from pathlib import Path

EXCLUDED = {".git", "node_modules", "venv", ".venv", "__pycache__", "build", "dist", "target", ".idea", ".gradle", "site-packages", "data"}
SUFFIXES = {".py", ".java"}


def scan(root: Path):
    root = root.resolve()
    for path in sorted(root.rglob("*")):
        if any(part in EXCLUDED for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() not in SUFFIXES or path.name.startswith("id_rsa") or not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size > 500_000:
            continue
        raw = path.read_bytes()
        if b"\0" in raw or any(x in raw[:1000].lower() for x in (b"auto-generated", b"do not edit")):
            continue
        yield path.relative_to(root).as_posix(), raw.decode("utf-8", errors="replace"), hashlib.sha256(raw).hexdigest()
