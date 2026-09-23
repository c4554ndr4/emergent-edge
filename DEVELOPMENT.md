# Developing Emergent Edge

Requires Python 3.11 or later. From this source directory:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m pytest
python -m src.pipeline.run_pipeline examples/threads.jsonl --output-dir outputs/demo --no-write-watchlist-log --proposal-output-path outputs/demo/proposals.json
```

Leave all endpoint/key settings unset for this offline demo. The three input reports are fictional. The deterministic model fixture deliberately exercises heuristic fallbacks; its hash embeddings have no semantic meaning. The demo verifies wiring and output formats, not classification accuracy. Outputs remain ignored by version control.

## Live endpoint contract

Copy `.env.example` to `.env` and choose `LLM_BASE_URL`, `MODEL_NAME`, `LLM_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, and optionally a separate `EMBEDDING_API_KEY`. Keys are optional for local services that do not require authentication. Loopback HTTP is allowed; remote services require HTTPS. URLs must not contain credentials, a query, or a fragment. Redirects are not followed.

The text adapter sends `POST {LLM_BASE_URL}/chat/completions` with `model`, `messages`, and `max_tokens`, and expects `choices[0].message.content`. The embedding adapter sends `POST {EMBEDDING_BASE_URL}/embeddings` with `model` and `input`, and expects `data` entries containing `index` and a finite, consistently sized `embedding`. The adapters target this specific wire contract; arbitrary provider APIs may require a separate adapter. Endpoint/model availability must be checked with the service you choose.

Live text analysis must use a configured embedding endpoint. Placeholder model names are rejected. Adapter errors are explicit; several higher-level extraction/judgment stages retain heuristic fallbacks. Inspect outputs accordingly and do not treat a completed run as proof every model request succeeded.

## Data and decisions

Inputs are JSONL or CSV. See `examples/threads.jsonl` for the report shape. `subreddit` is a legacy source-group field; the example uses a fictional group. It does not imply community membership is a risk signal. Import only data you have permission to process and send to the selected endpoint.

The pipeline retains optional source-origin and relevance gates for experimentation. Both are disabled by default. Origin estimates are not proof of authorship. Pattern proposals need at least two supporting cases by default, and automatic library promotion is disabled. Human review is a research workflow around the saved files, not a built-in approval screen.

This export uses schema version 2.0.0, with generic `impact_pathways`, `why_review_matters`, and `impact_assessment` fields. Older private artifacts are intentionally not included and require an explicit migration before reuse. Source case/pattern IDs are preserved where useful for test continuity; labels have been revised to describe interaction behavior.

Tests cover policy decisions, escalation, JSON parsing, synthetic benchmarks, endpoint response contracts, and deterministic concurrent embedding fixtures. Stronger benchmarks need independent labels, representative distributions, and failure/provenance reporting.

## Public website

The [live walkthrough](https://emergent-edge-case-ai-use-detector.vercel.app) is served from `website/public`. It lets visitors inspect three fictional reports, their recorded case cards and decisions, and a diagram of the research workflow. The accompanying review notes are explanatory annotations. The offline results are not research findings or live model judgments.

The website is a static export: it contains no collected corpus, credentials, or model-service calls. To preview it, run `python -m http.server 8012 --directory website/public` and open `http://localhost:8012`. Deploy from the `website` directory using its Vercel configuration. Keep the public example set separate from private research data.
