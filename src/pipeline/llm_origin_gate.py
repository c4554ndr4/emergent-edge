from __future__ import annotations

import json
import re
from dataclasses import dataclass

from src.io.json_parsing import parse_json_from_text
from src.models.llm_client import LLMClient, get_default_llm_client
from src.schemas import Thread


@dataclass(frozen=True)
class LLMOriginDecision:
    source_id: str
    verdict: str  # "llm_like" | "human_like" | "unknown"
    llm_written_extent: str  # "full" | "partial" | "none" | "unknown"
    should_keep: bool
    confidence: float
    rationale: str


SYSTEM_PROMPT = (
    "You are a strict authorship-style gate for monitoring pipelines.\n"
    "Classify whether a post is primarily AI-written/AI-assisted style (llm_like) or primarily human-authored style (human_like).\n"
    "Also classify extent of AI-written content.\n"
    "Return JSON only with keys: verdict, llm_written_extent, confidence, rationale.\n"
    "verdict must be one of: llm_like, human_like, unknown.\n"
    "llm_written_extent must be one of: full, partial, none, unknown.\n"
    "Use full when most of the text reads LLM-written, partial when mixed human+LLM, none when human-authored, unknown when insufficient evidence.\n"
    "Use unknown if evidence is mixed or insufficient."
)


def decide_llm_origin(
    source: Thread,
    llm: LLMClient | None = None,
    model_name: str | None = None,
    api_key: str | None = None,
    keep_only_llm_like: bool = True,
) -> LLMOriginDecision:
    text = _compose_text(source)
    fallback = _heuristic_origin(source, keep_only_llm_like=keep_only_llm_like)
    client = llm or get_default_llm_client(model=model_name, api_key=api_key)

    prompt = (
        "Classify this post and return JSON only.\n"
        "Schema:\n"
        "{\"verdict\":\"llm_like|human_like|unknown\",\"llm_written_extent\":\"full|partial|none|unknown\",\"confidence\":0.0,\"rationale\":\"...\"}\n\n"
        f"Post:\n{text[:5000]}"
    )
    try:
        raw = client.generate(prompt, system_prompt=SYSTEM_PROMPT, max_tokens=240)
        obj = parse_json_from_text(raw)
        merged = _merge_obj(source.thread_id, obj, keep_only_llm_like=keep_only_llm_like)
        return merged
    except Exception:
        return fallback


def _compose_text(source: Thread) -> str:
    blob = {
        "thread_id": source.thread_id,
        "subreddit": source.subreddit,
        "title": source.title,
        "body": source.body,
        "comments": source.comments[:8],
        "author": source.author,
        "url": source.url,
    }
    return json.dumps(blob, ensure_ascii=True, indent=2)


def _merge_obj(source_id: str, obj: object, keep_only_llm_like: bool) -> LLMOriginDecision:
    if not isinstance(obj, dict):
        return LLMOriginDecision(
            source_id=source_id,
            verdict="unknown",
            llm_written_extent="unknown",
            should_keep=not keep_only_llm_like,
            confidence=0.2,
            rationale="origin detector parse failed",
        )
    verdict = str(obj.get("verdict", "unknown")).strip().lower()
    if verdict not in {"llm_like", "human_like", "unknown"}:
        verdict = "unknown"
    extent = str(obj.get("llm_written_extent", "")).strip().lower()
    if extent not in {"full", "partial", "none", "unknown"}:
        if verdict == "llm_like":
            extent = "full"
        elif verdict == "human_like":
            extent = "none"
        else:
            extent = "unknown"
    confidence = obj.get("confidence", 0.2)
    if not isinstance(confidence, (int, float)):
        confidence = 0.2
    confidence = max(0.0, min(1.0, float(confidence)))
    rationale = str(obj.get("rationale", ""))
    if not rationale:
        rationale = "origin detector response"
    should_keep = verdict == "llm_like" if keep_only_llm_like else verdict != "unknown"
    return LLMOriginDecision(
        source_id=source_id,
        verdict=verdict,
        llm_written_extent=extent,
        should_keep=should_keep,
        confidence=confidence,
        rationale=rationale[:280],
    )


def _heuristic_origin(source: Thread, keep_only_llm_like: bool) -> LLMOriginDecision:
    text = " ".join([source.title or "", source.body or "", " ".join(source.comments or [])]).lower()
    llm_style_markers = [
        r"\bhere(?:'s| is) (?:a|the)\b",
        r"\bstep(?:\s|-)?by(?:\s|-)?step\b",
        r"\bkey takeaways?\b",
        r"\bin conclusion\b",
        r"\bi cannot assist with\b",
        r"\bas an ai\b",
        r"\bfirst[, ]+second[, ]+third\b",
        r"\b###\b",
    ]
    human_style_markers = [
        r"\bi\b",
        r"\bmy\b",
        r"\bimo\b",
        r"\bidk\b",
        r"\blol\b",
        r"\bwtf\b",
        r"\bngl\b",
        r"\bcan'?t\b",
    ]
    llm_hits = sum(1 for rx in llm_style_markers if re.search(rx, text))
    human_hits = sum(1 for rx in human_style_markers if re.search(rx, text))
    if llm_hits >= human_hits + 2:
        verdict = "llm_like"
        extent = "full"
        confidence = 0.62
        rationale = "heuristic llm-style structure markers dominate"
    elif human_hits >= llm_hits + 2:
        verdict = "human_like"
        extent = "none"
        confidence = 0.62
        rationale = "heuristic conversational human markers dominate"
    else:
        verdict = "unknown"
        extent = "partial"
        confidence = 0.45
        rationale = "heuristic origin signal mixed"

    should_keep = verdict == "llm_like" if keep_only_llm_like else verdict != "unknown"
    return LLMOriginDecision(
        source_id=source.thread_id,
        verdict=verdict,
        llm_written_extent=extent,
        should_keep=should_keep,
        confidence=confidence,
        rationale=rationale,
    )
