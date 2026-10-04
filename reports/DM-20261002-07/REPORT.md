# DM-20261002-07 — Sector33 common/within hierarchical Momentum

**結論: 次段階へ進める候補はない。HIER33_WITHINとHIER33_COMBINEDをREJECT。HIER33_SECTORはfeasibilityを通過した記述的componentのみで、単独採用はしない。**

3候補を事前登録どおり各1回評価した。主評価は2011–2015と2016部分年、同一1,275営業日・576,535銘柄日。前実験DM-20261002-06の3候補はREJECTのまま、plan/config/report/decision/codeのhashが不変。全Trainは既知研究履歴で、独立OOSではない。

**固定1:1合成の点推定は改善したが、採用条件を満たさない。** COMBINEDのGross/Net SRは0.6655/0.3783、MOM60は0.6134/0.3081。年率Netは2.073%対1.613%（+0.460pp）、日次turnover0.06287対0.06342（−0.87%）、年率cost1.573%対1.598%。ex2016 Net SRも0.3708対0.3243と僅かに改善。しかしfull-year Net SR改善は2011/2013/2015の3/5のみ（2012/2014悪化）、必要な4/5未達。paired20-session bootstrap ΔNet SR95%区間[−0.1203,+0.2436]は0を跨ぎ、下限>0未達。raw finite coverage93.890%も95%未達。3つの事前条件不通過によりREJECTする。2016部分年の改善をfull-year改善数に含めない。

CombinedのMean RankICは0.00843、HAC5 t1.658（MOM60 0.00759、t1.568）。Q1–Q5は1.441/1.837/2.287/3.197/5.098bp/dayで単調、Q monotonicity1.0。全5年でgross/net正だが、統計的・coverage・fold改善の不足は残る。最大compound DD−9.768%はMOM60−9.706%より僅かに悪い。未達条件を弱めたりweight/alpha/filterを追加したりしない。

**共通成分と業種内成分。** Sector単独はGross/Net SR0.6059/0.2117、Mean RankIC0.00605（t1.376）、year gross正5/5、net正4/5、raw coverage95.021%でfeasibility通過。ただしMOM60よりNet SR−0.0964、年率Net−0.589pp、bootstrap区間[−0.5802,+0.3457]。事前計画どおり成分診断の証拠に留め、standalone adoptionへ昇格しない。WithinはGross/Net SR0.4863/0.0478、RankIC0.00451（t1.382）、year gross正4/5、net正3/5、raw coverage93.890%でfeasibility不通過。対MOM60 bootstrap区間[−0.6099,+0.0534]も0を跨ぐ。両成分に弱い正の断面情報は見えるが、独立した安定alphaが確立したとは言わない。

**Short改善の内訳。** 年率Short gross/netはSector−1.625%/−2.515%、Within−3.475%/−4.258%、Combined−1.963%/−2.753%、MOM60−2.233%/−3.026%。Short Gross/Net Sharpeは順に−0.314/−0.486、−0.733/−0.898、−0.373/−0.523、−0.427/−0.579。CombinedのShort net改善+0.2730ppはgross改善+0.2700ppとShort cost減+0.0030ppに分解され、主に損失縮小そのもの。Long net改善+0.1868ppとは分けて照合済み。Short損益自体は依然負。WithinのShortはgross−1.242pp/net−1.232pp悪化している。

**Agreement。** 自社を含むraw Commonの符号で、D（Stock<0/Common<0）のforward target平均は−0.45bp、C（Stock<0/Common>0）は+3.31bp。ex2016でもD−0.17bp/C+3.10bp。だがDのoriginal Short book年率gross寄与はMOM60−0.405%からCombined−0.551%へ悪化。一方Cは−1.902%から−1.405%へ改善し、CombinedのShort改善は主に「個社弱・業種強」のShort損失縮小から来る。DのShort収益化ではない。自社を含むCommonなので符号診断にもpart-whole関係があり、独立peer効果の因果証明にしない。D-onlyやagreement filterは作っていない。

**順位安定性。** Sector/Within/Combinedのrank自己相関は0.9907/0.9960/0.9962、MOM60 0.9966。quintile retentionは90.93%/92.59%/92.48%対92.40%、平均tail spell21.55/25.49/25.34日対24.79日。mean absolute percentile rank changeは0.01897/0.01593/0.01607対0.01621。Within/Combinedのholding/turnover改善は小幅で、Sector turnover0.07614はMOM60より20.1%高い。前実験のunsmoothed0.16–0.17より大幅に低いが、自社inclusive aggregationとsmoothingを同時に変えた新仮説であり、各変更の寄与を単独帰属しない。Controlはrank→EWMA、候補はraw→EWMAで、同じalpha/primitiveでも変換順は異なる。

