# Bedesten article validation — 2026-09-23

Scope: the seven laws already represented in `data/mevzuat`, plus eight additional law numbers requested for İSO Pulse. Each number was resolved through an exact Bedesten `KANUN` catalog match and its consolidated full text was stored locally under ignored `var/collectors/bedesten/<number>/`. This audit ran parser `bedesten-article-block-v6` on those saved texts. `trusted` means structural checks passed; it does **not** certify legal interpretation or exhaustively verify every boundary by hand. A first capture is a local baseline, not a newly enacted law.

## Cross-check against the seven existing JSON files

| Law | Bedesten article blocks | Existing JSON provisions | Article-ID comparison | Notes |
| --- | ---: | ---: | --- | --- |
| 4857 | 137 | 137 | Exact | No parser warnings. |
| 6331 | 52 | 50 | Two additional | Bedesten has ordinary `24/A` and `25/A` articles; the existing PDF-derived JSON omits these IDs. |
| 4447 | 69 | 69 | Exact | One unincorporated supplemental provision is labelled separately; repeated temporary number receives `#2`. |
| 4632 | 36 | 35 | One additional | Bedesten has ordinary `20/A`; the existing JSON omits this ID. |
| 5174 | 125 | 125 | Exact | No parser warnings. |
| 5510 | 246 | 246 | Exact | One unincorporated supplemental provision is labelled separately; repeated temporary numbers receive suffixes. |
| 6698 | 36 | 36 | Exact | No parser warnings. |

The three additional lettered articles above have explicit `Madde` markers in the official Bedesten text. Do not silently rewrite the team's existing JSON files: review the source-text differences with its owner first. A matching ID set validates discovery/counting, not the exact text span of each article.

## Additional requested laws without a repo baseline

| Law | Article blocks | Structural result | Caution |
| --- | ---: | --- | --- |
| 5737 | 97 | Trusted | No independent article-by-article baseline. |
| 2860 | 33 | Trusted, warning | Non-contiguous normal numbering; inspect before using an article deletion signal. |
| 5072 | 8 | Trusted | Small law; no independent baseline. |
| 3308 | 63 | Trusted, warnings | Repeated temporary number; occurrence suffixes require source-context review. |
| 2547 | 227 | Trusted, warnings | 18 blocks follow an explicit `işlenemeyen` heading and are labelled supplemental. |
| 6098 | 651 | Trusted, warnings | Repeated temporary number and non-contiguous normal numbering. |
| 193 | 259 | Trusted, warnings | `Mükerrer` and lettered articles required parser changes; 14 blocks are explicitly unincorporated supplemental provisions. Manually review before production handoff. |
| 5520 | 77 | Trusted, warnings | Repeated temporary number and non-contiguous normal numbering. |

## Validation rules and remaining risk

The parser requires an identifiable amendment-history appendix, first normal article 1, and plausible article count; hard failures return `review_required` with no automatic article diff. It distinguishes ordinary, `Ek`, `Geçici`, and `Mükerrer` markers, preserves lettered numbers, and labels explicit unincorporated sections. It normalizes whitespace for hashing but retains the original extracted text blocks and offsets.

Article blocks can include nearby headings. Duplicate temporary numbers are numbered by occurrence, so inserting a new earlier occurrence could shift `#2` identities. Laws without an independent baseline still need representative manual boundary checks, particularly 193, 2547, and other warning-bearing documents. No real source revision was observed during this audit; added/removed/changed article results are covered by synthetic tests, not a live amendment.

To reproduce the network collection from the repo root, run `python -m scripts.collect_bedesten --law-number NUMBER` for each number above. To run offline parser tests, use `python -m unittest discover -s tests -q`. Local source documents are Git-ignored and are not included in the branch.
