# DM-20260911-03: 採否

判定日: 2026-09-11。**R_RAW/R_RES/E_RAW/E_RESを全て不採用。現Champion H0を維持する。**
Run: `artifacts/DM-20260911-03/run-20260911T043254Z`。
[結果と解釈](../../reports/DM-20260911-03/REPORT.md) / [事前計画](plan.md)。

## 判断理由

- 技術的な全ゼロ化は全4候補で解消した。開発年の非ゼロ係数はRidge RAW/RES各42、Elastic Net RAW 2–3、RES 6。
- 日次断面予測の全同値日は0。係数を人工的に非ゼロ化するノイズや手動係数は使用していない。
- 各候補のH0比Short損益/全体NetSR改善年は全て0/4。Short単独が正の年も全て0/4。
- R_RAW: NetSR -1.1955、Short年率Net -6.17%、全体年率Cost 7.69%。
- R_RES: NetSR -1.7771、Short年率Net -6.98%、全体年率Cost 6.59%。
- E_RAW: NetSR -2.5783、Short年率Net -8.49%、全体年率Cost 11.59%。
- E_RES: NetSR -1.7621、Short年率Net -6.92%、全体年率Cost 5.41%。
- H0: NetSR +0.7839、Short年率Net -1.04%、全体年率Cost 1.47%。
- Short Grossも全候補で負。RAW全体のGrossには改善があるが、コストを回収できなかった。
- 残差版のinitial CV MSEはnullより僅かに改善しても、後続開発期間のRankIC/損益に持続しなかった。

## 設定と試行数

選択lambda/rhoはR_RAW=1.0、R_RES=1.0、E_RAW=0.9、E_RES=0.5。
2008–2010の旧2fold MSEで選択し、2011–2016の年次fitでは同じ比率を固定した。
RAW/RESの21日42特徴量とEWMA0.25は旧DRIと同一。Long/Short全体DRIの比較で、Long固定hybridの採点ではない。
4新候補+4対照=8採点、累積83（対照再採点含む）。別途12 hyperparameter configurations、24 CV fits、24 annual fits。
旧実験の結果・設定を変更していない。事後候補追加や未実行枠転用なし。

## 監査と再現

全76テストPASS（新規10）。既存Freeze129 hashと既存zip全809,636行の予測一致。
3cutoffで旧特徴量との一致、future-mutation/truncationによる特徴量・予測一致。
未実現ラベル改変による年次refitとinitial CV選択もbitwise一致。
各候補の独立推論コピーはラベルなしで2回決定的に動作し、全809,636行が研究予測とbitwise一致。
公式qcut weightと日次PLは全974開発営業日で一致。
実行71.94秒、最大RSS約3.41 GiB（本体プロセス）。設定・source・モデル・入力hashをrunに保存。

2015–2016-03の既読Trainは採否保存後に記述的確認だけを行った。独立OOSとは呼ばない。
Valid/raw target読込なし、Freeze/提出なし。
今回の固定daily DRI正則化候補を却下するもので、DRI一般や原論文の月次戦略の無効性を意味しない。
