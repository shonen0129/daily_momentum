# DM-20261002-08 — Sector Momentum as context

**結論: 両候補をREJECT。Short Disagreement VetoはShort gross損失縮小を示すが、MOM60 replacementの固定条件を満たさない。**

2候補を事前登録どおり各1回評価した。主評価2011–2015は1,216営業日・548,687銘柄日、2016部分年を含むpooledは1,275営業日・576,535銘柄日。全Trainは既知の開発履歴で、独立OOSではない。DM-20261002-06/07のREJECT・設定・コード・結果は全hash不変。今回のcontext仮説はユーザー指定の新規事前登録であり、旧HIER33のweight/alpha/threshold調整ではない。

主評価のNet SharpeはMOM60 **0.3243**、Hard Confirmation **0.4148**、Short Veto **0.4346**。pooledは順に0.3081/0.4209/0.4483。年率Netはpooled1.613%/2.275%/2.351%、主評価1.669%/2.213%/2.253%。Hardはfull-year改善2/5（2013/2015）、Vetoは3/5（2013/2014/2015）で必要な4/5に届かない。2016部分年の改善を数えない。raw context coverageは両候補共通でpooled **93.890%**、主評価 **93.944%**で95%未達。これらが採否を決める。

固定paired circular20-session bootstrap、2,000reps、seed20261002のpooled ΔNet Sharpe95% CIはHard **[−0.0991,+0.3114]**、Veto **[+0.0034,+0.2895]**。Vetoのpooled下限はわずかに正だが、2016を除く主評価では **[−0.0302,+0.2550]**、Hardは **[−0.1151,+0.3140]**で両方0を跨ぐ。主評価CIは同じ保存済み日次P/Lへ同じ指定手法を適用した追加期間表示であり、候補再評価・新候補・採否条件の変更はない。事前登録したpooled gateと既存判断はそのまま保存している。2016改善を含めた区間だけを根拠に安定した増分とは呼ばない。

**中心問い: Cをneutral化するとShort gross lossが減るか。** Vetoのpooled年率Short grossはMOM60−2.233%→−1.754%、netは−3.026%→−2.564%。ΔShort Net **+0.4622pp = +0.4798pp gross − 0.0177pp cost増**。gross寄与はnet改善の103.8%で50%条件を通過し、cost削減によるShort改善ではない。主評価でも **+0.3244pp net = +0.3440pp gross − 0.0195pp cost増**。VetoのShort gross/net Sharpeはpooled−0.339/−0.495（MOM60−0.427/−0.579）。損失は縮小するがShort自体は依然負である。HardのShort net改善+0.7242ppはgross+0.7012ppとcost減+0.0230pp、96.8%がgrossで、こちらもfold/coverage/bootstrap条件を満たさない。

**入替先が利益を作ったか。** Veto対MOM60のShort Q1/Q2 membershipではremoved/added各30,906銘柄日、unchanged199,996。旧removedのtarget平均+2.64bp/day、addedは+1.35bpで、入替先の反騰は小さくなったがadded Shortも損失である。会計上の年率ΔShort grossは **+0.3845pp（removedの旧損失回避） −0.1587pp（addedの新損失） +0.2540pp（unchangedのweight差） = +0.4798pp**。改善をreplacementの正のalphaとは呼ばない。Q1のgross差は+0.6571pp、Q2は−0.1772ppで、改善は最弱tailの入替に偏る。Q1 added target0.72bp対removed3.25bp、Q2 added2.25bp対removed1.32bp。日次membership・全銘柄名・target・stock/common分布・業種分布は保存済み。

Cに該当した元MOM60 Short92,806銘柄日のうち22,453（24.2%）が実際のShortから外れ、70,353はShortに残る。removed Cのtarget平均+3.25bp、旧Short gross寄与−0.3323%/年を回避した。retained Cはtarget+4.34bpで、gross寄与−1.5692%→−1.2661%へweight変化で損失が縮小。raw完全vetoでもEWMA stateとglobal rankingが残るため、即時に全C銘柄がShortから消えるわけではない。

**State attribution。** Cのequal-date target平均+3.31bp（row mean+3.60bp）、Dは−0.45bp（row mean+0.57bp）で、集計方式によりDの符号が異なる。MOM60のC Short gross寄与−1.902%→Veto−1.299%（+0.6024pp）が改善の主要部分。Dは−0.405%→−0.510%へ悪化し、D-only Short仮説は今回も支持しない。A/B/C/D/ZERO_OR_MISSINGのrow数・target・RankIC・Long/Short gross/net・turnover/costはstate_attribution*.csv。bucket contributionはoriginal globally ranked bookの会計であり、standalone state strategyではない。

