from __future__ import annotations

import json
from typing import Dict

from rich.console import Console
from rich.table import Table

console = Console()


def print_metrics_table(metrics: Dict[str, object]) -> None:
    table = Table(title="Novelty Evaluation")
    table.add_column("Metric")
    table.add_column("Value")
    for key, value in metrics.items():
        if isinstance(value, (dict, list)):
            val = json.dumps(value)
        else:
            val = f"{value:.3f}" if isinstance(value, float) else str(value)
        table.add_row(key, val)
    console.print(table)


def save_confusion(confusion: Dict[str, Dict[str, int]], path) -> None:
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(confusion, indent=2))
    console.log(f"saved confusion table to {path}")
