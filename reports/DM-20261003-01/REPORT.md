# DM-20261003-01 — 株価下落の原因分解

**結論: A・B・Cを全て却下。3/3 performance trialsで終了。次段階へ進めるcandidateなし。**

2011–2015のNet Sharpe改善は全候補0/5。COMPOSITEのpooled ΔNet Sharpeは−8.9187、20session paired bootstrap95%CIは[−10.7961, −7.2336]。FLOWのGross Sharpe1.040はMOM60の0.613より高いが、turnover1.024/日、年率cost25.772%に対して年率gross2.077%で、net−23.695%となった。COMPOSITEも年率cost23.213%、net−22.079%。Short grossはA−5.569%、B−2.412%、C−3.524%で、MOM60−2.234%より全て悪化した。

固定3候補の採否: FUND_REV=REJECT, FLOW_REV=REJECT, CAUSE_COMPOSITE=REJECT.
2026-10-03 JST。全結果は既知Trainでの仮説検証。Historical Valid/Valid、符号反転、追加filter、救済候補、Freeze、外部提出は実施していない。
Run: `artifacts/DM-20261003-01/run-20261002T205924Z`。

## Pooled comparison

| strategy | rankic | rankic_t_hac5 | gross_sharpe | net_sharpe | annual_gross | annual_net | turnover | annual_cost | annual_long_net | annual_short_gross | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FUND_REV | -0.001317 | -0.558829 | -0.655462 | -0.804359 | -0.017421 | -0.021376 | 0.015803 | 0.003955 | 0.036165 | -0.055693 | -0.057541 |
| FLOW_REV | 0.004726 | 2.540276 | 1.040043 | -11.769978 | 0.020773 | -0.236951 | 1.024000 | 0.257723 | -0.084802 | -0.024121 | -0.152149 |
| CAUSE_COMPOSITE | 0.003551 | 1.571569 | 0.443945 | -8.610617 | 0.011346 | -0.220786 | 0.926026 | 0.232132 | -0.070558 | -0.035240 | -0.150228 |
| MOM60 | 0.007590 | 1.567643 | 0.613360 | 0.308092 | 0.032108 | 0.016128 | 0.063418 | 0.015981 | 0.046391 | -0.022335 | -0.030263 |
| SLOW_CONTROL | 0.008257 | 2.802064 | 2.179334 | 2.093538 | 0.080272 | 0.077119 | 0.012888 | 0.003153 | 0.075064 | 0.003525 | 0.002055 |

P/Lはdecimal fraction。年率=日次平均×252、Sharpe=sample SDで年率化、IC tはNewey–West/Bartlett HAC5。Q1=低score、Q5=高score。Long/Shortは符号付き市場残差寄与。SLOW_CONTROLは保存済みの記述参照のみで採用条件に不使用。

## Full years and 2016 partial

