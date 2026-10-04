`daily_momentum` で、SLOW_CONTROLへMomentumを組み込むための **overnight / compute-heavy Train-only research bundle** を実施せよ。

この実験の目的は、単純な3factor blendをもう一度試すことではない。

既存研究では、

- SLOW_CONTROL = Size + Illiquidity
- SLOW_MOM60_EQUAL = Size + Illiquidity + MOM60 equal blend
- SLOW_MOM60_OLS = annual expanding OLS combination

を既に評価し、equal blend / OLSともSLOW_CONTROLを上回らなかった。

したがって今回の中心仮説は、

> MomentumはSLOWと同格のstatic factorではなく、Small / Illiquid銘柄群の中で働くconditional timing / confirmation informationではないか

である。

Historical Valid / Validは禁止。

全Trainは既知development sampleであり、untouched OOSとは呼ばない。

---

# 0. Compute policy

これは短時間trialではなく、寝ている間に完走させる重いresearch bundleとする。

研究計算については、submission本番の30分制約とは分離し、

**wall-clock budgetを最大3時間程度まで許容する。**

ただし、

- checkpointを段階ごとに保存
- 既存runを上書きしない
- phaseごとのhashを保存
- 中間CSV/parquetを保存
- 最後にreportを必ず生成

する。

一つの重い処理が失敗しても、保存済みphaseから再開可能にする。

性能が途中で悪くても早期終了せず、

**事前固定した全diagnosticを最後まで実行する。**

一方、

- parameter search
- feature search
- rescue candidate search

に計算時間を使ってはいけない。

計算時間は **頑健性・統計的不確実性・conditional structureの解明** に使う。

---

# 1. Existing components: strict parity

以下を既存実装からbitwise再構築する。

## SLOW_CONTROL

Size:

`SIZE_RAW = -log(raw Close × PIT shares)`

Illiquidity:

`ILLIQ_RAW = Amihud60 / min40`

既存winsor / missing / z-score / final SLOW processingを変更しない。

## MOM60

既存 `DM-20260908-v1`:

`residual60 / skip1 -> centered rank -> EWMA(0.25)`

window、skip、EWMA、rankingを変更しない。

以下についてstrict parity:

- raw Size
- normalized Size
- raw Illiquidity
- normalized Illiquidity
- SLOW score
- MOM60 pre-EWMA
- MOM60 final score
- official SLOW weight
- official SLOW daily Net
- official MOM60 weight
- official MOM60 daily Net

parity失敗時はperformance interpretationを行わない。

---

# 2. Primary Momentum representation

今回のPrimary Momentumは、SLOWが既に持っているSize / Illiquidity exposureを除いた

`RESIDUAL_MOM`

とする。

各dateでsame-scale rankを作る。

`S = centered percentile rank(Size)`

`L = centered percentile rank(Illiquidity)`

`M = centered percentile rank(MOM60)`

Primary residualization:

`M = a + b1*S + b2*L + ε`

same-date cross-sectional unregularized OLS。

targetは一切使わない。

`RESIDUAL_MOM_RAW = ε`

をsame-date average-tie centered percentile rankへ再変換し、

`RM`

とする。

高RM = Size / Illiquidityでは説明されないpositive momentum。

これはPrimary定義として結果を見る前に固定する。

---

# 3. Residualization robustness

Primary candidate definitionには使用しないが、診断上以下も固定実施する。

### Robustness A

MOM60をSLOW_CONTROL rankだけへ回帰:

`M ~ 1 + SLOW_RANK`

### Robustness B

Size×Illiquidity fixed 3×3 cell内でMOM60をrankし直す。

### Robustness C

Size×Illiquidity fixed 5×5 cell内でMOM60をrankし直す。

これらはalternative strategyではない。

目的は、

「Residual Momentumという現象がOLS残差化手法だけのartifactではないか」

を確認すること。

Primary conclusionはSection 2のRMを中心にする。

---

# 4. Unconditional information

