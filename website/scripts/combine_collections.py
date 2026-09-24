#!/usr/bin/env python3
"""Build a unified explorer from the public, saved research snapshots.

No model calls. The two layouts have different projections: use a least-squares
similarity transform (optionally reflected) through shared cases, not a claim
that their coordinates or cosine distances were already in a common space.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "public" / "data"


def read(name):
    return json.loads((DATA / name).read_text())


def write(name, value):
    (DATA / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def align(source, target):
    """Return the best 2-D similarity transform for corresponding points."""
    source_mean = sum(source) / len(source)
    target_mean = sum(target) / len(target)
    centered = [point - source_mean for point in source]
    targets = [point - target_mean for point in target]
    fits = []
    for reflect in (False, True):
        points = [point.conjugate() if reflect else point for point in centered]
        denominator = sum(abs(point) ** 2 for point in points)
        if denominator <= 0:
            raise ValueError("Shared cases cannot define a common layout")
        factor = sum(point.conjugate() * goal for point, goal in zip(points, targets)) / denominator
        error = sum(abs(factor * point - goal) ** 2 for point, goal in zip(points, targets))
        fits.append((error, factor, reflect))
    error, factor, reflect = min(fits, key=lambda fit: fit[0])

    def transform(case):
        point = complex(case["x"], case["y"]) - source_mean
        return factor * (point.conjugate() if reflect else point) + target_mean

    return transform, math.sqrt(error / len(source))


def main():
    original = read("case_graph_data.json")
    expanded = read("case_graph_data_v2.json")
    old = {case["case_id"]: case for case in original["cases"]}
    new = {case["case_id"]: case for case in expanded["cases"]}
    shared = sorted(old.keys() & new.keys())
    transform, rms_error = align(
        [complex(new[key]["x"], new[key]["y"]) for key in shared],
        [complex(old[key]["x"], old[key]["y"]) for key in shared],
    )
    cases = copy.deepcopy(original["cases"])
    for case in cases:
        if case["case_id"] in new:
            case["other_recorded_versions"] = [copy.deepcopy(new[case["case_id"]])]
    for case_id, case in new.items():
        if case_id in old:
            continue
        point = transform(case)
        merged = copy.deepcopy(case)
        merged["x"], merged["y"] = point.real, point.imag
        cases.append(merged)

    # Fit the whole collection in the viewport with a uniform scale.
    mid_x = (max(c["x"] for c in cases) + min(c["x"] for c in cases)) / 2
    mid_y = (max(c["y"] for c in cases) + min(c["y"] for c in cases)) / 2
    scale = max(max(abs(c["x"] - mid_x), abs(c["y"] - mid_y)) for c in cases) / .94
    for case in cases:
        case["x"] = (case["x"] - mid_x) / scale
        case["y"] = (case["y"] - mid_y) / scale

    patterns = copy.deepcopy(original["patterns"])
    for key, pattern in expanded["patterns"].items():
        # Richer criteria from the later library; identity is stable across runs.
        patterns[key] = {**patterns.get(key, {}), **copy.deepcopy(pattern)}
    for key, pattern in patterns.items():
        members = [case for case in cases if case["predicted_pattern_id"] == key]
        assert members, f"Pattern {key} has no cases"
        pattern["member_case_ids"] = [case["case_id"] for case in members]
        pattern["x"] = sum(case["x"] for case in members) / len(members)
        pattern["y"] = sum(case["y"] for case in members) / len(members)

    graph = {
        "meta": {
            "case_count": len(cases), "pattern_count": len(patterns),
            "source_files": ["case_graph_data.json", "case_graph_data_v2.json"],
            "deduplication": "One case per case_id; original record is primary; alternate recorded versions retained.",
            "layout": "Saved maps aligned by a similarity transform over shared cases, then uniformly scaled. Not a newly computed embedding projection; distances across snapshots are approximate.",
            "source_projections": [original["meta"]["projection"], expanded["meta"]["projection"]],
            "alignment_shared_cases": len(shared), "alignment_rms_error": rms_error,
            "pattern_positions": "Centroids of displayed member cases",
        },
        "cases": cases, "patterns": patterns,
    }
    write("case_graph_combined.json", graph)

    # Keep each recording bound to its own prompts, pattern library and batch.
    # A repeated case can have more than one recorded walkthrough.
    recordings, samples = {}, []
    for recording_id, name in [("1", "pipeline_demo_data.json"), ("2", "pipeline_demo_data_v2.json")]:
        bundle = read(name)
        recordings[recording_id] = {key: value for key, value in bundle.items() if key != "samples"}
        samples.extend({**sample, "recording_id": recording_id} for sample in bundle["samples"])
    write("pipeline_demo_combined.json", {"recordings": recordings, "samples": samples})
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert set(old) | set(new) == {case["case_id"] for case in cases}
    assert all(case["predicted_pattern_id"] in patterns for case in cases)
    print(f"Combined {len(cases)} cases, {len(patterns)} patterns, {len(samples)} recordings; {len(shared)} shared cases.")


if __name__ == "__main__":
    main()
