# DM-20261002-12 — baseline Sector Short-context veto

**A: REJECT。B（本命）: REJECT。** 固定2候補のTrain-only実験を終了。旧Sector実験の採否・証拠は変更していない。追加探索・Historical Valid/Valid・Freeze・外部提出なし。

損失回避の機構は部分的に確認できるが、採用できるNet改善はない。Pooled NetSRはBASELINE0.308092/A0.268556/B0.184835、EX2016は0.324348/0.264890/0.183362。両候補のfull-year改善は2013/2015の2/5のみ。B−BASELINE pooled95%CI[−0.272439,+0.007926]、EX2016[−0.298467,−0.005413]。正の安定した増分を支持しない。

BASELINE_SECTOR33_VETO: REMOVED 42,471行のforward target平均+4.406bp/day、旧signed Shortgross -0.8820pp/年は損失なので、その除去はGross改善+0.8820ppに寄与。一方ADDEDの新Shortgross -0.2737ppとUNCHANGEDのweight効果+0.0851ppを合わせ、全Shortgross差は+0.6933pp。Shortcost増+0.9049ppがこれを上回り、Shortnet差-0.2116pp。ΔShortNetが負のためGross/Net改善shareは定義せず、50%条件FAIL。単なるcost削減の改善でもない。Turnoverは0.099823/日、baseline比1.574倍で1.25x超。

BASELINE_HIER_SECTOR_VETO: REMOVED 43,129行のforward target平均+3.406bp/day、旧signed Shortgross -0.6509pp/年は損失なので、その除去はGross改善+0.6509ppに寄与。一方ADDEDの新Shortgross -0.3562ppとUNCHANGEDのweight効果+0.0250ppを合わせ、全Shortgross差は+0.3196pp。Shortcost増+0.9750ppがこれを上回り、Shortnet差-0.6554pp。ΔShortNetが負のためGross/Net改善shareは定義せず、50%条件FAIL。単なるcost削減の改善でもない。Turnoverは0.102606/日、baseline比1.618倍で1.25x超。

17 fallback: pooled24,761行、4.2948%の追加context coverage。B vs Aでfallback行のShort除去4,978、Gross寄与-0.2396%/年、Net寄与-0.3639%/年、Turnover寄与0.004942/日。B−Aのfallback行ΔGross-0.2575pp、ΔNet-0.2960pp、ΔTurnover+0.001531。全book B−AはΔNetSR-0.083721、annualNet差-0.4437pp、ShortNet差-0.4437pp。B−A pooled95%CI[−0.135782,−0.034707]、EX2016[−0.133094,−0.032622]。Coverage改善だけでalpha価値は認められず、今回のbookでは悪化。Source別寄与には33/unavailableへのglobal-ranking波及があるため、fallback単独効果と同一視しない。

Long側は今回実データで全Trainの日次Gross/Net/cost/turnoverがbitwise不変、評価期間membership overlap/Jaccardはいずれも1。Short改善と引き換えのLong alpha損失は観測されず、総Net悪化はShort側に対応する。一般にglobal rankingの波及は可能だが、今回の正score上位bookは変化していない。

Zero-score membership（公式Code tie orderingを保持）:

| candidate | vetoed_score_rows | vetoed_rows_still_short | vetoed_rows_still_short_share |
| --- | --- | --- | --- |
| BASELINE_SECTOR33_VETO | 135420 | 77637 | 0.573305 |
| BASELINE_HIER_SECTOR_VETO | 142699 | 84572 | 0.592660 |

Neutral化されたscoreが必ずShort bookから除去されるわけではない。Hard sign vetoによる変化とlarge0tie blockが同時に存在するため、Short turnover増の解釈はbookデータに基づく。原因の個別介入同定はしていない。

Short sector concentrationは同じPIT partitionで両候補とも増加。Top2平均exposureは33でbaseline22.13%→A22.38%→B23.02%、17で25.47%→25.76%→26.39%。日次HHI/平均最大weight:

| partition | strategy | mean_HHI | mean_max_sector_weight | max_sector_weight |
| --- | --- | --- | --- | --- |
| 17 | BASELINE | 0.092780 | 0.167316 | 0.306818 |
| 17 | BASELINE_HIER_SECTOR_VETO | 0.113586 | 0.196485 | 0.348485 |
| 17 | BASELINE_SECTOR33_VETO | 0.110045 | 0.193032 | 0.340909 |
| 33 | BASELINE | 0.067452 | 0.140483 | 0.272727 |
| 33 | BASELINE_HIER_SECTOR_VETO | 0.086399 | 0.170270 | 0.310606 |
| 33 | BASELINE_SECTOR33_VETO | 0.083472 | 0.167639 | 0.303030 |

Q Spearmanはbaseline0.9→両候補1.0で悪化せず、Gross/RankICの一部改善をcost控除後の安定した優位と取り違えない。

