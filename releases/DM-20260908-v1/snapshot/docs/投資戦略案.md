# 新規投資戦略案

## Momentum × Liquidity / Microstructure Strategy

---

# 1. 目的

本戦略では、日本株の翌営業日寄付から翌々営業日寄付までの1日残差リターンを予測する。

基本思想は、

> **Momentumによって基本的な価格方向を予測し、Liquidity / Volume / Price Impact / Intraday情報によって、そのMomentumが継続しやすい状態か、失敗・反転しやすい状態かを判定する。**

ことである。

Value / Qualityなどの低速ファンダメンタル因子を追加するのではなく、価格形成そのものに近い情報を利用する。

中心となる仮説は、

```math
FinalAlpha
=
MomentumPrior
+
Liquidity / Microstructure Correction
```

である。

Momentumをalpha generatorとし、

* Liquidity Shock
* Volume Shock
* Price Impact Anomaly
* Price Without Volume
* Volume Without Price
* Morning / Afternoon Price Structure
* Morning / Afternoon Volume Structure

をMomentumの

* Continuation
* Weakening
* Exhaustion
* Reversal

の判定に利用する。

---

# 2. コンペ上の重要な前提

シグナル日を `t` とする。

利用可能なのは `t` までに公開・観測された情報のみ。

予測対象は、

```math
t+1 Open -> t+2 Open
```

の市場調整後1日リターンである。

したがって、

```text
t日までのデータ
    ↓
Signal_t
    ↓
t+1 寄付で建玉
    ↓
t+2 寄付で評価
```

となる。

特にIntraday / Microstructure特徴量については、

> **t日に観測された現象が、t+1寄付までに完全に価格へ織り込まれず、t+1寄付以降も予測力を持つか**

を必ず検証する。

短期的な価格形成現象を発見しても、

```math
Close_t \rightarrow Open_{t+1}
```

で効果が消滅する場合、このコンペではalphaにならない。

---

# 3. 戦略仮説

同じ価格上昇でも、その背景によって将来リターンの意味は異なる。

例えば同じ+5%上昇でも、

### ケース1

* 大きな売買代金
* 出来高増加
* 流動性改善
* 正常なPrice Impact

を伴っている場合、

> 多数の市場参加者が新しい情報を価格へ反映している

可能性があり、Momentum continuationを想定する。

### ケース2

* 売買量が少ない
* 流動性が急低下
* 通常より異常に大きなPrice Impact

で+5%上昇している場合、

> Liquidity Vacuumによって価格だけが一時的に飛んだ

可能性があり、Momentum weakening / reversalを想定する。

したがって、

```math
PriceMove
\times
Volume
\times
LiquidityState
```

のinteractionを利用する。

---

# 4. Momentum Prior

## 4.1 基本定義

市場全体の影響を除いたResidual Momentumを基本とする。

提供されている、

* `raw_return`
* `beta`
* `topix_return`

を利用して、

```math
ResidualReturn_{i,t}
=
rawReturn_{i,t}
-
\beta_{i,t} TOPIXReturn_t
```

を作る。

そのResidual Returnから複数期間Momentumを作る。

候補：

```math
M_5
M_10
M_20
M_60
```

または、

```math
M_{5-20}
M_{20-60}
```

のような区間Momentum。

---

## 4.2 直近リターンの除外

短期Momentumと短期Reversalを区別するため、

### Current Included

```text
t ～ t-19
```

### Skip Current

```text
t-1 ～ t-20
```

### 2-Day Skip

```text
t-2 ～ t-21
```

などを比較する。

「20日Momentum」などの定義では、使用する営業日区間を必ず明示すること。

---

## 4.3 Momentum合成

複数期間を日次クロスセクショナルRank化し、

```math
M
=
w_1 Rank(M_5)
+
w_2 Rank(M_{20})
+
w_3 Rank(M_{60})
```

などとしてMomentum Priorを構築する。

最初から複雑な重み最適化は行わず、

* equal weight
* 少数の固定weight候補

をTrain-only walk-forwardで比較する。

---

## 4.4 Momentum候補

最低限、以下を比較する。

### Raw Momentum

```math
M(rawReturn)
```

### Market Residual Momentum

```math
M(rawReturn-\beta TOPIXReturn)
```

### Sector Residual Momentum

市場Residual MomentumからさらにSector effectを除く。

Sector Residualを利用する場合、各時点のPoint-in-Time Sector情報のみを利用する。