| strategy | scope | net_sharpe | annual_net | turnover | annual_long_net | annual_short_gross | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FUND_REV | 2011 | -0.491572 | -0.016067 | 0.016880 | 0.069083 | -0.083280 | -0.085150 |
| FUND_REV | 2012 | 0.165715 | 0.004461 | 0.016057 | 0.014498 | -0.007700 | -0.010038 |
| FUND_REV | 2013 | -0.179093 | -0.005076 | 0.014987 | 0.026054 | -0.029360 | -0.031130 |
| FUND_REV | 2014 | -1.356376 | -0.029349 | 0.014153 | 0.020892 | -0.048798 | -0.050241 |
| FUND_REV | 2015 | -2.575392 | -0.055274 | 0.015649 | 0.041712 | -0.095307 | -0.096987 |
| FUND_REV | 2016 | -1.699163 | -0.046357 | 0.021067 | 0.072460 | -0.116427 | -0.118817 |
| FLOW_REV | 2011 | -9.270744 | -0.212604 | 1.003065 | -0.045759 | -0.040882 | -0.166844 |
| FLOW_REV | 2012 | -13.227109 | -0.236126 | 1.059413 | -0.127731 | 0.024610 | -0.108396 |
| FLOW_REV | 2013 | -10.544024 | -0.238001 | 1.024190 | -0.085913 | -0.025130 | -0.152088 |
| FLOW_REV | 2014 | -14.879005 | -0.253343 | 1.012346 | -0.095329 | -0.031173 | -0.158014 |
| FLOW_REV | 2015 | -12.551342 | -0.242526 | 1.020369 | -0.073954 | -0.041108 | -0.168572 |
| FLOW_REV | 2016 | -11.421215 | -0.246236 | 1.024490 | -0.063351 | -0.055526 | -0.182885 |
| CAUSE_COMPOSITE | 2011 | -6.802114 | -0.186957 | 0.915848 | -0.027542 | -0.045794 | -0.159415 |
| CAUSE_COMPOSITE | 2012 | -8.332243 | -0.210602 | 0.933670 | -0.099757 | 0.006940 | -0.110845 |
| CAUSE_COMPOSITE | 2013 | -7.139571 | -0.207061 | 0.936073 | -0.075518 | -0.016267 | -0.131543 |
| CAUSE_COMPOSITE | 2014 | -12.962313 | -0.240407 | 0.929421 | -0.087998 | -0.037872 | -0.152409 |
| CAUSE_COMPOSITE | 2015 | -10.637279 | -0.250978 | 0.908965 | -0.069553 | -0.068402 | -0.181424 |
| CAUSE_COMPOSITE | 2016 | -7.096335 | -0.254794 | 0.950756 | -0.038136 | -0.098966 | -0.216658 |
| MOM60 | 2011 | 0.506792 | 0.029635 | 0.065571 | 0.075618 | -0.037842 | -0.045983 |
| MOM60 | 2012 | 0.636144 | 0.026788 | 0.065148 | 0.013081 | 0.021781 | 0.013708 |
| MOM60 | 2013 | 0.081809 | 0.005051 | 0.063355 | 0.038139 | -0.025160 | -0.033088 |
| MOM60 | 2014 | 0.910504 | 0.027522 | 0.060468 | 0.050474 | -0.015208 | -0.022952 |
| MOM60 | 2015 | -0.099053 | -0.005742 | 0.062057 | 0.045884 | -0.043947 | -0.051626 |
| MOM60 | 2016 | 0.067276 | 0.004639 | 0.065295 | 0.084217 | -0.071359 | -0.079579 |
| SLOW_CONTROL | 2011 | 2.728793 | 0.122760 | 0.013703 | 0.120853 | 0.003444 | 0.001907 |
| SLOW_CONTROL | 2012 | 1.033654 | 0.033888 | 0.013052 | 0.027510 | 0.007885 | 0.006378 |
| SLOW_CONTROL | 2013 | 1.896830 | 0.081311 | 0.014252 | 0.063015 | 0.019880 | 0.018295 |
| SLOW_CONTROL | 2014 | 1.664345 | 0.051361 | 0.011729 | 0.064063 | -0.011423 | -0.012702 |
| SLOW_CONTROL | 2015 | 3.267066 | 0.096957 | 0.011756 | 0.095971 | 0.002386 | 0.000986 |
| SLOW_CONTROL | 2016 | 2.003895 | 0.076413 | 0.012628 | 0.093747 | -0.015706 | -0.017334 |

## Bootstrap and gates

| contrast | point_delta | low | high |
| --- | --- | --- | --- |
| POOLED:FUND_REV-MOM60 | -1.112452 | -2.356879 | 0.050485 |
| POOLED:FLOW_REV-MOM60 | -12.078071 | -13.829747 | -10.481658 |
| POOLED:CAUSE_COMPOSITE-MOM60 | -8.918709 | -10.796099 | -7.233559 |
| EX2016:FUND_REV-MOM60 | -1.083831 | -2.347391 | 0.181869 |
| EX2016:FLOW_REV-MOM60 | -12.108719 | -13.911337 | -10.355741 |
| EX2016:CAUSE_COMPOSITE-MOM60 | -9.071470 | -10.993068 | -7.304443 |

Paired circular20-session/2000回/seed20261003/percentile95%。C−MOM60 pooledがprimary、A/Bはsecondary。EX2016も別保存。連結した適格営業日を再標本化し、年境界purgeのgapは連結する。既知Trainの標本不確実性であり、独立OOSや多重探索補正ではない。

- FUND_REV: full-year改善0/5。不通過: pooled_net_sharpe, ex2016_net_sharpe, full_year_improvements_4_of_5, bootstrap_lower_gt0, annual_net, short_gross, short_net.
- FLOW_REV: full-year改善0/5。不通過: pooled_net_sharpe, ex2016_net_sharpe, full_year_improvements_4_of_5, bootstrap_lower_gt0, annual_net, turnover_le_1_25x, short_gross, short_net, long_net_positive.
- CAUSE_COMPOSITE: full-year改善0/5。不通過: pooled_net_sharpe, ex2016_net_sharpe, full_year_improvements_4_of_5, bootstrap_lower_gt0, annual_net, turnover_le_1_25x, short_gross, short_net, long_net_positive.