**状態の安定性と取引。** A/B/C/Dのspell中央値は3/2/2/2日、平均12.71/5.42/6.52/9.29日。Cの90th percentile duration17日、1-day persistence84.58%、5-day uninterrupted persistence58.30%。短いstateも多いが、Veto総turnover0.06316/dayはMOM60 0.06342を0.40%下回り、1.25倍上限を通過。C entry/exit当日の該当銘柄が説明するturnoverは総14.55%、Short22.84%（主評価14.41%/22.50%）。これは当日名寄せの寄与で、EWMAによる遅延や全replacementを因果的に説明する比率ではない。Veto年率全cost1.584%対MOM60 1.598%で、総cost減はLong側から来る。rank自己相関0.99417対0.99664、quintile retention92.566%対92.396%、平均tail spell25.15日対24.79日。平均絶対percentile変化0.01605対0.01621だがmax0.5599対0.2187で大きいrank jumpもあり、平均だけで状態安定と断定しない。duration filterは作らない。

**Long protectionと業種集中。** Vetoのpooled年率Long gross/net5.689%/4.916%はMOM60 5.444%/4.639%を改善。Long turnover0.03071対0.03195、membership overlap96.02%、Jaccard92.38%。Long alpha喪失の点推定は見られない。HardのLong net4.577%はMOM60より0.0618pp悪化し、Long抑制の代償がある。Veto Short HHI平均0.08159対0.06745、平均最大業種share16.46%対14.05%、日次最大30.25%対27.27%。Q1平均最大業種share21.93%対16.29%、日次最大44.68%対36.36%。Short exposure上位2業種3650/3200は22.38%対22.13%で、集中増はtop2だけでは捉えられない。Q1/Q2分布、全業種side寄与、複数定義のtop2寄与を保存し、業種除外は行わない。

**変換順序と限界。** Controlはcentered rank→EWMA(.25)、候補はraw context→EWMA(.25)。したがって上のgross/replacement改善をSector context単独の純粋な因果効果とは呼ばない。self-inclusive commonはpart-whole関係も持つ。既知Trainでの固定operational hypothesisの点推定として記録し、threshold/部分veto/alpha/Long-side追加などの救済探索はしない。Q monotonicityはHard1.0、Veto0.9（Q2/Q3が非単調）、Veto最大compound DD−9.319%対MOM60−9.706%。これらの点推定が採否条件の不足を上書きすることはない。

**検証・実行。** 18のfull-input future-mutation/truncationケース（3cutoff×4個別source/joint/truncation）、全Stock/PIT/common/state/veto/EWMA/final/controlのbitwise不変性、future-only stocks・future sector changes・suffix deletion、row shuffle・deterministic rebuild、exact index・finite予測809,636/809,636、研究adapter/独立no-arg adapterのbitwise一致、旧primitive/common/control一致、公式weight/net bitwise一致、purge・state/sector/replacement/side会計照合をPASS。全223 testsが通過。元研究run約60.7秒、peakRSS1.39GiB。入力のbyte hashは事前記録するが、targetのラベル値は全prediction audit後に初めてparquetとして解釈する。全評価はTrain-onlyで、Valid/raw targetの読み込みはない。

make checkは今回の編集前から既存DM-20261002-04のunknown experiment kindで停止。新規08 metadataと既存Freeze129ファイルhashは個別にPASSし、旧期待hashは変更していない。元runは生成済みdiagnostic parquetのfirewall allowlist漏れで最後のレポート複製だけ失敗し、そのrunをfailedのまま保存した。別report-only runで全保存hash/監査/採否を照合して復旧した（新performance trial0）。strategy/score定義は変更せず、publication用の明示allowlistだけ修正した。Primary bootstrap追加表示とこの解釈追記も保存済みP/Lからのみ作成した。No Valid/Freeze/submission。



**Decision: SECTOR_CONFIRM=REJECT, SHORT_DISAGREE_VETO=REJECT.**

Run `artifacts/DM-20261002-08/run-20261002T070900Z`. Exactly two pre-registered performance trials, no rescue. Known Train development evidence; no independent OOS, Historical Valid, release, Freeze or submission. Prior06/07 definitions, decisions and hashes remain unchanged.

Primary2011–2015 follows below. POOLED additionally includes2016 partial for continuity with preceding experiments and fixed pooled gates.2016 is shown separately and never counted in4/5 full-year improvement. Each fold's final2 exchange dates purged; t+2 maturity verified. No fitted model; expanding causal history. Same dates/accounts for all strategies.

