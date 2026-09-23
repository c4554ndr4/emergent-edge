from __future__ import annotations

import concurrent.futures
import json
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from src.config import get_settings
from src.io.load_threads import load_threads
from src.io.save_artifacts import save_json
from src.pipeline.build_case_card import build_case_card
from src.pipeline.build_risk_gate import build_risk_gate_decision
from src.pipeline.build_pattern_cards import build_pattern_cards
from src.pipeline.escalate_context import escalate_if_needed
from src.pipeline.judge_novelty import judge_novelty
from src.pipeline.llm_origin_gate import decide_llm_origin
from src.pipeline.prompt_method_registry import get_prompt_method
from src.pipeline.propose_pattern_cards import (
    merge_pattern_cards,
    propose_pattern_cards_from_watchlist,
)
from src.pipeline.retrieve_similar_cards import construct_vector_store, make_evidence_packet, retrieve_for_candidate
from src.retrieval.canonicalize import (
    canonicalize_case_card_for_retrieval,
    canonicalize_pattern_card_for_retrieval,
)
from src.models.llm_client import get_default_llm_client
from src.schemas import CaseCard, NoveltyDecision, PatternCard

console = Console()
app = typer.Typer(help="Run open-set novelty detection pipeline")


def _load_case_cards(path: Optional[Path]) -> List[CaseCard]:
    if path is None or not path.exists():
        return []
    cards: List[CaseCard] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            cards.append(CaseCard.model_validate(obj))
    return cards


def _load_pattern_cards(path: Optional[Path]) -> List[PatternCard]:
    if path is None or not path.exists():
        return []
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return [PatternCard.model_validate(x) for x in data]
    return [PatternCard.model_validate(data)]


