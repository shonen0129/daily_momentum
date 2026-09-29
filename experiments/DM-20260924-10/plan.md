# DM-20260924-10: 可変長ボックス後の新高値ブレイク

Status: completed / rejected。可変長ボックス状態が新高値ブレイク候補の当日リターン予測へ追加情報を持つか、固定候補1本でTrain-only診断した。全Train期間は既知のため、結果は記述的で選択・採用には使わない。

## Hypothesis

過去5〜120観測でATR20の3倍未満に収まった最長ボックスの期間・幅・終値位置と、ボックス形成前の60日残差モメンタム・52週高値距離は、当日に250観測高値を終値で更新した銘柄の中で、ブレイク強度だけを使うより翌寄付後の順位予測に追加情報を持つ。

コンペ公式targetに合わせ、目的変数は `t+1 Open → t+2 Open` の1日市場残差リターンとする。仮説書にある20〜60日先Close-to-Closeリターンはこの戦略の選択対象にしない。

## Why it should work / Why it may persist

長く狭い持ち合いのあとに高値を更新した銘柄では、売り圧力を吸収した状態と方向の確認が揃い、通常の高値更新幅だけでは区別できない継続性が残る可能性がある。箱の時間幅を一つに固定せず、5営業日刻みで最長の条件適合期間を表す。

ブレイクと箱の両方が日次OHLCから計算可能であり、boxはsignal日t-1まで、breakoutはsignal日tの終値までに確定する。翌寄付までに効果が消える可能性を含め、公式target上のTrain walk-forwardで評価する。

## Expected turnover impact / Leakage risk / Complexity cost

候補は250観測新高値イベント内のLong順位を変えるため、turnoverとcostは増減どちらもあり得る。公式5分位weight、片道10bps、EWMA alpha=0.25を全候補で固定して測る。

OHLCはraw価格に当日まで観測済みのAdjustmentFactor累積を適用して同一単位へ揃える。box窓はsignal日t-1で終了し、ATR20もt-1までのtrue rangeだけを使う。ブレイク障壁はt-1以前250観測のHigh/Low。Adjusted OHLCV水準、Valid、raw targetは使わない。価格・リターン・beta・TOPIXとTrain targetの将来改変 / truncationに対するprefix-invarianceを複数cutoffで検査する。

モデルは高値breakout行に限るannual expanding Ridge（lambda=1.0）一つ。欠損補完・標準化は成熟Trainのfit範囲だけで計算する。breakout内の日次予測rankを既存B00のLong event scoreと50/50で合成し、Short側はB00のままにする。窓・閾値・重み・モデルの探索は行わない。

## Baselineと変更点

* **H0**: 凍結DM-20260908-v1の60観測残差Momentum、EWMA alpha=0.25。
* **B00**: 250観測の新高値Long / 新安値Short、既存仕様どおり。
* **BOX_RIDGE_001**: 高値breakout行内のbox_duration、box_width_atr、close_position、relative_strength_60、distance_to_prior_highを使うRidge。Long event scoreをB00と50/50合成し、Short側をB00から維持。

Box durationは5, 10, …, 120の各prior-only窓について `(rolling High - rolling Low) / prior ATR20 < 3` を満たす最長窓。Close positionはsignal日t-1終値をそのボックスの境界に写像する。52週距離もt-1終値・t-2以前の250観測Highから作る。

## Train-only期間・有限候補・採否基準

* Train: 2008-11-04〜2016-03-31。2010年をwarm-upとし、評価foldは2011〜2016（2016年は部分期間）。各年開始前にラベル成熟のため2取引日purgeし、fold終端も最後2 signal日を除く。
* 2011〜2016-03を含む全Train期間は過去実験で既読。各fold・pooled指標とpaired 20営業日block bootstrapは記述比較のみ。未使用holdoutまたは独立証拠とは扱わない。
* 候補1本。H0とB00に対するRankIC、Net/Gross Sharpe、年次損益/cost、turnover、drawdown、Q1-Q5、Long/Shortとfold差分を報告する。Net Sharpeの安定性とbaseline差分を見て診断し、candidate selection / re-selection / Freeze / Valid評価には使用しない。
* Valid・Valid target・raw targetは未参照。追加候補は結果後に作らない。

### 実行可能性記録

初回run `run-20260924T081216Z` は候補評価前に終了した。2010年開始時点の成熟新高値breakout学習行は99件で、事前実装の500行最低条件を満たさなかった。foldを2011年開始に移し、2010年をwarm-upとして扱う。2011年開始前には2日purge後も約1,000件あったことを全Trainのevent countで確認した。この修正は同じ候補1本・特徴量・パラメータを維持し、成績を見た変更ではない。

## 既知データ・過去実験

* 52週高値近接・channel、250観測breakout、breakout×Momentum/Volume、breakout内へのMomentum追加はDM-20260923-01〜DM-20260924-09で既読。該当範囲は `experiments/GRAVEYARD.md` と各reportを参照。
* 変数長box duration / ATR圧縮を特定したTrain比較は確認されていない。ただしすべてのTrain target期間はすでに参照されており、今回も探索的な既知データ診断である。

## 検証・実行コマンド

* `.venv/bin/python -m pytest -q tests/strategies/dm_variable_box_breakout`
* Source firewall / leak scan、3 cutoffのfuture-mutationとtruncationによる全特徴量・H0/B00/candidate prefix一致、Train target変更後の成熟fold refit/prediction一致、prediction coverage、有限値、決定性、Long+Short会計照合を実行。
* Run準備: `.venv/bin/python tools/workspace.py prepare-run DM-20260924-10`
* 期限付き実行: `.venv/bin/python tools/run_bounded.py --seconds 3600 .venv/bin/python -m research.experiments.variable_box_breakout --config artifacts/DM-20260924-10/<run_id>/config.json --output artifacts/DM-20260924-10/<run_id>`
