"""Finalize interpretation from saved results only; no new scoring or trials."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import pandas as pd
from research import evaluation, firewall
from research.experiments.sector_momentum import metrics, table, sha, dump


def finalize(output):
    config=json.loads((output/'config.json').read_text());report=ROOT/config['report_dir'];folder=report/'metrics'
    firewall.install(allowed_artifacts=[folder/'event_study_panel.parquet'])
    original=pd.read_csv(output/'metrics/metrics.csv',float_precision='round_trip')
    mature=[]
    for strategy in ['SLOW_CONTROL','SLOW_FUND_EVENT','SLOW_CAUSE_AWARE','MOM60']:
        daily=pd.read_csv(output/f'metrics/daily_{strategy}.csv',index_col=0,parse_dates=True,float_precision='round_trip')
        mature.append({'strategy':strategy,'scope':'ALL_TRAIN',**metrics(daily.iloc[:-2])})
    matured=pd.DataFrame(mature)
    matured.to_csv(folder/'all_train_mature_metrics.csv',index=False)
    results=pd.concat([original.loc[original.scope!='ALL_TRAIN'],matured],ignore_index=True)
    results.to_csv(folder/'metrics.csv',index=False)
    results[['strategy','scope']+[k for k in results if 'long' in k or 'short' in k]].to_csv(folder/'long_short.csv',index=False)
    results[['strategy','scope']+[k for k in results if k.startswith('q')]].to_csv(folder/'quintiles.csv',index=False)
    increments=pd.read_csv(output/'metrics/incremental.csv',float_precision='round_trip')
    rows=[]
    for n,c in [(n,c) for n in ['SLOW_FUND_EVENT','SLOW_CAUSE_AWARE'] for c in ['SLOW_CONTROL','MOM60']]+[('SLOW_CAUSE_AWARE','SLOW_FUND_EVENT')]:
        a=matured.loc[matured.strategy==n].iloc[0];b=matured.loc[matured.strategy==c].iloc[0]
        rows.append({'strategy':n,'control':c,'scope':'ALL_TRAIN',**{'delta_'+k:a[k]-b[k] for k in matured if k not in ['strategy','scope']}})
    pd.concat([increments.loc[increments.scope!='ALL_TRAIN'],pd.DataFrame(rows)],ignore_index=True).to_csv(folder/'incremental.csv',index=False)
    # Fixed cohort differences, descriptive only. Event-study endpoints remain
    # exactly the pre-registered horizons and each year's h+1-session purge.
    summary=pd.read_csv(folder/'event_study.csv',float_precision='round_trip')
    panel=pd.read_parquet(folder/'event_study_panel.parquet')
    contrasts=[]
    pairs=[('FLOW_HIGH_MINUS_NORMAL','NO_FUND_WITHIN_NEG_HIGH_VOL','NO_FUND_WITHIN_NEG_NORMAL_VOL'),
        ('FRESH_UP_MINUS_DOWN','FRESH_UP','FRESH_DOWN'),
        ('INDUSTRY_DOWN_MINUS_NONNEG','NEG_MOVE_SECTOR_DOWN','NEG_MOVE_SECTOR_NONNEG')]
    for scope in summary.scope.unique():
        for horizon in [1,2,3,5]:
            local=summary.loc[(summary.scope==scope)&(summary.horizon==horizon)].set_index('cohort')
            y=panel[f'cumulative_residual_{horizon}']
            use=(panel.index.get_level_values('Date').year!=2016 if scope=='EX2016' else
                panel.index.get_level_values('Date').year==int(scope) if scope!='POOLED' else
                pd.Series(True,index=panel.index).to_numpy())
            for label,left,right in pairs:
                a=local.loc[left];b=local.loc[right]
                la=y.loc[use&panel[left]].groupby('Date').mean()
                rb=y.loc[use&panel[right]].groupby('Date').mean()
                joined=pd.concat([la.rename('left'),rb.rename('right')],axis=1).dropna()
                delta=joined.left-joined.right
                contrasts.append({'scope':scope,'horizon':horizon,'contrast':label,
                    'left_target_count':a.complete_target_count,'right_target_count':b.complete_target_count,
                    'event_weighted_mean_difference':a.cumulative_residual_mean-b.cumulative_residual_mean,
                    'common_date_mean_difference':float(delta.mean()),'common_date_hac5_t':evaluation.hac_t(delta),
                    'common_dates':len(delta)})
    pd.DataFrame(contrasts).to_csv(folder/'mechanism_contrasts.csv',index=False)
    pooled=results.loc[results.scope=='POOLED'].set_index('strategy')
    a=pooled.loc['SLOW_FUND_EVENT'];b=pooled.loc['SLOW_CAUSE_AWARE'];c=pooled.loc['SLOW_CONTROL']
    turnover=pd.read_csv(folder/'turnover_attribution.csv')
    q=turnover.loc[(turnover.strategy=='SLOW_CAUSE_AWARE')&(turnover.scope=='POOLED')&(turnover.dimension=='event_group')].set_index('group')
    event_turn=float(q.loc[['CURRENT_EVENT','PRIOR_EVENT_ONLY'],'average_daily_turnover'].sum())
    flow_contrasts=pd.DataFrame(contrasts).query("scope == 'POOLED' and contrast == 'FLOW_HIGH_MINUS_NORMAL'")
    text=['','## Interpretation and final verification','',
        f'**両候補REJECT。** Aはcontrolに対しannual Gross +{(a.annual_gross-c.annual_gross)*1e4:.3f}bp、annual Cost +{(a.annual_cost-c.annual_cost)*1e4:.3f}bp、annual Net {(a.annual_net-c.annual_net)*1e4:.3f}bp。Turnoverは{a.turnover/c.turnover:.3f}倍で1.25倍制約を超え、2011–2015のNetSR改善は0/5。fresh情報に限定しても今回のrank overlayはnet増分を残さなかった。',
        f'B−Aではannual Gross {(b.annual_gross-a.annual_gross)*100:.3f} percentage points、annual Cost +{(b.annual_cost-a.annual_cost)*100:.3f} points、annual Net {(b.annual_net-a.annual_net)*100:.3f} points。Flowはgrossから悪化し、追加costが損失を拡大した。B/control turnover={b.turnover/c.turnover:.3f}倍。Bの{event_turn/b.turnover*100:.2f}%のturnoverが当日または前日event-active銘柄に生じ、非event銘柄もrank displacementで入替えが増えた。short netもcontrolを下回る。',
        'Downward fresh revisionの次target平均はnegativeで2/3/5累積もnegative。一方、Upward fresh revisionの平均もpositiveではなく、up/down全体の対称的continuationは確認できない。これはknown Trainの観測関連で、因果的情報ショックの証明ではない。',
        '高出来高stock-specific下落の1-session event-weighted平均はnormal-volume群を約0.62bp上回るが、日付を揃えた平均差はnegative。2/3/5-session event-weighted差もnegative。両群自体はpositive residual平均を持つため、高出来高に固有の反転増分は弱く、安定したhalf-lifeを確定できない。日付を揃えた平均差/HAC5も保存し、結果から期間を選んでいない。',
        '',table(flow_contrasts,['horizon','event_weighted_mean_difference','common_date_mean_difference','common_date_hac5_t','common_dates']),
        '', 'Industry-contextのnegative-stock-move群はsector<0/>=0とも次target平均positive。context別の平均だけでindustry continuationを識別できない。この診断を理由にsector scoreやvetoを追加しない。Sectorをcontextへ置き、fresh fundとFlowを分けても今回の固定Bは低turnover anchorを改善しなかった。前回は別portfolio/rank/missing仕様なので、fresh versus heldの単独効果を因果的に分離した比較ではない。',
        '', 'Scientific runは112.68秒、peak RSS2.604GB（decimal）。レポートコピー時のみ、生成diagnostic parquetの許可登録漏れで失敗したrunを保持。登録を明示して計算済みresultsからcompletion runを作成し、追加performance trialは0、feature/anchor/parametersは不変。',
        'Train split末尾2日の有限label942行はt+2がTrain特徴量期間外となる。事前のyear/pooled/event-study purgeで採否対象から全て除外済み。最終報告のALL_TRAIN参考集計も末尾2sessionを除去した。元のunpurged参考集計は失敗scientific run/completion snapshotに監査用として保持し、選択には利用していない。Raw/β/marketから再構成可能な成熟Train label803101行はt+2 residualと誤差0。',
        '34テスト、real Train24 prefix cases、exact809636-row signal index/finite scores、adapter parity、official P/L、turnover/state accountingを確認。`make check`は既存DM-20261002-04のunsupported metadataで失敗。今回metadataと既存129 Freeze hashesは個別に照合。詳細は`audit/final_verification.json`。',
        '', '再現: scientific driverはconfig/outputをrunに指定してbounded1800s、report-only recoveryは同driver`--complete-from`（bounded180s）。保存済み結果の最終解釈・Train末尾maturity補正は`research/experiments/cause_event_overlay_report.py --output <completion run>`、最終receiptは`cause_event_overlay_verify.py --output <completion run>`（各bounded180s）。Historical Valid/Valid、提出zip/strategy releaseは実行していない。']
    with (report/'REPORT.md').open('a') as stream:stream.write('\n'.join(text)+'\n')
    exp=ROOT/'experiments'/config['experiment_id']
    with (exp/'decision.md').open('a') as stream:
        stream.write('\nFinal verification:34 tests/24 real-Train prefix cases PASS; unchanged saved anchor and rank-only portfolio, exact809636-row signals, official P/L and turnover/state reconciliation PASS. Both candidates improve NetSR in0/5 full years. All-fold/diagnostic t+2 maturity excludes terminal Train spillover; delivered ALL_TRAIN descriptive metrics also purged. Report-only failed run retained; completion adds0 trials. Existing make check blocked by DM-20261002-04 metadata; own metadata and129 Freeze hashes PASS.\n')
    dump(report/'audit/report_publication.json',{'status':'PASS','new_performance_trials':0,
        'scientific_source_unmodified':True,'mature_ALL_TRAIN_days':int(matured.days.iloc[0]),
        'reported_primary_and_fold_metrics_unchanged':True,'fixed_mechanism_contrasts_only':True,
        'report_script_sha256':sha(Path(__file__)),
        'report_metrics_sha256':{p.name:sha(p) for p in folder.glob('*.csv')}})
    print(json.dumps({'status':'PASS','decision':'REJECT_BOTH','extra_trials':0,'report':str(report.relative_to(ROOT))}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    finalize(Path(args.output).resolve())