@app.command()
def main(
    input_paths: List[Path] = typer.Argument(..., help="Input JSONL/CSV files"),
    known_case_cards: Optional[Path] = typer.Option(
        None, help="Library case cards JSONL (defaults to curated live set)"
    ),
    pattern_cards_path: Optional[Path] = typer.Option(
        None, help="Pattern cards JSON list (defaults to configured library path)"
    ),
    output_dir: Path = typer.Option(Path("outputs"), help="Where to write outputs"),
    write_watchlist_log: bool = typer.Option(
        True, "--write-watchlist-log/--no-write-watchlist-log", help="Append novel-decision rows to live log"
    ),
    watchlist_log_path: Path = typer.Option(
        Path("outputs/live_set/watchlist_decisions_log.jsonl"),
        help="JSONL log of novel decisions (new_pattern and legacy labels) with case snapshots",
    ),
    proposal_min_support: int = typer.Option(
        2, help="Minimum novel cases needed to emit a pattern proposal"
    ),
    proposal_output_path: Path = typer.Option(
        Path("outputs/pattern_cards/live_pattern_proposals.json"),
        help="Where to write proposed live pattern cards",
    ),
    auto_promote_pattern_proposals: bool = typer.Option(
        False,
        "--auto-promote-pattern-proposals/--no-auto-promote-pattern-proposals",
        help="Automatically merge live novel-pattern proposals into the active pattern library",
    ),
    enable_origin_gate: bool = typer.Option(
        False,
        "--enable-origin-gate/--no-enable-origin-gate",
        help="Run AI-written origin gate before creating case cards",
    ),
    origin_gate_model: Optional[str] = typer.Option(
        None, help="Override model for AI-written origin gate"
    ),
    origin_bonus_model: Optional[str] = typer.Option(
        None, help="Override model for post-judgment AI-written extent classification"
    ),
    keep_only_ai_written: bool = typer.Option(
        True,
        "--keep-only-ai-written/--keep-non-unknown-origin",
        help="If enabled, only keep llm_like sources and drop human_like/unknown",
    ),
    prune_empty_patterns: bool = typer.Option(
        True,
        "--prune-empty-patterns/--no-prune-empty-patterns",
        help="Remove non-core patterns that have zero active cases after filtering",
    ),
    preserve_pattern_families: List[str] = typer.Option(
        ["structured_interaction"],
        help="Pattern families never pruned even if they currently have zero active cases",
    ),
    enable_risk_gate: bool = typer.Option(
        False,
        "--enable-risk-gate/--no-enable-risk-gate",
        help="Run liability/worthiness gate before creating case cards",
    ),
    prompt_method: Optional[str] = typer.Option(
        None,
        help="Prompt method for the liability/worthiness gate",
    ),
    workers: int = typer.Option(16, help="Parallel thread workers for per-case processing"),
):
    settings = get_settings()
    if known_case_cards is None:
        known_case_cards = settings.default_known_case_cards_path
    if pattern_cards_path is None:
        pattern_cards_path = settings.default_pattern_cards_path

    threads = load_threads(input_paths)
    console.log(f"Loaded {len(threads)} threads")
    console.log(f"Known case-card library: {known_case_cards}")
    console.log(f"Pattern-card library: {pattern_cards_path}")

    library_cases = _load_case_cards(known_case_cards)
    if library_cases:
        console.log(f"Loaded {len(library_cases)} known case cards")

    pattern_cards = _load_pattern_cards(pattern_cards_path)
    if not pattern_cards:
        pattern_cards = build_pattern_cards(training_cases=library_cases)
        console.log(f"Built {len(pattern_cards)} pattern cards from seeds")

    # ensure canonical text set
    for c in library_cases:
        c.canonical_text = canonicalize_case_card_for_retrieval(
            c, settings.case_card_canonicalization_version
        )
    for p in pattern_cards:
        p.canonical_text = canonicalize_pattern_card_for_retrieval(
            p, settings.pattern_card_canonicalization_version
        )

    store = construct_vector_store(library_cases, pattern_cards)
    raw_threads = {t.thread_id: t for t in threads}
    gate_prompt_method = get_prompt_method(prompt_method or settings.default_prompt_method)

    output_dir.mkdir(parents=True, exist_ok=True)
    case_dir = output_dir / "case_cards"
    decision_dir = output_dir / "decisions"
    dropped_dir = output_dir / "dropped_by_origin"
    case_dir.mkdir(parents=True, exist_ok=True)
    decision_dir.mkdir(parents=True, exist_ok=True)
    dropped_dir.mkdir(parents=True, exist_ok=True)

    decisions: List[NoveltyDecision] = []
    case_lookup: dict[str, CaseCard] = {}
    processed_threads = 0
    dropped_by_origin = 0
    dropped_by_risk_gate = 0

    def _process_thread(thread):
        origin_pre_gate = None
        risk_gate = None
        if enable_origin_gate:
            origin_pre_gate = decide_llm_origin(
                thread,
                model_name=origin_gate_model or settings.gate_model_name,
                api_key=settings.llm_api_key,
                keep_only_llm_like=keep_only_ai_written,
            )
            if not origin_pre_gate.should_keep:
                return {
                    "status": "dropped_by_origin",
                    "thread_id": thread.thread_id,
                    "source_url": thread.url,
                    "origin_gate_pre": {
                        "verdict": origin_pre_gate.verdict,
                        "llm_written_extent": origin_pre_gate.llm_written_extent,
                        "should_keep": origin_pre_gate.should_keep,
                        "confidence": origin_pre_gate.confidence,
                        "rationale": origin_pre_gate.rationale,
                    },
                }

        if enable_risk_gate:
            risk_gate = build_risk_gate_decision(
                thread,
                prompt_method=gate_prompt_method,
                llm=get_default_llm_client(settings.gate_model_name, settings.llm_api_key),
            )
            if not risk_gate.should_create_case_card:
                return {
                    "status": "dropped_by_risk_gate",
                    "thread_id": thread.thread_id,
                    "source_url": thread.url,
                    "origin_gate_pre": (
                        {
                            "verdict": origin_pre_gate.verdict,
                            "llm_written_extent": origin_pre_gate.llm_written_extent,
                            "should_keep": origin_pre_gate.should_keep,
                            "confidence": origin_pre_gate.confidence,
                            "rationale": origin_pre_gate.rationale,
                        }
                        if origin_pre_gate is not None
                        else None
                    ),
                    "risk_gate": risk_gate.model_dump(),
                }

        candidate = build_case_card(thread)
        case_hits, pattern_hits = retrieve_for_candidate(candidate, store)
        case_by_id = {c.case_id: c for c in library_cases}
        pattern_by_id = {p.pattern_id: p for p in pattern_cards}
        retrieved_cases = [case_by_id[h["id"]] for h in case_hits if h["id"] in case_by_id]
        retrieved_patterns = [pattern_by_id[h["id"]] for h in pattern_hits if h["id"] in pattern_by_id]
        case_scores = {h["id"]: float(h.get("score", 0.0)) for h in case_hits}
        pattern_scores = {h["id"]: float(h.get("score", 0.0)) for h in pattern_hits}

        decision = judge_novelty(
            candidate,
            retrieved_cases,
            retrieved_patterns,
            case_scores=case_scores,
            pattern_scores=pattern_scores,
        )
        if decision.needs_more_context:
            decision = escalate_if_needed(
                candidate,
                decision,
                raw_threads,
                lambda cand, rc, rp: judge_novelty(cand, rc, rp, case_scores=case_scores, pattern_scores=pattern_scores),
                retrieved_cases,
                retrieved_patterns,
            )

        # Bonus endpoint classification: track whether the final candidate appears fully/partially AI-written.
        origin_bonus = decide_llm_origin(
            thread,
            model_name=origin_bonus_model or origin_gate_model or settings.gate_model_name,
            api_key=settings.llm_api_key,
            keep_only_llm_like=False,
        )

        combined = {
            "decision": decision.model_dump(),
            "retrieval": {
                "case_hits": case_hits,
                "pattern_hits": pattern_hits,
            },
            "origin_gate_pre": (
                {
                    "verdict": origin_pre_gate.verdict,
                    "llm_written_extent": origin_pre_gate.llm_written_extent,
                    "should_keep": origin_pre_gate.should_keep,
                    "confidence": origin_pre_gate.confidence,
                    "rationale": origin_pre_gate.rationale,
                }
                if origin_pre_gate is not None
                else None
            ),
            "risk_gate": risk_gate.model_dump() if risk_gate is not None else None,
            "ai_written_judge_bonus": {
                "verdict": origin_bonus.verdict,
                "llm_written_extent": origin_bonus.llm_written_extent,
                "should_keep": origin_bonus.should_keep,
                "confidence": origin_bonus.confidence,
                "rationale": origin_bonus.rationale,
            },
        }
        return {
            "status": "processed",
            "thread_id": thread.thread_id,
            "candidate": candidate,
            "decision": decision,
            "combined": combined,
        }

    max_workers = max(1, workers)
    if max_workers == 1:
        results = [_process_thread(thread) for thread in threads]
    else:
        console.log(f"Running with parallel workers={max_workers}")
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_process_thread, thread) for thread in threads]
            for fut in concurrent.futures.as_completed(futures):
                results.append(fut.result())

    for result in results:
        processed_threads += 1
        if result["status"] == "dropped_by_origin":
            dropped_by_origin += 1
            save_json(
                {
                    "thread_id": result["thread_id"],
                    "source_url": result["source_url"],
                    "origin_gate": result["origin_gate_pre"],
                },
                dropped_dir / f"{result['thread_id']}.json",
            )
            continue
        if result["status"] == "dropped_by_risk_gate":
            dropped_by_risk_gate += 1
            save_json(
                {
                    "thread_id": result["thread_id"],
                    "source_url": result["source_url"],
                    "origin_gate": result["origin_gate_pre"],
                    "risk_gate": result["risk_gate"],
                },
                dropped_dir / f"{result['thread_id']}.json",
            )
            continue

        candidate = result["candidate"]
        decision = result["decision"]
        combined = result["combined"]
        case_path = case_dir / f"{candidate.case_id}.json"
        decision_path = decision_dir / f"{candidate.case_id}.json"
        save_json(candidate.model_dump(), case_path)
        save_json(combined, decision_path)
        decisions.append(decision)
        case_lookup[candidate.case_id] = candidate

    console.log(
        "Completed "
        f"{len(decisions)} cases (processed_threads={processed_threads}, "
        f"dropped_by_origin={dropped_by_origin}, dropped_by_risk_gate={dropped_by_risk_gate})"
    )

    if write_watchlist_log:
        watchlist_log_path.parent.mkdir(parents=True, exist_ok=True)
        seen_case_ids: set[str] = set()
        if watchlist_log_path.exists():
            with watchlist_log_path.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    cid = row.get("case_id")
                    if isinstance(cid, str):
                        seen_case_ids.add(cid)

        with watchlist_log_path.open("a") as f:
            for d in decisions:
                if d.verdict not in {"new_pattern", "watchlist_candidate", "candidate_new_pattern"}:
                    continue
                if d.case_id in seen_case_ids:
                    continue
                c = case_lookup.get(d.case_id)
                if c is None:
                    continue
                row = {
                    "case_id": d.case_id,
                    "source_thread_id": c.source_thread_id,
                    "decision": d.model_dump(mode="json"),
                    "case_card": c.model_dump(mode="json"),
                }
                f.write(json.dumps(row) + "\n")
                seen_case_ids.add(d.case_id)
        console.log(f"Updated novel decision log: {watchlist_log_path}")

    # Build novel-case hypotheses into proposal PatternCards.
    watch_case_cards: dict[str, CaseCard] = {}
    watch_decisions: list[NoveltyDecision] = []
    if watchlist_log_path.exists():
        with watchlist_log_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    d = NoveltyDecision.model_validate(row.get("decision", {}))
                    c = CaseCard.model_validate(row.get("case_card", {}))
                except Exception:
                    continue
                watch_decisions.append(d)
                watch_case_cards[d.case_id] = c

    proposals = propose_pattern_cards_from_watchlist(
        case_cards=watch_case_cards,
        decisions=watch_decisions,
        min_support=max(1, proposal_min_support),
    )
    proposal_output_path.parent.mkdir(parents=True, exist_ok=True)
    save_json([p.model_dump(mode="json") for p in proposals], proposal_output_path)
    console.log(f"Wrote {len(proposals)} live novel pattern proposals -> {proposal_output_path}")

    if auto_promote_pattern_proposals:
        promoted = merge_pattern_cards(pattern_cards, proposals)
        if pattern_cards_path is not None:
            if prune_empty_patterns:
                promoted = _prune_empty_patterns(
                    promoted,
                    decisions=decisions,
                    library_case_ids={c.case_id for c in library_cases},
                    new_case_ids=set(case_lookup.keys()),
                    preserve_families=set(preserve_pattern_families),
                )
            pattern_cards_path.parent.mkdir(parents=True, exist_ok=True)
            save_json([p.model_dump(mode="json") for p in promoted], pattern_cards_path)
            console.log(
                f"Auto-promoted {len(proposals)} novel proposals into active pattern library -> {pattern_cards_path} (total={len(promoted)})"
            )

    save_json(
        {
            "threads_total": len(threads),
            "threads_processed": processed_threads,
            "threads_dropped_by_origin_gate": dropped_by_origin,
            "threads_dropped_by_risk_gate": dropped_by_risk_gate,
            "decisions_emitted": len(decisions),
            "origin_gate_enabled": enable_origin_gate,
            "risk_gate_enabled": enable_risk_gate,
            "prompt_method": gate_prompt_method.name,
            "keep_only_ai_written": keep_only_ai_written,
        },
        output_dir / "run_summary.json",
    )


def _prune_empty_patterns(
    patterns: List[PatternCard],
    decisions: List[NoveltyDecision],
    library_case_ids: set[str],
    new_case_ids: set[str],
    preserve_families: set[str],
) -> List[PatternCard]:
    active_case_ids = set(library_case_ids) | set(new_case_ids)
    attached_counts: dict[str, int] = {}

    for d in decisions:
        ids = set(d.supporting_pattern_ids)
        if d.closest_pattern:
            ids.add(d.closest_pattern)
        for pid in ids:
            attached_counts[pid] = attached_counts.get(pid, 0) + 1

    kept: List[PatternCard] = []
    for p in patterns:
        if p.family in preserve_families:
            kept.append(p)
            continue
        exemplar_count = sum(1 for cid in p.exemplar_case_ids if cid in active_case_ids)
        attached = attached_counts.get(p.pattern_id, 0)
        if exemplar_count > 0 or attached > 0:
            kept.append(p)
    return kept


if __name__ == "__main__":
    app()
