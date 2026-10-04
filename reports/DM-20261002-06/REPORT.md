# DM-20261002-06 — PIT peer Momentum component identification

**結論: 固定3候補を全てREJECTし、このexperimentを終了する。Combinationの次実験条件を通過した候補はない。**

2011–2015と2016部分年の同一1,275営業日・576,535銘柄日で評価した。Sector17/Sector33/Relative33のGross SRは0.490/0.583/0.523、Net SRは−0.544/−0.357/−0.643。既存MOM60はGross0.613/Net0.308。Mean RankICは各0.00409/0.00576/0.00463と正だがHAC5 tは1.05/1.42/1.44に留まり、独立した強い予測力を示す証拠としては弱い。有限raw componentだけのRankIC診断も0.00395/0.00480/0.00473、t1.01/1.16/1.41で結論を強めない。

Sector17はfull-year gross正が4/5、Sector33/Relative33は5/5で、ex2016 Grossも正。しかしNet正のfull-yearは2/5、1/5、0/5で、ex2016 Net SRも−0.568/−0.390/−0.661。2016部分年を除いても不採用理由は残る。対MOM60のΔNet SR bootstrap95%区間は順に[−1.524,−0.260]、[−1.317,−0.100]、[−1.320,−0.629]。どれも区間全体が負であり、点推定だけの僅差ではない。ただし既知Train上の区間で、未使用OOSではない。

**Shortと中心仮説。** 年率Short gross/netはSector17−2.448%/−4.627%、Sector33−1.701%/−3.761%、Relative33−3.288%/−5.320%。MOM60は−2.233%/−3.026%。Sector33はgross損失を0.533pp減らす一方、netは0.735pp悪化し、業種情報による実用的Short改善とは解釈しない。Sector33 score<0かつ実際にShortされたポジションの年率gross寄与は−1.380%、net−2.469%、Gross/Net SR−0.310/−0.555で、負のsector群のShort gross alphaは今回確認できない（short_sector_sign.csv）。符号は公式full portfolioの元ポジションへ帰属させたもので、filterや別戦略を作っていない。

Agreement33のD（個社/業種とも負）forward target日次等ウェイト平均は−0.20bp、C（個社負・業種正）は+2.93bp。DはCより全6年で低く、中心仮説に沿う記述的差はある。一方ex2016ではDも+0.08bp、C+2.69bpで、Dの負のpooled平均には2016部分年が影響する。Dの平均自体が負のfull-yearは2012/2015の2/5のみ。MOM60 Short bookにおけるDの年率gross寄与は−0.643%、C−1.698%; Sector33 bookでもD−0.545%。平均targetの相対差を、安定した実際のShort収益と同一視しない。DのみをShortするstrategyは評価していない。

**Coverageと回転率。** raw finite coverageはSector17 97.980%、Sector33 94.018%、Relative33 92.886%。33系は95%gateを不通過。PIT分類は評価行の100%に存在し、Sector33の欠損34,489行はminimum5 peers不足。Relativeはさらにown history不足6,523行。Adapterは全Train809,636行をneutral0で100%出力するが、これをraw coverage合格とは呼ばない。最低peer数は変更しない。

日次turnoverは0.17459/0.16764/0.16052、MOM60 0.06342。年率costは4.373%/4.196%/4.045%、MOM60 1.598%。日次rank自己相関は0.9680/0.9714/0.9743（MOM60 0.9966）、quintile retention79.98%/80.64%/81.43%（92.40%）、平均tail spell9.34/9.96/9.97営業日（24.79）。候補は平滑化なし、controlは固定EWMA(.25)なので、turnover差全体をsector aggregationの効果とは帰属できない。P/Lを計算しないraw StockMom rank自己相関診断は0.9775で、今回のsector raw rankが個社raw rankより安定という仮説も支持しない。結果後にEWMAやstate persistenceを追加しない。

**成分の識別と階層。** StockとSector17/33のpooled Pearsonは0.366/0.380、日次平均0.287/0.298で、単なる個社Momentumの複製ではない。Sector17–33はpooled0.912/日次0.878と強い共通性がある。Relative17–Sector17は−0.072、Relative33–Sector33は−0.107。Stock=Sector33+Relative33の最大誤差は1.11e−16。33−17の標準偏差は0.02482で、industry-within-sector差は存在するが、直交分解や回帰factorと呼ばない。LOOの式はsector mean+(sector mean−own)/(n−1)であり、業種内でown Momentumへの負の係数が生じる。業種日内demeanしたStock対Sector33のpooled相関は−0.797。この機械的関係も保存し、業種共通alphaを個社順位の反転と混同しない。市場成分は各観測のbeta×TOPIXを控除済みで、beta-neutral residualの業種/個社成分を研究している。