---

# 5. Liquidity Features

Liquidityについては、

> Liquidity LevelとLiquidity Shockを明確に分離する。

---

## 5.1 Baseline Liquidity

銘柄自身の通常時の流動性水準。

候補：

```math
MedianTradingValue_{60}
```

```math
MedianVolume_{60}
```

```math
AmihudLiquidity_{60}
```

など。

例：

```math
LiquidityLevel
=
\log(MedianTradingValue_{60}+\epsilon)
```

---

## 5.2 Liquidity Shock

最近の流動性が通常状態からどれだけ変化したかを見る。

第一候補：

```math
LiquidityShock_5
=
\log
\frac{
MedianTradingValue_{5}+\epsilon
}{
MedianTradingValue_{60}+\epsilon
}
```

候補：

```math
TradingValue_1d / TradingValue_60d
TradingValue_5d / TradingValue_60d
Volume_1d / Volume_60d
Volume_5d / Volume_60d
Amihud_5d / Amihud_60d
```

重要なのは、

```text
Liquidity Level
Liquidity Shock
```

を別特徴量として保持することである。

---

# 6. Volume Shock

出来高または売買代金の異常度を測定する。

候補：

```math
VolumeShock_1
=
\log
\frac{
Volume_{1d}+\epsilon
}{
MedianVolume_{60}+\epsilon
}
```

```math
VolumeShock_5
=
\log
\frac{
MedianVolume_{5}+\epsilon
}{
MedianVolume_{60}+\epsilon
}
```

売買代金でも同様の特徴量を作る。

Volume Shockそのものを方向性alphaとして利用するのではなく、

> MomentumやPrice Moveがどのような取引参加を伴って発生したか

を判断するために使う。

---

# 7. Expected Price Impact

本戦略の中心特徴量の1つ。

単純な、

```math
|Return| / TradingValue
```

ではなく、

> **通常ならこのLiquidity / Volume / Volatility環境で、どれだけ価格が動くはずか**

を推定する。

---

## 7.1 Expected Move

例えば、

```math
ExpectedMove
=
f(
VolumeShock,
BaselineLiquidity,
Volatility,
Size
)
```

とする。

目的変数は、

```math
|ResidualReturn|
```

またはそのlog変換。

例：

```math
\log(|ResidualReturn|+\epsilon)
=
f(
\log TradingValue,
LiquidityLevel,
VolumeShock,
Volatility,
Size
)
```

---

## 7.2 Expected Price Impact Model候補

複雑なモデルから始めない。

以下の順で比較する。

### Model 1: Robust / Linear Regression

```math
log(|Return|+\epsilon)
=
a
+b_1 log(TradingValue)
+b_2 LiquidityLevel
+b_3 Volatility
+b_4 Size
```

### Model 2: Binning

例えば、

* Baseline Liquidity decile
* Volume Shock decile
* Volatility quintile

などによる2D / 3D binning。

### Model 3: Rolling Historical Relationship

銘柄自身の過去のVolume / Price Move関係からExpectedMoveを推定。

### Model 4: Shallow LGBM

上記よりTrain walk-forwardで安定して改善する場合のみ利用する。

---

## 7.3 Cross-Fitting

Expected Price Impact Modelを学習する場合、

> 学習に使った同じ行に対するin-sample residualを、そのまま後段モデルの特徴量に使用しない。

Train期間内でcross-fitting / walk-forward predictionを作り、

```math
ImpactResidual
=
ObservedMove
-
ExpectedMove_{OOS}
```

とする。

---

# 8. Price Without Volume / Volume Without Price

Expected Price Impactからの残差を、

```math
ImpactResidual
=
|ResidualReturn|
-
ExpectedMove
```

とする。

---

## 8.1 Price Without Volume

```math
PWV
=
max(ImpactResidual,0)
```

意味：

> 売買量・通常流動性・Volatilityなどから予想される以上に価格が動いた状態。

特に、

```math
PWV >> 0
```

かつ

```math
LiquidityShock < 0
```

なら、

> 流動性が枯れた状態で注文が入り、価格だけが大きく動いた

可能性を考える。

Momentumを弱める、またはReversal候補。

---

## 8.2 Volume Without Price

```math
VWP
=
max(-ImpactResidual,0)
```

意味：

> 通常ならこの売買量でより大きな値動きが発生するはずなのに、価格があまり動かなかった状態。