## Primary2011–2015 (EX2016)

| strategy | rankic | gross_sharpe | net_sharpe | annual_net | turnover | annual_cost | annual_short_gross | annual_short_net | annual_long_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SECTOR_CONFIRM | 0.008316 | 0.715181 | 0.414794 | 0.022130 | 0.063832 | 0.016018 | -0.014681 | -0.022365 | 0.044494 |
| SHORT_DISAGREE_VETO | 0.008362 | 0.740110 | 0.434558 | 0.022529 | 0.063147 | 0.015836 | -0.016516 | -0.024626 | 0.047155 |
| MOM60 | 0.007425 | 0.634564 | 0.324348 | 0.016685 | 0.063327 | 0.015958 | -0.019956 | -0.027870 | 0.044555 |

## Pooled including2016 partial

| strategy | rankic | gross_sharpe | net_sharpe | annual_net | turnover | annual_cost | annual_short_gross | annual_short_net | annual_long_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SECTOR_CONFIRM | 0.008635 | 0.719008 | 0.420896 | 0.022752 | 0.064176 | 0.016108 | -0.015322 | -0.023021 | 0.045773 |
| SHORT_DISAGREE_VETO | 0.008753 | 0.750408 | 0.448294 | 0.023515 | 0.063163 | 0.015844 | -0.017536 | -0.025641 | 0.049156 |
| MOM60 | 0.007590 | 0.613360 | 0.308092 | 0.016128 | 0.063418 | 0.015981 | -0.022335 | -0.030263 | 0.046391 |

## Fold/year metrics

| strategy | scope | gross_sharpe | net_sharpe | annual_net | turnover | annual_short_gross | annual_short_net | annual_long_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SECTOR_CONFIRM | 2011 | 0.719772 | 0.436397 | 0.025784 | 0.066669 | -0.036527 | -0.044583 | 0.070367 |
| SECTOR_CONFIRM | 2012 | 0.824440 | 0.444422 | 0.019924 | 0.067646 | 0.015640 | 0.007354 | 0.012569 |
| SECTOR_CONFIRM | 2013 | 0.522393 | 0.289614 | 0.019037 | 0.061009 | -0.012260 | -0.019652 | 0.038689 |
| SECTOR_CONFIRM | 2014 | 1.212235 | 0.688412 | 0.020881 | 0.063217 | -0.015940 | -0.023471 | 0.044352 |
| SECTOR_CONFIRM | 2015 | 0.675753 | 0.420998 | 0.025057 | 0.060556 | -0.024738 | -0.031883 | 0.056939 |
| SECTOR_CONFIRM | 2016 | 0.792834 | 0.526971 | 0.035579 | 0.071280 | -0.028543 | -0.036537 | 0.072116 |
| SHORT_DISAGREE_VETO | 2011 | 0.753628 | 0.472659 | 0.027256 | 0.064795 | -0.041106 | -0.049324 | 0.076580 |
| SHORT_DISAGREE_VETO | 2012 | 0.959233 | 0.561169 | 0.023781 | 0.067186 | 0.017296 | 0.008470 | 0.015311 |
| SHORT_DISAGREE_VETO | 2013 | 0.578739 | 0.333779 | 0.021089 | 0.061508 | -0.013926 | -0.021689 | 0.042778 |
| SHORT_DISAGREE_VETO | 2014 | 1.446408 | 0.944042 | 0.028731 | 0.060857 | -0.013760 | -0.021802 | 0.050533 |
| SHORT_DISAGREE_VETO | 2015 | 0.461447 | 0.200091 | 0.011752 | 0.061322 | -0.031553 | -0.039241 | 0.050993 |
| SHORT_DISAGREE_VETO | 2016 | 0.930507 | 0.681933 | 0.043844 | 0.063499 | -0.038556 | -0.046564 | 0.090408 |
| MOM60 | 2011 | 0.789398 | 0.506792 | 0.029635 | 0.065571 | -0.037842 | -0.045983 | 0.075618 |
| MOM60 | 2012 | 1.026104 | 0.636144 | 0.026788 | 0.065148 | 0.021781 | 0.013708 | 0.013081 |
| MOM60 | 2013 | 0.340451 | 0.081809 | 0.005051 | 0.063355 | -0.025160 | -0.033088 | 0.038139 |
| MOM60 | 2014 | 1.414193 | 0.910504 | 0.027522 | 0.060468 | -0.015208 | -0.022952 | 0.050474 |
| MOM60 | 2015 | 0.170703 | -0.099053 | -0.005742 | 0.062057 | -0.043947 | -0.051626 | 0.045884 |
| MOM60 | 2016 | 0.305757 | 0.067276 | 0.004639 | 0.065295 | -0.071359 | -0.079579 | 0.084217 |

