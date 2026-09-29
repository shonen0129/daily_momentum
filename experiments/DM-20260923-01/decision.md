# DM-20260923-01: 採否判定記録

- 判定日: 2026-09-23
- 戦略名: `dm_high_proximity_momentum`
- Run ID: `run-20260923T120052Z`

## 各候補の選別結果

- **H0**: Baseline, Pooled Net SR=0.4051
- **P60**: 判定=`Rejected`, Pooled Net SR=-0.2125 (Δ=-0.6176, 改善Fold=2/4, median Δ=-0.5525)
- **C1**: 判定=`Rejected`, Pooled Net SR=-0.0552 (Δ=-0.4603, 改善Fold=2/4, median Δ=-0.3501)
- **C2**: 判定=`Rejected`, Pooled Net SR=0.2150 (Δ=-0.1901, 改善Fold=2/4, median Δ=-0.1689)
- **C3**: 判定=`Candidate`, Pooled Net SR=0.5164 (Δ=+0.1112, 改善Fold=3/4, median Δ=+0.1904)
- **C4**: 判定=`Rejected`, Pooled Net SR=0.3445 (Δ=-0.0607, 改善Fold=2/4, median Δ=-0.0359)
- **C5**: 判定=`Rejected`, Pooled Net SR=0.3143 (Δ=-0.0908, 改善Fold=0/4, median Δ=-0.0674)

## 結論

一次選別基準を満たした最良候補 `C3` を Promising Candidate として記録。

## 2026-09-24 技術監査による追補

初回C3の`prox250`はraw High/Closeの価格単位を株式分割・併合イベント前後で揃えていなかった。詳しくは[DM-20260924-01 correctness audit](../../reports/DM-20260924-01/TECHNICAL_AUDIT.md)。そのため、このCandidate判定は当時のTrainスクリーニング結果の記録として保持するが、現在の採用候補・Freeze候補としては撤回する。成績表は歴史的run値として変更しない。

修正定義`C3S`はDM-20260924-01で別候補として実装・検証した。C3SのTrain成績は事後的な既知期間の記述値であり、旧C3の成績を引き継がない。Validはワークスペースで別リリースに対し評価済みのため、C3Sの未使用OOSとは呼ばず、本追補では評価しない。