**TieとCode依存。** Sector scoreの日次unique数平均28.18、exact tied-row share99.323%。tiny deterministic perturbationでQ1/Q5 membership Jaccard0.8800/0.8763、全分位変更行比11.56%、weight L1変化0.09637。Common portfolioはsector signalと公式Code tie orderに依存する結果として解釈する。Within/Combinedはunique426.85/430.86、exact tie share5.817%/4.975%。CombinedのQ1/Q5 Jaccard0.99785/0.99998、分位変更行比0.352%。保存列tail_migration_shareは実装上「全分位変更行比」であり、tailだけの比率ではない。tail自体はJaccard列で示す。近接する非同値のadjacent score順序変更も1日約0.109件（Sector）/0.119件（Combined）記録。perturbation P/Lは計算せず、random tie-break探索もしていない。

**Common alphaとWithinの広がり。** Equal-sector cross-sector RankIC0.01575、HAC5 t1.714、hit51.69%。Low/Middle/High sector momentumのequal-sector/equal-date targetは1.00/3.29/2.81bpで完全単調ではなく、Lowも正。Within rawが利用可能な24業種のうち19業種で平均IC正だが、多くのtは2未満。HAC5 t>2の2業種もmultiple-testing調整のない記述診断で、選択ルールにしない。全33業種のoriginal Within book Short grossが正なのは6業種のみ。raw coverage不足で9業種には有効within ICがなく、全業種へ広いalphaがあるとは判断できない。業種別signal/target/dispersion、内部Q1–Q5、global bookのLong/Short寄与を全件保存した。

**集中とLOSO。** Sector Long/Shortの平均最大sector share23.15%/23.86%、日次最大35.61%/36.09%。Combinedは16.67%/17.31%、日次最大約30.9%（side gross weightに対する正規化値）。SectorのQ1/Q5最大same-sector shareの日次平均34.22%/34.09%、日次最大53.93%/53.41%でtail集中が大きい。Gross上位2 sector（6100/9050）の寄与はSector57.38%、Combined35.84%、MOM60上位2は31.57%。Combinedの1-sector LOSO年率Net範囲+1.502%〜+2.364%、Net SR0.288〜0.468で全て正。SectorもNet+0.288%〜+1.374%で残る。特定1業種だけで全成績を作っていないが、集中/tie依存は残り、除外ルールは作らない。

**Coverageと分解恒等式。** Raw common95.021%、Within/Combined93.890%。Adapterは809,636/809,636行のfinite出力を保持するが、neutral化後100%をraw gate合格とは呼ばない。Raw Stock≈Common+Withinの自然な再構成誤差max2.22e−16（科学auditの逐次減算順は0）。実データ全体の平滑化後誤差max0.6285、joint raw finite行でもpast missing stateが残るmax0.1072で、全域恒等式は成立しない。各成分の独立neutral0によるraw defectを同じEWMAで伝播すると未説明誤差max2.22e−16。これは事前定義した欠損policyの限界で、隠すための候補変更は行わない。完全履歴synthetic identityは浮動精度で成立。Raw commonは同日同業種で厳密に同値、smooth/rank/segmentソースとraw/control出力は既存primitiveに一致する。

18の全入力future-mutation/truncationケース（3cutoff）、全特徴/EWMA/zscore/control/予測のbitwise不変性、row shuffle・決定性・exact index、研究adapter一致・公式会計・runtime firewallを確認。212 tests（新規13）とFreeze129hash PASS。make checkは既存DM-20261002-04のunknown experiment kindのみ停止し、そのmetadataは変更していない。研究run約123.0秒、peakRSS1.47GiB。独立no-arg Train adapter2.226秒・peak1.04GiB・809,636行bitwise一致。Historical Valid、後続split/zip評価、Freeze、外部提出なし。

報告追記はhash照合した保存済み成果物だけから行い、追加performance trial0。報告用CSV照合の初回は通常parserの末尾bit誤差で停止したため、round_tripで保存floatを復元し、同じ1e−15許容差のままsector/Agreement/side会計一致を確認した。科学run・予測・パラメータは変更せず、失敗したreport-only試行も保存している。


All three pre-registered performance trials completed on known Train history. Prior experiment's three candidates remain REJECT. No independent OOS claim, Valid, release, Freeze or external submission.

