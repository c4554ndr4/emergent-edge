from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


def ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_json(obj: Any, path: Path) -> None:
    ensure_dir(path)
    with path.open("w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    console.log(f"saved {path}")


def save_markdown(text: str, path: Path) -> None:
    ensure_dir(path)
    with path.open("w") as f:
        f.write(text)
    console.log(f"saved {path}")