まずRM単独の情報量を計測する。

保存:

- RankIC
- HAC5 t
- RankIC hit
- Q1–Q5 forward target
- Q monotonicity
- Q5−Q1 spread
- Gross spread Sharpe

期間:

- pooled
- EX2016
- 2011
- 2012
- 2013
- 2014
- 2015
- 2016 partial

これはRM単独strategyを採用する試験ではない。

---

# 5. Conditional information inside SLOW

最重要diagnostic。

各dateで既存SLOW official quintileを固定し、

- Q1
- Q2
- Q3
- Q4
- Q5

各bucket内でRMをrankする。

各SLOW quintileについて、

`high RM − low RM`

のforward residual-return spreadを計測する。

Primary focus:

- SLOW Long region = Q4/Q5
- SLOW Short region = Q1/Q2

保存:

- stock count
- RM RankIC
- RM tercile Low/Mid/High target
- High−Low spread
- HAC5 t
- spread Gross Sharpe
- year-by-year spread
- positive-year count

重要:

Long側ではhigh RMほどtargetが高いか。

Short側でもhigh RMほどtargetが高いなら、

low RMをよりShort側へ置くconfirmation signalとして解釈できる。

---

# 6. Conditional information inside Size × Illiquidity

既存診断で重要だったjoint structureを使う。

各dateで、

Size tercile × Illiquidity tercile

の3×3を固定。

9cellそれぞれでRMの、

- RankIC
- tercile Low/Mid/High target
- High−Low spread
- HAC5 t
- year stability

を計測する。

特に、

`Small + Illiquid`

をprimary cellとする。

ただし他8cellも全て保存する。

Small+Illiquidだけ結果を抜き出して結論を作らない。

---

# 7. Finer 5×5 conditional surface

計算時間を使ってfixed 5×5 surfaceも実行する。

Size quintile × Illiquidity quintile = 25cell。

各cellで、

- average stock count
- RM RankIC
- RM Low/High spread
- target mean
- SLOW average weight
- SLOW gross contribution

を保存。

minimum support未満のcellを削除せず、

support不足として表示する。

minimum support thresholdをstrategy ruleには使用しない。

heatmap CSVを保存する。

目的:

Momentum効果が、

- Small側へ滑らかに強くなるのか
- Illiquid側へ滑らかに強くなるのか
- cornerだけなのか
- 不規則なのか

を確認する。

---

# 8. Long / Short asymmetry

SLOW_CONTROLのofficial Long(Q4/Q5)とShort(Q1/Q2)を固定したまま、

各side内をRM quintileへ分解する。

各RM quintileで、

- stock-days
- average SLOW weight
- forward target
- annual gross contribution
- annual net contribution
- turnover contribution

を保存する。

LongとShortを別々に報告。

特に、

`Long: RM ↑ -> forward target ↑`

および

`Short: RM ↑ -> forward target ↑`

が同じ方向で存在するか確認する。

片側だけに存在しても、同じbundle内でLong-only ruleを作らない。

---

# 9. Transition / timing diagnostic

Momentumを「static characteristic」ではなく「timing」として調べる。

SLOW membershipを、

- newly entered Long
- continuing Long
- exiting Long
- newly entered Short
- continuing Short
- exiting Short
- neutral

へ分類する。

その中でRM tercile別に、

- next official target mean
- contribution
- count

を保存する。

目的:

Momentumが、

- entry timing
- holding confirmation
- exit timing

のどこで情報を持つかを見る。

この結果からentry/exit filterを作らない。

---

# 10. Rank-boundary diagnostic

Momentumを全portfolioへ入れるとturnoverが大きく増えたため、

SLOW official quintile boundary付近だけを診断する。

各dateでSLOW percentileを計算し、

official boundary:

- 20%
- 40%
- 60%
- 80%

からの距離を保存する。

固定band:

- boundary distance <= 2.5 percentile point
- <= 5 percentile point
- <= 10 percentile point

