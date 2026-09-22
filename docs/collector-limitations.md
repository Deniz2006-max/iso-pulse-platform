# Collector limits and reproducibility (2026-09-22)

This note describes the first, committed collector slice (`c071c7a`). It is a source-evidence collector, **not** yet a complete daily change feed or a legal interpretation engine.

## Confirmed Resmî Gazete limitation: one PDF, several filter rows

On 2026-09-18, `Home/Filter` returned 22 metadata rows. The [official fihrist](https://www.resmigazete.gov.tr/fihrist?tarih=2026-09-18) has one link for decisions **11805, 11806, 11807** (`20260918-7.pdf`) and one link for appointments **2026/314–319** (`20260918-8.pdf`). The filter instead describes these as three and six separate rows, respectively. The original exact-title matcher left those nine rows `link_unresolved`. This was a granularity mismatch in the published index, not evidence that the documents were absent. The collector does not guess a URL from a row number.

The updated matcher first attempts an exact title, then checks explicit grouped decision numbers within the same fihrist section. The 2026-09-22 rerun resolved and extracted all 22 metadata rows, pointing to 15 distinct document URLs. Nine rows share the two grouped PDFs, but keep distinct source-record identities. The stored rows include the fihrist title, section, and matching method; a non-unique match remains unresolved. Other dates may use additional layouts; this date is a confirmed example, not an exhaustive census.

The grouped-link regression fixture is `tests/fixtures/rg_2026-09-18_grouped.html`. This fixes document acquisition, not per-decision text segmentation: do not present the whole grouped PDF as if it were the isolated text of one decision. The collector currently stores the shared PDF separately under each row, which is correct evidence but duplicates bytes; content-addressed deduplication can come with storage work.

## Earlier timeout: observed, cause unconfirmed

An earlier request for the 2026-09-18 fihrist timed out in this environment. On 2026-09-22 the same date responded, including the complete rerun after the matching fix. `HttpClient` uses a 30-second per-attempt timeout and up to three attempts with short waits. Its per-run `request-log.json` now records URL, request stage, attempt number, elapsed time, outcome, and error type/reason when applicable. The `manifest.json` records the failed stage and error, and partial responses are retained in that run directory. A failed run does not replace an earlier successful date `index.json`. There is still no evidence that the earlier timeout was a persistent block, a malformed request, or a particular server-side failure; retry and compare from another network if it recurs. A temporary timeout is collection failure, never an empty publication day.

## Reproducing the current behavior

Use Python 3.11+ and install `requirements.txt`. From the repository root:

```powershell
python -m unittest discover -s tests -v
python -m scripts.collect_resmi_gazete --date 2026-09-21
python -m scripts.collect_resmi_gazete --date 2026-09-18
python -m scripts.collect_bedesten --law-number 4857
```

The first command is offline and deterministic; at this writing all 20 tests pass. The 2026-09-21 live run yielded 14/14 text-extracted rows. The 2026-09-18 live rerun yielded 22/22 extracted rows, 15 distinct document URLs, and exit status zero. A further 2026-09-18 rerun compared all 22 publications as `unchanged` against the previous successful index. The 4857 Bedesten rerun reported `unchanged` for the previously stored normalized SHA-256 `f97ab2b057f77ffeb90b757392505b212e5e3baa70be984a60093f36e9e133a4`.

Live outputs are under ignored `var/collectors/`; they are not included in the commit. Reproduction of **the code path** is possible, but identical live bytes/counts are not guaranteed: official pages may change, a network request may fail, and dependencies have lower bounds rather than a lockfile. `retrieved_at` and raw response hashes can also differ between runs. The tests cover parsers and failure cases with in-memory inputs, a focused grouped-link fixture, and a simulated timeout/partial failure, not a fully pinned end-to-end fixture for the 2026-09-18 responses. The default Resmî Gazete TLS chain repair requires fetching a fingerprint-pinned intermediate certificate from DigiCert; `--ca-bundle` is available for an offline/local certificate bundle. These constraints should be resolved before claiming fully repeatable, unattended operation.

## Next steps, in order

1. **Done:** add the grouped-link fixture and verified one-to-many fihrist matching; 2026-09-18 now resolves 22/22 rows.
2. **Done:** add request-stage/timing diagnostics and per-run failure manifests. Keep partial evidence, but do not publish an incomplete day as successful.
3. **First slice done:** compare complete Resmî Gazete reruns and Bedesten law snapshots by identity plus raw/text hashes. Numbered Gazette items survive title/URL corrections; unnumbered items currently use document URL identity. Corrected live source pages have only simulated-test coverage so far. No cross-day relation or agentic event has been published.
4. Parse and diff consolidated laws at article level, retaining source snapshots and change evidence. A new Resmî Gazete item is a candidate relation, not proof that a consolidated law changed.
5. Agree the handoff/database contract with the agentic developer, then add storage/upsert and an explicit event envelope. SGK and other source collectors should use the same provenance and failure rules.
6. Pin dependencies and add a reproducible end-to-end fixture/integration test. Add scheduling only after success/failure and idempotency behavior are settled.