**Breadth。** SectorMomとLOO breadthのpooled相関は17=0.889、33=0.877。33のhigh+broad参加bucketはmean SectorMom0.06055、breadth71.4%、forward target+3.75bp; high+narrowは0.01864、43.8%、+3.01bp; low+broad weaknessは−0.04912、31.3%、+0.96bp。後者でもtarget平均は負ではなく、breadthがShort問題を解消すると結論しない。17のhigh+narrow targetは+6.50bpとhigh+broadの+3.58bpを上回り、単純に参加率が高いほど良いとは読めない。業種別の日次breadth/count/common meanをsector_breadth_daily.csvに保存。診断条件をstrategy候補へ昇格しない。

**業種集中。** Sector17 candidateのSector17 Long最大weightの平均は32.11%、日次最大44.44%; Short29.18%/42.70%。Sector33 candidateのSector33 Long22.83%/35.61%、Short23.58%/36.09%（side全体に対する正規化weight）。Sector17候補の17分類gross寄与上位2業種（code10/14）は合計+2.088ppでpooled gross+2.069ppの100.9%; Sector33候補の17分類上位2業種も87.1%、33分類上位2業種は62.6%。広い全業種に均等なalphaとは言えず、集中は大きい。1業種ずつ除去したLOSOでは17/33どちらの分類でも全候補のgrossは正で残ったが、Netはすべて負。Sector33候補の33分類LOSO年率gross範囲+1.690%〜+2.994%、net−2.329%〜−0.975%。特定1業種だけで全grossを作っているわけではないが、上位2業種依存は残る。事後sector exclusionは作らない。

研究runは約43.1秒、peak RSS1.60GiB。独立top-level Train adapter defaultの809,636行parity smokeは約0.987秒（メモリ値は研究プロセス全体で測定）。全199 tests、新規12 tests、既存Freeze129ファイルhash、新規metadata、18の全feature/score bitwise future-mutation/truncationケース、row shuffle/決定性、研究adapter parityと公式会計照合はPASS。make checkのみ既存DM-20261002-04のunknown experiment kindで停止し、当該既存metadataは変更していない。Saved-result追加診断は0追加trial/0feature rebuildで、初回のCSV日付header不一致を修正したreport-only再実行を保存。科学runの結果・設定・コードhashは変更していない。

Three fixed candidates completed; Train-only known development evidence, not independent OOS. No Valid, Freeze or external submission.

Run `artifacts/DM-20261002-06/run-20261002T053435Z`. Fixed60-observation residual sum, skip-one observation, raw pre-rank StockMom signs; equal-weight LOO peers,17 minimum10 /33 minimum5, exact PIT join. Candidate components have no smoothing; unchanged MOM60 control is centered rank+EWMA(.25). This comparison identifies components and their fixed operationalizations, and does not isolate only the aggregation transformation.

## Overall matched2011–2016 partial

| strategy | rankic | rankic_t_hac5 | gross_sharpe | net_sharpe | annual_gross | annual_net | turnover | annual_cost | annual_short_gross | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SECTOR17_MOM | 0.004094 | 1.051217 | 0.489696 | -0.544274 | 0.020694 | -0.023040 | 0.174591 | 0.043733 | -0.024481 | -0.046275 |
| SECTOR33_MOM | 0.005759 | 1.422771 | 0.582642 | -0.356695 | 0.026015 | -0.015943 | 0.167637 | 0.041958 | -0.017006 | -0.037610 |
| RELATIVE33_MOM | 0.004630 | 1.435734 | 0.523180 | -0.642765 | 0.018148 | -0.022298 | 0.160517 | 0.040447 | -0.032877 | -0.053199 |
| MOM60 | 0.007590 | 1.567643 | 0.613360 | 0.308092 | 0.032108 | 0.016128 | 0.063418 | 0.015981 | -0.022335 | -0.030263 |

Decimal P/L; annual arithmetic mean×252, sample-SD Sharpe×sqrt252, HAC/Bartlett lag5, compound maximum DD. Both side Gross/Net Sharpe and all required Q1–Q5/hit/DD metrics are in metrics.csv. period_* fields are actual period sums; annual_* are annualized, including2016 partial. Official5-quintile weights includeQ2/Q4 and Code tie order. Full daily accounting precedes last2-date fold purge, retaining prior holdings.

