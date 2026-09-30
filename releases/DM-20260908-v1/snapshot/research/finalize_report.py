"""Publish local evidence and deterministic submission zip; never select a model."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from research.evaluation import metrics,daily_account
from research import firewall

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/DM-20260908'
STRATEGY=ROOT/'stock_comp_2026/strategies/dm_trainonly'


def read(name):return json.loads((OUT/name).read_text())
def dump(path,obj):Path(path).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False))
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+
                     ['| '+' | '.join(str(v) for v in row)+' |' for row in rows])
def pct(x):return f'{100*x:.3f}%'
def metric_row(name,m):
    return [name,f"{m['gross_sharpe']:.3f}",f"{m['net_sharpe']:.3f}",f"{m['rankic']:.5f}",
            f"{m['turnover']:.4f}",pct(m['annual_cost']),pct(m['max_drawdown_additive'])]
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    firewall.install([OUT/'selected_train_predictions.parquet'])
    registry=read('experiment_registry.json'); byid={r['id']:r for r in registry}
    selection=read('selection_before_confirmation.json')
    selected=byid[selection['selected_id']]; base=byid[selection['baseline_id']]
    confirmation=read('confirmation.json')[selected['id']]
    continuous=read('continuous_metrics.json')
    qa=read('verification.json'); resources=read('submission_resources.json'); coverage=read('coverage.json')
    tests=ET.parse(OUT/'tests.xml').getroot()
    suites=list(tests.iter('testsuite'))
    test_count=sum(int(s.attrib['tests']) for s in suites)
    assert all(int(s.attrib.get('errors',0))+int(s.attrib.get('failures',0))==0 for s in suites)
    assert qa['status']=='PASS' and selection['confirmation_seen'] is False
    assert selected['id']=='M_res60s1_a0.25'
    # Descriptive initial Train years are recorded only after selection and verification.
    pred=pd.read_parquet(OUT/'selected_train_predictions.parquet')
    dates=pred.index.get_level_values('Date').unique().sort_values()
    target=pd.read_parquet(ROOT/'stock_comp_2026/input/target_1day_train.parquet',filters=[('Date','<=',dates[-3])])
    descriptive=daily_account(pred.iloc[:,0].reindex(target.index),target.iloc[:,0])
    descriptive.to_csv(OUT/'daily/selected_full_train_descriptive.csv')
    full_years=[{'year':int(y),'scope':'descriptive, not used to select',**metrics(v)} for y,v in descriptive.groupby(descriptive.index.year)]
    pd.DataFrame(full_years).to_csv(OUT/'full_train_descriptive_yearly.csv',index=False)
    headers=['Model / 期間','Gross SR','Net SR','RankIC','日次turnover','年率cost','最大DD（加算）']
    main_ids=['M_res20s1_a1','M_res60s1_a1',selected['id'],'C1_rule','C1_ml','B_lambda0.25','B_lambda0.5','B_lambda1.0','C2_ml','A_rank','A_raw']
    comparison=table(headers,[metric_row(i,byid[i]['metrics']) for i in main_ids])
    year_table=table(headers,[metric_row(f"{v['year']} 開発",v) for v in selected['folds']]+
                     [metric_row(f"{v['year']} 確認"+('（1〜3月部分年）' if v['year']==2016 else ''),v) for v in confirmation['years']])
    detailed=table(['年/期間','日数','年率Gross PL','年率Net PL','年率Long PL','年率Short PL','IC HAC-t','IC hit','Q単調性'],
                  [[v['year'],v['days'],pct(v['annual_gross']),pct(v['annual_net']),pct(v['annual_long']),pct(v['annual_short']),
                    f"{v['rankic_t_hac5']:.3f}",pct(v['rankic_hit']),f"{v['q_monotonicity']:.2f}"]
                   for v in selected['folds']+confirmation['years']])
    qtable=table(['年','Q1日次bp','Q2日次bp','Q3日次bp','Q4日次bp','Q5日次bp'],
                 [[v['year']]+[f"{v[f'q{k}_daily_return']*10000:.3f}" for k in range(1,6)] for v in selected['folds']+confirmation['years']])
    compare_fold=table(['Model','2011 Net SR','2012 Net SR','2013 Net SR','2014 Net SR','改善fold数','ΔNet SR中央値','ΔSR bootstrap95%CI'],
                       [[i]+[f"{v['net_sharpe']:.3f}" for v in byid[i]['folds']]+[byid[i]['improved_folds'],
                         f"{byid[i]['median_increment_net']:.3f}",f"[{byid[i]['bootstrap_vs_baseline']['low']:.3f}, {byid[i]['bootstrap_vs_baseline']['high']:.3f}]"] for i in main_ids[2:]])
    feature_names=['liquidity_level','liquidity_shock','volume_shock','pwv','vwp','am','pm','intraday_range','volume_ratio',
                   'm_pwv','m_vwp','m_liquidity','m_volume','vwp_intraday']
    for record in registry:
        fam=record['parameters']['family']
        record['feature_set']=([record['parameters']['momentum']] if fam=='Momentum' else
                               [record['parameters']['momentum'],'liquidity_shock_value','pwv'] if fam=='C1_rule' else
                               feature_names+(['momentum'] if fam.startswith('A') else []))
        record['model']=fam
        record['change_from_baseline']='see parameters and fold_incremental.csv; same official portfolio/cost/dates'
    dump(OUT/'experiment_registry.json',registry)
    flat=[{'id':r['id'],'decision':r['decision'],'diagnostic_only':r['diagnostic_only'],**r['metrics']} for r in registry]
    pd.DataFrame(flat).to_csv(OUT/'model_comparison.csv',index=False)
    pd.DataFrame([{'model':r['id'],'scope':'development',**v} for r in registry for v in r['folds']]).to_csv(OUT/'all_models_fold_year_metrics.csv',index=False)
    pd.DataFrame([{'model':selected['id'],'scope':'development',**v} for v in selected['folds']]+
                 [{'model':selected['id'],'scope':'confirmation',**v} for v in confirmation['years']]).to_csv(OUT/'selected_fold_year_metrics.csv',index=False)
    impact_audit=read('impact_crossfit.json')
    fold_audits={p.name:json.loads(p.read_text()) for p in OUT.glob('fit_audit_*.json')}
    for audit in fold_audits.values():
        for fold in audit['folds']+audit['calibration']:
            assert pd.Timestamp(fold['max_label_available'])<pd.Timestamp(f"{fold['year']}-01-01")
    log=['# DM-20260908 実験ログ','',
         '事前計画: ../../docs/research_plan_20260908.md。全30試行を保持。20本が選択対象、10本は診断専用。',
         'MLの判定は固定baselineと同じ開発営業日の対応比較。確認期間で候補を追加・再選択していない。','']
    for r in registry:
        log += [f"## {r['id']}",'',f"Date: {r['date']}; Decision: {r['decision']}",
                f"Hypothesis: {r['hypothesis']}",
                f"Model: {r['model']}; Feature Set: {', '.join(r['feature_set'])}",
                f"Parameters: `{json.dumps(r['parameters'],ensure_ascii=False)}`",
                f"Train: {r['train_window']}; Evaluation: {r['evaluation_window']}",
                f"Baseline差分: {r['change_from_baseline']}",'',table(headers,[metric_row(r['id'],r['metrics'])]),'',
                'Fold Net Sharpe: '+', '.join(f"{v['year']}={v['net_sharpe']:.4f}" for v in r['folds']),
                f"理由: {r['reason']}",'']
    (OUT/'EXPERIMENT_LOG.md').write_text('\n'.join(log))
    report=f'''# DM-20260908-v1 Train-only研究・最終選択

作成日: 2026-09-08。**最終候補は60日市場残差Momentum＋EWMA α=0.25。Liquidity / Microstructureの追加補正は採用しない。**
これはFreeze可能な研究候補の選択であり、収益性を確認した実運用モデルの採用ではない。
開発Net Sharpeは0.400だが、選択後のTrain内確認Net Sharpeは-0.088。統計的な採用根拠は不足している。
**Valid特徴量・Valid targetを開かず、raw targetはTrainを含めて開かず、Valid評価も実行していない。**
ルール確認時にREADMEの既掲載サンプル成績を読んだが、モデル選択には使用していない。

## 1. Source of Truth・期間・実行経路

AGENTS.md、docs/投資戦略案.md、stock_comp_2026/README.md、evaluate_script.pyを最初に確認した。
旧V2実装・ExperimentRegistryはこの作業フォルダに存在しないため、research/と本レポート配下に同等の追跡可能な記録を実装。
Git管理情報は作業開始時に存在せず、コード・設定・データはsha256で固定する。
公式READMEのLightGBM版には4.1.0の記載もあるが、実験環境は同梱requirements.txt指定の4.6.0に統一。提出推論にはLightGBM不要。

- 開発walk-forward: 2011、2012、2013、2014年の4fold、合計982日。過去から拡張学習し、各境界前2営業日のラベルをpurge。
- Momentum形状→EWMA→条件付き集計→C1→B→C2→A→事前固定感度検証の順。30試行（うち診断10）で終了。
- 開発結果は選択に使ったため、未使用OOSとは呼ばない。形状・平滑化の選択も同じ開発期間に依存する。
- パラメータ選択をselection_before_confirmation.jsonへ保存してから、2015-01-05〜2016-03-29の303日を確認。再選択なし。
- 2016年は59営業日の部分年。2008〜2010年の成績は最終選択後に記録する参考値のみ。
- Train配布target末尾2日は実際には有限値があるが、t+2がTrain境界を越えるため2016-03-30/31を全PL評価から除いた。予測coverageには含む。
- 全Trainは1,814日、473コード、809,636行。公式全期間ユニバース498銘柄に対し、ここではTrainに実在する全コードを検査した。
- 後続split用predict契約は合成データだけで検証。実際のValidの列・行coverage・速度は未確認。

## 2. 最終モデルの定義・選択理由

`r_res[t] = raw_return[t] - beta[t] * topix_return[t]`。
銘柄ごとに直近行を1行除外し、その前60観測営業日の残差リターンをsumする。
当日のaverage percentile rankから当日mean rankを引き2倍する。非有限値・履歴不足はこの順位スコアを0にする。
その後、銘柄別EWMA `S[t]=0.25*M[t]+0.75*S[t-1]`、adjust=Falseを適用。
コード再登場の取引日ordinal差が20を超えたときはrolling/EWMA履歴をリセットする。
したがって、通常はt-1〜t-60の窓だが、少数の行欠落があると「銘柄の60観測行」の窓になる。
60日窓、1日skip、alpha=0.25は選択前後で固定。lambda=0、gateなし、追加hysteresis/bufferなし、学習済み係数なし。

短いMomentumはturnoverが高くコスト負けした。平滑化60日候補は開発4年すべてNet Sharpeが正。
α=0.15はturnoverが低い一方、正のfoldは3/4だったため、事前の安定性優先ルールで0.25を選んだ。
B λ=0.25は3/4fold改善したがΔNet SR中央値0.032、bootstrap95%下限-0.062であり、改善幅>=0.10・CI下限>0等の採用条件を満たさない。
C1 MLは2/4fold改善・Δ中央値0.001程度で、単純モデルを置き換える根拠がない。
全Train単一Sharpeの最大化では選んでいない。

## 3. Momentumと各Modelの比較（開発2011〜2014）

{comparison}

各候補の差分は **選択Momentum M_res60s1_a0.25** をbaselineとして計算。
M_res20s1_a1は初期の単純Momentum参照、M_res60s1_a1は平滑化なしの同期間参照。
costは片道0.1%×公式ポジション変更量。day turnoverはΣ|w_t-w_prev|で、0.0646は約6.46%/日。

{compare_fold}

全30試行のGross/Net/IC/cost/turnover/DDはmodel_comparison.csv、全foldはall_models_fold_year_metrics.csv、
IC/Gross SR/Net SR/turnover/costのfold差分はfold_incremental.csv、各試行の仮説・設定・却下理由はEXPERIMENT_LOG.md。
診断専用のB λ0.4が高くても再選択しない。

## 4. 最終候補のwalk-forward・年別指標

{year_table}

{detailed}

Long/Shortは公式残差targetに対するcost控除前の寄与であり、実資産の無ヘッジ損益ではない。
開発期間Long年率+4.989%に対してShort年率-1.376%、確認期間Long+5.954%・Short-4.822%。Shortの弱さが残る。
2013年のNet SRは0.040しかなく、alpha近傍0.20/0.30では正foldが3/4に減る。安定性の根拠は強くない。

{qtable}

Q単調性は年別Q1〜Q5平均リターンと1〜5のSpearman相関。Q平均は日ごと等重み平均を年内で平均。
資産曲線の最大DDは初期0を含む加算PLの最大低下幅。複利DDもCSV/JSONに保存。
PL/cost年率は日次平均×252、Sharpeは日次標本標準偏差×√252。部分年も同じ換算であり実現年率の保証ではない。
RankICはtargetが有限の行だけで両系列を日次再順位化。IC t-statはNewey-West型HAC、lag5。

開発合算: Gross SR {selected['metrics']['gross_sharpe']:.6f} / Net SR {selected['metrics']['net_sharpe']:.6f}。
確認合算: Gross SR {confirmation['metrics']['gross_sharpe']:.6f} / Net SR {confirmation['metrics']['net_sharpe']:.6f}。
開発と確認は各区間冒頭を現金開始として測定し、各区間内の年境界ではポジション継続。
補助の連続2011〜2016-03系列はNet SR {continuous['metrics']['net_sharpe']:.6f}、初期売買コストを1回だけ計上（continuous_metrics.json）。
2008年からの全Train参考SRは{qa['smoke']['descriptive_full_train_sharpe_not_used_for_selection']:.6f}。これは選択に使っていない。
2008〜2016の全Train年別参考値はfull_train_descriptive_yearly.csvに保存。

## 5. 条件付き仮説検証・特徴量の採否

条件付き集計はML fit前に保存した。形状選択済みの平滑化前Mを使い、毎日の条件内でRankICを計算する。
これらも開発データの診断であり、追加の独立検定ではない。

| 特徴量/仮説 | 検証結果・理由 | 最終採否 |
| --- | --- | --- |
| 市場残差Momentum60・skip1 | raw/sector20、5/10/20日よりコストと期間安定性が良い | 採用 |
| EWMA α=0.25 | turnover0.164→0.065、開発Net SR-0.150→0.400 | 採用 |
| Raw Momentum / PIT sector residual20 | Net SR -1.878 / -2.089、改善なし。PITは同日同Code結合 | 却下 |
| 5/10/20日、current/skip2、等重み合成 | 指定9形状の比較でコスト・安定性が劣る。追加horizon探索なし | 却下 |
| Liquidity levelとshock | 通常60日medianと5/60比を区別。単体で最終採用せず | 却下 |
| Liquidity vacuum gate | vacuum条件のM ICは全4年正(0.0113,0.0084,0.0174,0.0163)。一律弱める仮説を支持せず、C1ルールは全4年悪化 | 却下 |
| Volume confirmation | 高volume群M ICは2011〜2013負、2014のみ正。低volume群が強い年もあり、事前の単純継続仮説は不安定 | 却下 |
| Expected impact / PWV / VWP | 過去年だけでlinear ridge fit、log(abs residual)を予測。rolling60日歴史関係も条件付き比較。安定した補正の利益は確認できず | 却下 |
| AM/PM・range・PM/AM volume | PM反転のICは寄付前約-0.044〜-0.066、競技区間では約-0.001〜-0.023に弱まる。AMは符号不安定。volume ratioには正ICもあるがML比較でコスト後の上積みは未確認 | 却下 |
| M×PWV/VWP/liquidity/volume、VWP×intraday | 14〜15特徴の浅いモデルで検証。Bの小幅改善は採用基準未達 | 却下 |
| C2 reversal、A direct rank/raw | 高turnoverでNet悪化。符号反転・直接予測へ自由度を増やす根拠なし | 却下 |
| C3 amplification、深いimpact木、追加horizon/interaction | 前段の補正優位性が不足し、有限探索方針により未実施 | 見送り |

Expected impactの説明変数は前日log売買代金・通常流動性・volume shock・volatility・PIT size代理。
提供raw_return[t]は前日寄付→当日寄付のため、当日引けまでのvolumeをその値動きの同時説明にしない。
過去年の5日おき固定日サンプルでridgeをfitし、当年にはOOS予測のみ使用。126過去日未満は過去60日平均のfallback。
年次fitの列平均・scale・係数はimpact_crossfit.jsonに保存。学習行自身のin-sample residualを後段学習へ渡さない。
Momentum calibrationも年次cross-fitのlinear mapping。B targetはrank(target)-calibrated_OOF(M)、単純なrank(target)-rank(M)ではない。
B correctionは当日CS rankへ変換し、Mと[-1,1]の尺度を揃えて固定lambdaを掛けた。

intraday_decay.csvの寄付前returnは、Trainの翌日raw_returnと当日raw Open/Close比から診断用に別計算。
これはfeature builderから分離し、未来リターンを特徴量へ渡していない。寄付前はrawリターン、競技targetは市場残差で、完全に同じリスク調整ではない。
各特徴量の独立した限界寄与を証明する全組合せablationは行っていない。上記却下は本リリースへの不採用で、効果不存在の証明ではない。

## 6. 過学習対策・統計的不確実性

事前計画: docs/research_plan_20260908.md。30試行を記録し、確認後に候補を追加していない。
LightGBMはdepth2/leaves4/60trees/minleaf500/lr0.05/l2=10/seed20260908/CPU2threads。
固定感度検証: alpha0.20/0.30、B lambda0.4/0.6、C1 gate倍率0.8/1.2、木48/72、minleaf400/600。
gate倍率はクリップが発動しない領域では単なる全体尺度変換となり、順位をほぼ変えない。この感度診断だけでgateの頑健性を主張しない。
Momentum60日の局所±20%窓感度は未実施。指定5/10/20/60比較までで停止した。

paired circular block bootstrapは同日baseline/candidateを対応させて20日block、1000回、seed20260908、95%CI。
Sharpe差を直接再計算し、平均PL差のt検定で代替しない。positive fractionは真の改善確率とは呼ばない。
自己相関に対する有限block近似であり、block長の感度や構造変化の保証はない。

DSRは[Bailey & López de Prado (2014) の原論文](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)の
日次SR・候補間SR分散・歪度・非超過尖度・観測数に基づく式を実装。
選択候補DSR={selected['dsr']['dsr']:.8f}（30試行）、100試行感度={selected['dsr_100_trials']['dsr']:.8f}。
候補群は相関し、段階的選択とコストで大きく異なるSR分布を持つため、この値は仮定依存の厳しい参考診断である。
既存サンプルの累積探索回数は不明。30は今回の実試行数であり、100も全履歴の補正を保証しない。
DSRは時系列依存を完全には補正しない。複雑なモデルの採用条件DSR>=0.95は満たされず、Momentumも「統計的に採用済み」とは主張しない。

## 7. コスト・フォールバック・境界条件

公式は5分位すべてに(q-2)/N/1.2のweightを付け、片道0.001×銘柄別weight差absを控除する。
0スコアは公式のrank(method=first)で分位に分けられるため、履歴不足の0埋めはフラットポジションを意味しない。
60日履歴充足率は{coverage['full_60day_momentum_history_fraction']:.4%}。全評価日に予測を出し、欠損日の除外で成績を改善していない。
targetがNaNの行では公式のgross-cost全体がNaNとなりコストも落ちるため、同じ挙動の公式netと、全weightに課金するnet_all_costを併記。
開発公式Net SR {selected['metrics']['net_sharpe']:.6f}、全cost控除Net SR {selected['metrics']['net_all_cost_sharpe']:.6f}。
確認期間では両者は一致。日次gross-cost=netは検査済み。
公式costは固定10bpsのみ。slippage/借株料/financing/強制買戻し/impactの独立内訳は未計測で、0とはみなさない。
上場廃止時のポジション清算、欠測ラベル時損失、寄付不成・値幅制限の実約定は公式採点の外であり、未補正。
raw volumeの分割歪みは研究したmicrostructure特徴のリスクだが、最終予測はvolume/価格水準を使わない。

## 8. リーク監査・テスト・実行性能

- source AST firewall: 新戦略の全Pythonで禁止調整水準、負/dynamic shift、center rolling、bfill、forward as-of、禁止ラベル参照を検査。
- runtime: pandas parquet読込境界＋Python open監査でValid/raw target拒否。研究の明示allowlist以外は使わない。OSレベルの汎用DLP保証ではない。
- 実Train future-mutation: 2010-12-30 / 2012-06-29 / 2014-12-30の3cutoff。全5入力の未来部分を変更し、24特徴と最終予測のprefixがbitwise一致。
- 合成: cutoffで未来行を切り落とす試験、行順入替、NaN/Inf/0除算、窓不足、code再登場、tie、label purge、校正とC1/B/Aの未来変更・決定性。
- 全{test_count}テストPASS、失敗・skipなし。tests.xml、verification.json、データ読込監査JSON、学習max_label_availableを保存。
- 公式smoke: Train featureだけが見える一時ディレクトリで公式load_prediction/align_prediction/compute_pl/compute_srを使用し、日次PL一致。
- Train 809,636行/1,814日/473コード、予測欠損0。研究結果と提出predictはbitwise一致。
- 単独Train推論約{resources['seconds']:.3f}秒、peak RSS約{resources['peak_rss_bytes_macos']/1024**2:.1f}MiB。このマシンでの観測でありValid/採点ホストの時間保証ではない。
- 研究全体deadline1800秒、全Train検証600秒、tests180秒、単独推論120秒。すべて期限内exit0。不要なネットワーク/GPUは使用しない。

## 9. 残るリスクとFreeze設定

確認Net SR負、ICのHAC t値が弱い、Short側損失、2013年やalpha近傍の脆さ、Trainの期間/ユニバースへの依存が残る。
498銘柄ユニバース自体の選定バイアス、ETF近似市場系列・配布betaの生成過程はここでは再構築していない。
prefix-invarianceは入力から先の因果性を検査したもので、配布データ生成の全工程を保証しない。
現状は研究候補のFreezeまでであり、利益が残る新しいLiquidity/Microstructure戦略を確立したとはいえない。
改善が確認できなかった結果も保持し、次のリリースで同じ開発/確認期間を未使用OOSとして扱わない。

Freeze対象は以下。具体値は提出frozen_config.json、ハッシュはfreeze_manifest.json。

1. Strategy ID DM-20260908-v1、選択trial M_res60s1_a0.25。
2. raw_return/beta/topixの入力、当日残差化、60観測行sum、skip1、min_periods60。
3. 当日centered percentile rank、非有限/窓不足0埋め、code間隔リセット規則。
4. EWMA alpha0.25/adjustFalse/初期状態、lambda0、gateなし、hysteresis/buffer/cost-aware updateなし。
5. 学習なし、seed20260908、開発2011〜2014の選択手順、確認結果を反映しないルール。
6. submission.py/features.py、predict契約、Train履歴warmup、後続split出力index。
7. Python3.11.15、numpy2.4.6、pandas3.0.3、pyarrow24.0.0、CPU実行。
8. 公式5分位weight・片道10bps・252年率化、同梱zipとデータ/コード/設定hash。

Validは未実行。外部提出・実取引は行っていない。最終候補の仕様を変える場合は別Strategy IDの研究リリースとする。

## 10. 成果物と再現

- [最終設定](../../stock_comp_2026/strategies/dm_trainonly/frozen_config.json)
- [全試行ログ](EXPERIMENT_LOG.md)、[全比較](model_comparison.csv)、[全fold指標](all_models_fold_year_metrics.csv)
- [fold差分](fold_incremental.csv)、[最終候補年別](selected_fold_year_metrics.csv)
- [条件付き集計](conditional_states.csv)、[intraday decay](intraday_decay.csv)
- [学習・特徴量実装](../../stock_comp_2026/strategies/dm_trainonly/features.py)、[モデル実装](../../stock_comp_2026/strategies/dm_trainonly/models.py)
- [実データ検証](verification.json)、[テスト結果](tests.xml)、[Freeze manifest](freeze_manifest.json)
- [再現コマンド](../../README.md)、[事前計画](../../docs/research_plan_20260908.md)

各学習モデルはmodels/に保存。提出zipは最終Momentumの推論に必要な4ファイルだけを同梱。
'''
    (OUT/'REPORT.md').write_text(report)
    grave=['# 却下実験索引','',
           'DM-20260908: Train-only。詳細・再現データは ../reports/DM-20260908/EXPERIMENT_LOG.md。','']
    grave += [f"- **{r['id']}** — {r['reason']}" for r in registry if r['decision']!='selected']
    grave += ['', '- **C3 / deep impact / new interactions** — 未実施。前段の安定したincremental improvementがなく探索予算を拡大しない。',
              '- **Liquidity vacuum / volume confirmation** — 条件付き効果が事前仮説と一致しない期間が多く、一律gateや符号反転を正当化しない。',
              '- **最終Momentumの実運用採用** — 保留。Train確認Net Sharpe -0.088、統計的証拠不足。研究候補のFreezeのみ。']
    (ROOT/'docs/experiment_graveyard.md').write_text('\n'.join(grave)+'\n')
    audit={'feature_scope':'new dm_trainonly feature builders (all 24 columns) and selected predictor',
           'source_firewall':'PASS','future_mutation':'PASS','index_nan_coverage_determinism':'PASS',
           'purged_model_fold_records':sum(len(x['folds']) for x in fold_audits.values()),
           'calibration_audit_records':sum(len(x['calibration']) for x in fold_audits.values()),
           'impact_years':len(impact_audit),'official_smoke':'PASS','unit_tests':test_count,
           'valid_evaluation':'NOT RUN','upstream_distribution_builder':'NOT AUDITED',
           'inference_resources':resources}
    dump(OUT/'audit_summary.json',audit)
    archive=ROOT/'stock_comp_2026/strategies/dm_trainonly.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in ['submission.py','features.py','frozen_config.json','README.md']:
            info=zipfile.ZipInfo(f'dm_trainonly/{name}',date_time=(2026,9,8,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            z.writestr(info,(STRATEGY/name).read_bytes())
    firewall.save(OUT/'report_data_access.json')
    code_paths=[ROOT/'AGENTS.md',ROOT/'README.md',ROOT/'requirements-research.txt',ROOT/'docs/投資戦略案.md',ROOT/'docs/research_plan_20260908.md',
                ROOT/'stock_comp_2026/README.md',ROOT/'stock_comp_2026/evaluate_script.py',ROOT/'stock_comp_2026/requirements.txt']
    code_paths+=list(STRATEGY.glob('*.py'))+list(STRATEGY.glob('*.json'))+list((ROOT/'research').glob('*.py'))+list((ROOT/'tests').glob('*.py'))+list((ROOT/'tools').glob('*.py'))
    artifact_paths=[p for p in OUT.rglob('*') if p.is_file() and p.name!='freeze_manifest.json']+[archive]
    manifest={'strategy_id':'DM-20260908-v1','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
              'selection_file':'selection_before_confirmation.json','valid_evaluation':False,
              'economic_adoption':'withheld; research candidate frozen',
              'selected_parameters':json.loads((STRATEGY/'frozen_config.json').read_text()),
              'code_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sorted(set(code_paths))},
              'artifact_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sorted(artifact_paths)},
              'train_data_sha256':read('data_hashes.json'),'environment':read('environment.json')}
    dump(OUT/'freeze_manifest.json',manifest)
    print(f'Frozen {manifest["strategy_id"]}: {len(manifest["code_sha256"])} code/config files, {len(manifest["artifact_sha256"])} artifacts',flush=True)
    print(OUT/'REPORT.md');print(archive)


if __name__=='__main__':main()