可能性：

* 売りを大量の買い手が吸収
* 買いを大量の売り手が吸収
* Trend exhaustion
* Position transfer

VWP単独では方向性を決めない。

Morning / Afternoon price structureなどと組み合わせる。

---

# 9. Intraday Features

価格データに含まれる前場・後場情報を利用する。

すべて `t` 日までの観測済み情報のみ利用する。

---

## 9.1 Return Structure

候補：

```math
r_{AM}
```

```math
r_{PM}
```

```math
r_{PM}-r_{AM}
```

```math
r_{AM}+r_{PM}
```

---

## 9.2 Volume Structure

候補：

```math
Volume_{PM}/(Volume_{AM}+\epsilon)
```

```math
TradingValue_{PM}/(TradingValue_{AM}+\epsilon)
```

---

## 9.3 Intraday Range

候補：

```math
Range
=
\frac{High-Low}{Open}
```

またはraw OHLCから構築可能な因果的なRange指標。

---

## 9.4 Intraday Reversal

例：

```math
r_{AM}<0,\quad r_{PM}>0
```

なら、

> 前場の売りを後場で吸収した

可能性を考える。

逆に、

```math
r_{AM}>0,\quad r_{PM}<0
```

なら、

> 前場の買いを後場で吸収した

可能性を考える。

ただし、単純な符号だけでなく、

* Volume Shock
* Intraday Range
* Net Return
* PWV / VWP

とのinteractionで利用する。

---

# 10. 代表的な市場状態

## State A: Liquidity Vacuum Reversal

条件：

```text
Momentum ↑
PWV ↑
Liquidity Shock ↓
```

仮説：

```math
Momentum\uparrow
+
PWV\uparrow
+
Liquidity\downarrow
\Rightarrow
Momentum Weakening / Reversal
```

Momentum Longを弱める、または条件が強い場合のみShortへ反転。

下方向の場合は逆。

---

## State B: Volume-Confirmed Momentum

条件：

```text
Momentum ↑
Volume ↑
Liquidity ↑
Price Impact ≈ Normal
```

仮説：

```math
Momentum\uparrow
+
Volume\uparrow
+
Liquidity\uparrow
\Rightarrow
Continuation
```

Momentumを維持、または強化。

---

## State C: Trend Exhaustion / Absorption

条件：

```text
Momentum ↑
Volume Shock ↑
VWP ↑
```

意味：

> 大量の売買が行われているにもかかわらず、それ以上価格が上昇しなくなっている。

Momentum終了または反転の可能性。

Morning / Afternoon情報で方向を補完する。

---

## State D: Intraday Absorption

例：

```math
r_{AM}<0,\quad r_{PM}>0
```

かつ、

```text
Volume Shock 大
Net Return 小
Intraday Range 大
```

なら、

> 前場の大量売りを後場で買い手が吸収した

可能性。

翌営業日以降のLong候補。

逆に、

```math
r_{AM}>0,\quad r_{PM}<0
```

ならShort候補。

---

# 11. Interaction Features

LGBM自身にもinteractionを学習させるが、経済的意味が明確なものは明示的に作る。

重点候補：

```math
Momentum \times PWV
```

```math
Momentum \times VWP
```

```math
Momentum \times LiquidityShock
```

```math
PWV \times LiquidityShock
```

```math
VWP \times IntradayReversal
```

```math
Momentum \times VolumeShock
```

特徴量を無制限に増やさない。

最初は10～15特徴程度を目安とする。

---

# 12. Model A — Direct LGBM

## 12.1 定義

全特徴量から直接翌日リターン順位を予測する。

```math
FinalScore
=
LGBM(
Momentum,
Liquidity,
PriceImpact,
Volume,
Intraday,
Interactions
)
```

---

## 12.2 Target

第一候補：

```math
Y
=
CSRank(Target)
```

比較対象として、

```math
Raw Target
```

も検証可能。

---

## 12.3 特徴量候補

### Momentum

* Residual Momentum 5d
* Residual Momentum 20d
* Residual Momentum 60d
* Momentum Acceleration
* Momentum Rank

### Liquidity

* Baseline Liquidity
* Liquidity Shock
* TradingValue 5d / 60d
* Volume Shock 1d
* Volume Shock 5d

### Price Impact

* Impact Residual
* PWV
* VWP

### Intraday