## Full-year folds and2016 partial

| strategy | scope | rankic | gross_sharpe | net_sharpe | annual_gross | annual_net | annual_short_gross | annual_short_net | turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SECTOR17_MOM | 2011 | -0.001204 | 0.323399 | -0.651654 | 0.015354 | -0.031032 | -0.049757 | -0.073000 | 0.185105 |
| SECTOR17_MOM | 2012 | -0.003866 | -0.260950 | -1.593140 | -0.009560 | -0.058593 | -0.011762 | -0.036671 | 0.195586 |
| SECTOR17_MOM | 2013 | 0.011889 | 0.873356 | 0.063446 | 0.040824 | 0.002964 | -0.013831 | -0.032852 | 0.152057 |
| SECTOR17_MOM | 2014 | 0.000759 | 0.243803 | -1.658585 | 0.005785 | -0.039431 | -0.029885 | -0.052493 | 0.180003 |
| SECTOR17_MOM | 2015 | 0.011770 | 1.064237 | 0.210717 | 0.048873 | 0.009691 | -0.015756 | -0.034225 | 0.156220 |
| SECTOR17_MOM | 2016 | 0.009200 | 0.504754 | -0.256850 | 0.031488 | -0.016005 | -0.030892 | -0.055445 | 0.189720 |
| SECTOR33_MOM | 2011 | 0.002363 | 0.324798 | -0.552367 | 0.016284 | -0.027748 | -0.046218 | -0.067751 | 0.176005 |
| SECTOR33_MOM | 2012 | -0.001558 | 0.035528 | -1.144829 | 0.001387 | -0.044844 | -0.000705 | -0.022626 | 0.184377 |
| SECTOR33_MOM | 2013 | 0.010939 | 0.640503 | -0.056427 | 0.033689 | -0.002971 | -0.007033 | -0.025442 | 0.147356 |
| SECTOR33_MOM | 2014 | 0.004002 | 0.854924 | -1.036362 | 0.019396 | -0.023471 | -0.018355 | -0.039530 | 0.170865 |
| SECTOR33_MOM | 2015 | 0.011757 | 1.140709 | 0.311042 | 0.053200 | 0.014522 | -0.010178 | -0.029845 | 0.154218 |
| SECTOR33_MOM | 2016 | 0.011529 | 0.823468 | 0.088723 | 0.052821 | 0.005668 | -0.028212 | -0.050035 | 0.188703 |
| RELATIVE33_MOM | 2011 | -0.002468 | 0.001136 | -1.192376 | 0.000040 | -0.042441 | -0.064064 | -0.085353 | 0.168649 |
| RELATIVE33_MOM | 2012 | 0.012377 | 1.156399 | -0.195585 | 0.035217 | -0.005957 | 0.014438 | -0.006172 | 0.163391 |
| RELATIVE33_MOM | 2013 | 0.001638 | 0.353694 | -0.667543 | 0.014388 | -0.027169 | -0.029376 | -0.050195 | 0.164908 |
| RELATIVE33_MOM | 2014 | 0.009462 | 1.396945 | -0.092652 | 0.035285 | -0.002339 | -0.020830 | -0.039646 | 0.149299 |
| RELATIVE33_MOM | 2015 | 0.002017 | 0.079569 | -0.947061 | 0.003031 | -0.036084 | -0.051618 | -0.071522 | 0.155217 |
| RELATIVE33_MOM | 2016 | 0.004782 | 0.715003 | -0.316679 | 0.028767 | -0.012738 | -0.088664 | -0.109643 | 0.164704 |
| MOM60 | 2011 | 0.005071 | 0.789398 | 0.506792 | 0.046155 | 0.029635 | -0.037842 | -0.045983 | 0.065571 |
| MOM60 | 2012 | 0.011737 | 1.026104 | 0.636144 | 0.043206 | 0.026788 | 0.021781 | 0.013708 | 0.065148 |
| MOM60 | 2013 | 0.005413 | 0.340451 | 0.081809 | 0.021016 | 0.005051 | -0.025160 | -0.033088 | 0.063355 |
| MOM60 | 2014 | 0.009638 | 1.414193 | 0.910504 | 0.042759 | 0.027522 | -0.015208 | -0.022952 | 0.060468 |
| MOM60 | 2015 | 0.005213 | 0.170703 | -0.099053 | 0.009896 | -0.005742 | -0.043947 | -0.051626 | 0.062057 |
| MOM60 | 2016 | 0.010987 | 0.305757 | 0.067276 | 0.021093 | 0.004639 | -0.071359 | -0.079579 | 0.065295 |

