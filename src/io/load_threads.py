from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List

from src.schemas import Thread


EXPECTED_FIELDS = {
    "thread_id",
    "subreddit",
    "title",
    "body",
    "comments",
    "created_utc",
    "url",
    "author",
}


def _normalize_comments(raw) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    # try to parse json list
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass
    # fallback split on delimiter
    if isinstance(raw, str) and "||" in raw:
        return [p.strip() for p in raw.split("||") if p.strip()]
    return [str(raw)]


def _record_to_thread(record: dict) -> Thread:
    comments = _normalize_comments(record.get("comments"))
    created = record.get("created_utc")
    return Thread(
        thread_id=str(record.get("thread_id")),
        subreddit=str(record.get("subreddit", "")),
        title=str(record.get("title", "")),
        body=str(record.get("body", "")),
        comments=comments,
        created_utc=created,
        url=record.get("url"),
        author=record.get("author"),
        metadata={k: v for k, v in record.items() if k not in EXPECTED_FIELDS},
    )


def load_jsonl(path: Path) -> List[Thread]:
    threads: List[Thread] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            threads.append(_record_to_thread(obj))
    return threads


def load_csv(path: Path) -> List[Thread]:
    threads: List[Thread] = []
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            threads.append(_record_to_thread(row))
    return threads


def load_threads(paths: Iterable[str | Path]) -> List[Thread]:
    collected: List[Thread] = []
    for p in paths:
        path = Path(p)
        if path.suffix.lower() == ".jsonl":
            collected.extend(load_jsonl(path))
        elif path.suffix.lower() == ".csv":
            collected.extend(load_csv(path))
        else:
            raise ValueError(f"Unsupported file type: {path}")
    return collected
