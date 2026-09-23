# DM-20260909-03: Continuous Fundamental Weakness Short

事前登録: 2026-09-09。設定の正本は `config.json`。戦略仕様正本は
`docs/strategies/投資戦略仮説0909-03.md`、公式ルールおよび `AGENTS.md` を最優先する。

## Hypothesis

T1のM60 residual momentum Long（Q4/Q5）を完全に固定したまま、残り60%のShort
順位をCash Flowのみから、Profitability deteriorationとBalance Sheet weaknessを加えた
連続的なPIT fundamental weaknessへ広げる。これによりShort-side Net P/LがT1より
一貫して改善し、Total Net Sharpeを毀損しないかを検証する。

## Economic rationale and timing

開示済みの収益性悪化や低い資本・現金バッファは、投資家の期待修正・資金調達制約・
リスク再評価が即日で完了しない場合に翌寄付後にも残り得る。各特徴は開示翌営業日から
のみ有効にし、最新同一期間・同一会計基準の過去比較だけを使う。単発決算イベント、
forecast revision、価格・流動性・出来高・ML・重み最適化は対象外である。

## Fixed candidates (four scoring trials only)

1. **C0 — Champion T1**: `fd_cash = mean(rank(-CFO YoY delta), rank(-CFO/assets), rank(-net-cash proxy))`。
2. **C1 — Profitability deterioration**: equal weight of `rank(-OperatingProfit/assets YoY delta)`, `rank(-OrdinaryProfit/assets YoY delta)`, `rank(-Profit/assets YoY delta)`。
3. **C2 — Balance-sheet weakness**: equal weight of `rank(-Equity/assets)`, `rank(-CashAndEquivalents/assets)`。Total liabilities列は存在しないため使用しない。
4. **C3 — Multi-dimensional weakness**: equal weight of C0/C1/C2 blocks.

各日、既存T1のLong上位40%（Q4/Q5）のmembership、順位、weight、日次Long損益を
bitwise固定する。残り60%のうちShortRisk上位40%をQ1/Q2、残りをQ3にstitchする。
同値は既存Momentum順位、Codeで決定する。C0以外の財務欠損はrank=0.5のneutralとし、
欠損indicatorをalphaにしない。C0は既存T1をbitwise再現する。

## PIT / leakage and operational risks

`FinancialStatements_` の有効な1Q/2Q/3Q/FYのみ、開示日より後の営業日にbackward as-ofで
反映する。450暦日より古い状態は失効し、YoYは同一period/basisかつ開始・終了日±7日、
duration±7日の比較だけを許す。negative shift、bfill、forward as-of、raw target、Validは
用いない。全入力のfuture-mutation/truncation prefix-invarianceを3 cutoffsで検査する。

Longは完全固定なのでLong turnoverは不変。Short順位の置換によりturnoverはC0と異なり得るが、
パラメータ探索では抑制しない。固定式の計算量は銘柄×営業日×開示数で、提出30分以内を
期限付きの独立推論smokeで確認する。

## Evaluation and selection

Train-only。開発foldは2011/2012/2013/2014で各年末のt+2 label越境2営業日をpurgeする。
2015–2016-03と2008–2010は、候補定義・選択を一切変更しない記述的確認に限る。
主判定はC0比で、(A) Short annual Net改善が3/4 fold以上、(B) median ΔShort annual Net>0、
(C) pooled Short Net>C0、(D) Net Sharpe>=C0、(E) Long完全固定。pooled Short Net>0かつ
Short Net正のfoldが3/4以上なら明示するが、将来alphaの証明とは表現しない。

旧研究の累積known scoring候補は48。今回はC0–C3の4本のみを加え、累積52と記録する。
未使用枠の転用や結果後の候補追加はしない。乱数seedは20260909、bootstrapは20営業日block・1000回。

## Commands and required evidence

`research/experiments/fundamental_weakness.py` を `tools/run_bounded.py --seconds 1800` で起動する。
source firewall、source scan、C0/T1 prediction・portfolio/P&L再現、prefix-invariance、
index/NaN/決定性/独立推論smoke、Long preservation、cost/turnover/coverageを記録する。
Valid評価・Freeze・提出は今回の範囲外。