正式baselineはDM-20260908-v1のresidual60/skip1→centered rank→EWMA(.25)。既存実装・凍結snapshot・前回保存MOM60 scoreとbitwise一致。Vetoはその最終scoreの負値かつ正Sector contextのときだけexact0へ置換し、他はbaselineを保持。Candidate後の再平滑化はない。公式global rankingでzero scoreがShortに残る場合やLong側への波及がある。

Sectorは各historical dateのPIT銘柄のfinite残差60Momentumをself-inclusive equal mean。33min5、17min10は同じ60観測DM06の値を固定（直近Industry20のmin5とは別定義）。未回答のclarificationには事前告知したsame-horizon defaultを使用。33優先、33 unavailable時だけ17。No LOO/blend/weight/threshold search。

| strategy | scope | net_sharpe | annual_net | annual_short_gross | annual_short_net | annual_long_net | turnover | q_monotonicity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BASELINE | POOLED | 0.308092 | 0.016128 | -0.022335 | -0.030263 | 0.046391 | 0.063418 | 0.900000 |
| BASELINE | EX2016 | 0.324348 | 0.016685 | -0.019956 | -0.027870 | 0.044555 | 0.063327 | 0.900000 |
| BASELINE_SECTOR33_VETO | POOLED | 0.268556 | 0.014012 | -0.015402 | -0.032379 | 0.046391 | 0.099823 | 1.000000 |
| BASELINE_SECTOR33_VETO | EX2016 | 0.264890 | 0.013656 | -0.014063 | -0.030899 | 0.044555 | 0.099175 | 1.000000 |
| BASELINE_HIER_SECTOR_VETO | POOLED | 0.184835 | 0.009574 | -0.019138 | -0.036817 | 0.046391 | 0.102606 | 1.000000 |
| BASELINE_HIER_SECTOR_VETO | EX2016 | 0.183362 | 0.009397 | -0.017656 | -0.035158 | 0.044555 | 0.101823 | 1.000000 |

Pooled context33使用95.021%、17fallback4.295%、unavailable0.684%。Coverageは元のNaNを保持したcontext availabilityであり、全Trainのfinite予測100%とは別。

BASELINE_SECTOR33_VETO Short年率ΔNet -0.2116pp = ΔGross +0.6933pp + cost effect -0.9049pp。Gross share=nan（ΔNet>0の場合）。full-year NetSR改善2/5。未達: pooled_net_sharpe, ex2016_net_sharpe, full_year_improvements_4_of_5, bootstrap_lower_gt0, annual_net, short_net, turnover_le_1_25x, short_net_positive_increment, short_gross_share_ge50pct。

BASELINE_HIER_SECTOR_VETO Short年率ΔNet -0.6554pp = ΔGross +0.3196pp + cost effect -0.9750pp。Gross share=nan（ΔNet>0の場合）。full-year NetSR改善2/5。未達: pooled_net_sharpe, ex2016_net_sharpe, full_year_improvements_4_of_5, bootstrap_lower_gt0, annual_net, short_net, turnover_le_1_25x, short_net_positive_increment, short_gross_share_ge50pct。

Fallback B−A判定: **17 fallbackはoperational coverageを改善するがalpha改善は未確認**。判定チェックをcandidate_decision.jsonに保存。B−A source寄与はcurrent-row attributionであり、global rank spilloverやexit costsを含む。17単独portfolioを作っていない。

年別（2011–2015 full-year、2016 partialは改善年数から除外）:

| strategy | scope | net_sharpe | annual_net | annual_short_gross | annual_short_net | turnover |
| --- | --- | --- | --- | --- | --- | --- |
| BASELINE | 2011 | 0.506792 | 0.029635 | -0.037842 | -0.045983 | 0.065571 |
| BASELINE | 2012 | 0.636144 | 0.026788 | 0.021781 | 0.013708 | 0.065148 |
| BASELINE | 2013 | 0.081809 | 0.005051 | -0.025160 | -0.033088 | 0.063355 |
| BASELINE | 2014 | 0.910504 | 0.027522 | -0.015208 | -0.022952 | 0.060468 |
| BASELINE | 2015 | -0.099053 | -0.005742 | -0.043947 | -0.051626 | 0.062057 |
| BASELINE | 2016 | 0.067276 | 0.004639 | -0.071359 | -0.079579 | 0.065295 |
| BASELINE_SECTOR33_VETO | 2011 | 0.456700 | 0.026306 | -0.031610 | -0.049313 | 0.104005 |
| BASELINE_SECTOR33_VETO | 2012 | 0.209652 | 0.008889 | 0.013588 | -0.004191 | 0.103970 |
| BASELINE_SECTOR33_VETO | 2013 | 0.132608 | 0.008305 | -0.013881 | -0.029834 | 0.095741 |
| BASELINE_SECTOR33_VETO | 2014 | 0.570950 | 0.017761 | -0.014775 | -0.032713 | 0.101294 |
| BASELINE_SECTOR33_VETO | 2015 | 0.122451 | 0.007069 | -0.024023 | -0.038814 | 0.090783 |
| BASELINE_SECTOR33_VETO | 2016 | 0.332608 | 0.021334 | -0.042990 | -0.062883 | 0.113174 |
| BASELINE_HIER_SECTOR_VETO | 2011 | 0.328666 | 0.018833 | -0.038822 | -0.056786 | 0.105127 |
| BASELINE_HIER_SECTOR_VETO | 2012 | 0.151981 | 0.006352 | 0.011968 | -0.006729 | 0.107616 |
| BASELINE_HIER_SECTOR_VETO | 2013 | 0.118053 | 0.007386 | -0.014353 | -0.030753 | 0.097547 |
| BASELINE_HIER_SECTOR_VETO | 2014 | 0.433220 | 0.013252 | -0.018526 | -0.037221 | 0.104233 |
| BASELINE_HIER_SECTOR_VETO | 2015 | 0.020577 | 0.001182 | -0.028964 | -0.044702 | 0.094499 |
| BASELINE_HIER_SECTOR_VETO | 2016 | 0.211323 | 0.013223 | -0.049684 | -0.070994 | 0.118740 |

