# DM-20261003-03: SN1 × SLOW diversification

Decision: **REJECT**. One fixed score-blend trial; zero rescue trials. Historical Valid / Valid not read or evaluated. Run: `artifacts/DM-20261003-03/run-20261003T094246Z`.

目的はMomentum/BreakoutとSize/Liquidityを組み合わせたときの安定したNetの増分。単体の優劣を選ぶ実験ではない。低相関だけで採用しない。

| strategy | net_sharpe | gross_sharpe | annual_net | annual_gross | turnover | annual_cost | max_drawdown_compound | annual_long_net | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SN1_H1 | 1.063424 | 1.108539 | 0.045198 | 0.047111 | 0.007666 | 0.001913 | -0.061671 | 0.061580 | -0.016382 |
| SLOW_CONTROL | 2.093538 | 2.179334 | 0.077119 | 0.080272 | 0.012888 | 0.003153 | -0.022099 | 0.075064 | 0.002055 |
| SN1_SLOW_BLEND | 1.922898 | 2.019951 | 0.080008 | 0.084037 | 0.016373 | 0.004028 | -0.036836 | 0.077992 | 0.002017 |

Primary/secondary comparison and all required IC/HAC5/hit/Q1–Q5/side/period metrics are in `metrics/metrics.csv` and `metrics/incremental.csv`.

| strategy | scope | days | net_sharpe | annual_net | turnover | max_drawdown_compound |
| --- | --- | --- | --- | --- | --- | --- |
| SN1_H1 | 2011 | 243 | 0.002066 | 0.000091 | 0.015975 | -0.047689 |
| SN1_H1 | 2012 | 246 | 1.099258 | 0.048929 | 0.009330 | -0.027357 |
| SN1_H1 | 2013 | 243 | 1.659027 | 0.076797 | 0.000727 | -0.042969 |
| SN1_H1 | 2014 | 242 | 1.951841 | 0.040267 | 0.004065 | -0.013447 |
| SN1_H1 | 2015 | 242 | 0.925640 | 0.036819 | 0.003477 | -0.033827 |
| SN1_H1 | 2016 | 59 | 1.843075 | 0.139870 | 0.027052 | -0.038964 |
| SLOW_CONTROL | 2011 | 243 | 2.728793 | 0.122760 | 0.013703 | -0.021303 |
| SLOW_CONTROL | 2012 | 246 | 1.033654 | 0.033888 | 0.013052 | -0.016957 |
| SLOW_CONTROL | 2013 | 243 | 1.896830 | 0.081311 | 0.014252 | -0.018996 |
| SLOW_CONTROL | 2014 | 242 | 1.664345 | 0.051361 | 0.011729 | -0.022099 |
| SLOW_CONTROL | 2015 | 242 | 3.267066 | 0.096957 | 0.011756 | -0.009106 |
| SLOW_CONTROL | 2016 | 59 | 2.003895 | 0.076413 | 0.012628 | -0.008544 |
| SN1_SLOW_BLEND | 2011 | 243 | 2.252625 | 0.087196 | 0.021319 | -0.029486 |
| SN1_SLOW_BLEND | 2012 | 246 | 0.940239 | 0.039381 | 0.017527 | -0.023644 |
| SN1_SLOW_BLEND | 2013 | 243 | 1.940412 | 0.098237 | 0.013502 | -0.036836 |
| SN1_SLOW_BLEND | 2014 | 242 | 2.295267 | 0.062738 | 0.012419 | -0.017729 |
| SN1_SLOW_BLEND | 2015 | 242 | 2.358292 | 0.092642 | 0.014147 | -0.025989 |
| SN1_SLOW_BLEND | 2016 | 59 | 2.561980 | 0.163744 | 0.028368 | -0.023345 |

2011–2015 Net Sharpe改善 vs SLOW: **2/5**。2016は部分年として別記。POOLEDとEX2016は日付を揃えた2011以降の評価営業日。年間P/Lは日次平均×252であり2016も年率換算、実額はperiod_*。Sharpeはsample SD(ddof1)×sqrt252、RankICは日次average-tie Spearman、tはNewey-West/Bartlett HAC5。

## Orthogonality before performance trial

Pooled gross P/L correlation **0.159616**, net **0.159687**; mean daily score Spearman **0.035133**. Long/Short Jaccard **0.273205/0.251830**. Long/Short daily cross-sector exposure correlation **0.848727/0.717051**.