* Morning Return
* Afternoon Return
* PM − AM Return
* Intraday Range
* PM / AM Volume Ratio

### Interaction

* Momentum × PWV
* Momentum × VWP
* Momentum × Liquidity Shock
* PWV × Liquidity Shock
* VWP × Intraday Reversal

---

## 12.4 メリット

* 実装が簡単
* Benchmarkとして重要
* 非線形interactionを直接学習可能

---

## 12.5 デメリット

LGBMがMomentumの方向そのものまで自由に再学習する。

Train期間固有の、

```text
Momentum
×
Liquidity
×
Market Regime
```

へ過学習するリスクが高い。

主力モデルではなく、自由度の高いbenchmarkとして扱う。

---

# 13. Model B — Momentum + Residual Correction

## 13.1 基本構造

Momentumを明示的なPriorとして保持する。

```math
FinalScore
=
MomentumPrior
+
\lambda Correction
```

LGBMには、

> Momentumそのものを再発見させるのではなく、Momentum予測の誤差を修正させる。

---

## 13.2 Step 1 — Momentum Prior

```math
M_{i,t}
```

を作る。

日次クロスセクショナルRankなどによりスケールを固定する。

---

## 13.3 Step 2 — Target Rank

```math
Y_{i,t}
=
CSRank(Target_{i,t})
```

とする。

---

## 13.4 Step 3 — Momentum Calibration

単純に、

```math
Y - Rank(M)
```

をResidual Targetにはしない。

Momentum Rankの数値をそのまま未来Return Rankの予測値とみなすことになるためである。

代わりにTrain-onlyのwalk-forward / cross-fittingで、

```math
\hat{Y}_M
=
g(M)
```

を推定する。

`g` は複雑にしない。

候補：

### Linear Calibration

```math
\hat{Y}_M
=
a+bM
```

### Binned Calibration

Momentum Rankを5～10bin程度に分け、

```math
E[Y|MomentumBin]
```

を使う。

必要であればmonotonic mappingも検討する。

---

## 13.5 Step 4 — Residual Target

```math
ResidualTarget
=
Y-\hat{Y}_M
```

とする。

意味：

> Momentum Priorだけでは説明できなかった未来リターン順位。

---

## 13.6 Step 5 — Correction Model

```math
Correction
=
LGBM(
LiquidityShock,
LiquidityLevel,
PWV,
VWP,
VolumeShock,
IntradayFeatures,
Interactions
)
```

Momentum単独特徴量は原則として入れすぎない。

必要な場合は、

```math
Momentum × PWV
Momentum × VWP
Momentum × LiquidityShock
```

のようなinteractionを中心に使う。

これによりCorrection Modelが単純なMomentumモデルへ戻ることを防ぐ。

---

## 13.7 Final Score

```math
FinalScore
=
M
+
\lambda Correction
```

`\lambda` はTrain-only walk-forwardで選択する。

候補例：

```text
0.0
0.25
0.5
0.75
1.0
```

`lambda = 0` はMomentum-only benchmarkになる。

---

## 13.8 メリット

* Momentum Priorを保持できる
* MLの自由度を制限できる
* Liquidity / Microstructureの役割が明確
* 解釈しやすい
* Correctionのincremental valueを測定しやすい

---

## 13.9 現時点での位置付け

主力候補。

ただしModel Cとの比較を必須とする。

---

# 14. Model C — Momentum Gate

## 14.1 基本構造

Momentumの方向を基本的に維持し、

> Momentumをどれだけ信用するか

のみをMLに判断させる。

```math
FinalScore
=
M\times Gate
```

---

# 15. Model C1 — Attenuation Only

最も制約の強いGateモデル。

```math
Gate\in[0,1]
```

役割：

* Momentumを維持
* Momentumを弱める
* Momentumを無効化

のみ。

符号反転は禁止。

例：

| 状態               | Momentum | Gate | Final |
| ---------------- | -------: | ---: | ----: |
| 通常               |    +0.80 | 1.00 | +0.80 |
| やや怪しい            |    +0.80 | 0.60 | +0.48 |
| Liquidity Vacuum |    +0.80 | 0.20 | +0.16 |
| 無効               |    +0.80 | 0.00 |  0.00 |

最も過学習しにくいため、重要な比較対象とする。

---

# 16. Model C2 — Reversal Allowed

Momentumが失敗する強い状態では符号反転を許す。

```math
Gate\in[-1,1]
```

例：

