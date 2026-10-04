`daily_momentum` で、既存 `SLOW_CONTROL` の Size / Illiquidity に、既存 `MOM60` residual momentum を追加した固定3-factor experimentをTrain-onlyで実施せよ。

目的は、

**Size、Illiquidity、Residual Momentumという異なる3つのcross-sectional signalを等ウェイトで組み合わせることで、SLOW_CONTROL単体より高く安定したafter-cost Net Sharpeを得られるか**

を検証すること。

Historical Valid / Validは禁止。

新しいmomentum window、weight、threshold、filterは探索しない。

---

# 1. Components

以下3componentを既存実装から再現し、定義を変更しない。

## Size

既存SLOW_CONTROLのSize signal:

`SIZE_RAW = -log(raw Close × PIT shares)`

高score = 小型。

## Illiquidity

既存SLOW_CONTROLのLiquidity signal:

`ILLIQ_RAW = Amihud60 / min40`

高score = 低流動性。

既存SLOW_CONTROLと同じwinsorization、missing処理、standardizationを使用する。

## Momentum

既存 `MOM60 / DM-20260908-v1` をそのまま使用する。

既存仕様:

`residual60 / skip1 -> same-date centered rank -> EWMA(0.25)`

window、skip、EWMA alpha、ranking orderを変更しない。

SN1_H1は今回使用しない。

---

# 2. Component parity

performance trial前に、

- SLOW_CONTROL score
- Size component
- Illiquidity component
- MOM60 score

を既存保存結果とbitwise照合する。

SLOW_CONTROLについて、

`Size + Illiquidity`

から既存scoreが完全再現されることを確認する。

MOM60も既存保存scoreとbitwise一致を要求する。

---

# 3. Orthogonality diagnostics

blend前に以下を保存する。

各component間について、

- daily cross-sectional Spearman
- pooled mean Spearman
- year-by-year mean Spearman
- score correlation matrix

特に、

- Size vs Illiquidity
- Size vs MOM60
- Illiquidity vs MOM60
- SLOW_CONTROL vs MOM60

を報告する。

さらにSLOW_CONTROLとMOM60について、

- daily Gross P/L correlation
- daily Net P/L correlation
- year-by-year P/L correlation
- Long Jaccard
- Short Jaccard
- drawdown depth correlation

を保存する。

低相関自体を採用根拠にはしない。

---

# 4. Fixed candidate

performance candidateは1本のみ。

名称:

`SLOW_MOM60_EQUAL`

各dateについて3factorを同一尺度へ変換し、

`SizeRank`
`IlliquidityRank`
`MomentumRank`

を作る。

各factorはsame-date average-tie centered percentile rankへ変換し、

`Score = (SizeRank + IlliquidityRank + MomentumRank) / 3`

とする。

固定1:1:1。

その後はofficial global ranking / five-quintile portfolioへ渡す。

追加smoothingは禁止。

---

# 5. Important implementation condition

SLOW_CONTROL内部ではSizeとIlliquidityを既存仕様で処理しているが、今回の3factor candidateでは、

**Size / Illiquidity / Momentumを3つの独立factorとして等ウェイト**

にする。

したがって、

`0.5 × SLOW_CONTROL + 0.5 × MOM60`

とは別のstrategyであることを明記する。

今回知りたいのは、

`Size + Illiquidity + Momentum`

というclassic three-factor style combinationの効果。

---

# 6. Diagnostic controls

以下を必ず同一期間・同一official accountingで表示する。

- `SLOW_CONTROL`
- `MOM60`
- `SLOW_MOM60_EQUAL`

SN1_H1は参考値を追加してもよいが、採否比較には使用しない。

---

# 7. Primary evaluation

各strategyについて、

- RankIC mean
- RankIC HAC5 t
- RankIC hit rate
- Gross Sharpe
- Net Sharpe
- annual gross
- annual net
- turnover
- annual cost
- maximum drawdown
- Q1–Q5 returns
- Q monotonicity
- annual Long gross/net
- annual Short gross/net

を保存する。

期間:

- pooled
- EX2016 = 2011–2015
- 2011
- 2012
- 2013
- 2014
- 2015
- 2016 partial

2016 partialはfull-year stability gateに含めない。

---

# 8. Incremental attribution

Primary comparison:

`SLOW_MOM60_EQUAL - SLOW_CONTROL`

について、

- ΔRankIC
- ΔGross Sharpe
- ΔNet Sharpe
- Δannual gross
- Δannual net
- Δturnover
- Δannual cost
- ΔLong gross/net
- ΔShort gross/net
- ΔMaxDD

を保存する。

Momentum追加による改善が、

`gross alpha improvement`

なのか、

`portfolio reshuffling / cost`

なのかを明確に分ける。

---

# 9. Momentum contribution diagnostic

各dateで、

SLOW_CONTROLとMOM60のsignal agreementを、

