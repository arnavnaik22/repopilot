"""Line-preserving Python AST chunks and conservative Java windows."""
import ast
import hashlib
import re
from dataclasses import dataclass


@dataclass
class Chunk:
    path: str
    start_line: int
    end_line: int
    language: str
    symbol_name: str
    symbol_kind: str
    text: str
    content_hash: str = ""

    def __post_init__(self):
        self.content_hash = hashlib.sha256(self.text.encode()).hexdigest()


def _emit(lines, path, start, end, language, name, kind):
    # Windows retain exact source lines. Every result satisfies the line invariant.
    for a in range(start, end + 1, 50):
        b = min(end, a + 59)
        yield Chunk(path, a, b, language, name, kind if a == start else "window", "\n".join(lines[a - 1:b]))
        if b == end:
            break


def chunk(path: str, source: str) -> list[Chunk]:
    lines = source.splitlines()
    if not lines:
        return []
    if path.endswith(".java"):
        return _java(path, lines)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return list(_emit(lines, path, 1, len(lines), "python", "module", "window"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    result, cursor = [], 1
    for node in nodes:
        start = min([node.lineno] + [d.lineno for d in node.decorator_list])
        if cursor < start:
            result.extend(_emit(lines, path, cursor, start - 1, "python", "module", "module"))
        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        if isinstance(node, ast.ClassDef) and node.end_lineno - start > 80:
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            first = min((n.lineno for n in methods), default=node.end_lineno + 1)
            result.extend(_emit(lines, path, start, first - 1, "python", node.name, "class")) if first > start else None
            for method in methods:
                a = min([method.lineno] + [d.lineno for d in method.decorator_list])
                result.extend(_emit(lines, path, a, method.end_lineno, "python", f"{node.name}.{method.name}", "method"))
        else:
            result.extend(_emit(lines, path, start, node.end_lineno, "python", node.name, kind))
        cursor = node.end_lineno + 1
    if cursor <= len(lines):
        result.extend(_emit(lines, path, cursor, len(lines), "python", "module", "module"))
    return result


JAVA_DECL = re.compile(r"\b(class|interface|enum)\s+(\w+)|\b(?:public|private|protected|static|final|synchronized|abstract|native|\s)+[\w<>\[\], ?]+\s+(\w+)\s*\([^;]*\)\s*(?:throws\s+[\w, ]+)?\s*\{")


def _java(path, lines):
    # A heuristic parser: take declarations as anchors, then preserve exact windows.
    starts = [(i, m.group(2) or m.group(3), "class" if m.group(2) else "method") for i, line in enumerate(lines, 1) if (m := JAVA_DECL.search(line))]
    if not starts:
        return list(_emit(lines, path, 1, len(lines), "java", "module", "window"))
    result = []
    if starts[0][0] > 1:
        result.extend(_emit(lines, path, 1, starts[0][0] - 1, "java", "module", "module"))
    for i, (start, name, kind) in enumerate(starts):
        end = (starts[i + 1][0] - 1) if i + 1 < len(starts) else len(lines)
        result.extend(_emit(lines, path, start, end, "java", name, kind))
    return result
