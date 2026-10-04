# DM-20261002-10 — Industry continuation / within-industry reversal

**結論: 固定3候補を全てREJECTし、今回の研究を終了する。次段階候補はない。**

「Industry continuation + Within-industry reversal」という全体の符号構造を、今回の日本株コンペ条件で実用的な投資戦略として支持する結果にはならなかった。Industry continuationには記述的な正の予測関連があるが、20観測Stock/Within reversalは安定したGross収益を作らず、結合しても高い回転率とShort損失によりMOM60を下回った。これは固定20観測・skip1・公式残差target・EWMA(.25)の棄却であり、論文や日本株Reversal一般の否定ではない。符号の再反転、horizon・weight・alpha・業種選別などのrescueは実施しない。

評価は2011–2015と2016部分年の同一1,275営業日・576,535銘柄日。2016を除くと1,216営業日。過去06–09の採否・文書・レポート・戦略コード276ファイルのhashは不変。今回の事前符号は外部研究に基づき、過去Train成績を見た救済調整として扱わない。初回事前登録も保存し、結果前にLOO診断の記述を禁止事項へ合わせた修正履歴を残した。performance定義・パラメータ・採否基準の変更はない。

**Q1 — 20観測Stock reversalはあるか。** 今回の運用条件では支持しない。STOCK_REV20のpooled RankICは-0.00589、HAC5 t=-1.38、Gross/Net SRは-0.452/-1.110。2011–2015のGross正は0/5、Netも全5年負。2016部分年だけGross/Netが正で、ex2016 Gross/Net SRは−0.596/−1.264に悪化する。raw20 Reversal自体のICも−0.00548、t=−1.31で、EWMAだけが不成立理由とは言えない。ただしICは通常の有意水準で有意な負とは言えず、「Reversal不存在の証明」とはしない。

**Q2 — Industry-relative化は安定性を増すか。** WithinはStockよりannual Netが+1.245pp改善し、Long/Short netも改善するが、Net SRは-0.143と低下する。Grossの正は2/5へ増えるものの、2011/2015のGross SRは0.101/0.048と小さく、全5年のNetは負。Within−Stock ΔNet SR95%CIは[−0.530,+0.196]、ex2016も[−0.542,+0.251]。Within raw IC−0.00096/t−0.34はStockより0に近いだけで、安定したReversalの増分を示さない。Withinのpooled raw coverage94.214%も基準未達。

**Q3 — 結合に増分があるか。** CombinedはWithinに対してGross/Net SRが+0.939/+0.714、annual Netが+2.441pp改善する。ただしΔNet SR95%CI[−0.680,+2.110]は0を跨ぎ、安定した増分とは判定しない。Combined対MOM60ではGross SRは僅かに高い一方、annual Grossは-1.524pp、annual Costは+1.470pp、annual Netは-2.994pp。SharpeのGross差だけをalpha改善とは呼ばない。Net SR差は-0.847、95%CI[−2.171,+0.385]、ex2016差−0.855、CI[−2.198,+0.479]。full-year Net SR改善2/5で4/5gate未達。Industry-only Net比較は、禁止された第4performance candidateを作らないため未識別。

**Q4 — LongだけでなくShortにも効くか。** WithinのShort annual Gross/Netは-4.571%/-6.047%、MOM60比-2.337pp/-3.020pp。過度に買われた同業銘柄をShortする仮説は、Shortのpositive GrossやMOM60損失縮小に至らない。CombinedはWithinよりLong/Short netが+0.617pp/+1.824pp改善する一方、MOM60比ではLong/Shortとも-1.798pp/-1.196pp悪化。Combined Short Gross/Netは-2.690%/-4.222%。Longは正でも、両側に対する採用上の増分はない。Long/Short SR・turnover・costと全fold値はlong_short.csv。

**Mechanism。** IndustryMom20のstock-row raw RankICは+0.01038/t2.32、cross-industry RankICは+0.01810/t1.97。業種を等ウェイトにしたLow/Middle/High tercileの翌target平均は+0.11/+3.17/+3.86bp/day、ex2016でも+0.02/+3.16/+3.76bp。Cross-industry ICは2011–2015で4/5年が正だが、2013は+0.0580/t3.10、2012は−0.0084で、強い年への偏りもある。Industry continuationと整合する記述的関連はあるが、選択済みTrainで複数診断を行った証拠であり、独立OOSや論文replicationではない。Low業種でも平均targetは負ではなく、そのまま安定したShort alphaとは読めない。

