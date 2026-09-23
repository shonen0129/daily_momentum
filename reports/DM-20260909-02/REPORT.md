# DM-20260909-02: Fixed Momentum Long / Independent Short Ranking

Run: `run-20260909T061458Z`。Train-only。Valid/raw target未参照。提出用Freezeなし。

## 1. 判定結果サマリー

| Candidate | 判定 | 改善fold (Short/NetSR) | median ΔShort年率Net | median ΔNet SR | bootstrap 95% CI | Long固定 |
|---|---|---:|---:|---:|---|:---:|
| T0 | **却下** | 0/4 / 0/4 | 0.00% | 0.0000 | [0.0000, 0.0000] | PASS (0差分) |
| T1 | **採用可能** | 3/4 / 3/4 | 1.16% | 0.3631 | [0.0281, 0.6834] | PASS (0差分) |
| T2 | **Promising but insufficient** | 3/4 / 3/4 | 0.23% | 0.0722 | [-0.0981, 0.3621] | PASS (0差分) |
| T3 | **却下** | 0/4 / 0/4 | -2.39% | -0.5168 | [-0.7633, -0.1023] | PASS (0差分) |

実試行数: 5/5。旧研究44試行を含む既知の累積scoring試行数は **48**（新規scoring候補4本）。未実行枠の転用なし。

## 2. 全候補の開発成績 (2011–2014 Walk-Forward Pooled)

| Trial | Gross SR | Net SR | RankIC | Turnover | 年率Cost | Short年率Net | Long年率Net | MaxDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 | 0.7703 | 0.4413 | 0.00797 | 0.0649 | 1.64% | -2.21% | 4.41% | -10.11% |
| T0 | 0.7703 | 0.4413 | 0.00797 | 0.0649 | 1.64% | -2.21% | 4.41% | -10.11% |
| T1 | 1.1263 | 0.7839 | 0.01005 | 0.0584 | 1.47% | -1.04% | 4.41% | -7.23% |
| T2 | 1.0438 | 0.5628 | 0.01077 | 0.0886 | 2.23% | -1.79% | 4.41% | -8.41% |
| T3 | 1.0900 | 0.0108 | 0.00785 | 0.1802 | 4.54% | -4.36% | 4.41% | -9.86% |

## 3. Long固定の完全検証 (Long Preservation Audit)

全候補について、B0 (Momentum Baseline) と比較した上位40% (Q4/Q5) の所属一致、ウェイト一致、日次Long貢献一致を検証した。

| Candidate | Q4/Q5所属不一致数 | Longウェイト最大差 | 日次Long損益最大差 | 判定 |
|---|---:|---:|---:|:---:|
| B0 | 0 | 0.0e+00 | 0.0e+00 | 完全一致 (PASS) |
| T0 | 0 | 0.0e+00 | 0.0e+00 | 完全一致 (PASS) |
| T1 | 0 | 0.0e+00 | 0.0e+00 | 完全一致 (PASS) |
| T2 | 0 | 0.0e+00 | 0.0e+00 | 完全一致 (PASS) |
| T3 | 0 | 0.0e+00 | 0.0e+00 | 完全一致 (PASS) |

## 4. Fold別・年別詳細とBaseline差分

各年の損益は、境界を跨ぐ2営業日をパージした2011/2012/2013/2014年（各243/246/243/242日、計974日）で集計。

### T0: Stitched Momentum Control (Bitwise match against B0 required)

- 判定: **却下**
- Primary Criteria チェック: {'short_side_improved_folds': False, 'median_delta_short_net': False, 'net_sharpe_improved_folds': False, 'median_delta_net_sr': False, 'pooled_total_net_sr': False, 'pooled_short_net': False, 'long_fixed_preserved': True}