## Mechanism: negative raw stock move

| component | sign | count | target_count | next_target_mean | rankic | rankic_t_hac5 |
| --- | --- | --- | --- | --- | --- | --- |
| FUND_REV_raw | NEGATIVE | 19175 | 19145 | -0.000147 | 0.014832 | 0.971826 |
| FUND_REV_raw | POSITIVE | 26221 | 26190 | 0.000376 | 0.005998 | 0.462174 |
| SECTOR33_SHOCK_raw | NEGATIVE | 173122 | 172178 | 0.000239 | 0.014652 | 2.412100 |
| SECTOR33_SHOCK_raw | POSITIVE | 97572 | 96874 | 0.000428 | -0.004790 | -0.714440 |
| FLOW_REV_raw | NEGATIVE | 31287 | 31285 | 0.000187 | -0.000236 | -0.016838 |
| FLOW_REV_raw | POSITIVE | 99158 | 99149 | 0.000428 | -0.003874 | -0.885341 |

この表は各raw componentの状態別の関連。日次ICは状態内で定義できた日のみ。単なるtarget平均の符号だけでContinuation/Reversalの識別や経済原因の因果性を確定しない。joint/marginal全状態とLong/Short寄与はCSVに保存。ゼロと欠測を独立状態に保持し、診断を候補に変換していない。Sectorのみの追加performance trialは行っていない。

## Primary questionsへの回答

1. **下方revision後のContinuation**: raw株価下落＋finite下方revision stateの19,175行（target19,145行）では翌target平均−1.47bp。既知の下方revisionが下落の継続と関連する部分的な証拠がある。ただし開示直後だけのevent studyではなく、次開示まで持続するstateを繰り返し観測した集計。negative-move subsetのraw FUND RankIC0.01211/HAC5 t1.733に対し、全株のA portfolio RankIC−0.001317/t−0.559、Net SR−0.804であり、単独で採用できるpredictive valueは確認できない。
2. **Sector-wide下落のContinuation**: negative stock move内のSector<0では翌target平均+2.39bp、Sector>0では+4.28bp。Sector component IC0.009482/t2.451は相対的なContinuationと整合するが、Sector下落後に平均negative targetが続くという絶対方向は確認できない。Sector-onlyの追加performance trialは行わず、tradable standalone Sector alphaを確定しない。
3. **Stock-specific abnormal-volume下落のReversal**: raw株価下落かつWithin<0のうちAbnormalVolume>0は99,158行、翌target平均+4.28bp。同じWithin<0でVolume normalは102,707行、+3.51bp。差は+0.77bpという記述的な関連で、原因の因果識別や統計的有意性の証明ではない。FLOW全体RankIC0.004726/HAC5 t2.540・Gross SR1.040は正だが、コスト後に残らない。下方revisionと同時に出るFlow状態では翌平均が負になる例もあり、出来高だけでtemporary shockを同定できない。
4. **MOM60よりNetを改善できるか**: 全候補がpooled/ex2016 Net SRとannual Netで劣る。2016 partialを除いても結論は変わらず、全候補4/5年改善条件を不通過。
5. **Short grossを改善できるか**: 全候補のpooled Short gross/netがMOM60より悪化。正方向への改善を確認できない。

FUND raw coverage43.951%、3要因全てfinite43.819%。欠測をneutral rankとして扱う固定設計はCode順の任意性を持つ。Aの補完行だけの年率Short gross寄与は−4.070%（finite行−1.500%）、Cの補完行のShort net寄与は−8.732%（complete行−6.291%）。この影響を仮説の経済的失敗と同一視しない。拒否対象は今回固定したproxy・coverage・rank・portfolio構成であり、原因分解という一般仮説の否定ではない。結果後のfield/volume/sector/weight変更で救済していない。

## Definitions and limits

