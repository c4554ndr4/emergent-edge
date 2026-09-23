from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptMethod:
    name: str
    gate_prompt_path: Path
    case_card_prompt_path: Path
    description: str


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts" / "loose"

PROMPT_METHODS: dict[str, PromptMethod] = {
    "loose_v1": PromptMethod(
        name="loose_v1",
        gate_prompt_path=PROMPTS_DIR / "gate_loose_v1.txt",
        case_card_prompt_path=PROMPTS_DIR / "case_card_loose_v1.txt",
        description="Balanced loose risk monitoring prompt set",
    ),
    "liability_heavy_v1": PromptMethod(
        name="liability_heavy_v1",
        gate_prompt_path=PROMPTS_DIR / "gate_liability_heavy_v1.txt",
        case_card_prompt_path=PROMPTS_DIR / "case_card_liability_heavy_v1.txt",
        description="Liability-forward tighter extraction prompt set",
    ),
    "continuous_v2": PromptMethod(
        name="continuous_v2",
        gate_prompt_path=PROMPTS_DIR / "gate_continuous_v2.txt",
        case_card_prompt_path=PROMPTS_DIR / "case_card_liability_heavy_v1.txt",
        description="Strict continuous monitoring gate for liability or genuinely strange edge cases",
    ),
}


def get_prompt_method(name: str) -> PromptMethod:
    if name not in PROMPT_METHODS:
        known = ", ".join(sorted(PROMPT_METHODS))
        raise ValueError(f"Unknown prompt method '{name}'. Known methods: {known}")
    return PROMPT_METHODS[name]


def list_prompt_methods() -> list[str]:
    return sorted(PROMPT_METHODS)