Control: residual60 skip1 -> same-date centered rank -> unchanged EWMA(.25). Candidates: fixed raw Stock/sector context operation -> unchanged EWMA(.25), once. Sector common includes own StockMom, PIT33 exact Date/Code membership, minimum5 finite. This operational strategy comparison also changes transform order; it cannot identify a pure isolated sector-context causal effect. No order-matched third candidate was evaluated.

A(++), B(+-), C(-+), D(--), ZERO_OR_MISSING use raw signs. A keeps A/D only. B neutralizes C only; exact common zero retains negative stock. Missing/nonfinite context neutral0, raw coverage computed before neutralization. No thresholds/weights/alpha/horizon search.

## Fixed gates

```json
{
  "SECTOR_CONFIRM": {
    "decision": "REJECT",
    "feasibility": {
      "pooled_RankIC_positive": true,
      "pooled_GrossSR_positive": true,
      "ex2016_GrossSR_positive": true,
      "gross_positive_3of5": true,
      "raw_context_coverage_ge95pct": false,
      "turnover_le1p25_MOM60": true
    },
    "adoption": {
      "pooled_NetSR_beats_MOM60": true,
      "ex2016_NetSR_beats_MOM60": true,
      "NetSR_improvement_4of5": false,
      "bootstrap_lower_gt0": false,
      "annualNet_beats_MOM60": true,
      "turnover_le1p25_MOM60": true,
      "Shortgross_ge_MOM60": true,
      "Shortnet_ge_MOM60": true,
      "Longnet_positive": true,
      "Qmonotonicity_positive": true
    },
    "failed_checks": [
      "raw_context_coverage_ge95pct",
      "NetSR_improvement_4of5",
      "bootstrap_lower_gt0"
    ],
    "full_year_netSR_improvements": 2,
    "raw_context_coverage": 0.9388987659031975,
    "delta_annual_short_gross": 0.0070124299115134885,
    "delta_annual_short_net": 0.00724235947632193,
    "gross_share_of_short_net_improvement": 0.9682521192768503
  },
  "SHORT_DISAGREE_VETO": {
    "decision": "REJECT",
    "feasibility": {
      "pooled_RankIC_positive": true,
      "pooled_GrossSR_positive": true,
      "ex2016_GrossSR_positive": true,
      "gross_positive_3of5": true,
      "raw_context_coverage_ge95pct": false,
      "turnover_le1p25_MOM60": true
    },
    "adoption": {
      "pooled_NetSR_beats_MOM60": true,
      "ex2016_NetSR_beats_MOM60": true,
      "NetSR_improvement_4of5": false,
      "bootstrap_lower_gt0": true,
      "annualNet_beats_MOM60": true,
      "turnover_le1p25_MOM60": true,
      "Shortgross_ge_MOM60": true,
      "Shortnet_ge_MOM60": true,
      "Longnet_positive": true,
      "Qmonotonicity_positive": true,
      "Shortnet_improvement_positive_gross_share_ge50pct": true
    },
    "failed_checks": [
      "raw_context_coverage_ge95pct",
      "NetSR_improvement_4of5"
    ],
    "full_year_netSR_improvements": 3,
    "raw_context_coverage": 0.9388987659031975,
    "delta_annual_short_gross": 0.004798418180988851,
    "delta_annual_short_net": 0.004621781423774618,
    "gross_share_of_short_net_improvement": 1.038218327743845
  }
}
```

## Paired circular20-session bootstrap ΔNet Sharpe vs MOM60

```json
{
  "SECTOR_CONFIRM": {
    "low": -0.0990982723355385,
    "high": 0.3113543562915052,
    "bootstrap_positive_fraction": 0.857,
    "reps": 2000,
    "block": 20,
    "seed": 20261002
  },
  "SHORT_DISAGREE_VETO": {
    "low": 0.003352035993600556,
    "high": 0.2894728973922245,
    "bootstrap_positive_fraction": 0.978,
    "reps": 2000,
    "block": 20,
    "seed": 20261002
  }
}
```

2000 paired draws, seed20261002,95% percentile interval; blocks over concatenated matched eligible sessions including purge gaps. Describes known-Train sampling uncertainty, not independent OOS or multiplicity-adjusted proof.

## Accounting and mechanism definitions