Run `artifacts/DM-20261002-07/run-20261002T062103Z`. Self-inclusive Sector33 finite-stock mean, minimum5, and raw Within=Stock−Common; fixed60 observations/skip1. Both raw components independently neutral0 then unchanged per-Code/relisting EWMA(.25). Combined=same-date sample z(Sector EWM)+z(Within EWM), fixed1:1, no additional smoothing. MOM60 remains centered-rank-before-EWMA. Same operator/alpha does not make raw-before-EWMA equivalent to rank-before-EWMA.

## Overall2011–2016 partial, matched official accounting

| strategy | rankic | rankic_t_hac5 | gross_sharpe | net_sharpe | annual_gross | annual_net | turnover | annual_cost | annual_short_gross | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HIER33_SECTOR | 0.006052 | 1.376102 | 0.605946 | 0.211664 | 0.029288 | 0.010235 | 0.076143 | 0.019053 | -0.016250 | -0.025147 |
| HIER33_WITHIN | 0.004511 | 1.381663 | 0.486341 | 0.047753 | 0.017290 | 0.001698 | 0.061879 | 0.015592 | -0.034752 | -0.042581 |
| HIER33_COMBINED | 0.008433 | 1.657658 | 0.665512 | 0.378321 | 0.036455 | 0.020726 | 0.062867 | 0.015729 | -0.019635 | -0.027533 |
| MOM60 | 0.007590 | 1.567643 | 0.613360 | 0.308092 | 0.032108 | 0.016128 | 0.063418 | 0.015981 | -0.022335 | -0.030263 |

All P/L decimal fractions; arithmetic daily mean×252 annualized, sample-SD Sharpe×sqrt252, HAC/Bartlett lag5, compound and additive DD. period_* are actual sums, annual_* annualizations including2016 partial. Official five-quintile Code order/10bp one-way; continuous accounting before final2-date annual purge. Missing-target cost omission matches official scorer; all-position conservative net/cost recorded separately. Long/Short gross/net/Sharpe/cost and Q1–Q5/hit/DD are in metrics.csv.

## Full-year fold metrics and2016 partial

| strategy | scope | rankic | gross_sharpe | net_sharpe | annual_net | turnover | annual_short_gross | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HIER33_SECTOR | 2011 | 0.002105 | 0.415996 | 0.038197 | 0.002037 | 0.080484 | -0.043452 | -0.052876 |
| HIER33_SECTOR | 2012 | 0.001140 | 0.213541 | -0.264184 | -0.010979 | 0.079120 | 0.004241 | -0.005259 |
| HIER33_SECTOR | 2013 | 0.007454 | 0.558858 | 0.263191 | 0.015098 | 0.068139 | -0.011673 | -0.019129 |
| HIER33_SECTOR | 2014 | 0.005543 | 0.919243 | 0.125674 | 0.003155 | 0.079614 | -0.016078 | -0.024972 |
| HIER33_SECTOR | 2015 | 0.011028 | 0.902754 | 0.554952 | 0.028310 | 0.070758 | -0.013539 | -0.021906 |
| HIER33_SECTOR | 2016 | 0.018705 | 1.255864 | 0.951396 | 0.067333 | 0.086661 | -0.020322 | -0.032651 |
| HIER33_WITHIN | 2011 | 0.000494 | 0.484281 | 0.055749 | 0.002073 | 0.063212 | -0.056862 | -0.064838 |
| HIER33_WITHIN | 2012 | 0.012782 | 1.309651 | 0.798435 | 0.024373 | 0.061822 | 0.017445 | 0.009755 |
| HIER33_WITHIN | 2013 | 0.001315 | 0.284206 | -0.095358 | -0.003999 | 0.063151 | -0.029594 | -0.037586 |
| HIER33_WITHIN | 2014 | 0.006883 | 0.794851 | 0.202103 | 0.005122 | 0.059596 | -0.029295 | -0.036785 |
| HIER33_WITHIN | 2015 | 0.000804 | -0.028953 | -0.423602 | -0.016639 | 0.061514 | -0.059808 | -0.067723 |
| HIER33_WITHIN | 2016 | 0.005212 | 0.146340 | -0.240796 | -0.009756 | 0.062243 | -0.102166 | -0.110341 |
| HIER33_COMBINED | 2011 | 0.005825 | 0.834776 | 0.564021 | 0.034254 | 0.065617 | -0.034381 | -0.042680 |
| HIER33_COMBINED | 2012 | 0.008598 | 0.642356 | 0.274790 | 0.012472 | 0.066587 | 0.009209 | 0.000932 |
| HIER33_COMBINED | 2013 | 0.007651 | 0.432154 | 0.195044 | 0.012448 | 0.060731 | -0.017121 | -0.024685 |
| HIER33_COMBINED | 2014 | 0.009612 | 1.336762 | 0.841015 | 0.025860 | 0.060966 | -0.017961 | -0.025802 |
| HIER33_COMBINED | 2015 | 0.008680 | 0.488509 | 0.241283 | 0.014772 | 0.060404 | -0.032056 | -0.039580 |
| HIER33_COMBINED | 2016 | 0.015851 | 0.720216 | 0.505231 | 0.036886 | 0.062721 | -0.045432 | -0.053245 |
| MOM60 | 2011 | 0.005071 | 0.789398 | 0.506792 | 0.029635 | 0.065571 | -0.037842 | -0.045983 |
| MOM60 | 2012 | 0.011737 | 1.026104 | 0.636144 | 0.026788 | 0.065148 | 0.021781 | 0.013708 |
| MOM60 | 2013 | 0.005413 | 0.340451 | 0.081809 | 0.005051 | 0.063355 | -0.025160 | -0.033088 |
| MOM60 | 2014 | 0.009638 | 1.414193 | 0.910504 | 0.027522 | 0.060468 | -0.015208 | -0.022952 |
| MOM60 | 2015 | 0.005213 | 0.170703 | -0.099053 | -0.005742 | 0.062057 | -0.043947 | -0.051626 |
| MOM60 | 2016 | 0.010987 | 0.305757 | 0.067276 | 0.004639 | 0.065295 | -0.071359 | -0.079579 |

