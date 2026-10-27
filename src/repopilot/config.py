import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def data_dir() -> Path:
    return Path(os.getenv("REPOPILOT_DATA_DIR", "data")).resolve()


def allowed_repo(path: Path) -> bool:
    roots = [x.strip() for x in os.getenv("REPOPILOT_ALLOWED_ROOTS", "").split(",") if x.strip()]
    return not roots or any(path.is_relative_to(Path(root).resolve()) for root in roots)
