# Phase 1 — Source review

Review date: 2026-10-02. Scope is the public repository documentation and paper records. The JMV JSON relation/evidence files and EDINET raw filings were not present in the workspace and were not downloaded for this audit.

## A. JP_Market_Vis

| Topic | Source finding | PIT implication |
|---|---|---|
| Relation type | README calls the type 主要販売先 (`major_customer` in the requested taxonomy): a disclosed major customer, mainly a customer representing at least 10% of consolidated sales. Direction is selling company/supplier → customer. | Direction fits customer-to-supplier return propagation only when traversed from a supplier's disclosed customer. No reverse or undirected propagation. |
| Current filing sample | The 2026-09-21 snapshot reports 2025-06-14 through 2026-06-13 EDINET filings. The published type-count table is labeled an older/reference count: 2,191 major-customer relations, 656 listed-listed. | All these reports were published after the 2011-2016 Train period. Their economic/reference dates cannot be substituted for publication dates. Applying the current snapshot to Train would be relationship look-ahead. |
| Evidence fields | Pipeline README describes `source`, `source_tier`, `as_of`, `published`, `retrieved`, `url`, `doc_id`, classification/direction provenance, raw counterparty name, and extraction metadata. `as_of` for annual reports is the fiscal period end; `published` is filing/submission date. | `published`, conservatively shifted when time is unknown, controls availability. `as_of` is not an availability timestamp. |
| Relationship status/history | Status includes `confirmed`, `needs_review`, and `historical`. Later evidence can supersede an edge (`valid_until`). README reports one historical relation across all types in its overall snapshot. Ownership ratio history is retained separately. | Current evidence does not establish a full annual 2011-2016 major-customer sequence, successor-confirmation rate, or edge termination history. One historical row is not enough. |
| Code mapping | Current M4 master includes security/EDINET codes and company aliases; pipeline resolves listed companies by code, legal name, QID, then aliases. | This is a current 2026 mapping, not by itself a PIT mapping for old names/codes. Train-era counterparty matching must be rebuilt against date-matched listed information; ambiguous names must be excluded. |
| Raw evidence / redistribution | Full raw evidence is retained in local pipeline stores; public JSON is a restricted structured projection. README says upstream source usage conditions apply. | Neither historical source coverage nor redistribution rights for every JMV-derived row are certified. Do not bundle the current aggregate on this review alone. |

The code-facing path described by the repository is `public/M5_company_relations.json`, with evidence shards under `public/data/<version>/evidence/`. Pipeline instructions retrieve EDINET with an API key and, for the observed snapshot, list only 2025-06-14 through 2026-06-13. No such data files or EDINET archive exist in this workspace.

## B. Related research

### Customer Momentum (Pinchuk; working paper)

The paper defines customer momentum as supplier/focal-company performance associated with past returns of its customers. It reports statistically and economically significant results in a U.S. CRSP sample, notes that it is distinct from ordinary price and earnings momentum, and reports weaker/non-significant post-discovery performance. Its frequency and portfolio evidence are monthly; the paper also discusses short-term daily-return tests. It therefore supports the economic direction and motivates a small fixed feature, but does not guarantee persistence after discovery.

The paper's publicly visible abstract/text reviewed here does not establish the exact PIT relationship-feed vintage, an EDINET-style filing-availability contract, the requested Japanese 2011-2016 code mapping, or the costs for this competition. Those details are not inferred.

### Tanaka & Tsuda (2025), statistical causal discovery

The Doshisha repository identifies a Japanese-language departmental bulletin paper by Hisanori Tanaka and Hiroshi Tsuda, published January 2025. It studies supplier-customer information in Japan, proposes Customer Impact Index (CII), and reports that a CII-sorted portfolio had higher return and lower standard deviation than conventional customer momentum. The text indexed for the paper describes CMOM quintiles, equal-weighting within portfolios, monthly rebalancing/one-month performance, and a CII built from DirectLiNGAM effects estimated on the previous three months of daily returns, combined with customer monthly returns and averaged over customers. The indexed figure period is March 2015–March 2023.

The paper's causal coefficient/sign weighting is materially more complex than the requested equal-weight NCMOM20 and is not being copied. From the accessible primary record/text, we could not verify a publication-time PIT relation reconstruction, a historical relationship vintage protocol, a transaction-cost treatment, or an independent robustness design adequate to claim competition net performance. The paper is inspiration, not evidence that JMV's 2026 snapshot can be backfilled.

### Japanese supplier-customer link persistence evidence

Mizuno, Souma, and Watanabe (2014) analyze annual Japanese customer/supplier links for more than 500,000 non-financial firms over 2008-2012. They estimate one-year link survival of 92% for customer links and 93% for supplier links, while also noting that some firms change partners frequently. A later Japan firm-network panel covering 2007-2016 reports that link survival rises with relationship tenure and that younger firms change links more often. These studies make a **one-annual-cycle forward carry** a defensible prior after a dated observation. They do not establish that every JMV `major_customer` entry (a disclosure threshold category) persists for multiple years, nor do they justify carrying 2025 disclosures back to Train. Repeated PIT-dated annual confirmation remains the preferred way to extend an edge over several years.

Sources: [Mizuno, Souma & Watanabe (2014), PLOS ONE](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0100712); [The Dynamics of Inter-firm Networks and Firm Growth, RIETI Discussion Paper 17-E-110](https://www.rieti.go.jp/jp/publications/dp/17e110.pdf).

| Requested review item | Research evidence found | What remains unverified |
|---|---|---|
| Market | Pinchuk: U.S. equities; Tanaka/Tsuda: Japanese equities | Direct quantitative transferability to this 498-stock competition universe |
| Horizon | Customer returns predict later focal/supplier performance; Tanaka/Tsuda monthly CMOM and one-month portfolio with three months of daily inputs to CII | Exact compatibility with competition's next-day residual target |
| Relationship | Directed customer/supplier commercial link; customer → supplier information channel | Full historic relationship-feed lineage/vintages and edge persistence in the sources available here |
| Weighting | Equal-weight customer momentum portfolios; CII weights customer returns by DirectLiNGAM-derived effect/sign and normalizes across relation count | No CII or learned edge weight is proposed here |
| Findings | Papers report positive customer-momentum evidence; Tanaka/Tsuda's abstract reports higher return/lower standard deviation for CII versus CMOM | No claim about after-cost performance for this experiment; numerical net-cost evidence not verified |
| Look-ahead handling | The papers motivate historical relationships and later returns | Publicly reviewed text did not establish a first-public-timestamp rule sufficient for our PIT contract |
| Costs | Not established in the accessible evidence reviewed | Competition's fixed 10 bp one-way cost would need applying in any future candidate run |
| Robustness | Pinchuk documents post-discovery weakening; Tanaka/Tsuda compares CII and CMOM over its stated period | No inference of stable Train-era Japanese network alpha or target-horizon robustness |

## Primary references

- [JP_Market_Vis README](https://github.com/mattyamonaca/JP_Market_Vis) and [pipeline README](https://github.com/mattyamonaca/JP_Market_Vis/blob/main/pipeline/README.md).
- [Tanaka & Tsuda (2025), Doshisha Repository record](https://doshisha.repo.nii.ac.jp/records/2000820) and [paper PDF](https://doshisha.repo.nii.ac.jp/record/2000820/files/023065040008.pdf).
- [Pinchuk, “Customer Momentum”](https://arxiv.org/abs/2301.11394).
