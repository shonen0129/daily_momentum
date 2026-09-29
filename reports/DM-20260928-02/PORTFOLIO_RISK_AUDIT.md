# Portfolio Risk Audit — SN1_H1

Risk exposure is attributed to the fixed portfolio and the existing PIT descriptors `Sector17Code`, `Sector33Code`, and `ScaleCategory`. Beta is shown as a continuous signal-date exposure using the existing 120-market-day rolling beta. No new beta bucket, predictor, neutralization strength, or risk rule was created. Attribution remains descriptive, not a counterfactual.

## Persistent Short size exposure

| Split | PIT size group | Share of persistent Short gross weight | Annualized Net contribution |
|---|---|---:|---:|
| Train | TOPIX Mid400 | 67.4% | −1.188% |
| Train | TOPIX Small 2 | 10.1% | −0.711% |
| Train | TOPIX Large70 | 15.8% | +0.242% |
| Train | TOPIX Core30 | 6.3% | +0.178% |
| Historical Valid | TOPIX Mid400 | 74.9% | −1.078% |
| Historical Valid | TOPIX Small 1 | 3.0% | −0.182% |
| Historical Valid | TOPIX Small 2 | 2.0% | −0.193% |
| Historical Valid | TOPIX Large70 | 14.4% | +0.015% |
| Historical Valid | TOPIX Core30 | 5.5% | −0.078% |

Mid400 exposure is persistent and is the largest loss contribution in both periods. Losses also appear in small-size groups; the result is not isolated to a single segment.

## Sector pattern

The largest persistent-Short Sector17 net losses in Train are codes 14 (−0.619%), 10 (−0.467%), 3 (−0.307%), and 1 (−0.262%). In historical Valid they are codes 10 (−0.521%), 9 (−0.321%), 8 (−0.288%), and 3 (−0.205%). Sector 3 recurs, but the largest-loss sector changes. Sector33 contributions are available in the full exposure table.

## Continuous PIT beta

| Split | Side, sleeve age | Mean stock beta | Mean daily signed beta load | Mean daily gross beta load | Beta coverage |
|---|---|---:|---:|---:|---:|
| Train | Long, ≥20 | 0.905 | +0.431 | 0.431 | 98.7% |
| Train | Short, ≥20 | 1.110 | −0.514 | 0.514 | 100.0% |
| Historical Valid | Long, ≥20 | 0.956 | +0.462 | 0.462 | 99.6% |
| Historical Valid | Short, ≥20 | 1.065 | −0.483 | 0.483 | 100.0% |

The persistent book has a modest net short beta load in both periods (about −0.083 Train and −0.021 historical Valid). Beta exposure is stable, but the evaluated H1 target is already beta-adjusted; the observed residual Short losses are not, by themselves, evidence that a beta projection will fix them. No PIT market-cap field was present in the saved listing profile; `ScaleCategory` is the available size proxy. No separate point-in-time volatility descriptor was used.

## Year stability and machine-readable detail

Sector17, Sector33, and size exposure/contribution by year are in `risk_exposure_by_year.csv`; continuous beta exposure by year is in `risk_beta_exposure_by_year.csv`. The account-side annual contributions by year are present in `daily_account_replay_train.csv` and `daily_account_replay_historical_valid.csv`. Partial years are flagged in the annual exposure tables. Persistent-Short net contribution changes sign across years, so its aggregate loss is not a constant annual sector effect.

- `artifacts/DM-20260928-02/run-20260928T103320Z/metrics/risk_exposure.csv`
- `artifacts/DM-20260928-02/run-20260928T103320Z/metrics/risk_exposure_by_year.csv`
- `artifacts/DM-20260928-02/run-20260928T103320Z/metrics/risk_beta_exposure.csv`
- `artifacts/DM-20260928-02/run-20260928T103320Z/metrics/risk_beta_exposure_by_year.csv`

No exposure-neutralized strategy was created. The size concentration and beta load do not uniquely imply a parameter-free projection that preserves the economic interpretation and submission contract.

