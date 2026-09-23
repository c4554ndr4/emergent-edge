from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, ConfigDict

try:  # Prefer pydantic-settings when available
    from pydantic_settings import BaseSettings
except Exception:  # pragma: no cover - fallback for older envs
    from pydantic import BaseModel as BaseSettings  # type: ignore

load_dotenv()


class Settings(BaseSettings):
    """Project-wide settings loaded from environment variables or defaults."""

    data_root: Path = Field(default=Path(os.getenv("DATA_ROOT", "data")))
    output_root: Path = Field(default=Path(os.getenv("OUTPUT_ROOT", "outputs")))
    default_known_case_cards_path: Path = Field(
        default=Path(
            os.getenv(
                "DEFAULT_KNOWN_CASE_CARDS_PATH",
                "examples/known_cases.jsonl",
            )
        )
    )
    default_pattern_cards_path: Path = Field(
        default=Path(os.getenv("DEFAULT_PATTERN_CARDS_PATH", "examples/patterns.json"))
    )
    case_card_prompt_path: Optional[Path] = Field(
        default=Path(os.getenv("CASE_CARD_PROMPT_PATH")) if os.getenv("CASE_CARD_PROMPT_PATH") else None
    )
    novelty_judge_prompt_path: Optional[Path] = Field(
        default=Path(os.getenv("NOVELTY_JUDGE_PROMPT_PATH")) if os.getenv("NOVELTY_JUDGE_PROMPT_PATH") else None
    )
    llm_api_key: Optional[str] = Field(default=os.getenv("LLM_API_KEY"))
    model_name: str = Field(default=os.getenv("MODEL_NAME", "analysis-model"))
    gate_model_name: str = Field(default=os.getenv("GATE_MODEL_NAME", os.getenv("MODEL_NAME", "analysis-model")))
    casecard_model_name: str = Field(default=os.getenv("CASECARD_MODEL_NAME", os.getenv("MODEL_NAME", "analysis-model")))
    router_model_name: str = Field(default=os.getenv("ROUTER_MODEL_NAME", os.getenv("MODEL_NAME", "analysis-model")))
    embedding_model: str = Field(default=os.getenv("EMBEDDING_MODEL", "embedding-model"))
    environment: str = Field(default=os.getenv("ENVIRONMENT", "dev"))
    schema_version: str = Field(default="2.0.0")
    max_neighbors: int = Field(default=5)
    max_pattern_neighbors: int = Field(default=3)
    router_confidence_threshold: float = Field(default=0.65)
    neighbor_agreement_threshold: float = Field(default=0.65)
    loose_summary_sentence_cap: int = Field(default=5)
    loose_monitor_sentence_cap: int = Field(default=4)
    loose_liability_sentence_cap: int = Field(default=3)
    loose_safety_sentence_cap: int = Field(default=4)
    default_prompt_method: str = Field(default=os.getenv("DEFAULT_PROMPT_METHOD", "loose_v1"))
    case_card_canonicalization_version: str = Field(
        default=os.getenv("CASE_CARD_CANONICALIZATION_VERSION", "v1")
    )
    pattern_card_canonicalization_version: str = Field(
        default=os.getenv("PATTERN_CARD_CANONICALIZATION_VERSION", "v1")
    )
    novelty_pipeline_version: str = Field(default=os.getenv("NOVELTY_PIPELINE_VERSION", "v1"))
    novelty_existing_close_confidence_threshold: float = Field(
        default=float(os.getenv("NOVELTY_EXISTING_CLOSE_CONFIDENCE_THRESHOLD", "0.8"))
    )

    model_config = ConfigDict(env_file=".env", extra="ignore")


def get_settings() -> Settings:
    return Settings()
