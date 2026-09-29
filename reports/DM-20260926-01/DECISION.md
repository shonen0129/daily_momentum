# DM-20260926-01 Decision

All comparisons use Train periods already reviewed. These labels summarize fixed descriptive diagnostics and do not imply independent OOS validation.

### 1. Current BOX

- **Reject** as the current B00 alternative.
- BOX Net SR 0.7851, annual Net +3.65%; B00 Net SR 0.8197, annual Net +3.83%. The current candidate does not establish an incremental Box/Ridge advantage. Tie and Short attribution are in `AUDIT.md`.

### 2. Candidate A

- **Stop** under the predeclared descriptive criteria.
- BOX Low-no-carry ΔNet SR vs current BOX: -0.0461; ex-2016 ΔNet SR: +0.0228. Same rule on B00 ΔNet SR vs B00: -0.0181.
- BOX annual selection-component change: -0.315%; common-residual component change: +0.034%; weak-year nondegradation check (2011/2015, BOX and B00): False.
- Low carry stop raises turnover by +0.01404/day and annual cost by +0.35%; Q1 zero-score gross-weight share moves 9.5%→51.9%. Total Short score-zero/code-order tie weight moves 8.1%→46.9%; actual Short positions remain. This candidate worsens Net SR and is strongly exposed to code-order tie-breaks.
- Separate non-official gamma diagnostics reach BOX Net SR 1.043/1.057/1.012 at γ=.50/.25/0; same-rule B00 is 1.060/1.064/1.013. At γ=0, B00 is slightly better; both ex-2016 Sharpe are below 1 (0.950 BOX, 0.952 B00). BOX γ=0 net exposure change is +50.11%, common-component change +3.44%, and selection-component change -2.03% vs BOX original. The apparent Sharpe gain is not Box-specific and includes greater net-long/common-drift exposure plus lower Short loss/cost.
- Cause split for BOX γ=.50/.25/0: net exposure +25.0%/+37.5%/+50.1%; common component +1.78%/+2.64%/+3.50%; selection +3.38%/+2.87%/+2.37%; Net vol 4.29%/4.62%/5.23% vs BOX 4.65%; annual cost 0.68%/0.63%/0.57% vs BOX 0.80%. At γ=0 the Short contribution falls from -1.65% to +0.00%; same-rule B00 has higher full-period Net SR at every gamma < 1.
- Net SR >= 1 in a non-official gamma sleeve rule alone is not an adoption rule.
- `A_LOW_NO_CARRY` and `A_B00_LOW_NO_CARRY` use official five-quintile weights. All gamma<1 descendants are separate non-official short-scaled operating rules.

### 3. Candidate B

- Box condition: **Box condition adds a possible pooled point-estimate value**. B2−B1 Net SR +0.0424; annual Net return difference +0.006%; ex-2016 Sharpe difference +0.0509. The net-return point difference is small, gross return is lower, only 2/6 yearly folds improve, and the paired bootstrap interval includes zero; treat it as weak, mixed Train evidence.
- Ridge ranking: **no evidence that Ridge adds value**. B3−B2 Net SR -0.1517; ex-2016 difference -0.1634.
- These comparisons use the same eligible event set for B2/B3 and are not independent OOS proof.

### 4. Next action

- One action: record eligible-Box gating as a possible hypothesis without adding windows/thresholds; stop this fixed Train series. No Valid access or parameter search.
