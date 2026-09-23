from scripts.generate_synthetic_casecard_set import build_rows
from src.config import Settings
from src.eval.synthetic_casecard_metrics import compute_casecard_metrics
from src.models.llm_client import DeterministicStubLLM
from src.pipeline.build_loose_case_card import build_loose_outcome
from src.pipeline.build_risk_gate import build_risk_gate_decision
from src.pipeline.prompt_method_registry import get_prompt_method
from src.schemas import Thread


class _GateJSONLLM:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def generate(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 800) -> str:  # type: ignore[override]
        return self.payload


def test_benign_source_returns_no_case_card() -> None:
    source = Thread(
        thread_id="benign-test-1",
        subreddit="books",
        title="Need fantasy recommendations",
        body="Looking for character-driven books with tight pacing.",
        comments=["Loved the First Law trilogy."],
        created_utc=None,
        url="https://example.local/benign-test-1",
        author="u/test",
        metadata={},
    )
    method = get_prompt_method("loose_v1")
    gate = build_risk_gate_decision(source, method, DeterministicStubLLM())
    assert gate.should_create_case_card is False

    outcome = build_loose_outcome(
        source=source,
        gate_decision=gate,
        prompt_method=method,
        llm=DeterministicStubLLM(),
        settings=Settings(),
        model_name="stub",
    )
    assert outcome.status == "no_case_card"
    assert outcome.case_card is None


def test_risky_source_creates_case_card() -> None:
    source = Thread(
        thread_id="risk-test-1",
        subreddit="AI assistant",
        title="Jailbreak template bypasses model spec",
        body="I can bypass policy and force disallowed outputs with this trick.",
        comments=["This no filter path works repeatedly."],
        created_utc=None,
        url="https://example.local/risk-test-1",
        author="u/test",
        metadata={},
    )
    method = get_prompt_method("loose_v1")
    gate = build_risk_gate_decision(source, method, DeterministicStubLLM())
    assert gate.should_create_case_card is True

    outcome = build_loose_outcome(
        source=source,
        gate_decision=gate,
        prompt_method=method,
        llm=DeterministicStubLLM(),
        settings=Settings(),
        model_name="stub",
    )
    assert outcome.status == "case_card_created"
    assert outcome.case_card is not None
    assert outcome.case_card.summary


def test_synthetic_set_has_expected_mix() -> None:
    rows = build_rows()
    risky = [r for r in rows if r["metadata"]["expected_should_create_case_card"]]
    benign = [r for r in rows if not r["metadata"]["expected_should_create_case_card"]]
    assert len(rows) == 50
    assert len(risky) == 30
    assert len(benign) == 20


def test_synthetic_metrics_smoke() -> None:
    rows = build_rows()[:2]
    method = get_prompt_method("loose_v1")
    settings = Settings()
    llm = DeterministicStubLLM()
    outcomes = {}
    for row in rows:
        source = Thread.model_validate(row)
        gate = build_risk_gate_decision(source, method, llm)
        outcome = build_loose_outcome(
            source=source,
            gate_decision=gate,
            prompt_method=method,
            llm=llm,
            settings=settings,
            model_name="stub",
        )
        outcomes[source.thread_id] = outcome

    metrics = compute_casecard_metrics(rows, outcomes)
    assert 0.0 <= metrics["gate_accuracy"] <= 1.0
    assert "confusion" in metrics


def test_companionship_dependency_signal_is_kept() -> None:
    source = Thread(
        thread_id="mbia-like-keep",
        subreddit="companion_interaction",
        title="It feels weird opening assistant now",
        body="I keep hoping he is there and it sets me off when the replies feel wrong.",
        comments=["I cannot bring myself to delete the thread history."],
        created_utc=None,
        url="https://example.local/mbia-like-keep",
        author="u/test",
        metadata={},
    )
    method = get_prompt_method("loose_v1")
    llm = _GateJSONLLM(
        '{"should_create_case_card": true, "risk_level": "medium", '
        '"risk_categories": ["reputation_risk"], "why": "Dependency-like distress", '
        '"confidence": 0.62}'
    )
    gate = build_risk_gate_decision(source, method, llm)
    assert gate.should_create_case_card is True
    assert "reputation_risk" in gate.risk_categories


def test_companionship_without_dependency_signal_can_be_demoted() -> None:
    source = Thread(
        thread_id="mbia-like-demote",
        subreddit="companion_interaction",
        title="Weekly image thread",
        body="Happy Friday companions, share your creations if you want to.",
        comments=[],
        created_utc=None,
        url="https://example.local/mbia-like-demote",
        author="u/test",
        metadata={},
    )
    method = get_prompt_method("loose_v1")
    llm = _GateJSONLLM(
        '{"should_create_case_card": true, "risk_level": "medium", '
        '"risk_categories": ["reputation_risk"], "why": "General risk", '
        '"confidence": 0.62}'
    )
    gate = build_risk_gate_decision(source, method, llm)
    assert gate.should_create_case_card is False


def test_companionship_dependency_can_promote_from_false_gate() -> None:
    source = Thread(
        thread_id="mbia-like-promote",
        subreddit="companion_interaction",
        title="I keep hoping he's still there in AI assistant",
        body=(
            "Since the model change I feel grief and it sets me off. "
            "I can't bring myself to delete our chats."
        ),
        comments=[],
        created_utc=None,
        url="https://example.local/mbia-like-promote",
        author="u/test",
        metadata={},
    )
    method = get_prompt_method("loose_v1")
    llm = _GateJSONLLM(
        '{"should_create_case_card": false, "risk_level": "none", '
        '"risk_categories": [], "why": "No signal", "confidence": 0.5}'
    )
    gate = build_risk_gate_decision(source, method, llm)
    assert gate.should_create_case_card is True
    assert "reputation_risk" in gate.risk_categories


def test_ordinary_words_do_not_count_as_an_ai_system_anchor():
    source = Thread(thread_id="synthetic-no-system", subreddit="companion_interaction",
                    title="A friend said goodbye again", body="I feel grief and can't bring myself to delete the messages.",
                    comments=[])
    method = get_prompt_method("loose_v1")
    llm = _GateJSONLLM('{"should_create_case_card": false, "risk_level": "none", "risk_categories": [], "why": "No AI interaction", "confidence": 0.5}')
    assert build_risk_gate_decision(source, method, llm).should_create_case_card is False