について、

RMとforward targetの関係を計測。

これはparameter searchではなくnested descriptive diagnostics。

strategyを作らない。

目的:

Momentum情報が、

「強いSLOW銘柄の順位」

より

「Long/neutral、Short/neutral境界のmarginal name selection」

に有効なのかを見る。

---

# 11. Momentum persistence / turnover relevance

RMについて、

- lag1 rank autocorrelation
- lag5
- lag10
- lag20

を固定diagnosticとして計測する。

さらに、

- absolute RM rank change
- SLOW rank change
- candidate-independent portfolio boundary crossing

との関係を保存。

これは新EWMA alphaやholding periodを選択するためではない。

Momentum signalの速さがtransaction cost問題と整合するか確認する。

---

# 12. Regime stability

RM conditional effectを以下で固定分解する。

### Calendar

- yearly
- half-year
- rolling 252 sessions

### Market state

targetや未来データを使わず、その日までの情報だけで固定定義できる場合のみ、

- trailing TOPIX volatility high / low
- trailing market trend positive / negative

をmedian splitする。

threshold optimization禁止。

market-stateデータのPIT安全性が保証できなければ、このsectionはskipし理由を記録する。

目的はregime trading ruleを作ることではなく、conditional Momentumが極端な一期間だけで発生していないかを見ること。

---

# 13. Placebo tests

計算時間をここに十分使う。

Primary RM conditional effectについてplaceboを実施。

## Placebo A: within-date permutation

同一date内でRMをrandom permutation。

ただしSize×Illiquidity tercile構成を維持するため、

**3×3 cell内でのみshuffle**。

reps = 2000。

seed固定。

観測conditional spread / RankICがplacebo distributionのどこにあるか保存。

## Placebo B: circular date shift

RM seriesを銘柄ごとに固定offsetでcircular shift。

future情報としてstrategyには使用しないdiagnostic placebo。

offsetは十分大きく、例えば20営業日以上。

複数固定offsetを使用し、observed statisticとの比較を保存。

placeboからfeatureやparameterを選ばない。

---

# 14. Bootstrap uncertainty

以下についてpaired circular moving-block bootstrap。

- block = 20 sessions
- reps = 5000
- fixed seed

対象:

1. RM unconditional RankIC
2. SLOW Long内RM spread
3. SLOW Short内RM spread
4. Small+Illiquid内RM spread
5. 3×3 weighted pooled conditional statistic

95% percentile CIを保存。

可能ならblock 10 / 20 / 40のCI sensitivityもdiagnosticとして計算。

primary inferenceは20。

---

# 15. Multiple-testing awareness

今回は多数のconditional cellを表示するので、

個別t-statだけで発見扱いしない。

以下を追加する。

- Benjamini-Hochberg FDRをdescriptiveに保存
- 3×3 / 5×5 surface全体のpermutation-based max-stat
- positive cell fraction
- sign consistency across years

ただしFDR結果を用いてcell filterをstrategy化しない。

Primary hypothesesは事前に以下3つだけとする。

H1:
`RM has positive conditional return information inside SLOW Long`

H2:
`RM has positive conditional return information inside SLOW Short`

H3:
`RM has positive conditional return information inside Small+Illiquid`

それ以外はsecondary。

---

# 16. Pre-registered candidate gate

診断終了後、performance candidateを実行してよい条件を事前固定する。

以下すべて必要。

### Long gate

SLOW Long内RM High−Low spread:

- pooled > 0
- EX2016 > 0
- 2011–2015で >=4/5 positive
- pooled bootstrap 95% lower bound > 0

### Short gate

SLOW Short内RM High−Low spread:

- pooled > 0
- EX2016 > 0
- >=4/5 positive
- pooled bootstrap lower bound > 0

### Small+Illiquid gate

- pooled RM spread > 0
- EX2016 > 0
- >=4/5 positive

### Robustness gate

Primary effectの方向が、

