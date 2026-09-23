from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from src.config import get_settings
from src.io.load_threads import load_threads
from src.io.save_artifacts import save_json, save_markdown
from src.models.llm_client import get_default_llm_client
from src.pipeline.build_loose_case_card import build_loose_outcome
from src.pipeline.build_risk_gate import build_risk_gate_decision
from src.pipeline.prompt_method_registry import get_prompt_method, list_prompt_methods
from src.schemas import LooseOutcome

app = typer.Typer(help="Run loose case-card generation with no-card gating")
console = Console()


@app.command()
def main(
    input_paths: List[Path] = typer.Argument(..., help="Input JSONL/CSV files"),
    output_dir: Path = typer.Option(Path("outputs_loose"), help="Base output directory"),
    prompt_method: str = typer.Option("loose_v1", help="Prompt method"),
    workers: int = typer.Option(8, help="Parallel workers"),
    gate_model: Optional[str] = typer.Option(None, help="Override gate model name"),
    casecard_model: Optional[str] = typer.Option(None, help="Override case-card model name"),
):
    settings = get_settings()
    method = get_prompt_method(prompt_method)
    gate_model_name = gate_model or settings.gate_model_name
    case_model_name = casecard_model or settings.casecard_model_name

    threads = load_threads(input_paths)
    console.log(f"Loaded {len(threads)} sources")

    method_root = output_dir / method.name
    outcomes_dir = method_root / "outcomes"
    cards_dir = method_root / "case_cards"
    skipped_dir = method_root / "skipped"
    reports_dir = method_root / "reports"
    outcomes_dir.mkdir(parents=True, exist_ok=True)
    cards_dir.mkdir(parents=True, exist_ok=True)
    skipped_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0
    outcomes: List[LooseOutcome] = []

    def _process(source):
        gate_client = get_default_llm_client(gate_model_name, settings.llm_api_key)
        case_client = get_default_llm_client(case_model_name, settings.llm_api_key)
        gate = build_risk_gate_decision(source, method, gate_client)
        outcome = build_loose_outcome(
            source=source,
            gate_decision=gate,
            prompt_method=method,
            llm=case_client,
            settings=settings,
            model_name=case_model_name,
        )
        return source.thread_id, outcome

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(_process, source) for source in threads]
        by_id = {}
        for fut in concurrent.futures.as_completed(futures):
            source_id, outcome = fut.result()
            by_id[source_id] = outcome

    for source in threads:
        outcome = by_id[source.thread_id]
        outcomes.append(outcome)
        save_json(outcome.model_dump(), outcomes_dir / f"{source.thread_id}.json")

        if outcome.status == "case_card_created" and outcome.case_card:
            created += 1
            save_json(outcome.case_card.model_dump(), cards_dir / f"{outcome.case_card.case_id}.json")
        else:
            skipped += 1
            save_json(outcome.model_dump(), skipped_dir / f"{source.thread_id}.json")

    report = {
        "prompt_method": method.name,
        "gate_model": gate_model_name,
        "casecard_model": case_model_name,
        "total_sources": len(threads),
        "case_cards_created": created,
        "no_case_card": skipped,
        "available_prompt_methods": list_prompt_methods(),
    }
    save_json(report, reports_dir / "summary.json")

    md = (
        f"# Loose Case Card Run\n\n"
        f"- prompt_method: {method.name}\n"
        f"- gate_model: {gate_model_name}\n"
        f"- casecard_model: {case_model_name}\n"
        f"- total_sources: {len(threads)}\n"
        f"- case_cards_created: {created}\n"
        f"- no_case_card: {skipped}\n"
    )
    save_markdown(md, reports_dir / "summary.md")

    console.log(f"Completed run: created={created}, skipped={skipped}")


if __name__ == "__main__":
    app()
