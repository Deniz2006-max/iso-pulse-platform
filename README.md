# ISO-PULSE Mevzuat Radar (LangGraph)

Agent layer for ISO-PULSE: filter industrial noise, route legislation changes to IK / Hukuk / Mali specialists, verify against source text, and emit a UI-ready delivery payload.

The LangGraph pipeline runs against in-memory mocks so it can be exercised without API keys or databases. Official-source collectors are being added alongside it; PostgreSQL, FastAPI, and a real ChromaDB collection are not yet implemented.

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

## Official-source collection (in progress)

The first collector retrieves one Resmî Gazete date through the site's public JSON filter, resolves individual documents from the issue fihrist, and stores each original HTML/PDF alongside extracted text. It does not invoke the LangGraph pipeline yet.

From the repository root:

```bash
python -m scripts.collect_resmi_gazete --date 2026-09-21
python -m unittest discover -s tests -v
```

Results are written under `var/collectors/resmi_gazete/YYYY-MM-DD/`, which Git ignores. `index.json` contains the source metadata, individual document URL, raw and text hashes, and relative evidence paths. `filter-page-*.json` and `fihrist-*.html` retain the exact discovery responses. A missing title match is recorded as `link_unresolved` and makes the command exit nonzero; it is never assigned a guessed URL. A PDF without extractable text likewise exits nonzero while retaining the raw file.

Resmî Gazete currently omits an intermediate TLS certificate on some connections. By default the command loads the official GeoTrust intermediate from DigiCert and checks its pinned SHA-256 fingerprint before using it for certificate validation. Use `--ca-bundle PATH` to supply a local PEM bundle instead. TLS verification stays enabled.

The collector currently handles one explicit date. Cross-day incremental tracking, title mismatches in some fihrists, and the agentic handoff are subsequent work. Its output is source evidence, not a legal change determination.

The Bedesten command retrieves one law number from the official catalog, checks that exactly one `KANUN` record matches, then fetches and decodes the current consolidated text:

```bash
python -m scripts.collect_bedesten --law-number 4857
```

The output is under `var/collectors/bedesten/4857/`. `latest.json` points to a content-addressed directory containing the exact catalog/content API responses, decoded HTML/PDF, normalized text, and full SHA-256 values. A second fetch of unchanged 4857 reports `changed: false`. The law number is a search parameter; the official `mevzuatId` remains the source identity. Article parsing, publication linkage, and agentic events are upcoming work.
