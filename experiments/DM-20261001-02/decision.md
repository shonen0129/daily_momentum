# DM-20261001-02 decision

**Result: NOT SUPPORTED** for the preregistered claim that SN1_H1 ranking quality deteriorates as VOL20 rises. **No trading strategy change.** No confidence adjustment candidate was fit or evaluated.

## Evidence

- Pooled within-volatility RankIC increased from 0.00794 in V1 to 0.01541 in V5; HAC-5 t-stat increased from 1.83 to 2.94.
- Score-ranked Q5−Q1 increased from 1.09 bp/day in V1 to 8.70 bp/day in V5. It was higher in V5 in all six year/fold rows, including the 61-session partial 2016 fold; RankIC was higher in V5 in four of five complete years.
- Official Short gross loss was more negative in V1 (-0.539% annual contribution) than V5 (-0.087%); official Long contribution was larger in V5 (+2.202%) than V1 (+0.869%). These are accounting attributions of existing holdings, not counterfactual portfolios.
- Near-zero-score RankIC was 0.00226 in V1 and 0.00732 in V5, with weak HAC t-statistics in both groups. The fixed tiny perturbation changed fewer quintile rows in V5 (49.45%) than V1 (61.51%).
- The non-near-zero subset showed a mixed descriptive interaction: RankIC was 0.02785 in V1 and 0.00179 in V5. This does not alter the pooled result or justify a monotone VOL shrinkage rule; any follow-up would need a separate predeclared experiment.

## Audit and scope

- Current-route, independent-route, saved-current, and prior SN1_H1 scores matched bit for bit over 809,636 rows.
- VOL20 source/definition audit, static scan, Train firewall, deterministic replay, official account comparison (within `2e-15` CSV/numeric tolerance), and three-cutoff future-mutation prefix invariance passed.
- Valid and raw-target inputs were not opened. Candidate fits: zero. Train evidence is development history, not independent OOS.
- Full metrics and limitations: [report](../../reports/DM-20261001-02/REPORT.md). Primary run: `run-20261001T104507Z-03`.

No entry is added to `GRAVEYARD.md`: this experiment evaluated no candidate to reject.