| 状態       | Momentum |  Gate | Final |
| -------- | -------: | ----: | ----: |
| Normal   |    +0.80 | +1.00 | +0.80 |
| Weak     |    +0.80 | +0.30 | +0.24 |
| Reversal |    +0.80 | -0.50 | -0.40 |

C1より自由度が高いため、

> reversalを許すことによる改善がTrain walk-forwardで一貫している場合のみ採用する。

---

# 17. Model C3 — Amplification Allowed

Continuation状態でMomentumを強化する。

例：

```math
Gate\in[-1.5,1.5]
```

Volume-confirmed momentumなどで、

```math
Gate>1
```

を許す。

ただしC1 / C2より過学習リスクが高い。

優先順位は低い。

---

# 18. Model比較

| Model | 構造                             | 自由度 | 過学習リスク |  解釈性 | 位置付け       |
| ----- | ------------------------------ | --: | -----: | ---: | ---------- |
| A     | 全特徴量 → LGBM                    |   高 |      高 |    中 | Benchmark  |
| B     | Momentum + Residual Correction |   中 |    低～中 |    高 | 主力候補       |
| C1    | Momentum × Gate [0,1]          |   低 |      低 | 非常に高 | 主力比較       |
| C2    | Momentum × Gate [-1,1]         | 低～中 |    低～中 | 非常に高 | Reversal検証 |
| C3    | Momentum × Gate amplification  |   中 |      中 |    高 | 後回し        |

基本的な比較順序：

```text
Momentum Only
↓
C1
↓
B
↓
C2
↓
A
↓
C3
```

---

# 19. LightGBM設計方針

今回の目的は、

> 多数の特徴量から未知のalphaを自動発見すること

ではない。

事前に、

* Momentum continuation
* Liquidity vacuum reversal
* Volume confirmation
* Price impact anomaly
* Absorption
* Trend exhaustion

という仮説を定義し、

> どの市場状態でMomentumを信用すべきか

のみを学習させる。

そのためモデルは浅くする。

初期候補：

```text
max_depth: 2–3
num_leaves: 4–8
min_data_in_leaf: 大きめ
feature数: 約10–15から開始
tree数: 必要以上に増やさない
```

Hyperparameter searchを広く行わない。

少数候補をTrain-only walk-forwardで比較する。

---

# 20. Turnover / Transaction Cost対策

本戦略は短期価格・出来高情報を使うため、turnoverが高くなりやすい。

コンペでは片道10bpsのコストがあるため、

> RankICが高くてもTurnoverが高ければNet Sharpeは悪化する。

したがって、Turnover対策はモデル完成後ではなく、モデル選択段階から組み込む。

---

## 20.1 EWMA / Score Persistence

候補：

```math
Score_t
=
\alpha NewScore_t
+
(1-\alpha)Score_{t-1}
```

比較候補：

```text
alpha = 1.0
0.5
0.25
0.15
```

---

## 20.2 Signal Decay

イベント特徴量について、

```math
Signal_t
=
NewSignal_t
+
\rho Signal_{t-1}
```

などを比較する。

---

## 20.3 Hysteresis

5分位境界を跨ぐたびに売買しない。

例：

> Q5へ新規参入するための閾値と、既存Q5銘柄がQ5から離脱する閾値を別にする。

これにより境界付近の無駄な売買を削減する。

---

## 20.4 Quintile Boundary Buffer

順位が分位境界の近辺にある場合、既存ポジションを維持する。

Turnover削減効果とalpha損失を比較する。

---

## 20.5 Cost-Aware Update

Raw Scoreの改善が小さい場合にはポジション変更を行わない。

例えば、

```math
|NewScore-OldScore| < threshold
```

の場合、旧scoreを維持する。

---

# 21. 学習Target

少なくとも以下を比較する。

## Target A: Raw Return

```math
Target
```

---

## Target B: Cross-Sectional Rank

```math
CSRank(Target)
```

本コンペでは最終的に日次5分位Portfolioになるため、有力候補。

---

## Target C: Momentum Residual Target

Model B用。

```math
CSRank(Target)
-
\hat{Y}_M
```

ここで、

```math
\hat{Y}_M=g(M)
```

はTrain-only cross-fitted Momentum予測。

単純な、

```math
Rank(Target)-Rank(Momentum)
```

は使用しない。

---

# 22. Train内Walk-Forward検証

Validをモデル選択に利用しない。

