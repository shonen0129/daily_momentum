# DM-20261002-09 — Transform-order matched Sector C-veto

## 結論と主比較の解釈

固定2試行を完了し、**RAW_EWMA_SHORT_VETOはREJECT**。主評価2011–2015のNet SharpeはRAW control 0.319879 → Veto 0.434558、Δ+0.114679。Gross Sharpe Δ+0.115309、年率Net P/L Δ+0.6069pp。改善はraw→EWMAを揃えても点推定として残る。しかし改善年は2013/2014/2015の3/5、2011/2012は悪化し、主比較paired bootstrap95% CI [-0.024014, +0.252484]は0を跨ぐ。4/5安定性・CI下限>0の事前条件を満たさないため、次段階への昇格条件は不通過。

RAW control対MOM60の主評価ΔNet SRは-0.004469で小さく負、Veto対MOM60は+0.110210。したがって前回の改善がraw→EWMAへの変更のみで生じた、という説明とは今回の点推定は整合しない。一方、Sector contextに安定した独立予測価値があるとの結論にも進めない。識別範囲はraw→EWMA内の固定C-veto（既存missingness policy込み）の運用上の増分であり、MOM60順位化pipelineや一般的Sector効果へ一般化しない。Sharpe差の足し算は算術的整合でありalphaの因果寄与率ではない。

2016partialを含むpooled ΔNet SRは+0.130488、95% CI [+0.001577, +0.269059]。この正の下限は2011–2015主評価の未達を置き換えない。2016partialも改善するがstability countには入れない。

## Short mechanism / replacement

主評価 ΔShort Net=+0.3694pp = ΔShort Gross +0.4002pp + Cost Effect -0.0308pp。Gross寄与率108.34%で、Short costは増加している。gross-loss reductionでありcost savingsではない。Short net自体はcontrol -2.8320%、Veto -2.4626%と依然負。

Short Q1+Q2のREMOVED/ADDEDは各28,186銘柄日、UNCHANGED 191,565。Gross差は旧Short損失回避+0.3316pp + replacement Short -0.1133pp + unchanged weight差+0.1819pp。Added Short自体のtarget meanは+0.963bpでsigned grossは負、Removedは+2.160bp。改善はreplacement自体の収益化ではなく、旧損失回避と残留銘柄のweight変化。各群net/exit-only OTHER cost/StockMom・Common分布/33分布は保存し、全Short差へ照合済み。

RAW controlでShortだったCは86,906銘柄日、removed 21,240、retained 65,666（75.56%残留）。Removed target平均+2.893bp、retained +4.041bp。Raw Cを0にしてもEWMAの負の過去stateが徐々に減衰し、全体順位でShortが続く。C cohort平均absolute Short weightはcontrol 0.002689→Veto 0.001765。C all/removed/retainedのannual gross/net・average weights・業種分布を保存。

State attributionのC Short grossは-1.7225%→-1.1771%、Dは-0.4029%→-0.5267%と悪化。C損失縮小の一部を他stateの損失増が相殺する。A/B/C/D/ZERO_OR_MISSINGの等row/等date target,RankIC,side gross/net/turn/costを全て保存し、stateをstandalone strategyとは読まない。

## Duration / turnover / Long / concentration

C spell median 2、mean 6.611、p90 17営業日、1-day persistence 84.65%、5-day persistence 58.40%。観測gapとsample端のcensoringを保持した診断値であり、duration filterを作らない。

Total turnover 0.062475→0.063147、Long 0.031294→0.030662、Short 0.031181→0.032485。年率cost 1.5687%→1.5836%（Δ+0.0150pp）。C entry/exit namesのtotal turnover share 9.07%→14.41%、Short share 12.76%→22.50%。

ΔShort turnoverのdisjoint current-row attribution: removed C -0.003850、removed non-C +0.001871、replacement +0.000699、unchanged weight +0.001451、OTHER exit-only等 +0.001133。合計はofficial side差と一致。Raw C temporal exitとは異なる日次membership分類で、EWMA遅延の因果帰属を一意に説明するものではない。

Long gross Δ+0.2216pp、net Δ+0.2375pp。Long net 4.4780%→4.7155%、Long turnoverは低下。対RAW controlのLong membership overlap 96.12%、Jaccard 92.55%。主評価Long損失と引き換えのShort改善ではないが、2014 Long netは僅かに低下。

Short33集中は上昇: mean HHI 0.06769→0.08214、mean最大sector share 14.13%→16.57%、日次最大 27.27%→30.25%。期間平均exposure上位2業種(3650,3200)share 22.15%→22.52%。日次exposure/Q1/Q2 distribution/sector signed contributionを保存し、sector exclusionはしない。

## Coverage / matched-row診断