## Fixed gates and decision

```json
{
  "SECTOR17_MOM": {
    "decision": "REJECT",
    "feasibility": {
      "pooled_rankic_positive": true,
      "pooled_grossSR_positive": true,
      "ex2016_grossSR_positive": true,
      "positive_full_year_gross_3of5": true,
      "raw_finite_coverage_95pct": true,
      "turnover_le_MOM60": false
    },
    "short_gate": {
      "short_gross_positive": false,
      "short_gross_ge_MOM60": false,
      "short_net_ge_MOM60": false
    },
    "next_stage": {
      "pooled_netSR_positive": false,
      "ex2016_netSR_positive": false,
      "pooled_netSR_beats_MOM60": false,
      "netSR_improvement_4of5": false,
      "bootstrap_lower_positive": false,
      "quintile_monotonicity_positive": true
    },
    "failed_checks": [
      "turnover_le_MOM60",
      "short_gross_positive",
      "short_gross_ge_MOM60",
      "short_net_ge_MOM60",
      "pooled_netSR_positive",
      "ex2016_netSR_positive",
      "pooled_netSR_beats_MOM60",
      "netSR_improvement_4of5",
      "bootstrap_lower_positive"
    ],
    "no_release_adoption": true
  },
  "SECTOR33_MOM": {
    "decision": "REJECT",
    "feasibility": {
      "pooled_rankic_positive": true,
      "pooled_grossSR_positive": true,
      "ex2016_grossSR_positive": true,
      "positive_full_year_gross_3of5": true,
      "raw_finite_coverage_95pct": false,
      "turnover_le_MOM60": false
    },
    "short_gate": {
      "short_gross_positive": false,
      "short_gross_ge_MOM60": true,
      "short_net_ge_MOM60": false
    },
    "next_stage": {
      "pooled_netSR_positive": false,
      "ex2016_netSR_positive": false,
      "pooled_netSR_beats_MOM60": false,
      "netSR_improvement_4of5": false,
      "bootstrap_lower_positive": false,
      "quintile_monotonicity_positive": true
    },
    "failed_checks": [
      "raw_finite_coverage_95pct",
      "turnover_le_MOM60",
      "short_gross_positive",
      "short_net_ge_MOM60",
      "pooled_netSR_positive",
      "ex2016_netSR_positive",
      "pooled_netSR_beats_MOM60",
      "netSR_improvement_4of5",
      "bootstrap_lower_positive"
    ],
    "no_release_adoption": true
  },
  "RELATIVE33_MOM": {
    "decision": "REJECT",
    "feasibility": {
      "pooled_rankic_positive": true,
      "pooled_grossSR_positive": true,
      "ex2016_grossSR_positive": true,
      "positive_full_year_gross_3of5": true,
      "raw_finite_coverage_95pct": false,
      "turnover_le_MOM60": false
    },
    "short_gate": {
      "short_gross_positive": false,
      "short_gross_ge_MOM60": false,
      "short_net_ge_MOM60": false
    },
    "next_stage": {
      "pooled_netSR_positive": false,
      "ex2016_netSR_positive": false,
      "pooled_netSR_beats_MOM60": false,
      "netSR_improvement_4of5": false,
      "bootstrap_lower_positive": false,
      "quintile_monotonicity_positive": true
    },
    "failed_checks": [
      "raw_finite_coverage_95pct",
      "turnover_le_MOM60",
      "short_gross_positive",
      "short_gross_ge_MOM60",
      "short_net_ge_MOM60",
      "pooled_netSR_positive",
      "ex2016_netSR_positive",
      "pooled_netSR_beats_MOM60",
      "netSR_improvement_4of5",
      "bootstrap_lower_positive"
    ],
    "no_release_adoption": true
  }
}
```

Feasibility, Short-improvement claim and next-experiment eligibility are distinct. Failure is retained as rejection of this fixed candidate, not a theorem about industry information. No diagnostics create filters, exclusions, sign flips, smoothing or new candidates.

## Paired20-session bootstrap ΔNet Sharpe vs MOM60