## Fixed feasibility and combined eligibility

```json
{
  "HIER33_SECTOR": {
    "decision": "DESCRIPTIVE_COMPONENT_ONLY",
    "feasibility": {
      "pooled_RankIC_positive": true,
      "pooled_GrossSR_positive": true,
      "ex2016_GrossSR_positive": true,
      "gross_positive_3of5": true,
      "raw_coverage_ge95pct": true,
      "turnover_le1p25_MOM60": true
    },
    "adoption": {},
    "failed_checks": [],
    "no_release_adoption": true,
    "raw_coverage": 0.9502129098840487
  },
  "HIER33_WITHIN": {
    "decision": "REJECT",
    "feasibility": {
      "pooled_RankIC_positive": true,
      "pooled_GrossSR_positive": true,
      "ex2016_GrossSR_positive": true,
      "gross_positive_3of5": true,
      "raw_coverage_ge95pct": false,
      "turnover_le1p25_MOM60": true
    },
    "adoption": {},
    "failed_checks": [
      "raw_coverage_ge95pct"
    ],
    "no_release_adoption": true,
    "raw_coverage": 0.9388987659031975
  },
  "HIER33_COMBINED": {
    "decision": "REJECT",
    "feasibility": {
      "pooled_RankIC_positive": true,
      "pooled_GrossSR_positive": true,
      "ex2016_GrossSR_positive": true,
      "gross_positive_3of5": true,
      "raw_coverage_ge95pct": false,
      "turnover_le1p25_MOM60": true
    },
    "adoption": {
      "pooled_NetSR_gt_MOM60": true,
      "ex2016_NetSR_gt_MOM60": true,
      "NetSR_improvement_4of5": false,
      "bootstrap_lower_gt0": false,
      "annual_net_gt_MOM60": true,
      "turnover_le1p25_MOM60": true,
      "Short_gross_ge_MOM60": true,
      "Short_net_ge_MOM60": true,
      "Q_monotonicity_positive": true
    },
    "failed_checks": [
      "raw_coverage_ge95pct",
      "NetSR_improvement_4of5",
      "bootstrap_lower_gt0"
    ],
    "no_release_adoption": true,
    "raw_coverage": 0.9388987659031975
  }
}
```

A/B are descriptive component identification, not selectable standalone replacements. Combined must satisfy all user-fixed feasibility/adoption criteria; failure does not trigger weights, alpha, filters, side changes or sector exclusion. Components/diagnostics remain saved regardless of gates.

## Paired circular20-session ΔNetSR bootstrap vs MOM60