SN1とSLOWのdrawdown pathは同一か: **False**。Underwater Jaccard **0.738956**、depth correlation **0.131070**。SN1のみunderwater **242**日、SLOWのみ **83**日、両方 **920**日。異なるdrawdownは診断上の観測であり、独立した経済原因の証明ではない。

SN1 net<0日にSLOW平均Net **-0.00010559**、SLOW net<0日にSN1平均Net **-0.00040064**。両方負 **300**日、片方のみ負 **543**日。

| scope | gross_pl_corr | net_pl_corr | score_spearman_mean | drawdown_jaccard | both_negative_days | exactly_one_negative_days |
| --- | --- | --- | --- | --- | --- | --- |
| POOLED | 0.159616 | 0.159687 | 0.035133 | 0.738956 | 300 | 543 |
| EX2016 | 0.163485 | 0.163381 | 0.034013 | 0.740304 | 288 | 518 |
| 2011 | -0.177936 | -0.177747 | 0.031000 | 0.662447 | 47 | 114 |
| 2012 | 0.289798 | 0.289095 | 0.099177 | 0.790795 | 68 | 97 |
| 2013 | 0.363183 | 0.363206 | 0.021822 | 0.701754 | 62 | 96 |
| 2014 | 0.183770 | 0.183354 | 0.022386 | 0.733624 | 50 | 116 |
| 2015 | 0.265126 | 0.265496 | -0.005334 | 0.633621 | 61 | 95 |
| 2016 | 0.145936 | 0.147942 | 0.058213 | 0.696429 | 12 | 25 |

Sector33は各signal日PIT、欠損/9999はUNKNOWN。各日sector断面相関とsectorごとの時系列相関を両方保存。Long=Q4/Q5, Short=Q1/Q2、Q3はneutral。Overlap=intersection/min(side set sizes)、Jaccard=intersection/union。Underwaterはwealth/peak−1<0、初期wealth1を含む。各scopeでcurveを再初期化し年別episodesも保存。

## Pure-weight diagnostic (not a candidate)

0.5×official weightsの仮想portfolio pooled NetSR **2.021777**、GrossSR **2.104855**、年率Net **0.061185**、turnover **0.010168**。Nettingしない0.5×両戦略P/Lのsleeve NetSR **2.020895**。

| scope | net_sharpe | gross_sharpe | sleeve_net_sharpe | annual_net | turnover | annual_cost | max_drawdown_compound |
| --- | --- | --- | --- | --- | --- | --- | --- |
| POOLED | 2.021777 | 2.104855 | 2.020895 | 0.061185 | 0.010168 | 0.002507 | -0.026918 |
| EX2016 | 2.004401 | 2.085712 | 2.003590 | 0.058903 | 0.009715 | 0.002390 | -0.026918 |
| 2011 | 2.148212 | 2.272056 | 2.146339 | 0.061481 | 0.014611 | 0.003541 | -0.022179 |
| 2012 | 1.326966 | 1.414895 | 1.326168 | 0.041434 | 0.011091 | 0.002745 | -0.018967 |
| 2013 | 2.147498 | 2.197084 | 2.147248 | 0.079063 | 0.007445 | 0.001831 | -0.026437 |
| 2014 | 2.283470 | 2.378891 | 2.282594 | 0.045832 | 0.007824 | 0.001950 | -0.013793 |
| 2015 | 2.407172 | 2.475383 | 2.406671 | 0.066900 | 0.007569 | 0.001877 | -0.018611 |
| 2016 | 2.409584 | 2.522666 | 2.407676 | 0.108224 | 0.019511 | 0.004902 | -0.016222 |

合成後weightの差分で売買をnettingする主診断と、各戦略コストを半分ずつ負担するsleeve診断を区別。前者のLong/Shortは合成weight符号、後者のside attributionは元戦略sideの平均。純粋な分散効果とranking interactionを分離して解釈する。

## Bootstrap and adoption

Paired circular moving-block: block20, reps2000, seed20261003, 95% percentile CI. Primary ΔNetSR(BLEND−SLOW) **-0.170640**, CI **[-0.881013, 0.534931]**. Secondary ΔNetSR(BLEND−SN1) **0.859474**, CI **[0.385236, 1.360397]**.

