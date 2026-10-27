import json
import sqlite3
from pathlib import Path
from repopilot.ingestion.chunker import Chunk


class Store:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(directory / "meta.sqlite", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, sha256 TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, path TEXT, start_line INTEGER, end_line INTEGER,
          language TEXT, symbol_name TEXT, symbol_kind TEXT, text TEXT, content_hash TEXT, vector TEXT);
        CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
        CREATE INDEX IF NOT EXISTS chunks_path ON chunks(path);
        """)

    def set_state(self, **values):
        with self.db:
            self.db.executemany("INSERT OR REPLACE INTO state VALUES (?,?)", [(k, json.dumps(v)) for k, v in values.items()])

    def state(self):
        return {r["key"]: json.loads(r["value"]) for r in self.db.execute("SELECT * FROM state")}

    def files(self):
        return {r["path"]: r["sha256"] for r in self.db.execute("SELECT * FROM files")}

    def cached_vectors(self):
        return {r["content_hash"]: json.loads(r["vector"]) for r in self.db.execute("SELECT content_hash,vector FROM chunks")}

    def replace_file(self, path: str, sha: str, chunks: list[Chunk], vectors: list[list[float]]):
        with self.db:
            self.db.execute("DELETE FROM chunks WHERE path=?", (path,))
            self.db.execute("INSERT OR REPLACE INTO files VALUES (?,?)", (path, sha))
            self.db.executemany("INSERT INTO chunks(path,start_line,end_line,language,symbol_name,symbol_kind,text,content_hash,vector) VALUES (?,?,?,?,?,?,?,?,?)",
                [(c.path,c.start_line,c.end_line,c.language,c.symbol_name,c.symbol_kind,c.text,c.content_hash,json.dumps(v)) for c,v in zip(chunks,vectors)])

    def remove_file(self, path):
        with self.db:
            self.db.execute("DELETE FROM chunks WHERE path=?", (path,))
            self.db.execute("DELETE FROM files WHERE path=?", (path,))

    def chunks(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM chunks ORDER BY id")]
