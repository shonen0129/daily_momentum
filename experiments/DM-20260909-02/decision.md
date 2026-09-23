# Decision: DM-20260909-02

Evaluated on 2026-09-09T06:19:05.935074+00:00 via run `run-20260909T061458Z`.

## Primary Criteria Evaluation

### T0 (Stitched Momentum Control (Bitwise match against B0 required))
- Decision: **却下**
- Short side improved folds: 0/4
- Median ΔShortNet: 0.00%
- Net Sharpe improved folds: 0/4
- Median ΔNetSR: 0.0000
- Pooled ΔNetSR: 0.0000
- Bootstrap 95% CI: [0.0000, 0.0000]
- Long preservation: PASS

### T1 (Fixed Long + Equal FD Short)
- Decision: **採用可能**
- Short side improved folds: 3/4
- Median ΔShortNet: 1.16%
- Net Sharpe improved folds: 3/4
- Median ΔNetSR: 0.3631
- Pooled ΔNetSR: 0.3427
- Bootstrap 95% CI: [0.0281, 0.6834]
- Long preservation: PASS

### T2 (Fixed Long + Equal FD x WeakPrice Short)
- Decision: **Promising but insufficient**
- Short side improved folds: 3/4
- Median ΔShortNet: 0.23%
- Net Sharpe improved folds: 3/4
- Median ΔNetSR: 0.0722
- Pooled ΔNetSR: 0.1215
- Bootstrap 95% CI: [-0.0981, 0.3621]
- Long preservation: PASS

### T3 (Fixed Long + Equal FD x WeakPrice + RecentCrash Avoidance)
- Decision: **却下**
- Short side improved folds: 0/4
- Median ΔShortNet: -2.39%
- Net Sharpe improved folds: 0/4
- Median ΔNetSR: -0.5168
- Pooled ΔNetSR: -0.4305
- Bootstrap 95% CI: [-0.7633, -0.1023]
- Long preservation: PASS