| gate | passed |
| --- | --- |
| improved_full_years_ge4 | False |
| POOLED_net_sharpe_gt_slow | False |
| POOLED_annual_net_ge_slow | True |
| POOLED_MDD_magnitude_le_slow | False |
| POOLED_long_net_gt0 | True |
| POOLED_short_net_ge0 | True |
| POOLED_turnover_le_max_components | False |
| EX2016_net_sharpe_gt_slow | False |
| EX2016_annual_net_ge_slow | False |
| EX2016_MDD_magnitude_le_slow | False |
| EX2016_long_net_gt0 | True |
| EX2016_short_net_ge0 | True |
| EX2016_turnover_le_max_components | False |
| primary_pooled_bootstrap_lower_gt0 | False |

## Diversification attribution

metrics/diversification_attribution.csv とstock/daily panelにcount、forward target、全3bookのgross/net/turnover/cost、BLEND−各component差分を保存。Exclusive viewはopposite official sideをSIGNAL_DISAGREEMENTへ先に割当て、onlyLong/Shortは他方neutral。BOTH_NEUTRALにexitコストを保持するため全会計へ照合できる。MARGINAL_OVERLAPPING viewは要求された「片方のみLong/Short」を他方oppositeも含めて集計し、disagreementとの重複を明記。群を合算して重複計上しない。新filterは作らない。

## Causality and reproducibility

Component source copies byte-identical, current originals/adapter/saved scores float64 bitwise parity; exact809636-row input/output index and finite coverage; deterministic rebuild. Future mutation covers each/all sources and Train labels; truncation covers all sources at three cutoffs, features/all3 scores bitwise. Annual SN1 models are refit on original mature prior-fold labels, so learning path is included. Cutoff後のmodel年を監査時に使用しない。No later split prediction is implemented in new adapter.

Official weights and daily Net are bitwise reconciled. Stock/sleeve attribution uses1e-15 numerical sum tolerance and is not called bitwise. The official expression omits cost when target is missing; cost_all/net_all_cost are also saved. Official turnover follows last observed stock row across absences, unchanged. Full-panel accounting precedes fold purge, preserving holdings across omitted days. Training maturity and reconstructed t+2 target are saved in audit/maturity.json.

Elapsed **341.27s**, peak RSS **2.611 GB**. Source/input/config/plan/artifact hashes, environment versions, bounded command and phase timestamps saved. Tests and workspace verification are in audit/verification.json. The new adapter is a Train research candidate, not a frozen later-split submission. No release or external submission.

Conclusion applies to this fixed operationalization and known Train sample. Low correlation cannot establish higher tradable after-cost Sharpe. No weight/feature/parameter/filter changes or rescue candidates after results.

## Saved-result interpretation and final receipts

**REJECT**: tradable1:1 blendはSLOW_CONTROLより高く安定したNet Sharpeを作らなかった。Pooled年率Netは0.289ポイント増えたが、Net volatilityも増加しNetSRは低下。Gross改善だけで採用しない。低score/P/L相関と異なるDD深度は確認できたが、economic alpha源の独立性を証明した結果ではない。

| strategy | scope | annual_net | annual_net_volatility | net_sharpe |
| --- | --- | --- | --- | --- |
| SN1_H1 | POOLED | 0.045198 | 0.042502 | 1.063424 |
| SN1_H1 | EX2016 | 0.040605 | 0.040217 | 1.009628 |
| SLOW_CONTROL | POOLED | 0.077119 | 0.036837 | 2.093538 |
| SLOW_CONTROL | EX2016 | 0.077153 | 0.036789 | 2.097190 |
| SN1_SLOW_BLEND | POOLED | 0.080008 | 0.041608 | 1.922898 |
| SN1_SLOW_BLEND | EX2016 | 0.075946 | 0.040236 | 1.887524 |
| PURE_WEIGHT_50_50 | POOLED | 0.061185 | 0.030263 | 2.021777 |
| PURE_WEIGHT_50_50 | EX2016 | 0.058903 | 0.029387 | 2.004401 |

Blend turnover増分 0.003485/day（27.04%増）、年率charged cost増分 0.0875ポイント。MaxDD magnitude 2.210% → 3.684%。Long/Short Netは正でもNetSR/安定性条件を満たさない。