主評価548,687銘柄日。Stock raw coverage 98.807%、Common 95.070%、C evaluable joint coverage 93.944%。RAW controlのraw requirementはStockのみ、Vetoはjoint context。両方のfinite出力809,636/809,636行をraw100%とは呼ばない。Year/33別coverageはcoverage.csv。今回95%coverageを新しいadoption gateには追加していない。

両scoreを同一515,459joint-finite rowsで比較すると、日次平均RankIC 0.007352→0.007517（HAC5 t 1.495→1.500）。Matched diagnostic Q5−Q1 3.095→4.037bp/day。公式full-book Short gross差のmatched寄与+0.4054pp、unavailable寄与-0.0052pp; Net全体差のmatched寄与+0.4875pp、unavailable+0.1194pp。Matched/unavailable contributionsはfull official resultへ一致。Subset ranksは診断だけで別portfolio P/Lを作らない。現時点の同一row分析でも過去のcontext欠損がEWMAに残るため、missingness影響の完全除去ではない。

## 検証・制約

全235 tests（新規12）、全Train入力27 prefixケース/3cutoff（各source・joint・truncation・future stocks・future sectors・suffix deletion）、row shuffle/決定性、exact index/finite出力、research/adapter一致、raw/common/MOM60/source primitive一致、公式weights/Net P/L bitwise一致、mechanism/side/state/sector/matched/turnover reconciliation PASS。今回Veto予測は08保存予測とも809,636行bitwise一致。RAW adapterはSectorを読まず3 Train sourcesのみ。

研究run 104.23秒、peak RSS 2.092GiB。独立no-arg adapterは約3.95秒（同一subprocessでdefaultと2候補を連続実行）。Train-only firewallがValid/raw targetを拒否。既存Freeze129hashと新experiment構成はPASS。make checkのみ既存DM-20261002-04 unknown experiment kindで停止し、該当metadataは変更していない。計画/config、過去06/07/08の証拠・REJECT、完成runを保持。追加performance trials0。REJECTのためRANK_PIPELINE_SHORT_VETOを提案・実装せず、当experimentを終了する。


Decision: RAW_EWMA_SHORT_VETO = REJECT; RAW control is diagnostic only.

Run `artifacts/DM-20261002-09/run-20261002T074832Z`. Exactly2 fixed trials; known Train development evidence. Prior06/07/08 REJECT decisions and artifacts preserved. No Historical Valid, Freeze or external submission.

## Primary 2011–2015 (EX2016)

| strategy | gross_sharpe | net_sharpe | annual_net | annual_short_gross | annual_short_net | annual_long_net | turnover | annual_cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RAW_EWMA_CONTROL | 0.624801 | 0.319879 | 0.016460 | -0.020519 | -0.028320 | 0.044780 | 0.062475 | 0.015687 |
| RAW_EWMA_SHORT_VETO | 0.740110 | 0.434558 | 0.022529 | -0.016516 | -0.024626 | 0.047155 | 0.063147 | 0.015836 |
| MOM60 | 0.634564 | 0.324348 | 0.016685 | -0.019956 | -0.027870 | 0.044555 | 0.063327 | 0.015958 |

## Primary VETO minus RAW_EWMA_CONTROL

| scope | delta_net_sharpe | delta_gross_sharpe | delta_annual_short_gross | delta_annual_short_net | short_cost_effect | delta_turnover | delta_annual_cost | delta_annual_long_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EX2016 | 0.114679 | 0.115309 | 0.004002 | 0.003694 | -0.000308 | 0.000673 | 0.000150 | 0.002375 |

## Pooled continuity including 2016 partial

| strategy | gross_sharpe | net_sharpe | annual_net | annual_short_gross | annual_short_net | annual_long_net | turnover | annual_cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RAW_EWMA_CONTROL | 0.617825 | 0.317806 | 0.016640 | -0.022393 | -0.030203 | 0.046843 | 0.062588 | 0.015707 |
| RAW_EWMA_SHORT_VETO | 0.750408 | 0.448294 | 0.023515 | -0.017536 | -0.025641 | 0.049156 | 0.063163 | 0.015844 |
| MOM60 | 0.613360 | 0.308092 | 0.016128 | -0.022335 | -0.030263 | 0.046391 | 0.063418 | 0.015981 |

## Year/fold results

