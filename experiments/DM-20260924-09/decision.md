# DM-20260924-09: 採否記録

- 判定日: 2026-09-24
- Status: Rejected
- Run ID: `run-20260924T073715Z`
- 実試行数: 1/1（事前上限1、結果後の追加なし）
- [結果レポート](../../reports/DM-20260924-09/REPORT.md)

## 固定候補

前営業日終値を前営業日を除く過去250観測High/Lowへ写像したsplit-safe channel positionと、前日/2営業日前のsplit-safe raw Volume比から1を引いた1日変化率の2特徴。年次expanding Ridge(lambda=1)、日次centered target rank、fold内Train標準化/欠損補完、EWMA alpha=0.25。H0、B00、既存channel単独scoreを同じ1518評価日で比較。

## 結果

| Metric | H0 | B00 | Channel単独 | RIDGE_001 |
|---|---:|---:|---:|---:|
| Gross Sharpe | 0.3074 | 0.7334 | 0.4036 | 0.1165 |
| Net Sharpe | -0.0220 | 0.5687 | 0.1184 | -0.8545 |
| Δ Net Sharpe vs baseline | — | — | H0 +0.1404 | H0 -0.8325 / B00 -1.4232 / channel -0.9729 |
| 年率Net P/L | -0.11% | +2.50% | +0.57% | -4.06% |
| 年率Cost | 1.63% | 0.72% | 1.38% | 4.61% |
| 日次Turnover | 0.06460 | 0.02870 | 0.05487 | 0.18418 |
| RankIC | +0.0041 | +0.0067 | +0.0071 | +0.0007 |
| Long / Short年率Net | +3.59% / -3.70% | +4.60% / -2.10% | +3.89% / -3.32% | +1.62% / -5.68% |
| 最大DD | -10.10% | -6.99% | -10.67% | -34.17% |

H0比のNet Sharpe改善は2/7 fold、B00比1/7、channel単独比2/7。B00比paired 20日block bootstrap 95%区間は[-2.6561,-0.2508]、H0比[-2.2359,+0.5036]、channel単独比[-2.2791,+0.2622]。年次係数の符号・大きさも安定せず、特にShort損失、turnover、cost、drawdownが悪化した。

**判定:** `RIDGE_001`を不採用。今回固定した2特徴・raw出来高変化率・Ridge(lambda=1)の組合せは、channel単独および両baselineを改善しなかった。これは出来高変化や線形モデル一般を否定する結果ではないが、全Train既知のため、volume変換・外れ値処理・lambda・窓幅をこの成績を見て追加探索しない。

## 検証と範囲

- 対象特徴テスト: 4 passed（位置窓/時点、volume比較時点、split連続性、cutoff後mutation prefix-invariance）。
- Source scan: PASS。raw OHLCVと観測済みAdjustmentFactorイベントのみを使い、Adjusted OHLCV水準・future target等を特徴に読まない。
- 2010-12-30、2012-12-28、2015-12-30 cutoffで全入力source mutation/truncationを実施。特徴、H0/B00/channel、成熟Train rows、Ridge refitと直近予測はbitwise一致。
- 決定的な2016 fold再fit、評価日682,038行の全signal coverage、有限値、Long+Short会計照合: PASS。
- `make check`: PASS。Train firewallはValid/Valid target/raw target未読を記録。Freezeなし、submission既定値変更なし。

全期間は既知で独立OOSではない。未解決の確認は、新しい独立評価根拠なしにこの実験からは得られない。