- BOTH_HIGH
- SLOW_HIGH_MOM_LOW
- SLOW_LOW_MOM_HIGH
- BOTH_LOW
- OTHER

の固定groupへ分類する。

High/Lowはofficial Long/Short membershipを用いる。

各groupについて、

- stock-days
- forward target mean
- candidate gross contribution
- candidate net contribution
- Δgross vs SLOW
- Δnet vs SLOW
- turnover contribution

を保存する。

この結果を見てveto/filterを作らない。

---

# 10. Turnover / cost analysis

Momentum追加の最大の論点はtransaction costなので、

以下を必ず報告する。

- SLOW turnover
- MOM60 turnover
- candidate turnover
- candidate / SLOW turnover ratio
- annual incremental cost
- annual incremental gross
- incremental gross / incremental cost

特に、

`Δannual gross > Δannual cost`

かを明示する。

gross improvementだけで採用しない。

---

# 11. Pure sleeve diagnostic

performance candidateとは別のdiagnosticとしてのみ、

`1/3 Size sleeve + 1/3 Illiquidity sleeve + 1/3 MOM60 sleeve`

を作る必要はない。

SizeとIlliquidity単独のofficial strategy化による新しいportfolio constructionは今回の目的外。

ただし既存SLOW_CONTROLとMOM60について、

`0.5 × SLOW official weights + 0.5 × MOM60 official weights`

のpure-weight diagnosticを既に再現可能なら参考として表示してよい。

新しいparameter trialとは数えない。

---

# 12. Bootstrap

paired circular moving-block:

- block = 20 sessions
- reps = 2000
- seed = 20261003
- 95% percentile CI

Primary:

`SLOW_MOM60_EQUAL - SLOW_CONTROL`

のΔNet Sharpe。

Secondary:

`SLOW_MOM60_EQUAL - MOM60`

も保存する。

Primary CIを採否に使用する。

---

# 13. Adoption gates

`SLOW_MOM60_EQUAL` を次段階候補にするには、最低限すべて満たすこと。

- pooled Net Sharpe > SLOW_CONTROL
- EX2016 Net Sharpe > SLOW_CONTROL
- annual Net >= SLOW_CONTROL
- 2011–2015 Net Sharpe improvement vs SLOW_CONTROL >= 4/5 years
- bootstrap ΔNet Sharpe lower bound > 0
- Long net > 0
- Short net >= SLOW_CONTROL Short net
- MaxDD magnitude <= SLOW_CONTROL
- turnover <= 1.50 × SLOW_CONTROL
- incremental annual gross > incremental annual cost

Gross SharpeまたはRankICだけの改善では採用しない。

---

# 14. Prohibited

以下は禁止。

- momentum window search
- skip-period search
- EWMA alpha search
- factor weight search
- 2:1:1 / 1:1:0.5等のweight変更
- Momentum sign変更
- Long/Short別factor weight
- disagreement veto
- momentum threshold
- sector neutralization
- regime switching
- volatility targeting
- score smoothing追加
- result後のrescue candidate
- Historical Valid / Valid

固定1:1:1の1candidateだけで終了する。

---

# 15. Causality / leakage audit

新candidateについて、

- exact input/output index
- future mutation
- truncation invariance
- row shuffle
- deterministic rebuild
- component parity
- official accounting reconciliation
- Train-only firewall
- t+2 maturity
- fold-end purge

を確認する。

MOM60 residual return生成にも未来情報が入っていないことを既存auditと照合する。

---

# 16. Interpretation framework

最終的に以下のどれかとして整理する。

### A. Complementary Momentum

Momentum追加によってGross、Net、stabilityが改善し、追加costを十分上回る。

→ Size / Illiquidity / Momentumの3factor structureに価値。

### B. Gross-only improvement

Grossは改善するが、turnover/costによりNetが改善しない。

→ Momentum informationはあるが現在のdaily implementationでは経済的価値なし。

### C. Dilution

Momentum追加でSLOWのstrong alphaが薄まり、Gross/Netとも悪化。

→ SLOW単独維持。

### D. Unstable complement

pooledでは改善するが年別安定性、bootstrap、Short等で失敗。

→ known Trainでは採用しない。

---

# 17. Decision principle

今回の問いは、

**「Momentumは単体で強いか」ではない。**

問いは、

**「既に強いSize / Illiquidity strategyへ、既存のplain residual Momentum60を独立factorとして等ウェイト追加すると、after-costでより高く安定したstrategyになるか」**

である。

低相関、RankIC上昇、Gross上昇だけでは採用しない。

新Experiment IDを採番し、

`plan/config freeze`
→ `component parity`
→ `orthogonality diagnostics`
→ `fixed 1:1:1 trial`
→ `incremental attribution`
→ `turnover/cost analysis`
→ `bootstrap`
→ `causality audit`
→ `decision`

まで完了せよ。