| 年 | Net SR | ΔNet SR | Short年率Net | ΔShort年率Net | Long年率Net | ΔLong年率Net | Turnover | ΔTurnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 0.4904 | +0.0000 | -4.65% | +0.00% | 7.51% | +0.00% | 0.0694 | +0.0000 |
| 2012 | 0.6333 | +0.0000 | 1.37% | +0.00% | 1.30% | +0.00% | 0.0656 | +0.0000 |
| 2013 | 0.0799 | +0.0000 | -3.31% | +0.00% | 3.81% | +0.00% | 0.0638 | +0.0000 |
| 2014 | 0.9080 | +0.0000 | -2.30% | +0.00% | 5.05% | +0.00% | 0.0608 | +0.0000 |

### T1: Fixed Long + Equal FD Short

- 判定: **採用可能**
- Primary Criteria チェック: {'short_side_improved_folds': True, 'median_delta_short_net': True, 'net_sharpe_improved_folds': True, 'median_delta_net_sr': True, 'pooled_total_net_sr': True, 'pooled_short_net': True, 'long_fixed_preserved': True}

| 年 | Net SR | ΔNet SR | Short年率Net | ΔShort年率Net | Long年率Net | ΔLong年率Net | Turnover | ΔTurnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 0.7141 | +0.2237 | -3.84% | +0.81% | 7.51% | +0.00% | 0.0639 | -0.0055 |
| 2012 | 0.5823 | -0.0510 | 0.79% | -0.58% | 1.30% | +0.00% | 0.0602 | -0.0055 |
| 2013 | 0.6858 | +0.6059 | -0.35% | +2.97% | 3.81% | +0.00% | 0.0568 | -0.0070 |
| 2014 | 1.4104 | +0.5025 | -0.79% | +1.51% | 5.05% | +0.00% | 0.0527 | -0.0081 |

### T2: Fixed Long + Equal FD x WeakPrice Short

- 判定: **Promising but insufficient**
- Primary Criteria チェック: {'short_side_improved_folds': True, 'median_delta_short_net': True, 'net_sharpe_improved_folds': True, 'median_delta_net_sr': True, 'pooled_total_net_sr': True, 'pooled_short_net': True, 'long_fixed_preserved': True}

| 年 | Net SR | ΔNet SR | Short年率Net | ΔShort年率Net | Long年率Net | ΔLong年率Net | Turnover | ΔTurnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 0.5362 | +0.0458 | -4.54% | +0.11% | 7.51% | +0.00% | 0.0942 | +0.0248 |
| 2012 | 0.5475 | -0.0859 | 0.86% | -0.51% | 1.30% | +0.00% | 0.0897 | +0.0240 |
| 2013 | 0.4014 | +0.3215 | -1.58% | +1.73% | 3.81% | +0.00% | 0.0875 | +0.0236 |
| 2014 | 1.0065 | +0.0986 | -1.94% | +0.36% | 5.05% | +0.00% | 0.0832 | +0.0224 |

### T3: Fixed Long + Equal FD x WeakPrice + RecentCrash Avoidance

- 判定: **却下**
- Primary Criteria チェック: {'short_side_improved_folds': False, 'median_delta_short_net': False, 'net_sharpe_improved_folds': False, 'median_delta_net_sr': False, 'pooled_total_net_sr': False, 'pooled_short_net': False, 'long_fixed_preserved': True}

| 年 | Net SR | ΔNet SR | Short年率Net | ΔShort年率Net | Long年率Net | ΔLong年率Net | Turnover | ΔTurnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 0.3235 | -0.1669 | -5.92% | -1.27% | 7.51% | +0.00% | 0.1863 | +0.1169 |
| 2012 | 0.0400 | -0.5934 | -1.17% | -2.53% | 1.30% | +0.00% | 0.1849 | +0.1193 |
| 2013 | -0.3604 | -0.4403 | -5.69% | -2.37% | 3.81% | +0.00% | 0.1769 | +0.1131 |
| 2014 | 0.1162 | -0.7917 | -4.72% | -2.41% | 5.05% | +0.00% | 0.1726 | +0.1118 |

## 5. 既読Trainの記述的確認 (Confirmation 2015–2016-03 & Stability 2008–2010)