Within>0とWithin<0のequal-date targetは+3.05/+3.02bp/dayで差が小さく、ex2016は+2.99/+2.79bp。Industry>0のA(Within>0)/B(Within<0)は+4.48/+4.40bp、Industry<0のC/Dは+0.43/+1.17bp。B>AというWithin reversalの期待順序はpooledで現れず、D>Cは整合するが記述的な一部に留まる。共通成分とWithin reversalの日次平均Pearsonは約−0.00021で、単純な分解の機械的関係もある。A–Dからfilterを作らない。

固定lag1 self-inclusive Industry return対future targetのICは+0.00287/t0.81、own lag1 residualは−0.00355/t−1.20。どちらも強い統計的証拠ではない。LOO禁止を維持したためIndustry値にはownも含まれ、同一industry内ではcommon scoreに分散がない。Within-sector ICは定義不能としてNaNを保存し、0に置換しない。純粋なpeer情報拡散・lead-lag因果効果を識別したとは言えない。追加lag、leader、networkや取引候補はない。

**Turnover / coverage / concentration。** 各候補の日次turnoverは0.1193/0.1179/0.1225で、全て0.08gate超過。MOM60は0.0634、Combinedはその1.93倍で1.25倍gateも超える。年率costは3.005%/2.970%/3.068%、MOM601.598%。rank自己相関は0.9891/0.9880/0.9874、MOM600.9966。quintile retentionは85.70%/85.88%/85.31%、MOM6092.40%。平均tail spellは13.30/13.47/12.96営業日、MOM6024.79。20観測signalの回転率増加をEWMA(.25)だけでは抑えられなかった。

Stock20 raw coverage99.132%、Industry20 95.022%、Within/Combined 94.214%。pooled内のStock履歴不足5,002行、Industry履歴不足28,700行、current-date minimum5不足28,704行。これらはoverlapがあり単純加算しない。全required Train809,636行のfinite predictionは100%でもraw coverage合格とは呼ばない。finite Stock20の571,533評価行でindustryとStockの形成calendar endpointの差は0行だった。

CombinedのLong/Short Sector33HHIは0.0922/0.0927（MOM600.0681/0.0675）、side最大業種weightの平均16.81%/17.62%（MOM6012.97%/14.05%）。Gross上位2業種3650/6100の寄与は+1.130pp、総Grossの67.0%（MOM6031.6%）。LOSO記述的Grossは+0.983%〜+2.022%で残るがNetは全業種の除去で−1.752%〜−0.759%。1業種だけが不成立理由ではない。元bookから寄与を控除した診断のみでrerank/exclusionはしない。Gross合計が負のReversal候補のtop2比率は符号付き比率であり、集中度の正の割合として解釈しない。

**検証。** 全260 tests（新規25）PASS。全Train入力18 future-mutation/truncationケース・3cutoff、IndustryResidualReturn/historyからfinal scoresまでuint64 bits厳密一致。row shuffle/決定性、exact index、原始MOM60と前回controlのbitwise一致、research/adapter parity、独立no-argument smoke、公式会計照合、2-session target maturity、runtime Train firewall、前実験hash確認もPASS。科学run80.45秒・peak RSS1.77GiB、独立smoke2.75秒・1.08GiB。make checkだけは既存DM-20261002-04のunknown experiment kindで停止。新metadataと既存Freeze129hashは別途PASSし、既存metadataは変更していない。Valid、実zip提出、独立OOSやborrow costは本研究の対象外。

Exactly3 fixed Train-only trials completed; known development evidence, not independent OOS. No Valid, rescue search, Freeze or submission.

Run `artifacts/DM-20261002-10/run-20261002T091211Z`. Plan/config/preregistration in experiments/DM-20261002-10. Prior06–09 remain unchanged.

| strategy | rankic | rankic_t_hac5 | gross_sharpe | net_sharpe | annual_net | turnover | annual_short_gross | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STOCK_REV20 | -0.005887 | -1.382773 | -0.451859 | -1.110439 | -0.050674 | 0.119259 | -0.047485 | -0.062385 |
| WITHIN33_REV20 | -0.002660 | -0.937962 | -0.279690 | -1.253057 | -0.038225 | 0.117852 | -0.045706 | -0.060467 |
| IND33_MOM_WITHIN_REV20 | 0.003222 | 1.270265 | 0.659250 | -0.539263 | -0.013815 | 0.122539 | -0.026895 | -0.042223 |
| MOM60 | 0.007590 | 1.567643 | 0.613360 | 0.308092 | 0.016128 | 0.063418 | -0.022335 | -0.030263 |