Paired circular moving-block20eligible sessions/2000reps/seed20261002/95%percentile、同一session vector。Primary pooled B−BASELINE、secondary A−BASELINE/B−A。EX2016はrobustness別表示。purge gapsを除いたeligible sessionsを連結。既知Train・多重比較補正なし・独立OOSの保証なし。

| contrast | point_delta | low | high |
| --- | --- | --- | --- |
| POOLED:BASELINE_HIER_SECTOR_VETO-BASELINE | -0.123258 | -0.272439 | 0.007926 |
| POOLED:BASELINE_SECTOR33_VETO-BASELINE | -0.039537 | -0.181364 | 0.083437 |
| POOLED:BASELINE_HIER_SECTOR_VETO-BASELINE_SECTOR33_VETO | -0.083721 | -0.135782 | -0.034707 |
| EX2016:BASELINE_HIER_SECTOR_VETO-BASELINE | -0.140986 | -0.298467 | -0.005413 |
| EX2016:BASELINE_SECTOR33_VETO-BASELINE | -0.059458 | -0.216804 | 0.075267 |
| EX2016:BASELINE_HIER_SECTOR_VETO-BASELINE_SECTOR33_VETO | -0.081528 | -0.133094 | -0.032622 |

removed_added_*にはShortQ1+Q2/Q1/Q2ごとのREMOVED/ADDED/UNCHANGEDのforward target、signed gross/net、両Sector Momentum、baseline score、両sector分布を保存。UNCHANGEDはweight差を含み、OTHERのexit-only costsも保存。Short差分はgross/net/cost/turnover全て1e-15内で日次reconcile。Loss avoidanceの解釈はremoved cohortの旧signed grossとreplacementの新signed grossを併せて判断し、cost削減だけをalpha改善と呼ばない。

long_impact.csvにLonggross/net/turnover/overlap/Jaccard、sector17/sector33に同じPIT partitionでの全3bookのShortHHI/max/Q1Q2分布/top2 exposure/contribution。Unknown sectorを除去せず保持し、rerankやexclusionなし。fallback_attribution.csvはB vs baseline/B vs Aを33/fallback/unavailableで分離し、全行・Short除去・gross/net/turnoverを保存。

公式5quintiles/Q2Q4 half-weight/Code tie order、one-way0.1%cost、Sharpe sampleSD×sqrt252、annual arithmetic mean×252、RankIC HAC5 Bartlett、Q1low/Q5high Spearman単調性、additive/compound DD、period sums。全Trainbook/cost計算後にfold選択し、過去保有を維持。各fold末2sessions purge/t+2 maturity監査。Missing targetのcost除外は公式互換、保守的all-position costも別保存。Shortはborrowcost未控除の市場残差signed P/L。2016年率値は実現full-year returnではない。

Auditは全4Train入力、3cutoffs×6mutation/truncation、future-only stocks、future PIT33/17 changes、全intermediate/final score bits、row shuffle、決定性、exact index/coverage、研究/adapter/isolated no-argument smoke、公式accounting、source firewall/purge/prior証拠hashを含む。動的監査は実施入力での証拠、Python firewallはbest-effort。実zip検証はFreeze/提出を依頼されていないため対象外。

Run: `artifacts/DM-20261002-12/run-20261002T102506Z`。全metric/accounting/audit/config/code/input/environment hashesを保存。

Scientific run completed2trials/all diagnostics but failed while its firewall hashed a prior diagnostic parquet. Original failed run retained unchanged. This recovery uses identical saved scores/accounts/diagnostics and verifies421prior evidence hashes and original code snapshots;0additional performance trials. No plan/config/strategy changes. Science peakRSS was not recorded before finalization failed; isolated inference resources remain in audit/standalone_smoke.json.

Validation: 全307tests PASS、保存処理修正後の対象24tests（新規firewall/hash/copy回帰を含む）PASS。make checkは既存DM-20261002-04 unknown experiment kindで停止するが、新metadataとFreeze129hash再検査PASS。最初のreport recoveryも自身のdiagnostic parquet copy許可漏れで失敗し、0trialsとして保持。最終recoveryは保存結果のみ利用し成功、累積performance2trials。
