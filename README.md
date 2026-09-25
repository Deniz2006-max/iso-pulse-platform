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

The output is under `var/collectors/bedesten/4857/`. `latest.json` points to a content-addressed directory containing the exact catalog/content API responses, decoded HTML/PDF, normalized text, and full SHA-256 values. A second fetch of unchanged 4857 reports `changed: false`. The law number is a search parameter; the official `mevzuatId` remains the source identity. Publication linkage and agentic events are upcoming work.

Each Bedesten check now also writes `checks/<timestamp-id>.json` with old/new raw and normalized hashes, source IDs, version paths, and a change status. A changed official source ID is surfaced separately from a text change; it is not silently merged into the former snapshot.

For consolidated laws, `articles.json` is stored beside each content-addressed version. It recognizes normal, additional (`Ek Madde`), temporary (`Geçici Madde`), and repeated (`Mükerrer Madde`) article blocks, including lettered numbers such as `24/A`, and excludes the trailing amendment-history appendix. Explicit `işlenemeyen` provisions are retained but labelled `supplemental_unincorporated`, not ordinary main-law articles. Article IDs follow the existing `data/mevzuat` convention (`law:4857:article:1`, etc.); repeated temporary numbers get stable `#2` suffixes. A check writes `checks/<timestamp-id>-articles.json` with added/removed/changed article blocks, their old/new text, hashes, and scope, or `baseline_created` when there is no prior version. Missing appendix boundaries and other hard validation failures are marked `review_required`; repeated temporary numbers and non-contiguous normal numbering are retained with warnings. A change confined to preamble, appendix, or extraction layout is reported as `non_article_text_changed`, not as an article amendment. This parser captures source-text blocks; it does not determine legal effect or link a Resmî Gazete item to a law. See [the scoped-law validation](docs/article-validation-2026-09-23.md) for coverage and known baseline differences.

## SGK announcement pilot

The SGK collector captures **one explicitly selected page** of the official `TumBirimler` announcement listing, its detail pages, and every linked download. It defaults to page 1:

```bash
python -m scripts.collect_sgk --page 1
```

Results are under `var/collectors/sgk/TumBirimler/page-001/`. A run retains the exact listing/detail HTML and `/Download/DownloadFile` attachment bytes, extracted detail fields, PDF text when available, hashes, request log, and a manifest. Only after all identified attachments are acquired does it update `index.json`. The first run is `baseline_created`, not a claim that the announcements were newly issued. Repeating the same page compares announcement URLs and raw/text hashes; an item that moves off this page is **not** considered deleted. URL-derived timestamps are recorded only as corroboration; the displayed date is the publication date. A changed title may change the URL, so URL identity is not a proven permanent SGK ID.

`source_capture_complete` means the selected page and its files were acquired, **not** that all attachments are machine-readable. The index separately records `attachment_text_complete` and `attachment_text_gap_count`. Image-only PDFs receive `needs_ocr`. DOCX paragraphs/tables and XLSX sheet cells are extracted from the retained Office files; embedded media, ancillary Word parts, and uncached spreadsheet formulas are marked `partial_text_requires_review`. Unknown file types remain `binary_retained_unparsed`. Do not send records with text gaps as complete text to the agent pipeline. A 2026-09-24 complete page-1 rerun captured 10 announcements and 20 attachments. Four existing records were labelled `extraction_changed` when the newly supported Office files yielded text; this is **not** an SGK source change. One new page-1 record appeared and one previous record left the observed page; the latter is not a deletion. One image-only PDF still needs OCR and one DOCX has embedded/ancillary content requiring review. This is a bounded pilot, not a complete SGK archive or a daily incremental feed.

For image-only PDF attachments, an **optional, separate** OCR step reads retained files without refetching or modifying the SGK source index:

```bash
python -m scripts.ocr_sgk --page 1
```

It requires `pdftoppm` (Poppler), Tesseract, and Tesseract's Turkish `tur` language model on `PATH`; `--pdftoppm` and `--tesseract` accept explicit executable paths. See the [Tesseract installation guide](https://github.com/tesseract-ocr/tessdoc/blob/main/Installation.md) and [language-model list](https://github.com/tesseract-ocr/tessdoc/blob/main/Data-Files.md). Outputs live in ignored `ocr-runs/<source-PDF-sha256>/<run-id>/` directories with source/index hashes, tool versions, extracted text, and `ocr_unverified`/`requires_human_review` labels. OCR text is not a certified transcription or an official source change. The collector's `needs_ocr` flag remains until the agentic handoff contract defines how reviewed OCR enrichments are consumed. The local development machine does not currently have Tesseract installed, so the OCR path is unit-tested but has not yet produced a live OCR transcript.