Q1: Stock reversal final-score RankIC -0.005887, HAC5 t -1.383; Gross/Net SR -0.4519/-1.1104. Raw signal diagnostics and all years are saved; this fixed competition test does not establish universal Japanese reversal.

Q2: Within minus stock ΔNet SR -0.1426, ΔRankIC +0.003227, ΔAnnualNet +1.245pp. Year and paired-CI evidence in incremental/bootstrap, with raw coverage kept separate.

Q3: Combined minus Within ΔNet SR +0.7138; combined minus MOM60 -0.8474. Industry-only has no performance portfolio by design, so a claim of better Net than industry-only is unidentified. Cross-industry IC/terciles/dispersion/proxy diagnose it without a fourth trial.

Q4: Combined annual Long gross/net +4.376%/+2.841%, Short gross/net -2.690%/-4.222%. Within Short gross/net -4.571%/-6.047%, vs MOM60 -2.233%/-3.026%. Side Sharpe/cost/turnover, tail overlap and sector concentration saved.

Fixed criteria and decisions:

```json
{
  "STOCK_REV20": {
    "decision": "REJECT",
    "feasibility": {
      "pooled_rankic_positive": false,
      "pooled_gross_positive": false,
      "ex2016_gross_positive": false,
      "gross_positive_3of5": false,
      "raw_coverage_ge95pct": true,
      "turnover_le008": false
    },
    "combined_adoption": {},
    "failed_checks": [
      "pooled_rankic_positive",
      "pooled_gross_positive",
      "ex2016_gross_positive",
      "gross_positive_3of5",
      "turnover_le008"
    ],
    "raw_coverage": 0.9913240306312713,
    "full_year_gross_positive": 0,
    "full_year_netSR_improvements_vs_MOM60": 0
  },
  "WITHIN33_REV20": {
    "decision": "REJECT",
    "feasibility": {
      "pooled_rankic_positive": false,
      "pooled_gross_positive": false,
      "ex2016_gross_positive": false,
      "gross_positive_3of5": false,
      "raw_coverage_ge95pct": false,
      "turnover_le008": false
    },
    "combined_adoption": {},
    "failed_checks": [
      "pooled_rankic_positive",
      "pooled_gross_positive",
      "ex2016_gross_positive",
      "gross_positive_3of5",
      "raw_coverage_ge95pct",
      "turnover_le008"
    ],
    "raw_coverage": 0.9421405465409732,
    "full_year_gross_positive": 2,
    "full_year_netSR_improvements_vs_MOM60": 0
  },
  "IND33_MOM_WITHIN_REV20": {
    "decision": "REJECT",
    "feasibility": {
      "pooled_rankic_positive": true,
      "pooled_gross_positive": true,
      "ex2016_gross_positive": true,
      "gross_positive_3of5": true,
      "raw_coverage_ge95pct": false,
      "turnover_le008": false
    },
    "combined_adoption": {
      "pooled_netSR_beats_MOM60": false,
      "ex2016_netSR_beats_MOM60": false,
      "netSR_improvements_4of5": false,
      "bootstrap_lower_positive": false,
      "annual_net_beats_MOM60": false,
      "turnover_le125_MOM60": false,
      "long_net_positive": true,
      "short_net_ge_MOM60": false,
      "Q_monotonicity_positive": true
    },
    "failed_checks": [
      "raw_coverage_ge95pct",
      "turnover_le008",
      "pooled_netSR_beats_MOM60",
      "ex2016_netSR_beats_MOM60",
      "netSR_improvements_4of5",
      "bootstrap_lower_positive",
      "annual_net_beats_MOM60",
      "turnover_le125_MOM60",
      "short_net_ge_MOM60"
    ],
    "raw_coverage": 0.9421405465409732,
    "full_year_gross_positive": 3,
    "full_year_netSR_improvements_vs_MOM60": 2
  }
}
```

Bootstrap paired circular20 eligible sessions,2000reps,seed20261002,95%percentile ΔNetSR. PrimaryPOOLED combined-MOM60, EX2016 sensitivity, secondary within-stock/combined-within. Purged gaps are concatenated eligible sessions; no multiple-testing correction.