```json
{
  "SECTOR17_MOM": {
    "low": -1.5243641452281997,
    "high": -0.2604783066315203,
    "bootstrap_positive_fraction": 0.001,
    "reps": 2000,
    "block": 20,
    "seed": 20261002
  },
  "SECTOR33_MOM": {
    "low": -1.31712761079651,
    "high": -0.10048530180292847,
    "bootstrap_positive_fraction": 0.008,
    "reps": 2000,
    "block": 20,
    "seed": 20261002
  },
  "RELATIVE33_MOM": {
    "low": -1.3198264648204148,
    "high": -0.6286288177549977,
    "bootstrap_positive_fraction": 0.0,
    "reps": 2000,
    "block": 20,
    "seed": 20261002
  }
}
```

2000 paired circular moving-block draws, seed20261002, percentile95% intervals. Concatenated eligible signal dates skip purged gaps; intervals are known-Train sampling variation and are not independent OOS or multiplicity-adjusted evidence.

## Mechanism and robustness

Agreement A(++),B(+-),C(-+),D(--) uses raw StockMom/peer signs. agreement.csv contains equal-date forward residual target means, Stock/sector within-bucket RankIC/HAC5 and official fixed Short-book contributions for every candidate/control, pooled/year. Equal-short target mean is descriptive only; no filtered portfolio is evaluated. Short net bucket attribution includes turnover costs on bucket rows, and must not be interpreted as the cost of a standalone bucket trading rule.

Breadth is finite positive OTHER peers / finite peers. HIGH/LOW uses same-date equal-sector median of group StockMom means; broad-positive breadth>=.5, broad-weakness<.5. breadth.csv summarizes pre-fixed descriptive participation categories, while sector_breadth_daily.csv saves group-level common mean/count/positive breadth and target. Correlation files contain the requested5 pairs, daily Pearson/Spearman, pooled raw and same-date-demeaned Pearson, plus full matrix.

StockMom=Sector33Mom+Rel33Mom holds up to recorded floating subtraction error. Sector33−Sector17 is a descriptive industry-within-sector component, not an orthogonal factor. Importantly, LOO sector score equals group mean+(group mean−own)/(n−1): within a fixed sector it carries a mechanically NEGATIVE own-StockMom ordering. Exact PIT33→17 mapping and within-date/sector correlation are recorded in hierarchy files; this can affect within-sector quintile ordering even when the common component varies little.

Sector17/33 Q1/Q5 distributions, Long/Short normalized exposures, daily HHI/max concentration and gross/net/cost contributions are saved. LOSO subtracts one sector's original portfolio contribution and attributed costs without reranking/renormalization. Its Sharpe is descriptive; lower gross exposure after subtraction limits comparability. No good/bad sector selection results. rank_persistence.csv/daily and holding_spells.csv retain rank autocorrelation, quintile retention and complete tail spells intersecting evaluation (right-censored marked). This is quintile holding, not a trading-order holding time.

## Coverage and causal audit

Full-feature/score bitwise mutation/truncation at3 cutoffs, all4 sources individually/jointly, suffix membership/new stocks/sector/return changes; row shuffle/deterministic rebuild, exact index, raw finite coverage vs100% neutral adapter coverage, research/adapter parity and standalone top-level Train smoke passed. Source scan covers new builder/adapter plus unchanged control primitives. Runtime firewall rejects Valid/raw-target/unknown parquet paths; prediction is audited before any Train label read. Audit records limitations: Python-level guard is best-effort, tests are evidence on exercised cases rather than a mathematical proof.

Missing-target rows remain in ranking; official scorer omits their cost, so all-position conservative cost/net are separate columns. Short residual P/L is signed target contribution, not a raw short-security return or borrow-cost estimate. Universe is the supplied498-stock dataset, not a reconstructed historical all-exchange universe: only date-present rows with PIT classifications enter peers, but provider universe survivorship cannot be independently removed here. Real Valid/zip/late-split runtime is untested by design.

Artifacts: metrics.csv, fold_metrics.csv/year_metrics.csv, incremental.csv, long_short.csv, quintiles.csv, bootstrap.json/csv, daily_*.csv, agreement*.csv, breadth.csv, sector_exposure_daily.csv, sector_concentration.csv, sector_contribution.csv, leave_one_sector_out.csv, correlation*.csv, hierarchy.json/mapping.csv, rank_persistence*.csv, holding_spells.csv, coverage.csv, audit/*.json. Full features/scores, code snapshots/data/environment hashes and resource measurements are stored in the run.
