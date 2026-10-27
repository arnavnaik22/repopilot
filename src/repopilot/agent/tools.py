import ast
import re
from pathlib import Path
from repopilot.agent.path_guard import guarded_path
from repopilot.ingestion.scanner import scan

SCHEMAS = [
    {"name":"search_code","description":"Search indexed code and return source ranges.","input_schema":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}},
    {"name":"read_file","description":"Read numbered lines from a repository file.","input_schema":{"type":"object","properties":{"path":{"type":"string"},"start_line":{"type":"integer"},"end_line":{"type":"integer"}},"required":["path","start_line","end_line"]}},
    {"name":"find_references","description":"Find definitions and usages of a symbol.","input_schema":{"type":"object","properties":{"symbol_name":{"type":"string"}},"required":["symbol_name"]}},
    {"name":"submit_answer","description":"Submit the final answer with citations and evidence status.","input_schema":{"type":"object","properties":{"answer":{"type":"string"},"evidence_status":{"type":"string","enum":["supported","inferred","insufficient"]},"citations":{"type":"array","items":{"type":"object","properties":{"path":{"type":"string"},"start_line":{"type":"integer"},"end_line":{"type":"integer"}},"required":["path","start_line","end_line"]}}},"required":["answer","evidence_status","citations"]}},
]


class InvestigationTools:
    def __init__(self, root: Path, retriever, k=8, mode="hybrid"):
        self.root, self.retriever, self.k, self.mode = root, retriever, k, mode
        self.seen_ranges: dict[str, list[tuple[int,int]]] = {}

    def _remember(self, path, start, end):
        self.seen_ranges.setdefault(path, []).append((start,end))

    def search_code(self, query: str):
        hits = self.retriever.search(query, self.k, self.mode)
        for h in hits:
            self._remember(h.path,h.start_line,min(h.end_line,h.start_line+39))
        return "\n\n".join(f"{h.path}:{h.start_line}-{h.end_line}\n" + "\n".join(f"{h.start_line+i}: {line}" for i,line in enumerate(h.snippet.splitlines()[:40])) for h in hits) or "No results"

    def read_file(self, path: str, start_line: int, end_line: int):
        file = guarded_path(self.root, path)
        lines = file.read_text(encoding="utf-8", errors="replace").splitlines()
        if not isinstance(start_line,int) or not isinstance(end_line,int) or start_line < 1 or end_line < start_line or end_line-start_line >= 200:
            raise ValueError("Invalid line range; request at most 200 lines")
        end_line = min(end_line,len(lines))
        if start_line > end_line:
            raise ValueError("Start line exceeds file length")
        rel = file.relative_to(self.root.resolve()).as_posix()
        self._remember(rel,start_line,end_line)
        return "\n".join(f"{i}: {lines[i-1]}" for i in range(start_line,end_line+1))

    def find_references(self, symbol_name: str):
        if not re.fullmatch(r"[A-Za-z_]\w*", symbol_name):
            raise ValueError("Provide one identifier")
        hits = []
        for path, source, _ in scan(self.root):
            if path.endswith(".py"):
                try:
                    tree = ast.parse(source)
                    for n in ast.walk(tree):
                        name = n.id if isinstance(n, ast.Name) else n.attr if isinstance(n, ast.Attribute) else n.name if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) else None
                        if name == symbol_name:
                            kind = "definition" if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) else "usage"
                            hits.append((path,n.lineno,kind,"exact"))
                    continue
                except SyntaxError:
                    pass
            for i,line in enumerate(source.splitlines(),1):
                if re.search(r"\b"+re.escape(symbol_name)+r"\b",line):
                    hits.append((path,i,"usage","approximate"))
        hits.sort(key=lambda x:(x[2]!="definition",x[0],x[1]))
        for path,line,_,_ in hits[:30]:
            self._remember(path,line,line)
        return "\n".join(f"{path}:{line} {kind} ({confidence})" for path,line,kind,confidence in hits[:30]) or "No references"

    def execute(self, name, args):
        if name not in {"search_code","read_file","find_references"}:
            raise ValueError("Unknown tool")
        return getattr(self,name)(**args)