全ての特徴量選択、モデル選択、パラメータ選択はTrain期間のみで完結する。

Train期間内を時系列で複数foldに分け、

```text
Past → Future
```

のwalk-forward評価を行う。

---

## 22.1 Purging

Targetは未来の `t+2` 情報を含むため、Train / evaluation fold境界でlabel horizonが跨がないようにする。

最低限、境界に必要な営業日数のpurgeを入れる。

---

# 23. 評価指標

各foldおよび年別に最低限以下を確認する。

### Prediction

* Daily RankIC
* Mean RankIC
* RankIC t-stat
* RankIC hit ratio

### Portfolio

* Gross Sharpe
* Net Sharpe
* Annual Gross P/L
* Annual Net P/L
* Annual Cost
* Turnover
* Maximum Drawdown

### Cross Section

* Q1～Q5 Return
* Q1～Q5 monotonicity
* Long side P/L
* Short side P/L

---

# 24. Momentum Baselineに対するIncremental評価

今回最も重要な評価。

単なるFinal Modelの性能だけではなく、

```math
IC(Final)-IC(Momentum)
```

```math
NetSharpe(Final)-NetSharpe(Momentum)
```

```math
GrossSharpe(Final)-GrossSharpe(Momentum)
```

```math
Turnover(Final)-Turnover(Momentum)
```

を各foldで測定する。

目的は、

> Liquidity / Microstructure CorrectionがMomentum baselineを時代を跨いで一貫して改善するか

を確認すること。

平均性能が高くても、

```text
特定期間だけ大幅改善
その他期間では悪化
```

するCorrectionは優先しない。

---

# 25. 安定性を重視したモデル選択

Full Train Sharpe最大化では選ばない。

優先するのは、

> 各時代で同じ方向の効果が確認できる戦略。

例えば、

```text
Fold 1 : +0.15 Sharpe改善
Fold 2 : +0.12
Fold 3 : +0.18
Fold 4 : +0.09
```

を、

```text
Fold 1 : -0.30
Fold 2 : -0.20
Fold 3 : +1.50
Fold 4 : +1.00
```

より優先する。

確認項目：

* 年別RankIC
* 年別Net Sharpe
* 年別Correction Effect
* Long / Short consistency
* Turnover stability
* Cost stability
* Feature importance stability
* State別performance

---

# 26. State別診断

モデル全体の結果だけでなく、市場状態別にMomentumの性能を測る。

例えば、

## PWV Low / High

```text
Low PWV
High PWV
```

ごとのMomentum RankIC。

## Liquidity Shock

```text
Liquidity improving
Normal
Liquidity deteriorating
```

ごとのMomentum performance。

## Volume Shock

```text
Low
Normal
High
```

## Intraday Reversal

```text
AM↓ PM↑
AM↑ PM↓
Same Direction
```

これにより、

> MLを使う前に、経済仮説そのものがTrain内で確認できるか

を調べる。

---

# 27. Intraday AlphaのDecay診断

Intraday / Microstructure特徴量では特に重要。

可能な範囲で、イベント発生後のリターンを、

```text
t Close → t+1 Open
```

と、

```text
t+1 Open → t+2 Open
```

に分解して確認する。

本コンペで必要なのは後者。

もしalphaの大半が、

```text
t Close → t+1 Open
```

に存在する場合、

> 経済仮説として正しくてもコンペでは利用価値が低い

と判断する。

---

# 28. 実装上のデータ制約

特徴量は必ず因果的に作成する。

禁止事項：

* future targetを特徴量として読む
* Valid targetを予測時に読む
* 負のshift
* centered rolling
* future方向のbfill
* forward as-of
* 将来情報を含む標準化
* 将来情報を含むランキング
* 最新時点のSector情報を過去へ遡及適用

---

# 29. Price / Volumeデータの利用方針

価格・出来高の「水準」特徴量にはraw OHLCVを利用する。

遡及調整された、

```text
AdjustmentOpen
AdjustmentHigh
AdjustmentLow
AdjustmentClose
AdjustmentVolume
```

の水準は特徴量に使用しない。

リターン特徴量については、提供されている、

```text
raw_return
```

を基本として使用する。

---

# 30. Future-Mutation / Prefix-Invariance

新規Feature Builderについては、

> 将来部分の入力データを変更しても、cutoff以前の特徴量が一切変化しない

ことを確認する。

特に、

