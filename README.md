# ISO-PULSE Mevzuat Radar (LangGraph)

Agent layer for ISO-PULSE: filter industrial noise, route legislation changes to IK / Hukuk / Mali specialists, verify against source text, and emit a UI-ready delivery payload.

Scrapers, PostgreSQL, FastAPI, and a real ChromaDB collection are out of scope. This scaffold runs against in-memory mocks so the graph can be exercised without API keys or databases.

## Layout

- `schemas/` — Pydantic v2 outputs and `PulseState`
- `nodes/` — LangGraph node functions
- `config/` — settings and system prompts
- `mocks/` — sample documents, Chroma stand-in, mock LLM
- `graph.py` — compiled `StateGraph`
- `main.py` — CLI runner

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run the mock pipeline

```bash
python main.py
python main.py --list
python main.py --doc ik-overtime
python main.py --doc noise-appointment
python main.py --doc hukuk-environment
python main.py --doc multi-wage-tax
```

By default `ISO_PULSE_USE_MOCK_LLM=true`. To call a live OpenAI-compatible model, set that flag to `false` and provide `OPENAI_API_KEY`.
