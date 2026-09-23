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

Results are written under `var/collectors/resmi_gazete/YYYY-MM-DD/`, which Git ignores. Each attempt gets a unique `runs/<run-id>/` directory containing its request log, manifest, and captured evidence. Only a complete run updates the day's `index.json`; a failed run keeps its partial evidence without replacing a previous successful index. The index contains source metadata, individual document URL, raw and text hashes, and evidence paths relative to the date directory. `filter-page-*.json` and `fihrist-*.html` retain exact discovery responses in the run directory. Exact titles are matched first; a grouped fihrist PDF can be linked to several filter rows only when section and explicit decision number give a unique match. Other missing/ambiguous matches remain `link_unresolved` and make the command exit nonzero; they are never assigned a guessed URL. A PDF without extractable text likewise exits nonzero while retaining the raw file.

Resmî Gazete currently omits an intermediate TLS certificate on some connections. By default the command loads the official GeoTrust intermediate from DigiCert and checks its pinned SHA-256 fingerprint before using it for certificate validation. Use `--ca-bundle PATH` to supply a local PEM bundle instead. TLS verification stays enabled.

The collector currently handles one explicit date. Cross-day incremental tracking, other possible fihrist formats, and the agentic handoff are subsequent work. Its output is source evidence, not a legal change determination.

On a complete rerun of the same date, the collector compares each publication with the previous successful `index.json`. An official decision number identifies numbered rows; otherwise the verified document URL identifies the item. The run-specific `comparison.json` distinguishes `new`, `unchanged`, `text_changed` (raw and extracted text differ), `raw_changed_only`, and `metadata_changed_only`. If the raw bytes are identical but extracted text differs, it records `extraction_changed`; a changed normalizer version with changed text records `normalizer_changed` for review. Changes include old/new hashes and evidence paths. The daily index receives each row's `publication_id` and `change_status`. Items missing from a later source index are listed for review, **not** silently treated as repealed or deleted. This comparison does not assert that a publication amended another law.

See [collector limits and reproducibility](docs/collector-limitations.md) for the confirmed 2026-09-18 grouped-PDF behavior, the earlier intermittent timeout, and the next implementation steps.

The Bedesten command retrieves one law number from the official catalog, checks that exactly one `KANUN` record matches, then fetches and decodes the current consolidated text:

```bash
python -m scripts.collect_bedesten --law-number 4857
```

The output is under `var/collectors/bedesten/4857/`. `latest.json` points to a content-addressed directory containing the exact catalog/content API responses, decoded HTML/PDF, normalized text, and full SHA-256 values. A second fetch of unchanged 4857 reports `changed: false`. The law number is a search parameter; the official `mevzuatId` remains the source identity. Article parsing, publication linkage, and agentic events are upcoming work.

Each Bedesten check now also writes `checks/<timestamp-id>.json` with old/new raw and normalized hashes, source IDs, version paths, and a change status. A changed official source ID is surfaced separately from a text change; it is not silently merged into the former snapshot.

For consolidated laws, `articles.json` is stored beside each content-addressed version. It recognizes normal, additional (`Ek Madde`), and temporary (`Geçici Madde`) article blocks, and excludes the trailing amendment-history appendix. Article IDs match the existing `data/mevzuat` convention (`law:4857:article:1`, etc.). A check writes `checks/<timestamp-id>-articles.json` with added/removed/changed article blocks, their old/new text and hashes, or `baseline_created` when there is no prior version. Duplicate IDs, missing appendix boundaries, or implausible article sequences are marked `review_required` and do not produce an automatic article diff. A change confined to preamble, appendix, or extraction layout is reported as `non_article_text_changed`, not as an article amendment. This parser captures source-text blocks; it does not determine legal effect or link a Resmî Gazete item to a law.
