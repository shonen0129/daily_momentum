# DM-20260909-02: Fixed Momentum Long / Independent Short Ranking

事前登録: 2026-09-09。設定の正本は config.json。
戦略仕様正本: docs/strategies/投資戦略仮説0909-02.md。公式ルールおよび AGENTS.md を最優先とする。

## 1. 今回の目的と仮説

直前研究 DM-20260909-01 では、従来の `FinalScore = LongMomentum - λ × FundamentalShortRisk` という合成を試みたが、Shortスコアの変更によってLong側の銘柄構成や順位まで変化してしまい、一次選別基準を満たさなかった。
一方、Weak Momentum群の中にFundamental悪化によるShort順位分離の兆候が確認された。

そこで本実験では、
> **Long側（上位40%、Q4/Q5）を既存Residual Momentum baselineから完全に固定し、Short側（残り60%中の上位40%分、Q1/Q2）だけを独立したFundamental / Price Weaknessランキングで入れ替えた場合に、Short損益およびTotal Net Sharpeが改善するか**
を検証する。

## 2. 重要な研究上の制約

本実験は過去研究結果を参照して立案された新仮説であり、Train期間（2008-2016）は未使用OOSではない。
したがって「独立検証」「未使用holdout」とは主張せず、**再利用Train上で事前固定した有限個の新仮説を比較した研究結果**として扱う。
Validデータは一切使用せず、raw targetも参照しない。

## 3. 候補一覧（有限固定全5試行）

試行枠は以下に限定し、事後的なパラメータ探索・特徴量追加・試行枠転用は行わない。

1. **B0 (Existing Momentum Baseline)**:
   - 60日市場残差Momentum (res60s1) + EWMA $\alpha=0.25$
   - 比較の基準線。
2. **T0 (Stitched Momentum Control)**:
   - Long PoolはMomentum上位40%、Short/Neutralも従来のMomentum順位だけで決定。
   - 新しいscore stitching方式を通した対照群。B0とポートフォリオweight、日次損益、コストがビット単位で完全一致することを要求。
3. **T1 (Fixed Long + Equal FD Short)**:
   - Long Pool固定。残り60%の中で $FD = \frac{1}{3}(\text{Rank}(-CFOYoYDelta) + \text{Rank}(-CFOAssets) + \text{Rank}(-NetCashProxy))$ の高い順に40%分をShort Pool（Q1/Q2）へ配分。
4. **T2 (Fixed Long + Equal FD × WeakPrice Short)**:
   - Long Pool固定。ShortRisk = $FD \times \text{WeakPrice}$ （WeakPrice = $\text{Rank}(-M60)$）。
5. **T3 (Fixed Long + Equal FD × WeakPrice + RecentCrash Avoidance)**:
   - Long Pool固定。ShortBase = $FD \times \text{WeakPrice}$。
   - M5（5日残差Momentum）が下位20%の銘柄をRecentCrashとし、Short Poolから原則除外（不足時のみfallback補充）。

## 4. 特徴量定義

- **M60 (Residual Momentum)**:
  - rawReturn - beta * topixReturn の前60観測営業日和、skip 1、min_periods=60、centered rank。
  - EWMA $\alpha=0.25$, adjust=False。
- **FD (Equal Weight Fundamental Deterioration)**:
  - 開示翌営業日反映、450暦日失効、同一期間種別・連結基準でのYoY。
  - $D = \text{Rank}(-CFOYoYDelta, \text{period})$
  - $W = \text{Rank}(-CFOAssets, \text{period})$
  - $F = \text{Rank}(-NetCashProxy)$
  - $FD = \frac{1}{3} D + \frac{1}{3} W + \frac{1}{3} F$
- **WeakPrice**:
  - $\text{Rank}(-M60)$ (全銘柄 percentile rank)。
- **M5 & RecentCrash**:
  - M5: 直近5観測営業日の残差Momentum和（skip 1, min_periods=5）。
  - RecentCrash: M5の全銘柄日次パーセンタイルランク $\le 0.20$。

## 5. Score Stitching と Long 固定

各営業日において全銘柄数 $N$ に対し、
- Long Pool (Q4/Q5): $r_L > \lfloor 0.6(N-1)+1 \rfloor$ の上位40%銘柄。
  - Baseline $r_L$ の順序と位置をそのまま保持。
- Remaining 60%: 残りの $M = \lfloor 0.6(N-1)+1 \rfloor$ 銘柄。
  - Short Pool (Q1/Q2): ShortRisk上位 $K_{short\_max} = \lfloor 0.4(N-1)+1 \rfloor$ 銘柄をランク $1 \dots K_{short\_max}$ に割り当て。
  - Neutral Pool (Q3): 残り銘柄をランク $K_{short\_max}+1 \dots M$ に割り当て。
- 最終スコア: $(r_{final} - 1.0) / (N - 1.0)$
- **Long完全固定検査**:
  全候補について、Q4/Q5 membership difference count = 0、Long-side daily contribution difference = 0 をビット単位で検証する。

## 6. ウォークフォワード期間とパージ

- Train評価期間: 2008-11-04 〜 2016-03-31
- 開発Fold: 2011, 2012, 2013, 2014 の4年間
- Purge: $t+1 \to t+2$ のラベルが各年境界を跨ぐ末尾2営業日を損益集計から除外。
- 既読確認期間: 2015-01-01 〜 2016-03-31（descriptive checkのみ、再選択には使用しない）。
- 2008-2010: descriptive stability check。

## 7. 評価指標と判定基準

### Primary Selection Criteria
1. **Short側**:
   - Short年率Net貢献がbaselineより改善するfold $\ge 3/4$
   - median $\Delta\text{ShortNet} > 0$
2. **Total Portfolio**:
   - Net Sharpeがbaselineより改善するfold $\ge 3/4$
   - median $\Delta\text{NetSharpe} > 0$
3. **開発期間合算**:
   - Total Net Sharpe > Baseline
   - Short年率Net > Baseline
4. **Long固定**:
   - Q4/Q5 membership・ウェイト・Long損益が設計通り完全固定。

### Statistical Diagnostics
- Circular block bootstrap: 20営業日ブロック、1000回反復、固定シード 20260909。
- 95% CI を算出。

## 8. 試行管理と停止条件

- 直前研究 DM-20260909-01 時点での累積既知試行数: 44
- 本実験の新規scoring候補: 4 (T0, T1, T2, T3)
- 累積試行数: 48
- 順次評価: T1 $\to$ T2 $\to$ T3。T1が悪化してもT2/T3は事前登録済みのため実行。T3以降の試行追加は禁止。全滅時は仮説却下とし終了。