```json
{
  "HIER33_SECTOR": {
    "low": -0.5801732755198173,
    "high": 0.3457382781455059,
    "bootstrap_positive_fraction": 0.337,
    "reps": 2000,
    "block": 20,
    "seed": 20261002
  },
  "HIER33_WITHIN": {
    "low": -0.6099091567782015,
    "high": 0.053375854731081036,
    "bootstrap_positive_fraction": 0.0525,
    "reps": 2000,
    "block": 20,
    "seed": 20261002
  },
  "HIER33_COMBINED": {
    "low": -0.12027083987176841,
    "high": 0.2435852778025995,
    "bootstrap_positive_fraction": 0.771,
    "reps": 2000,
    "block": 20,
    "seed": 20261002
  }
}
```

2000 paired draws, seed20261002, percentile95% intervals, same eligible dates for candidate/control. Blocks run over concatenated eligible sessions including gaps left by purge. Intervals describe known-Train sampling variation, not independent OOS or multiplicity-adjusted assurance.

## Interpretation conventions and saved diagnostics

Raw common is exactly equal inside a PIT sector/date and includes own observed stock; no LOO negative own coefficient. Its smoothed per-Code history can differ for new stocks, relistings and sector changes because the existing Code EWMA carries state across sector changes. This history effect and ties are measured. Raw decomposition identity is tested on joint-finite rows. Missing components independently neutralized0 can violate smoothed identity; EWMA(Stock0−Common0−Within0) must explain the entire discrepancy within1e−14. Prefix comparisons remain bitwise with zero tolerance. Full real identity error and explanation are in audit/decomposition_identity.json.

tie_sensitivity*.csv reports unique scores/exact tied-row share, Code ranks in Q1/Q5, same-sector concentration and one tiny deterministic score perturbation's membership/Jaccard/weight changes. Code_tie_tail_membership.csv saves tied-row tail allocation. No perturbed P/L, random tie-breaking, candidate or performance search is evaluated. The perturbation can also reorder numerically near but unequal adjacent scores, explicitly counted.

sector_common_daily.csv saves sector mean raw/smoothed signal, finite members and mean future residual target; dispersion and fixed rank-thirds low/middle/high buckets are descriptive. Cross-sector RankIC uses equal sector mean target. within_sector*.csv saves each sector's finite-raw smoothedWithin RankIC/HAC5 and deterministic internal quintile target means; its Long/Short gross are contributions of the ORIGINAL globally ranked Within portfolio, not an independently constructed within-sector trading rule.

Agreement A(++),B(+-),C(-+),D(--) uses raw Stock/Common signs. agreement*.csv saves equal-date target mean, rawStock/rawCommon/smoothedWithin RankIC/HAC and original MOM60/COMBINED book gross/net/Long/Short/cost attribution. No D-only portfolio/filter is created. Attributed cost on the bucket's date rows is not a standalone bucket strategy's turnover.

Sector33 daily exposure/normalized side weights/HHI/max/Q1Q5 shares, annual gross/net/side contribution and top2 concentration are saved. LOSO subtracts one original sector's P/L and attributed costs, without reranking/renormalization; remaining gross exposure differs, so its Sharpe is descriptive. Rank autocorrelation uses adjacent exchange dates and average percentile ranks; retention uses official quintiles; tail spells intersecting evaluation retain full contiguous observed lengths, right-censored marked. Rank-change percentiles are stock-day distributions; daily versions are also saved.

## Causality, parity and limitations

Static source scan, runtime Train firewall, full-feature/score/EWMA/Z/control bitwise future-mutation/truncation at3 cutoffs (four sources individually/jointly), future-only stocks/membership/source-row deletion, row shuffle/rebuild, exact index and finite adapter coverage pass. Prediction/adapter audits precede any Train target read. Existing raw primitive and MOM60 output are bitwise equal; cloned smooth/rank/segment function sources identical. Separate-process no-argument adapter smoke matches all809,636 Train rows. All raw-coverage gates use availability before neutral0; finite adapter output does not imply raw coverage passed.

Runtime Python firewall is best-effort, not an OS-level sandbox. Mutations are exercised-case evidence rather than a mathematical proof. Supplied498-stock dataset's historical survivorship cannot be independently removed; daily membership only uses present rows with PIT33. Short P/L is signed market-residual attribution, not raw-security short return or borrow cost. Real later split/Valid/zip runtime is outside scope. Existing global make check metadata failure, if present, is reported separately from strategy tests and original Freeze hash verification.

Full features/scores, immutable plan/config/source/environment/data hashes and resources are in the run. Metrics contain overall/fold/year/incremental/bootstrap, Long/Short cost decomposition, Q1Q5, coverage, rank persistence/changes, ties, identities, agreement, common/within alpha, sector exposure/contribution/top2 and LOSO. Technical failures remain retained; no post-result trial added.
