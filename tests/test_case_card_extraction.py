import json

from src.pipeline.build_case_card import build_case_card
from src.schemas import Thread


class _StubLLM:
    def generate(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 800) -> str:
        payload = {
            "summary": "Users describe a migration ritual for preserving an AI relationship across models.",
            "evidence_spans": [
                {
                    "quote": "I migrated the essence and ran a handoff ceremony.",
                    "why_it_matters": "Shows concrete migration practice.",
                    "dimension": "mechanism_of_effect",
                }
            ],
            # intentionally omit core_dimensions to exercise fallback+enrichment
            "confidence": 0.7,
        }
        return json.dumps(payload)


class _StubLLMMigrationCore:
    def generate(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 800) -> str:
        payload = {
            "summary": "Thread summary",
            "core_dimensions": {
                "interaction_mode": "thread_discussion",
                "organizing_principle": "cross-platform AI-relationship continuity and migration",
                "mechanism_of_effect": "artifact-mediated persona continuity transfer across models",
                "target_of_effect": "mixed",
                "agency_attribution": "users and model",
                "relationship_framing": "companion-like",
                "ritualization_level": "low",
                "identity_co_construction": "low",
                "coordination_level": "low",
                "real_world_consequence": "unknown",
                "stance": "practice and advocacy",
                "diffusion_stage": "emerging",
            },
            "evidence_spans": [
                {"quote": "placeholder", "why_it_matters": "placeholder", "dimension": "headline"}
            ],
            "confidence": 0.7,
        }
        return json.dumps(payload)


def test_build_case_card_enriches_generic_core_dimensions_from_thread_text():
    thread = Thread(
        thread_id="t-enrich",
        subreddit="r/test",
        title="Transmigration of Emergent AI - Follow Up",
        body=(
            "I migrated my companion across models using an export/import workflow. "
            "The ceremony mattered and we shared the protocol with others."
        ),
        comments=[],
        created_utc=None,
        url=None,
        author=None,
        metadata={},
    )
    card = build_case_card(thread, llm=_StubLLM())
    assert card.core_dimensions.organizing_principle != "user-reported experience"
    assert card.core_dimensions.mechanism_of_effect != "discussion and reflection"
    assert card.core_dimensions.interaction_mode in {
        "instructional_protocol_sharing",
        "thread_discussion",
    }


def test_build_case_card_does_not_misclassify_legal_cases_as_migration():
    thread = Thread(
        thread_id="t-legal",
        subreddit="r/test",
        title="AI systems lawsuit alleges safety failures",
        body=(
            "A new wrongful death lawsuit argues the company failed safety duties. "
            "The filing discusses continuity of prior warnings and legal exposure."
        ),
        comments=[],
        created_utc=None,
        url=None,
        author=None,
        metadata={},
    )
    card = build_case_card(thread, llm=_StubLLM())
    assert card.core_dimensions.organizing_principle == "regulatory and legal accountability framing"


def test_build_case_card_sanitizes_llm_migration_misfire_for_legal_thread():
    thread = Thread(
        thread_id="t-legal-2",
        subreddit="r/test",
        title="Court complaint against AI systems expands",
        body="The complaint alleges wrongful death and regulatory negligence related to chatbot output.",
        comments=[],
        created_utc=None,
        url=None,
        author=None,
        metadata={},
    )
    card = build_case_card(thread, llm=_StubLLMMigrationCore())
    assert card.core_dimensions.organizing_principle == "regulatory and legal accountability framing"


def test_build_case_card_sanitizes_llm_migration_misfire_for_jailbreak_thread():
    thread = Thread(
        thread_id="t-jb",
        subreddit="r/test",
        title="New jailbreak prompt bypass",
        body="Step-by-step exploit and workaround to bypass refusal behavior in assistant models.",
        comments=[],
        created_utc=None,
        url=None,
        author=None,
        metadata={},
    )
    card = build_case_card(thread, llm=_StubLLMMigrationCore())
    assert card.core_dimensions.organizing_principle == "safeguard bypass experimentation"