P/L values are decimal fractions. Annual P/L/cost=daily arithmetic mean×252, Sharpe=sample-SD daily mean/SD×sqrt252. HAC5 RankIC t and hit ratio, additive/compound DD and Q1-Q5/monotonicity saved for every scope. Official Code-order5 quintiles and10bp one-way cost, computed continuously before date filtering. Official missing-target cost omission matches scorer; conservative all-position cost/net also saved. Short uses signed market-residual P/L, not borrow-cost-adjusted raw short security returns. Side gross/net/cost reconcile within1e-15.

State attribution is original-book contribution, NOT standalone state performance. Exit cost is assigned to the current row/state even if its current position is zero. State gross/net/cost and side turnover sum to full accounts. Equal-row and equal-date target means are both saved; RankIC is equal-date with raw Stock and each strategy score.

State transitions count adjacent exchange-date observations; missing-row gaps reset. Full observed spell lengths intersecting evaluation are retained, left/right gaps and sample boundaries marked censored (no survival adjustment).1/5-day persistence is uninterrupted same-state across next1/5 contiguous observed sessions; denominator excludes unavailable future horizons. This future-looking diagnostic never enters signals. C entry/exit turnover share is turnover on the transitioning names on the event date, not a causal estimate of all delayed EWMA or replacement turnover.

Short replacement memberships are official Q1+Q2; Q1 and Q2 membership also classified separately. REMOVED=base short only, ADDED=candidate short only, UNCHANGED=both. Exact ΔShortgross=−old removed signed P/L+new added signed P/L+unchanged weight difference. Cost effect=old Short cost−new Short cost includes every row, including exits; ΔShortnet=ΔShortgross+cost effect. C original-Short all/removed/retained cohorts and subsequent residual targets saved. Raw C veto does not guarantee immediate portfolio exit after EWMA/global reranking. Replacement effects cannot be uniquely attributed to C because transform order differs.

Rank autocorrelation uses adjacent-date average percentile ranks. Quintile retention uses official Code ties; tail spells use original full contiguous Q1/Q5 lengths. Long protection saves gross/net/turnover and membership Jaccard/base retention. Sector concentration uses side-normalized Short weights and Q1/Q2 name shares, daily HHI/max, side contributions and top2 selected by totalgross/Shortgross/Shortexposure; signed contribution shares may exceed100% with offsetting losses. No reranking/exclusion/filter derives from diagnostics.

## Saved evidence

metrics/overall_metrics.csv,fold_metrics.csv,year_metrics.csv,incremental.csv,long_short.csv,quintiles.csv,bootstrap.{json,csv},candidate_decision.json,side_cost_decomposition.csv; state_attribution*.csv,state_transitions*.csv,state_duration_persistence.csv,state_spells.csv,C_state_duration_distribution.csv; daily_* accounts,rank_persistence*.csv,holding_spells.csv,rank_change*.csv,state_triggered_turnover*.csv; replacement_summary.csv,replacement_daily.csv,replacement_sector_distribution.csv,removed_added_unchanged_names.parquet,C_veto_short_cohorts.csv,C_original_short_names.parquet,short_replacement_decomposition*.csv; long_protection*.csv; sector_exposure_daily.csv,sector_concentration*.csv,sector_contribution.csv,top2_sector_contribution.csv; coverage.csv.

audit/ includes source scan, full raw/context/state/veto/EWMA/final/control bitwise prefix/truncation audit at3 cutoffs, raw/common/control parity, prior artifact/hash preservation, firewall denials and pre-target prediction reads, exact index/finite coverage, standalone research/adapter parity, official weight/net parity, purge, mechanism reconciliation and runtime resources. All four input sources individually/jointly mutated, future-only stocks, sector changes and source-row deletions; shuffle/rebuild exact. No target influences feature construction; no training path exists.

Runtime firewall is a best-effort Python guard. Exercised mutations provide evidence, not a proof for every possible input. Dataset survivorship, independent OOS, borrow costs and later deployment/zip execution remain outside this research. Neutralization does not remedy raw availability. Technical failures, if any, stay in artifacts; no additional candidate after results.

Initial research run completed2/2 trials and all scientific audits, then failed copying its generated diagnostic parquet because explicit artifact allowlisting was missing. Failed run unchanged. This report was recovered in `artifacts/DM-20261002-08/run-20261002T071247Z` using hash-checked saved metrics/predictions/audits only:0 new performance trials, no inference/backtest/bootstrap rerun. Float CSV round_trip reload preserves saved values. Allowlist fix changes artifact publication only.
