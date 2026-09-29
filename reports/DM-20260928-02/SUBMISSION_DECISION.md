# Submission Decision — SN1_H1 Final Structural Audit

Correction to the side-level cost attribution: [ACCOUNTING_ERRATA.md](ACCOUNTING_ERRATA.md).

### Root cause

1. Low event H1 information is weak and inconsistent between Train and historical Valid.
2. Low-state precedence plus persistent cross-sectional ranks prolongs Short assignments after event information decays; recent/recurrent Low Shorts also lose in historical Valid.
3. Most scores are near zero, making membership sensitive to tiny perturbations and, in Train, to tie ordering.

### Low branch integrity

**PASS** — sign orientation, prediction timing, H1 target alignment, EWMA order, reset behavior, portfolio-weight sign, and P/L sign match the fixed contract. No implementation bug was found.

### SN1_H1

**MIXED** — Train annualized Net +4.517% / Net SR 1.063; historical-Valid development Net +0.245% / Net SR 0.052 at 10 bps. Historical Valid is weak and must not be described as forward OOS.

### New structural candidate

**None — REJECTED at the eligibility gate.** No candidate was created or evaluated. The documented 60-session expiry remains rejected; no replacement age variant was tried.

### Submission strategy

**Submit `SN1_H1` unchanged.** Freeze its existing specification and code for submission; future paper observations are the forward OOS period.

### Why

1. No Low-branch implementation defect requires correction.
2. Source and sector behavior do not support a unique parameter-free rule across both development periods; the visible size/beta exposures are descriptive.
3. A cost or tie result does not authorize a new rule: historical-Valid Net is nearly flat at 20 bps, while near-zero tie dependence is material and cannot be fixed by changing the official ranking order.

### Remaining uncertainty

1. Historical Valid has already been observed and is development data; only future paper is prospective OOS.
2. At 30 bps, historical-Valid SN1_H1 Net turns negative. Relative advantage over D is not established because no exact saved D H1 artifact exists in the fixed run.
3. Attribution does not establish that removing Short exposure, neutralizing size/sector, or changing source precedence would persist or improve submission performance.

## Answers to the 13 audit questions

1. **Low target/sign/execution/P&L:** Yes. Negative Low score means more bearish; signal date t trades Open(t+1)→Open(t+2); raw residual target reconstruction error is 0; weight×target signs agree.
2. **Weak Low event predictor:** Partly yes. H1 Low event RankIC is −0.0146 Train and −0.0009 historical Valid, with opposite Q5−Q1 spread signs.
3. **State/rank cause:** Yes, materially. Old near-zero Low states can continue to control rankings, but recurrent Low Short losses show this is not the only cause.
4. **Sector/size/systematic cause:** Size and beta exposure are visible; no stable single sector loss explains both periods. Attribution is descriptive, not causal.
5. **Persistent Long via High renewal:** Partly in Train; not consistently. Persistent High Long contributes +5.156% Train and +0.859% historical Valid; Low Long contributes +0.840% and +1.081%.
6. **Stable Low-source Long profit:** Positive in both annual aggregates, but smaller in Train and larger than High in historical Valid; its selection is highly near-zero/rank-sensitive.
7. **Long source or relative ranking:** Both interact. The dominant source changes across periods and High/Low Long RankICs are modest; portfolio membership comes from relative rank, not absolute score size.
8. **Near-zero/tie dependence:** High. `abs(score)<1e−12` covers 75.86% Train and 81.36% historical Valid; a tiny perturbation changes 328,467/751,723 quintile rows.
9. **Reset/missing bug:** None observed. Reset rows match raw event scores exactly; no 2–20 or exact-20 gap cases exist to test.
10. **Worse-cost robustness:** SN1 itself remains positive through 20 bps Train, but historical Valid is nearly zero at 20 bps and negative at 30 bps. Relative advantage versus D is unknown; no exact saved D artifact was available.
11. **One-year dependence:** No single year reverses the leave-one-year-out aggregate; all Train and historical-Valid leave-one-year-out Net SRs stay positive. Historical-Valid annual strength is still modest and uneven.
12. **One structural intervention justified:** No.
13. **If none, submit SN1_H1 unchanged:** Yes, per the predeclared stopping rule.