τは共通の直前営業日。株returnは配布open-to-open過去returnの市場残差でありclose-to-close下落ではない。Volumeはτの通日raw出来高で、return区間の終点openより後の取引を含む。したがってmechanismは価格下落の厳密な会計分解や観測された売買主体の識別ではなく、固定proxyの検証。翌寄付までの遅れ込みで評価した。
FUNDは総額ForecastOperatingProfitのみ。同一fiscal start/end/過去のaccounting basisで比較し、開示時点のAssetsでscale。次開示まで状態を保持し、pair/scale不足やforecast欠測の開示でmissingへ更新。初回period forecastはmissing。NextYear予想は使わない。財務Dateにintraday clockが無いため当日23:59:59 JST availabilityで翌sessionから使用。各日時点の提供financial vintageが正しいというデータ契約に依存する。
Sector33はhistorical-date exact PIT/self-inclusive finite mean、min1。小sectorも許容する固定仕様で、membership変更後を過去へ遡及しない。AbnormalVolumeはlog1p当日から直前20観測中央値を引き、max(surprise,0)を掛けてWithinの符号を反転。No smoothing。raw Volumeのsplit/取引単位変化を因果的に補正する情報は利用していない。
欠測componentは同日medianで補完、Code順ordinal centered rank。これは経済情報ではなくcoverage契約。同値の予想据置・非高出来高Flow=0もCode順に分散し、合成にCode orderingが入り得る。raw coverage/大tie/補完行の損益は別保存。この実装上の分散を新alphaや原因識別の証拠と呼ばない。結果後のmissing/rank再設計はしていない。

## Audit and artifacts

全中間特徴量/3scoresの全入力源future mutation・joint mutation・truncationを3cutoffでbitwise照合。suffix値/NaN/zero、日付/fiscal/basis/sector変更、行削除、future-only stocksを含む。row shuffle、deterministic rebuild、exact index、finite coverage、explicit disclosure-before/after/fiscal/basis fixtures、PIT33 switch、Volume history、research/adapter/standalone一致を検証。audit/*とtestログを参照。動的検査は試したcutoff/inputでの証拠。
公式5分位weightと全Train日次Net P/Lはbitwise一致。Long+Short cost/netは1e−15以内で照合。joint状態寄与は全bookとnegative subsetを1e−12以内で照合。公式はmissing target行のcostを落とすためall-position conservative Net/Costも保存。毎年末2sessionをpurgeしてt+2終点をfold内へ固定。保持/costは完全Train系列上で算出してから評価日を選ぶ。
`metrics/metrics.csv`全指標、`fold_metrics.csv`/`year_metrics.csv`、`incremental.csv`、`long_short.csv`、`quintiles.csv`、`bootstrap.csv`、`raw_coverage.csv`、`ties_daily.csv`、`raw_component_diagnostics.csv`、`mechanism_joint_states.csv`、`mechanism_marginal_states.csv`、`imputed_attribution.csv`、`daily_*.csv`。runにplan/config/code/data/environment hashesと予測、状態panelを保存。

## Final contract verification and workspace checks

新strategy32テスト合格。24件の実Train全入力future-mutation/truncation caseは全中間・全scoreをメモリ上でbitwise照合済み。809,636行のoriginal raw indexとの完全一致と、公式`load_prediction()`の引数なし呼出しも合格。実研究149秒、peak RSS2.065GB（約1.92GiB）。release zip・後半splitの時間/メモリは未測定で、Train専用研究adapterの検証範囲である。

performance評価後、adapter既定data_dirを`input`から`.`へ、smoke呼出しのcwdをTrain stageへ変更した。これは公式graderの作業ディレクトリ契約に合わせる変更。feature source、plan/config、全中間のメモリ再構築と全3scoreは変更なし。追加performance trial0。科学的run49artifactのhashを再照合し、完了済みrunは更新していない。最終adapter/code hashesは`audit/adapter_directory_verification.json`、新テストは`audit/final_tests.log`。

保存parquet比較の初回補助検証はFLOW_REV_rawのNaN内部表現6,161件で失敗し、その記録を保持。原因はparquetのNaN正規化で、有限値のbit差0・欠損位置差0。メモリ上のprefix-invariance比較に許容差やNaN正規化を追加していない。保存artifactの比較では有限値bitとNaN maskを明示的に別検査し、全3有限scoreはbitwise一致。失敗記録は`audit/adapter_verification_failed.json`と`audit/parquet_nan_diagnostic_failure.log`。

`make check`は既存DM-20261002-04のmetadata kind `historical_valid_descriptive_backtest`がworkspace CLI未対応のため失敗。この既存metadata/研究結果は変更していない。新実験の構成検査と既存Freeze snapshot129hashを個別に照合して合格。詳細は`audit/workspace_checks.json`。今回Historical Valid/Validデータは読んでいない。
