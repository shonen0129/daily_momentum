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