* Rolling features
* Momentum
* Liquidity Shock
* Expected Price Impact
* Cross-sectional transforms
* Intraday features

はprefix-invarianceを確認する。

---

# 31. 推奨研究順序

最初からFull LGBMを作らない。

以下の順で研究する。

## Phase 1 — Momentum Baseline

比較：

```text
M5
M10
M20
M60
Current Included
Skip Current
2-Day Skip
Raw Momentum
Market Residual Momentum
Sector Residual Momentum
```

Momentum-only + Turnover smoothingで基準性能を確立する。

---

## Phase 2 — Simple Conditional Tests

MLなしで、

```text
Momentum × Liquidity Shock
Momentum × PWV
Momentum × VWP
Momentum × Volume Shock
```

の条件付きperformanceを測る。

仮説そのものの存在を確認する。

---

## Phase 3 — Model C1

```math
Final=M\times Gate,\quad Gate\in[0,1]
```

Momentumを弱めるだけで改善するか確認。

---

## Phase 4 — Model B

Cross-fitted Momentum Calibrationを作り、

```math
Final=M+\lambda Correction
```

を検証。

---

## Phase 5 — Model C2

強い条件のみMomentum Reversalを許可。

```math
Gate\in[-1,1]
```

---

## Phase 6 — Model A

全特徴量を直接LGBMへ入力。

制約モデルより本当に改善するかを確認する。

---

## Phase 7 — Advanced Variants

必要な場合のみ、

* Gate amplification
* Shallow LGBM Expected Price Impact
* Additional Intraday interactions
* Additional Momentum horizons

を試す。

---

# 32. 過学習防止方針

以下を原則とする。

1. 特徴量を無制限に増やさない
2. Hyperparameter searchを広く行わない
3. 経済的意味が明確な特徴量を優先
4. Full Train性能よりwalk-forward consistencyを優先
5. Model Aより制約付きModel B / Cを優先
6. Correctionのincremental valueを必ず測る
7. Validをモデル選択に利用しない
8. Turnover / Costを最初から評価に入れる

---

# 33. 最終候補アーキテクチャ

現時点の主力候補は2つ。

---

## Candidate 1 — Model B

```math
MomentumPrior=M
```

```math
\hat{Y}_M=g(M)
```

```math
ResidualTarget
=
CSRank(Target)-\hat{Y}_M
```

```math
Correction
=
LGBM(
LiquidityLevel,
LiquidityShock,
VolumeShock,
PWV,
VWP,
Intraday,
Interactions
)
```

```math
\boxed{
FinalScore
=
M
+
\lambda Correction
}
```

---

## Candidate 2 — Model C1

```math
Gate
=
ML(
LiquidityLevel,
LiquidityShock,
VolumeShock,
PWV,
VWP,
Intraday,
Interactions
)
```

```math
Gate\in[0,1]
```

```math
\boxed{
FinalScore
=
M\times Gate
}
```

---

# 34. 最終的な戦略思想

本戦略では、LightGBMに、

> 「未来の株価をゼロから予測してください」

とは依頼しない。

Momentumを構造的なPriorとして与え、

> **Momentumが継続しやすい状態なのか、信用できない状態なのかをLiquidity / Volume / Price Impact / Intraday情報から判断する**

ことを主目的とする。

中心仮説は、

```math
\boxed{
Direction
=
Momentum
}
```

```math
\boxed{
Confidence
=
Liquidity
+
Volume
+
PriceImpact
+
IntradayStructure
}
```

である。

最終的に重要なのは、単体モデルのFull Train Sharpeではなく、

> **Momentum baselineに対するCorrectionの改善が複数時代で一貫しており、かつ取引コスト控除後にも残ること**

である。

---

# 35. 最終Model選択ルール

最終候補はTrain-only walk-forwardの結果から選択する。

優先順位：

1. Net Sharpeの時系列安定性
2. Momentum baselineに対するincremental improvement
3. Turnover / Cost
4. RankIC stability
5. Q1～Q5 monotonicity
6. Long / Short双方の安定性
7. Maximum Drawdown
8. Model simplicity
9. Economic interpretability

単純なFull Train Net Sharpe最大モデルは選択しない。

最終仕様を決定後、

* Feature set
* Momentum definition
* Model structure
* Hyperparameters
* Smoothing / Turnover parameters

をすべて凍結する。

Validはモデル選択には使用せず、凍結後の最終評価のみとする。