```json
{
  "POOLED:IND33_MOM_WITHIN_REV20-MOM60": {
    "low": -2.1710533450585205,
    "high": 0.38494172900868273,
    "bootstrap_positive_fraction": 0.0855,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "days": 1275,
    "point_delta": -0.8473557442729736,
    "primary": true
  },
  "POOLED:WITHIN33_REV20-STOCK_REV20": {
    "low": -0.5301066006395891,
    "high": 0.19596869466301226,
    "bootstrap_positive_fraction": 0.206,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "days": 1275,
    "point_delta": -0.14261833505128574,
    "primary": false
  },
  "POOLED:IND33_MOM_WITHIN_REV20-WITHIN33_REV20": {
    "low": -0.6801047718402911,
    "high": 2.110321902336301,
    "bootstrap_positive_fraction": 0.8235,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "days": 1275,
    "point_delta": 0.7137940832738214,
    "primary": false
  },
  "EX2016:IND33_MOM_WITHIN_REV20-MOM60": {
    "low": -2.1983276220845953,
    "high": 0.47866977862293403,
    "bootstrap_positive_fraction": 0.0955,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "days": 1216,
    "point_delta": -0.8550962235636941,
    "primary": false
  },
  "EX2016:WITHIN33_REV20-STOCK_REV20": {
    "low": -0.5421845983085881,
    "high": 0.2511453661585291,
    "bootstrap_positive_fraction": 0.251,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "days": 1216,
    "point_delta": -0.1317683251553292,
    "primary": false
  },
  "EX2016:IND33_MOM_WITHIN_REV20-WITHIN33_REV20": {
    "low": -0.5899668049638432,
    "high": 2.358197933555382,
    "bootstrap_positive_fraction": 0.884,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "days": 1216,
    "point_delta": 0.8651825150090576,
    "primary": false
  }
}
```

Full-year chronology2011–2015;2016partial separated. All folds use expanding causal history without fit; final2 exchange sessions purged, t+2 maturity verified. Official full-panel daily accounting occurs before fold selection, retaining previous holdings. Official Code ties/five quintiles includingQ2/Q4,10bp one-way. Annual arithmetic mean×252 (2016 annualization is not a full-year realized return), sample-SD SR×sqrt252, RankIC HAC5 Bartlett and hit, Q1low/Q5high and monotonicity, additive/compound DD. Period sums saved. Missing-label cost omission follows official score; conservative all-position costs/net are also saved. Short residual P/L excludes borrow costs.

Industry return uses historical-date PIT33 membership, self-inclusive equal finite residual mean min5; lag1 then20-calendar-observation sum, gaps/insufficient days stayNaN. Stock uses existing observed-row/relisting convention, same20/skip1; rare calendar-span differences saved in formation_timing_gaps.csv. Map today's sector only after historical industry construction. Raw Within=Stock-Industry, reversal sign registered from literature. Centered ranks before EWMA for all3; combined separately ranks both components, sums1:1, reranks then smooths. Missing raw is measured before neutral ranks and remains unavailable in raw diagnostics. No post-result sign/horizon/weight/alpha change.

Mechanism: raw component IC, industry equal-sector terciles/cross-industry IC/year/dispersion/rank-change proxy, Within +/- and four Industry/Within sign states, original-book state contributions. Lead-lag is one fixed lag1 self-inclusive industry association versus own residual: it cannot separate peer information from own persistence/common shocks, and the common score has no within-sector variation. No LOO or causal diffusion claim. Sector33HHI/max/Q1Q5 distributions/top2 and LOSO subtract original-book contribution/cost without rerank; no sector exclusion. Spells follow contiguous observed sessions, reset on gaps, include boundary censoring; period means can include full spells intersecting the period.

Audit: static scan, runtime Train firewall/pre-target score construction,3cutoff full-source mutations including future-only stocks/classifications/deletions, bitwise full industry-history/raw/final prefix, truncation/row shuffle/rebuild, exact index/finite outputs, unchanged primitive/MOM60 and saved control parity, research/adapter and isolated no-argument smoke, official weights/P/L reconciliation and target maturity. The Python firewall is best-effort; dynamic checks cover exercised inputs, not mathematical proof. Literature full-text replication, independent OOS, actual zip deployment and borrow costs are outside this research.