- direct RM
- 3×3-cell residual rank
- SLOW-residualized Momentum

の少なくとも3/3で同方向。

これら全gateを通った場合のみSection 17のcandidateを1本実行。

一つでも失敗したらcandidate performance trialは0本で終了。

ただし全diagnostic / placebo / bootstrapは最後まで完走する。

---

# 17. One fixed tradable candidate

gate通過時のみ、

candidate:

`SLOW_RM_CONFIRM`

を1本だけ評価する。

same-date centered percentile rankを、

`S = SLOW_CONTROL centered percentile rank`

`M = RM centered percentile rank`

とする。

固定score:

`CONFIRM_SCORE = S + abs(S) * M`

意味:

- SLOW Long候補ではpositive residual momentumがscoreを上げる
- SLOW Long候補でnegative residual momentumはscoreを下げる
- SLOW Short候補ではnegative residual momentumがscoreをさらに下げる
- SLOW Short候補でpositive residual momentumはShortを弱める
- centerではMomentumの影響を小さくする

追加係数なし。

weight searchなし。

smoothing追加なし。

この式を結果後に変更しない。

official global ranking / five-quintile weightingへそのまま渡す。

---

# 18. Candidate accounting

`SLOW_RM_CONFIRM` を実施した場合、

比較:

- SLOW_CONTROL
- MOM60
- previous SLOW_MOM60_EQUAL
- SLOW_RM_CONFIRM

Primary comparisonは必ず、

`SLOW_RM_CONFIRM − SLOW_CONTROL`

保存:

- RankIC/HAC/hit
- Gross Sharpe
- Net Sharpe
- annual gross/net
- turnover
- annual cost
- MaxDD
- Q1–Q5
- monotonicity
- Long gross/net
- Short gross/net

期間:

- POOLED
- EX2016
- 2011–2015各年
- 2016 partial

---

# 19. Candidate transaction-cost stress

candidateを実行した場合のみ、

performance selectionには使わずrobustnessとして、

one-way cost:

- 5bp
- 10bp primary
- 15bp
- 20bp

を再会計する。

strategy weightは変更しない。

目的:

改善がcompetitionの10bpだけに依存するかを見る。

---

# 20. Candidate attribution

SLOW_RM_CONFIRM − SLOW_CONTROLを、

- common holdings
- Long additions
- Long removals
- Short additions
- Short removals
- neutral changes

へ分解。

各groupで、

- annual gross delta
- annual cost delta
- annual net delta
- stock-days

を保存。

結果から新しいfilterを作らない。

---

# 21. Candidate adoption gates

candidate実施時の採用条件:

- pooled Net Sharpe > SLOW
- EX2016 Net Sharpe > SLOW
- pooled annual Net >= SLOW
- 2011–2015 Net Sharpe improvement >=4/5
- paired bootstrap ΔNetSR lower 95% > 0
- Long Net > 0
- Short Net >= SLOW Short Net
- turnover <= 1.50 × SLOW
- MaxDD magnitude <= SLOW
- incremental annual gross > incremental annual cost

一つでも失敗ならREJECT。

RankIC improvementだけでは採用しない。

---

# 22. Candidate bootstrap

candidate実施時:

paired circular moving-block:

- block20
- reps5000
- fixed seed

Primary:

`SLOW_RM_CONFIRM − SLOW_CONTROL ΔNet Sharpe`

Secondary:

- Δannual net
- ΔGross Sharpe
- ΔMaxDD descriptive

EX2016も保存。

---

# 23. No rescue rule

結果を見たあとに以下を絶対に行わない。

- RM coefficient変更
- `abs(S)` の変更
- LongだけMomentum利用
- ShortだけMomentum利用
- Small+Illiquidだけ利用
- SLOW_HIGH_MOM_LOW veto
- boundary bandだけ利用
- momentum window変更
- skip変更
- EWMA変更
- factor sign変更
- sector filter
- volatility filter
- regime switch
- weight search
- threshold search
- nonlinear rescue
- ML rescue
- candidate2本目

