# DM-20260925-03: 可変長ボックスの高値・安値ブレイク独立スコア

Status: planned。Train-onlyの固定候補1本を診断する。B00との比較は行うが、候補scoreの生成にB00を混合しない。

## 仮説

約52週の高値を上抜く前、または安値を下抜く前に長く狭いボックスを形成した銘柄は、単なるブレイク幅だけでは捉えられない方向継続性を持つ可能性がある。従来候補は高値側のみを学習しB00と合成していた。今回は高値側・安値側を別々に学習し、ボックス特徴から作った単独scoreがLong/Short双方で翌日寄付後の残差リターンを順位付けできるかを診断する。

## 経済的理由・持続性・翌寄付後

長い圧縮後の上抜けは売り圧力の吸収、下抜けは買い支えの枯渇を表す可能性がある。こうした需給調整が一晩で全て織り込まれない場合、翌日寄付後にも差が残ると考える。逆に、日中のブレイク情報が翌寄付までに消える可能性も明示的に評価する。新しい窓・閾値・モデルの探索はしない。

## 固定仕様

- Boxはt-1までのraw価格から、5〜120観測を5刻みで確認し、価格幅 / prior ATR20 が3未満となる最長窓を選ぶ。
- t終値が直前250観測のHighを超える行を高値イベント、Lowを下回る行を安値イベントとする。価格は当日までに観測済みのAdjustmentFactorで共通単位へ変換する。
- 方向ごとに別々のannual expanding Ridge (lambda=1)。特徴はbox duration、box width / ATR、breakout前closeのボックス内位置、60観測残差モメンタム、breakout前の同方向250観測極値への距離。
- 安値側は位置を `1 - close_position`、モメンタムを `-relative_strength_60`、距離を `prior_low / prior_close - 1` とし、上値側と同じく大きい値が下方向継続の強さを表すよう向きをそろえる。
- 教師は全銘柄断面の当日target percentile rank。高値モデルはそのrank、安値モデルは符号反転rankを使う。各側のイベント行だけで学習・予測し、日ごとに同方向イベント内の予測順位を0.5〜1へ写像する。高値は正、安値は負、非イベントは0とする。
- 高値/安値の単独scoreを合成した後、銘柄ごとにEWMA alpha=0.25で平滑化する。B00は比較baselineとしてのみ使い、候補scoreの生成に使わない。
- 目的変数は公式のt+1 Open → t+2 Open市場残差リターン。片道10bps、公式5分位weight、年率換算252日。

## 比較・予算・採否

- Baselines: H0 (frozen 60日残差Momentum) と B00 (250観測新高値Long / 新安値Short)。
- 候補は `BOX_BIDIR_STANDALONE` 1本のみ。lambda、ATR閾値、box窓、blend、平滑化は変更しない。
- Train期間2008-11-04〜2016-03-31。評価foldは2011〜2016（2016年は部分年）、各fold前にtarget成熟の2取引日purge。全Train期間は既読なので記述診断であり、独立確認や採用根拠にしない。
- B00との差分をRankIC、Net/Gross Sharpe、P/L、cost、turnover、drawdown、Q1-Q5、Long/Shortで記録し、20日paired block bootstrapを1,000回行う。安定した改善が見られなければ候補を却下する。Valid、Freeze、採用選択には進まない。

## リスク・検証

主なリークリスクはAdjustmentFactor、prior-only rolling、当日イベント確定時刻、target maturity。OHLC・raw return・beta・TOPIX・AdjustmentFactor・Train targetを対象に、複数cutoffのfuture-mutation/truncation prefix-invarianceを実行する。Source scan、Train firewall、index alignment、欠損/Inf、coverage、決定性、Long+Short会計照合、annual refit再現を確認する。

実行は期限付きTrain-only stageで行う。Valid target/raw targetは開かない。
