from pathlib import Path, PureWindowsPath


def guarded_path(root: Path, requested: str) -> Path:
    candidate = PureWindowsPath(requested)
    if not requested or Path(requested).is_absolute() or candidate.is_absolute() or candidate.drive or requested.startswith(("/", "\\")):
        raise ValueError("Use a repository-relative path")
    root = root.resolve()
    result = (root / requested.replace("\\", "/")).resolve()
    if not result.is_relative_to(root) or not result.is_file():
        raise ValueError("File does not exist inside repository")
    return result