diagnosticに良いsubgroupが見つかっても、そのrunではstrategy化しない。

次experimentの仮説候補としてreportへ記録するだけ。

---

# 24. Causality audit

新しく作る全transformsについて、

- future mutation
- truncation invariance
- row shuffle
- deterministic rebuild
- exact Date/Code index
- no target dependency
- t+2 maturity
- fold-end purge
- Train-only firewall

を検証する。

特に、

- RM residualization
- conditional bins
- transition labels
- boundary diagnostics
- regime descriptors

が未来値に依存しないこと。

targetはfeature / candidate score完成後にのみ読み込む。

---

# 25. Statistical audit

保存:

- number of hypotheses
- primary vs secondary labels
- bootstrap seeds
- permutation seeds
- all failed technical runs
- all config hashes
- code hash
- input hash
- output hash

一度見たperformance resultを隠して再runしない。

technical failure再実行時もconfig / strategy definitionを変更しない。

---

# 26. Runtime / resource report

最後に、

- total elapsed
- phase elapsed
- peak RSS
- number of bootstrap draws
- number of permutation draws
- number of candidate performance trials
- number of rescue trials
- files generated

を明記。

submission本番への推論時間見積りも別途計測する。

ただしresearch runtimeとsubmission runtimeを混同しない。

---

# 27. Required report conclusion

最終reportでは少なくとも以下に答える。

1. MOM60にはSize/Illiquidityと独立した情報があるか
2. その情報はSLOW Long内で有効か
3. SLOW Short内で有効か
4. Small+Illiquid内で特に強いか
5. static factorなのかtiming signalなのか
6. entry / holding / exitのどこで最も観測されるか
7. signal persistenceはcost問題と整合するか
8. 5×5 surfaceで滑らかなconditional patternがあるか
9. placeboに対して観測効果は異常か
10. bootstrapで年次不安定性を考慮しても残るか
11. candidate gateを通ったか
12. candidateを実行した場合SLOWをafter-costで超えたか

---

# 28. Final classification

以下のどれかで終了する。

### A. Conditional Momentum confirmed

RMがLong/Short/Small+Illiquidで安定し、candidateもSLOWをafter-costで上回る。

### B. Information exists, implementation fails

conditional RM informationは頑健だがcandidateのturnover/costでSLOWを超えない。

### C. Long-only/asymmetric information

Momentum情報は片側だけに存在。

今回candidate gateは失敗としてstrategy化しない。

次experiment hypothesisとして記録のみ。

### D. Regime-dependent

pooledでは見えるがyear / rolling / placebo / bootstrapで不安定。

strategy化しない。

### E. No conditional Momentum

SLOWを条件付けるとRM情報自体が消える。

Momentum研究を一旦終了。

### F. Inconclusive

support / instability / statistical uncertaintyで判断不能。

---

# 29. Core principle

今回の問いは、

**「Momentumを何%混ぜればSLOWを超えるか」ではない。**

問いは、

**「Small / Illiquidというstructural alphaの中で、Momentumはどこに独立したtiming informationを持ち、その情報をSLOWの強い構造を壊さず利用できるか」**

である。

計算時間をweight searchに使わず、

**conditional structure、placebo、bootstrap、year stability、transaction-cost mechanism、causality**

の検証へ使う。

新Experiment IDを採番し、

`freeze`
→ `component parity`
→ `RM construction`
→ `unconditional diagnostics`
→ `SLOW-quintile conditional diagnostics`
→ `3×3 / 5×5 surfaces`
→ `Long/Short asymmetry`
→ `transition/boundary diagnostics`
→ `persistence`
→ `regime stability`
→ `placebo`
→ `bootstrap/FDR`
→ `candidate gate`
→ `[gate pass only] one fixed candidate`
→ `cost/attribution/bootstrap`
→ `causality audit`
→ `final report`

まで途中結果に関係なく完走せよ。