群別増分は群のalphaを独立に推定した値ではなく、元2戦略の当日membershipで固定portfolioの会計を分解した観測。以下は互いに排他的なprimary/secondaryの年率寄与。全forward targetは公式t+1 Open→t+2 Open残差リターン。

| group | count | forward_target_mean | DELTA_VS_SLOW_CONTROL_gross_annual | DELTA_VS_SLOW_CONTROL_net_annual | DELTA_VS_SLOW_CONTROL_turnover_daily | DELTA_VS_SN1_H1_gross_annual | DELTA_VS_SN1_H1_net_annual | DELTA_VS_SN1_H1_turnover_daily |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BOTH_LONG | 98701 | 0.000711 | 0.007212 | 0.007351 | -0.000614 | 0.007026 | 0.006935 | 0.000467 |
| BOTH_NEUTRAL | 21533 | 0.000373 | 0.000112 | 0.000108 | 0.000019 | 0.000112 | -0.000035 | 0.000606 |
| BOTH_SHORT | 92163 | -0.000126 | -0.000481 | -0.000407 | -0.000295 | 0.003006 | 0.003178 | -0.000681 |
| SIGNAL_DISAGREEMENT | 177338 | 0.000279 | -0.012619 | -0.013326 | 0.002814 | 0.017791 | 0.016797 | 0.003991 |
| SLOW_ONLY_LONG | 42152 | 0.000514 | -0.002250 | -0.002271 | 0.000103 | 0.011048 | 0.010899 | 0.000630 |
| SLOW_ONLY_SHORT | 51248 | -0.000018 | 0.000136 | 0.000010 | 0.000502 | 0.000658 | 0.000435 | 0.000886 |
| SN1_ONLY_LONG | 44508 | 0.000543 | 0.011906 | 0.011881 | 0.000125 | -0.001638 | -0.001935 | 0.001260 |
| SN1_ONLY_SHORT | 48892 | 0.000012 | -0.000252 | -0.000457 | 0.000830 | -0.001078 | -0.001465 | 0.001548 |

対SLOWのSN1_ONLY_LONGは年率Net+1.1881ポイント、BOTH_LONGは+0.7351ポイント。一方SIGNAL_DISAGREEMENTは−1.3326ポイント、SLOW_ONLY_LONGは−0.2271ポイント。これらにneutral exitとShort各群を含めた合計がPooled Net差と一致する。disagreement vetoや群別weightの変更は行わない。

Virtual NetSR2.0218はSN1より高いがSLOW2.0935には届かず、tradable blend1.9229はvirtualより低い。固定50/50から1:1 scoreへのranking interactionと追加turnoverが異なるportfolioを作るため、低相関をtradable増分の保証として扱わない。Secondary対SN1のpositive CIはPrimary対SLOWの失敗を救済しない。

27 real-Train prefix cases（各6特徴量入力＋Train target＋ALL＋truncation、3cutoffs）PASS。財務source timezoneは監査時の比較だけJST wall-dateへ正規化し、original componentは一切変更していない。full scientific inputs/artifacts/source hashesとcompleted runの保存物を照合済み。phase順序とblend trial前の診断保存を照合済み。

未定義のsector時系列相関: {'long_exposure_time_corr': 46, 'short_exposure_time_corr': 24}。定数/ゼロ分散の相関はNaNのまま保存し、平均は定義された観測のみ。portfolio P/L/Sharpe評価日は全eligible営業日で欠落なし。全部NaN/空の診断群はNaNを維持し、0のalphaと解釈しない。

4 scientific runsを保持。先行3runsはtarget hash監査/生成parquet許可/path保存の技術的失敗でcandidate0。第4runは唯一のcandidate1を保存後、financial timezone監査で停止。completion runは既存損益・bootstrap・scoresをhash一致のまま使用して因果性監査/報告を完了し、新performance試行0。科学計算の元コードとaudit-only修正版を別snapshotで保持した。

再現のaudit-only完了command: bounded1800s `python -m research.experiments.sn1_slow_diversification_complete --source <scientific run> --output <new prepared run>`。レポート/最終receiptのみはbounded180s `python -m research.experiments.sn1_slow_diversification_report --output <completed run>`。これらはweight/candidate探索を行わない。

make checkは既存metadataの不整合で失敗（logs/make_check.log）。本experiment metadataと既存Freeze129 hashesは独立に照合済み。検証不足を隠さず、既存無関係metadataは変更しなかった。