2015–2016-03 および 2008–2010 は過去研究で既読であり、独立したholdoutではない。モデル選択の根拠には使用せず、記述的安定性の確認としてのみ記録する。

### 2015–2016-03 (Confirmation Window)

| Trial | Net SR | ΔNet SR | Short年率Net | ΔShort年率Net | Long年率Net | Turnover |
|---|---:|---:|---:|---:|---:|---:|
| B0 | -0.0768 | +0.0000 | -5.76% | +0.00% | 5.29% | 0.0663 |
| T0 | -0.0768 | +0.0000 | -5.76% | +0.00% | 5.29% | 0.0663 |
| T1 | 0.2185 | +0.2954 | -4.20% | +1.56% | 5.29% | 0.0603 |
| T2 | 0.0858 | +0.1626 | -4.82% | +0.93% | 5.29% | 0.0875 |
| T3 | -0.4422 | -0.3654 | -7.58% | -1.82% | 5.29% | 0.1790 |

### 2008–2010 (Descriptive Pre-sample)

| Trial | Net SR | ΔNet SR | Short年率Net | ΔShort年率Net | Long年率Net | Turnover |
|---|---:|---:|---:|---:|---:|---:|
| B0 | -1.9070 | +0.0000 | -9.14% | +0.00% | 1.23% | 0.0665 |
| T0 | -1.9070 | +0.0000 | -9.14% | +0.00% | 1.23% | 0.0665 |
| T1 | -1.0744 | +0.8326 | -5.60% | +3.54% | 1.23% | 0.0613 |
| T2 | -1.3588 | +0.5481 | -6.82% | +2.33% | 1.23% | 0.0854 |
| T3 | -1.7257 | +0.1813 | -8.06% | +1.08% | 1.23% | 0.1804 |

## 6. 研究上の問いに対する最終回答

### Q1. 結論は何か？
**結論: T0: 却下, T1: 採用可能, T2: Promising but insufficient, T3: 却下**

### Q2. Long固定は本当に成立したか？
- 全候補（T0, T1, T2, T3）において、Q4/Q5の銘柄所属不一致数は **0件**、Longウェイト最大差は **0.0**、日次Long貢献差分は **0.0** を確認。
- Shortモデルの変更によるLong側の破壊は完全に防止された。

### Q3. Shortは改善したか？
- T1 (Equal FD Short): median ΔShort年率Net = +1.16%、改善fold = 3/4。
- T2 (FD × WeakPrice): median ΔShort年率Net = +0.23%、改善fold = 3/4。
- T3 (RecentCrash Avoidance): median ΔShort年率Net = -2.39%、改善fold = 0/4。

### Q4. Total Portfolioは改善したか？
- T1: Net SR = 0.7839 (Δ = +0.3427)
- T2: Net SR = 0.5628 (Δ = +0.1215)
- T3: Net SR = 0.0108 (Δ = -0.4305)

### Q5. T1 / T2 / T3 の比較と追加価値
- T1 vs B0: FD単体によるShort順位付けの効果。
- T2 vs T1: WeakPrice interaction による増分効果（ΔNet SR = -0.2211）。
- T3 vs T2: RecentCrash Avoidance（M5下位20%除外）による増分効果（ΔNet SR = -0.5520）。

### Q6. 統計的不確実性と過学習リスク
- Circular block bootstrap (1000回, 20日ブロック) の95% CI を算出し、区間が0を跨ぐか確認した。
- 既知の累積scoring試行数 48 回を記録。Train期間は過去研究で既知であるため、本結果は独立な有意性証明ではなく、Train内の有限比較である。

### Q7. Validの非参照確認
- **Validデータ（特徴量・ターゲット・行数・実測性能）は一切参照・実行していない。**
- raw_target も研究コードから一切読み込んでいない。

---
成果物パス: `artifacts/DM-20260909-02/run-20260909T061458Z`
レポートパス: `reports/DM-20260909-02/REPORT.md`
