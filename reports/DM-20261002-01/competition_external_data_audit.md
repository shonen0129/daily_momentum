# Phase 0 — Competition external-data audit

**Result: external public data is allowed conditionally; current JMV snapshot is not a usable Train-era network input.**

| Question | Finding | Evidence / condition |
|---|---|---|
| External public data | Allowed | The packaged `stock_comp_2026/input_data_explorer.ipynb`, section 6, says data outside the supplied bundle may be used subject to publication-time/PIT, quality, and submission checks. |
| EDINET data | Allowed as a public source, subject to its terms | EDINET terms put public content under PDL 1.0, require attribution, and direct machine acquisition to the API. Respect API load/access rules. |
| Static data in submission | Allowed/required when needed | Competition docs say required files must be retrieved in advance and included in the strategy folder; ZIP submission supports related files and trained models. |
| Inference-time network | Not allowed | Competition README says the grading environment has no network access. No runtime fetch may be required. |
| Runtime / dependencies | 30-minute grading limit; CPU-safe code | Competition README says submission evaluation must finish within 30 minutes, and GPU use cannot be required. Missing extra libraries should be confirmed with the organizer. |
| File-size limit | Not found in reviewed local competition materials | No numerical ZIP limit is stated in the checked README/notebook. This is not interpreted as unlimited size. |
| JMV data redistribution | Not cleared by this audit | JMV says dataset/source terms apply individually. We did not inspect or approve every upstream license for bundling. Do not package its existing aggregate snapshot based on competition permission alone. |
| EDINET-derived relation table | Potentially packageable with attribution, subject to source-level review | Use first-party public EDINET filings and keep file IDs, URLs, publication timestamps, extraction hashes, and attribution. Verify the exact package contents against PDL 1.0 and third-party embedded material before any release. |

## Phase 0 stop rule

Competition rules do not prohibit static external data, so there is no contest-rule stop. However, the current JMV aggregate is neither a Train-era PIT table nor cleared here for redistribution. A historical EDINET-derived static snapshot could be assessed separately. Since this audit found no such archive locally and no historical extraction was performed, the strict Phase 1 source gate fails; no Candidate follows.

## Sources

- Packaged competition rule text: [input_data_explorer.ipynb](../../stock_comp_2026/input_data_explorer.ipynb), section 6; [stock_comp_2026/README.md](../../stock_comp_2026/README.md), “Environment” and “Zip Submission”.
- [EDINET terms of use](https://disclosure2dl.edinet-fsa.go.jp/guide/static/submit/WZEK0030.html) (PDL 1.0, source attribution, API use for machine access).
- [EDINET API materials](https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/WZEK0110.html).
- [JP_Market_Vis README](https://github.com/mattyamonaca/JP_Market_Vis) (source-specific terms and snapshot limits).
