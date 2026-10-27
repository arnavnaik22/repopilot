from pathlib import Path
from repopilot.agent.path_guard import guarded_path
from repopilot.schemas import Citation


def verify(root: Path, requested: list[dict], seen: dict[str,list[tuple[int,int]]]):
    checked = []
    for item in requested[:20]:
        try:
            file = guarded_path(root, item["path"])
            path = file.relative_to(root.resolve()).as_posix()
            start, end = int(item["start_line"]), int(item["end_line"])
            lines = file.read_text(encoding="utf-8",errors="replace").splitlines()
            if not (1 <= start <= end <= len(lines) and end-start < 200):
                continue
            if not any(start <= b and end >= a for a,b in seen.get(path,[])):
                continue
            checked.append(Citation(path=path,start_line=start,end_line=end,snippet="\n".join(lines[start-1:end]),verified=True))
        except (ValueError,KeyError,TypeError,OSError):
            continue
    return checked
