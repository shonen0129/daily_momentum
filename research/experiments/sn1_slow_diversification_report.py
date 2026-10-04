"""Saved-result interpretation and final verification; no new trial/backtest."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from research.experiments import sn1_slow_diversification as d
from research import firewall


def finalize(output):
    run=json.loads((output/'run.json').read_text());config=json.loads((output/'config.json').read_text())
    assert run['status']=='completed' and run['actual_trials']==1 and run['new_performance_trials']==0
    report=d.ROOT/config['report_dir'];source=d.ROOT/run['scientific_source_run']
    parquets=[p for run_folder in [output,source] for folder in ['predictions','metrics'] for p in (run_folder/folder).rglob('*.parquet')]
    firewall.install(allowed_artifacts=parquets)
    for rel,h in run['artifact_sha256'].items():assert d.sha(output/rel)==h
    for rel,h in run['code_sha256'].items():assert d.sha(output/'code'/rel)==h
    for rel,h in run['audit_code_sha256'].items():assert d.sha(output/'audit_code'/rel)==h
    for name in ['plan.md','config.json']:
        assert d.sha(source/name)==d.sha(output/name)==d.sha(d.ROOT/'experiments'/config['experiment_id']/name)
    ordered=json.loads((output/'audit/phase_gates.json').read_text())
    expect=['plan_config_code_freeze','component_parity','orthogonality_diagnostics_saved','pure_weight_diagnostic_saved',
            'fixed_score_blend_trial_completed','bootstrap_completed','causality_audit_completed','decision_recorded']
    assert [x['phase'] for x in ordered]==expect
    assert all(x['actual_trials']==0 for x in ordered[:4]) and all(x['actual_trials']==1 for x in ordered[4:])
    audit=json.loads((output/'audit/prefix_invariance.json').read_text());assert audit['status']=='PASS' and len(audit['cases'])==27
    for name in ['component_parity','contract','purge','maturity','official_accounting','attribution','adapter_parity','verification','completion_parity']:
        assert json.loads((output/f'audit/{name}.json').read_text())['status']=='PASS'
    scores=pd.read_parquet(output/'predictions/strategy_scores.parquet')
    assert len(scores)==809636 and np.isfinite(scores.to_numpy()).all() and scores.index.is_unique
    for rel,h in json.loads((output/'audit/completion_parity.json').read_text())['all_saved_performance_artifacts_sha256'].items():assert d.sha(source/rel)==d.sha(output/rel)==h
    stats=pd.read_csv(output/'metrics/metrics.csv');boot=json.loads((output/'metrics/bootstrap.json').read_text())
    decision=json.loads((output/'metrics/decision.json').read_text());assert d.decisions(stats,boot)==decision
    attr=pd.read_csv(output/'metrics/diversification_attribution.csv')
    group=attr.loc[(attr.scope=='POOLED')&(attr.view=='EXCLUSIVE')].copy()
    cols=['group','count','forward_target_mean','DELTA_VS_SLOW_CONTROL_gross_annual','DELTA_VS_SLOW_CONTROL_net_annual','DELTA_VS_SLOW_CONTROL_turnover_daily',
          'DELTA_VS_SN1_H1_gross_annual','DELTA_VS_SN1_H1_net_annual','DELTA_VS_SN1_H1_turnover_daily']
    group[cols].to_csv(report/'metrics/primary_secondary_attribution_summary.csv',index=False)
    daily={n:pd.read_csv(output/f'metrics/daily_{n}.csv',index_col='Date',parse_dates=True) for n in [d.SN,d.SLOW,d.BLEND,d.VIRTUAL]}
    folds=json.loads((output/'audit/purge.json').read_text())['folds']
    # Reuse exact exchange dates from saved daily accounts and locked fold limits.
    dates=daily[d.SN].index[np.logical_or.reduce([(daily[d.SN].index>=pd.Timestamp(r['signal_start']))&(daily[d.SN].index<=pd.Timestamp(r['last_signal'])) for r in folds])]
    risk=[]
    for n,frame in daily.items():
        for scope,ds in d.scopes(dates)[:2]:
            s=frame.loc[ds]
            risk.append({'strategy':n,'scope':scope,'annual_net':s.net.mean()*252,'annual_net_volatility':s.net.std(ddof=1)*np.sqrt(252),
                         'daily_variance':s.net.var(ddof=1),'gross_sharpe':d.evaluation.sharpe(s.gross),'net_sharpe':d.evaluation.sharpe(s.net)})
    risk=pd.DataFrame(risk);risk.to_csv(report/'metrics/net_volatility.csv',index=False)
    o=pd.read_csv(output/'metrics/orthogonality_summary.csv');p=stats.loc[(stats.scope=='POOLED')&stats.strategy.isin([d.SN,d.SLOW,d.BLEND])].set_index('strategy')
    b,s=p.loc[d.BLEND],p.loc[d.SLOW]
    histories=[]
    for folder in sorted(output.parent.glob('run-*')):
        r=json.loads((folder/'run.json').read_text());histories.append({'run_id':r['run_id'],'status':r['status'],'actual_trials_recorded':r['actual_trials'],
            'new_performance_trials':r.get('new_performance_trials',r['actual_trials']),'failure':r.get('failure'),'source':r.get('scientific_source_run')})
    d.dump(report/'audit/run_history.json',{'runs':histories,'unique_performance_trials':1,'rescue_trials':0,'note':'early technical failures before score blend and audit-only completion retain all scientific artifacts'})
    # Counts of undefined correlations are explicit: constant exposures have no correlation.
    sectors=pd.read_csv(output/'metrics/sector_exposure_time_correlations.csv')
    secmissing={c:int(sectors[c].isna().sum()) for c in ['long_exposure_time_corr','short_exposure_time_corr']}
    verification=json.loads((output/'audit/verification.json').read_text())
    check_note=('make checkはPASS。' if verification['make_check_returncode']==0 else 'make checkは既存metadataの不整合で失敗（logs/make_check.log）。')
    check_note+=f"本experiment metadataと既存Freeze{verification['existing_freeze_hashes']} hashesは独立に照合済み。検証不足を隠さず、既存無関係metadataは変更しなかった。"
    text=['', '## Saved-result interpretation and final receipts', '',
          f'**REJECT**: tradable1:1 blendはSLOW_CONTROLより高く安定したNet Sharpeを作らなかった。Pooled年率Netは{(b.annual_net-s.annual_net)*100:.3f}ポイント増えたが、Net volatilityも増加しNetSRは低下。Gross改善だけで採用しない。低score/P/L相関と異なるDD深度は確認できたが、economic alpha源の独立性を証明した結果ではない。', '',
          d.table(risk,['strategy','scope','annual_net','annual_net_volatility','net_sharpe']), '',
          f'Blend turnover増分 {b.turnover-s.turnover:.6f}/day（{(b.turnover/s.turnover-1)*100:.2f}%増）、年率charged cost増分 {(b.annual_cost-s.annual_cost)*100:.4f}ポイント。MaxDD magnitude {abs(s.max_drawdown_compound)*100:.3f}% → {abs(b.max_drawdown_compound)*100:.3f}%。Long/Short Netは正でもNetSR/安定性条件を満たさない。', '',
          '群別増分は群のalphaを独立に推定した値ではなく、元2戦略の当日membershipで固定portfolioの会計を分解した観測。以下は互いに排他的なprimary/secondaryの年率寄与。全forward targetは公式t+1 Open→t+2 Open残差リターン。', '',
          d.table(group,cols), '',
          '対SLOWのSN1_ONLY_LONGは年率Net+1.1881ポイント、BOTH_LONGは+0.7351ポイント。一方SIGNAL_DISAGREEMENTは−1.3326ポイント、SLOW_ONLY_LONGは−0.2271ポイント。これらにneutral exitとShort各群を含めた合計がPooled Net差と一致する。disagreement vetoや群別weightの変更は行わない。', '',
          'Virtual NetSR2.0218はSN1より高いがSLOW2.0935には届かず、tradable blend1.9229はvirtualより低い。固定50/50から1:1 scoreへのranking interactionと追加turnoverが異なるportfolioを作るため、低相関をtradable増分の保証として扱わない。Secondary対SN1のpositive CIはPrimary対SLOWの失敗を救済しない。', '',
          f'27 real-Train prefix cases（各6特徴量入力＋Train target＋ALL＋truncation、3cutoffs）PASS。財務source timezoneは監査時の比較だけJST wall-dateへ正規化し、original componentは一切変更していない。full scientific inputs/artifacts/source hashesとcompleted runの保存物を照合済み。phase順序とblend trial前の診断保存を照合済み。', '',
          f'未定義のsector時系列相関: {secmissing}。定数/ゼロ分散の相関はNaNのまま保存し、平均は定義された観測のみ。portfolio P/L/Sharpe評価日は全eligible営業日で欠落なし。全部NaN/空の診断群はNaNを維持し、0のalphaと解釈しない。', '',
          '4 scientific runsを保持。先行3runsはtarget hash監査/生成parquet許可/path保存の技術的失敗でcandidate0。第4runは唯一のcandidate1を保存後、financial timezone監査で停止。completion runは既存損益・bootstrap・scoresをhash一致のまま使用して因果性監査/報告を完了し、新performance試行0。科学計算の元コードとaudit-only修正版を別snapshotで保持した。', '',
          '再現のaudit-only完了command: bounded1800s `python -m research.experiments.sn1_slow_diversification_complete --source <scientific run> --output <new prepared run>`。レポート/最終receiptのみはbounded180s `python -m research.experiments.sn1_slow_diversification_report --output <completed run>`。これらはweight/candidate探索を行わない。', '',
          check_note]
    (report/'REPORT.md').write_text((report/'REPORT.md').read_text()+'\n'.join(text)+'\n')
    receipt={'status':'PASS','decision':decision['decision'],'actual_unique_trials':1,'new_performance_trials':0,'rescue_trials':0,
             'phase_order':expect,'saved_performance_artifact_hashes':'PASS','plan_config_frozen':'PASS','exact_score_rows':len(scores),
             'real_train_prefix_cases':len(audit['cases']),'scientific_source_unmodified':True,'completed_run_unmodified':True,
             'historical_valid_access':False,'valid_evaluation':False,'report_script_sha256':d.sha(Path(__file__)),
             'report_additional_metrics_sha256':{p.name:d.sha(p) for p in [report/'metrics/net_volatility.csv',report/'metrics/primary_secondary_attribution_summary.csv']}}
    d.dump(report/'audit/final_receipt.json',receipt)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args();finalize(Path(args.output).resolve())