| strategy | scope | net_sharpe | annual_net | annual_short_gross | annual_short_net | annual_long_net | turnover |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RAW_EWMA_CONTROL | 2011 | 0.528013 | 0.030839 | -0.036688 | -0.044792 | 0.075632 | 0.064618 |
| RAW_EWMA_CONTROL | 2012 | 0.572213 | 0.024066 | 0.018377 | 0.010524 | 0.013542 | 0.063646 |
| RAW_EWMA_CONTROL | 2013 | 0.047792 | 0.002949 | -0.025872 | -0.033615 | 0.036563 | 0.062485 |
| RAW_EWMA_CONTROL | 2014 | 0.883742 | 0.026733 | -0.016103 | -0.023855 | 0.050589 | 0.060335 |
| RAW_EWMA_CONTROL | 2015 | -0.041570 | -0.002418 | -0.042861 | -0.050415 | 0.047997 | 0.061260 |
| RAW_EWMA_CONTROL | 2016 | 0.295284 | 0.020356 | -0.061035 | -0.069013 | 0.089369 | 0.064936 |
| RAW_EWMA_SHORT_VETO | 2011 | 0.472659 | 0.027256 | -0.041106 | -0.049324 | 0.076580 | 0.064795 |
| RAW_EWMA_SHORT_VETO | 2012 | 0.561169 | 0.023781 | 0.017296 | 0.008470 | 0.015311 | 0.067186 |
| RAW_EWMA_SHORT_VETO | 2013 | 0.333779 | 0.021089 | -0.013926 | -0.021689 | 0.042778 | 0.061508 |
| RAW_EWMA_SHORT_VETO | 2014 | 0.944042 | 0.028731 | -0.013760 | -0.021802 | 0.050533 | 0.060857 |
| RAW_EWMA_SHORT_VETO | 2015 | 0.200091 | 0.011752 | -0.031553 | -0.039241 | 0.050993 | 0.061322 |
| RAW_EWMA_SHORT_VETO | 2016 | 0.681933 | 0.043844 | -0.038556 | -0.046564 | 0.090408 | 0.063499 |
| MOM60 | 2011 | 0.506792 | 0.029635 | -0.037842 | -0.045983 | 0.075618 | 0.065571 |
| MOM60 | 2012 | 0.636144 | 0.026788 | 0.021781 | 0.013708 | 0.013081 | 0.065148 |
| MOM60 | 2013 | 0.081809 | 0.005051 | -0.025160 | -0.033088 | 0.038139 | 0.063355 |
| MOM60 | 2014 | 0.910504 | 0.027522 | -0.015208 | -0.022952 | 0.050474 | 0.060468 |
| MOM60 | 2015 | -0.099053 | -0.005742 | -0.043947 | -0.051626 | 0.045884 | 0.062057 |
| MOM60 | 2016 | 0.067276 | 0.004639 | -0.071359 | -0.079579 | 0.084217 | 0.065295 |

## Fixed gates

```json
{
  "RAW_EWMA_CONTROL": {
    "decision": "DIAGNOSTIC_NEGATIVE_CONTROL",
    "failed_checks": []
  },
  "RAW_EWMA_SHORT_VETO": {
    "decision": "REJECT",
    "checks": {
      "pooled_NetSR_beats_RAW": true,
      "ex2016_NetSR_beats_RAW": true,
      "primary_annualNet_beats_RAW": true,
      "primary_Shortgross_ge_RAW": true,
      "primary_Shortnet_ge_RAW": true,
      "primary_turnover_le1p25_RAW": true,
      "primary_Longnet_positive": true,
      "primary_Qmonotonicity_positive": true,
      "NetSR_improvements_4of5": false,
      "primary_bootstrap_lower_gt0": false,
      "primary_deltaShortnet_positive": true,
      "primary_gross_improvement_share_ge50pct": true
    },
    "failed_checks": [
      "NetSR_improvements_4of5",
      "primary_bootstrap_lower_gt0"
    ],
    "full_year_netSR_improvements": 3,
    "primary_delta_short_gross": 0.004002212360048992,
    "primary_delta_short_net": 0.003694142433841918,
    "primary_short_cost_effect": -0.00030806992620707394,
    "primary_gross_share_of_short_net_improvement": 1.0833941656891342,
    "control_raw_coverage": 0.98807152347331,
    "veto_raw_context_coverage": 0.9394408834180508,
    "coverage_gate": false
  }
}
```

## Paired circular moving-block bootstrap

```json
{
  "EX2016:RAW_EWMA_SHORT_VETO-RAW_EWMA_CONTROL": {
    "low": -0.02401354826070999,
    "high": 0.25248421102823065,
    "bootstrap_positive_fraction": 0.95,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "point_delta": 0.1146789112940651,
    "days": 1216,
    "primary": true
  },
  "EX2016:RAW_EWMA_CONTROL-MOM60": {
    "low": -0.041592631952106086,
    "high": 0.032845410287666764,
    "bootstrap_positive_fraction": 0.4245,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "point_delta": -0.004469146445675254,
    "days": 1216,
    "primary": false
  },
  "EX2016:RAW_EWMA_SHORT_VETO-MOM60": {
    "low": -0.030191450396311846,
    "high": 0.2549556799701393,
    "bootstrap_positive_fraction": 0.934,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "point_delta": 0.11020976484838985,
    "days": 1216,
    "primary": false
  },
  "POOLED:RAW_EWMA_SHORT_VETO-RAW_EWMA_CONTROL": {
    "low": 0.0015765678935835605,
    "high": 0.26905900026743823,
    "bootstrap_positive_fraction": 0.9755,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "point_delta": 0.13048782907451273,
    "days": 1275,
    "primary": false
  },
  "POOLED:RAW_EWMA_CONTROL-MOM60": {
    "low": -0.02760348739038512,
    "high": 0.046200177057839006,
    "bootstrap_positive_fraction": 0.7145,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "point_delta": 0.00971350673438065,
    "days": 1275,
    "primary": false
  },
  "POOLED:RAW_EWMA_SHORT_VETO-MOM60": {
    "low": 0.003352035993600556,
    "high": 0.2894728973922245,
    "bootstrap_positive_fraction": 0.978,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "point_delta": 0.14020133580889338,
    "days": 1275,
    "primary": false
  }
}
```

