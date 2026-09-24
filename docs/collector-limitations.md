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

The first command is offline and deterministic; at this writing all 28 tests pass. The 2026-09-21 live run yielded 14/14 text-extracted rows. The 2026-09-18 live rerun yielded 22/22 extracted rows, 15 distinct document URLs, and exit status zero. A further 2026-09-18 rerun compared all 22 publications as `unchanged` against the previous successful index. Bedesten article parsing has since expanded beyond the original 4857/6331 format; see [the scoped-law validation](article-validation-2026-09-23.md).

Live outputs are under ignored `var/collectors/`; they are not included in the commit. Reproduction of **the code path** is possible, but identical live bytes/counts are not guaranteed: official pages may change, a network request may fail, and dependencies have lower bounds rather than a lockfile. `retrieved_at` and raw response hashes can also differ between runs. The tests cover parsers and failure cases with in-memory inputs, a focused grouped-link fixture, and a simulated timeout/partial failure, not a fully pinned end-to-end fixture for the 2026-09-18 responses. The default Resmî Gazete TLS chain repair requires fetching a fingerprint-pinned intermediate certificate from DigiCert; `--ca-bundle` is available for an offline/local certificate bundle. These constraints should be resolved before claiming fully repeatable, unattended operation.

## Next steps, in order

1. **Done:** add the grouped-link fixture and verified one-to-many fihrist matching; 2026-09-18 now resolves 22/22 rows.
2. **Done:** add request-stage/timing diagnostics and per-run failure manifests. Keep partial evidence, but do not publish an incomplete day as successful.
3. **First slice done:** compare complete Resmî Gazete reruns and Bedesten law snapshots by identity plus raw/text hashes. Numbered Gazette items survive title/URL corrections; unnumbered items currently use document URL identity. Corrected live source pages have only simulated-test coverage so far. No cross-day relation or agentic event has been published.
4. **First slice done for Bedesten laws:** parse article blocks and diff stored versions, retaining old/new text and hashes. Fifteen scoped laws were fetched and structurally checked; five of seven repo JSON baselines match article-ID sets exactly, while the Bedesten text contains additional `24/A`, `25/A`, and `20/A` articles absent from the other two JSON files. Parser uncertainty becomes `review_required`; changes outside article blocks are separate. This does not yet establish which Resmî Gazete publication caused a changed law article.
5. **SGK pilot added:** a bounded `TumBirimler` page collector retains each detail page and all linked files, with an append-only run manifest and same-page comparison. The first 2026-09-24 page-1 run acquired 10 announcements and 17 attachments; the completed rerun with Office extraction acquired 10 announcements and 20 attachments. Four previously seen records are `extraction_changed`, not official source changes; one new record entered page 1 and one prior ID left it, without implying deletion. The current index has one image-only PDF needing OCR and one DOCX marked partial because of embedded/ancillary content. Source capture is complete for that page, but the page is **not yet a complete text seed**. The pilot does not claim full-archive completeness, permanent URL identity, or cross-page deletion semantics.
6. Agree the handoff/database contract with the agentic developer, then add storage/upsert and an explicit event envelope. SGK extraction gaps and other source collectors should use the same provenance and failure rules.
7. Pin dependencies and add a reproducible end-to-end fixture/integration test. Add scheduling only after success/failure and idempotency behavior are settled.