Primary inference is VETO minus RAW control within raw->EWMA(.25). MOM60 raw->centered rank->EWMA(.25) is secondary. This does not generalize automatically to rank->EWMA MOM60, other orders or general Sector context. Raw Common self-includes own StockMom, minimum5, same-date PIT33, equal weight. Exact prior08 Veto, thresholds/partial veto/alpha/horizon/ranking unchanged. RAW control does not read Sector input. Missing Stock neutral0 in control; unavailable raw context neutral0 in Veto exactly as08. Both predict every required row; raw coverage remains separate.

Primary2011–2015, 2016partial separate, pooled for continuity. Final2 exchange sessions each fold purged with t+2 maturity checked. No fitting; expanding history from2008. Continuous full required-row official weights and accounting before date selection. Official Code ties/five quintiles,10bp one-way,mean*252 annual P/L/cost,sample-SD Sharpe,HAC5 RankIC t/hit,compound/additive DD. Actual period sums and conservative all-position cost also saved. Official missing-label cost omission retained. Short residual signed P/L excludes borrow costs.

Bootstrap paired circular20 sessions/2000reps/seed20261002,95% percentile; concatenated eligible sessions include purge gaps. Only primary EX2016 Veto-vs-RAW lower bound is adoption gate. Known Train uncertainty, no independent OOS or multiplicity correction.

Replacement compares RAW control vs Veto official Q1/Q2 Shorts (and Q1,Q2 separately). Removed old signed losses, added signed P/L and unchanged weights reconcile deltaShortgross; all row costs including OTHER exit-only rows reconcile deltaShortnet=deltaShortgross+controlShortcost-vetoShortcost. Q-cost allocation: current Q on entry/rebalance, preceding Q on exits. C all/removed/retained cohorts preserve average weights/net/sector distribution. Raw veto can retain C Short positions because EWMA state decays gradually and global ranking determines membership.

State attribution is contribution to original globally ranked books, never standalone state strategies. Equal-row and equal-date targets/RankIC saved. Contiguous observed state spells intersect evaluation with gap/boundary censor flags;1/5day persistence conditional on available contiguous future diagnostic sessions. No duration filter. C entry/exit turnover share is turnover on event-date names, not complete delayed effect. Difference turnover buckets are disjoint current-row assignment: removed C (C_STATE_EXIT),removed non-C,replacement,unchanged weights,OTHER exits. Temporal raw-C exits are distinct and saved separately.

Long protection compares against RAW control; sector exposures side-normalized Short,HHI/max/top2, Q1/Q2 name distribution and original-book signed contributions. No exclusion. Matched-row RankIC/Q1-Q5 diagnostics use identical joint-finite raw rows; subset ranks never form another strategy. Original-book contributions on matched/unavailable rows sum to official result. Current matched availability cannot erase past missingness in EWMA.

Saved metrics: primary_ablation_comparison,overall/year/fold metrics,incremental,bootstrap,long_short,quintiles,side_cost_decomposition,state_attribution,state_transitions,state_duration_persistence,state_spells,C cohorts/replacement names and distributions,short_replacement_decomposition/Net classes,turnover_difference/state_triggered_turnover,long_protection,sector concentration/exposure/top2,coverage,matched_row_diagnostics and daily accounts.

Audit: source scan, runtime Train firewall/pre-target reads, full raw/context/state/veto/EWMA/control/final prefix mutations/truncation at3 cutoffs, future stocks/future sector changes/suffix deletion,row shuffle,deterministic rebuild,exact index/finite coverage,prior08 Veto and MOM60/raw/common parity,research-adapter and standalone parity,purge,official P/L bitwise reconciliation,mechanism/turnover/matched partition within1e-15,prior evidence hashes and resource usage. Python firewall is best-effort; mutation tests are evidence on exercised cases, not proof for every input. Independent OOS/survivorship/borrow costs/actual zip deployment are outside this research.
