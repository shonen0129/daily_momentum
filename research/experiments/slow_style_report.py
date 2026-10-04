"""Render the fixed diagnostic bundle; interpretation supplied explicitly."""
import argparse
import json
from pathlib import Path
import shutil
import pandas as pd
from research.experiments.slow_multifactor import table, sha, dump

ROOT=Path(__file__).resolve().parents[2]


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--interpretation',required=True);args=p.parse_args()
    run=Path(args.run).resolve();c=json.loads((run/'config.json').read_text());m=json.loads((run/'run.json').read_text())
    assert m['status']=='completed' and m['actual_trials']==0 and c['diagnostic_only']
    interpretation=json.loads(Path(args.interpretation).read_text())
    r=ROOT/c['report_dir'];folder=r/'metrics';audit=r/'audit'
    perf=pd.read_csv(folder/'portfolio_metrics.csv',dtype={'scope':str})
    perf['q5_q1_spread']=perf.q5_daily_return-perf.q1_daily_return
    profile=pd.read_csv(folder/'style_profile.csv',dtype={'scope':str})
    sorts=pd.read_csv(folder/'double_sort.csv',dtype={'scope':str})
    cohort=pd.read_csv(folder/'cohort_contribution.csv',dtype={'scope':str})
    coverage=pd.read_csv(folder/'descriptor_coverage.csv',dtype={'scope':str})
    reg=pd.read_csv(folder/'regime_factor_ols.csv',dtype={'scope':str})
    def t(f,cols):return table(f,cols)
    selected=perf.loc[perf.scope.eq('POOLED')]
    year=perf.loc[perf.scope.str.isnumeric()&perf.diagnostic.isin(['SLOW_CONTROL','STYLE_MATCHED_SLOW','STYLE_NEUTRAL_RESIDUAL','SLOW_COMMON_SUPPORT'])]
    z=profile.loc[profile.scale.eq('z')&profile.scope.eq('POOLED')]
    annual=profile.loc[profile.scale.eq('z')&profile.scope.str.isnumeric()&profile.descriptor.isin(['bp','ey','sales_growth','operating_growth','profit_growth','roe'])]
    paragraphs=[f'# {c["experiment_id"]}: SLOW_CONTROL Size / Illiquidity versus style diagnosis','',
      f'結論: **{interpretation["classification"]}: {interpretation["label"]}**。'+interpretation['reason'],'',
      'Diagnostic-only、Train-only。新candidate・売買rule・filter・blend・submission・Valid評価は作成していない。H0/H1への診断であり、Size/Illiquidity premiumの因果的証明ではない。','',
      f'Run `{run.relative_to(ROOT)}`。config SHA-256 `{sha(run/"config.json")}`。試行は固定診断1bundle、performance candidate0。全Trainは既読development sample。','',
      '## 固定方法と比較条件','',
      '元SLOWは `dm_slow_multifactor.build_features(sector=False).size_liquidity` を無変更で再構築。−log(raw Close×PIT shares)、Amihud60/min40、元のwinsor/median/zとofficial ranking/weightをそのまま使用し、保存score809,636行・official weight・official daily Netをbitwise照合した。diagnostic descriptorには元SLOWのmedian補完を使わない。','',
      'B/P=Equity/shares/raw Close、E/P=Forecast EPS/raw Close。ROE=通期FY Profit/Equity、CFO/Assets=通期FYの同一statementのCFO/Assets、Equity/Assets=最新同一statement。Growthは通期Sales・OperatingProfit・Profitの前年比。開始/終了が正確に1年前、同じ連結区分/会計基準のTypeOfDocument、365/366日、期末が開示日以前、前年分母>0のみ。開示時点で既知の前年statementを使い、後のrestatementで過去を修正しない。比較不能な新FYはGrowthを欠損へ戻す。予想Growthや代替proxyへの変更なし。','',
      '各descriptorを日次1/99 linear winsor、同日平均・sample SDでstandardize。欠損を保持。tercileはaverage-tie percentileのceil(3p): Low1/Mid2/High3、tiesはCode順に分割しない。Q1–Q5 characteristicは元official quintile、Q1がlow SLOW、Q5がhigh SLOW。Long weighted meanとShort weighted meanは各side内の観測weightへrenormalizeし、weight coverageを別記。日次表は毎営業日、年別/pooled表は日次平均。','',
      '評価2011–2015、2016は2016-03までのpartial。各年末2営業日をpurgeし、t+1 Open→t+2 Openラベルが年/fold境界を跨がない。年率P/L=日次平均×252、Sharpe=平均/sample SD×sqrt252、RankIC=同日average-tie Spearman、t-stat=HAC5。会計はpurge前の連続panelで計算する。公式はtarget欠損行のcostも落とすため、all-position cost/netもCSVへ保存。Matched/neutralは仮想構成であり採用判断へ使わない。','',
      '## SLOW Long / Short style profile と Q1–Q5','',
      t(z,['descriptor','long_mean','short_mean','spread','long_weight_coverage','short_weight_coverage','q1','q2','q3','q4','q5','q_style_monotonicity']),'',
      '値はwinsor後の断面z。spread>0はLongが高いcharacteristic。B/PまたはE/Pが低いことだけでGrowthとは断定しない。全raw比率、年別、日次平均・coverageは [style_profile.csv](metrics/style_profile.csv) と [daily_characteristics.csv](metrics/daily_characteristics.csv)。','',
      '## Growth / Value bucket内のSLOW spread','',
      t(sorts.loc[sorts.scope.eq('POOLED')],['descriptor','bucket','mean_spread','annual_spread','spread_t_hac5','gross_sharpe_spread','spread_days']),'',
      '各style tercile内でSLOWをaverage-tie再rankし、等weight Q5−Q1のforward市場残差returnを取る。公式portfolioのweight構成とは異なる条件付きspreadであり、新portfolioではない。日次quintile値・stock count、年別は [double_sort.csv](metrics/double_sort.csv) / [daily_double_sort.csv](metrics/daily_double_sort.csv)。','',
      '## Style matching / OLS residual','',
      t(selected,['diagnostic','gross_sharpe','net_sharpe','rankic','rankic_t_hac5','q5_q1_spread','annual_gross','annual_net','turnover','annual_long','annual_short','max_drawdown']),'',
      'STYLE_MATCHED_SLOWはB/P×Sales Growth3×3cellで元official Long/Shortをmatch。各cell共通mass=min(元Long mass,元Short mass)、side内relative weightを保持し、総side massを元Long/Shortの小さい方へscale。VALUE_MATCHED_SLOWは固定B/P-only3cellの補助診断。weight optimizationなし。bucket内の連続descriptor差・他style差は残るため「完全なstyle除去」とは呼ばない。欠損cellと片side-only cellを除外し、その影響も含む。','',
      'STYLE_NEUTRAL_RESIDUALは同日のSLOW scoreをintercept+固定8descriptorへunregularized OLS。complete casesのみで、targetは使わない。residualを同じcomplete-case universe内でofficial quintile weightへ変換し、それ以外はweight0。SLOW_COMMON_SUPPORTは同じ銘柄集合で元SLOWをrankする基準。common supportとの比較がstyle控除の診断であり、full universeとの差にはcoverage効果が含まれる。退場時costをfull panel上で保持。MatchedのRankIC/Q値はactive original score/quintileの参考で、matching後の新scoreではない。','',
      t(year,['scope','diagnostic','gross_sharpe','net_sharpe','rankic','annual_gross','annual_net','annual_long','annual_short','turnover']),'',
      'すべてのfold/year/pooled/ex2016でGross/Net、Annual Cost、Turnover、RankIC/HAC/hit、Q1–Q5 return/monotonicity、Long/Short、DDを [portfolio_metrics.csv](metrics/portfolio_metrics.csv) に保存。元SLOW、MOM60とcommon-support差分は [incremental.csv](metrics/incremental.csv)。Residualのquintile spreadはQ5 daily return−Q1 daily return。','',
      '## 年別style exposure / regime attribution','',
      t(annual,['scope','descriptor','long_mean','short_mean','spread','long_weight_coverage','short_weight_coverage']),'',
      t(reg.loc[reg.factor.eq('Growth_minus_Value')],['scope','factor','correlation','beta','r_squared','intercept_annual','factor_annual_return']),'',
      '固定factor: 同じuniverseでB/P tercile High−Low=Value、Sales Growth tercile High−Low=Growth、Growth−Value=両者の差。上表は元SLOW daily Grossへのintercept付きOLS。ValueとGrowthを個別に回帰した参考表も保存。同じ銘柄/targetを使うfactorとの同時相関は機械的共有・共通shockを含み、独立した因果説明/外部factor回帰ではない。年別factor meanを合わせてregimeの向きを見る。','',
      '## Long-side / Short-side cohort contribution','',
      t(cohort.loc[cohort.scope.eq('POOLED')&cohort.descriptor.isin(['bp','sales_growth','roe','market_cap','amihud'])],['descriptor','side','bucket','average_weight','stock_days','annual_gross','annual_net']),'',
      'bucket0はMISSING。元official side weightのaverage massとstock-days、signed gross/netを保存。Long/Shortのmarket cap、Amihud、全styleの分布は [book_distributions.csv](metrics/book_distributions.csv)（absolute book weightによるp10/p25/p50/p75/p90）、年別全cohortは [cohort_contribution.csv](metrics/cohort_contribution.csv)。各descriptor内の全bucketは元side gross/netに1e−12で照合。exit costは現在日descriptor cohortへ帰属、stock-daysは現在active sideだけを数える。cohortからfilterを作らない。','',
      '## Coverage / PIT・corporate-action制約','',
      t(coverage.loc[coverage.scope.eq('POOLED')],['descriptor','stock_days','finite_raw','finite_z','coverage']),'',
      '年度・Long/Short weight coverageも保存。Growthはpositive prior denominatorの通期比較であり、赤字→黒字や会計基準/決算期変更を網羅しない。Sales Growthは実績売上成長であり、市場が期待するSmall Growth分類そのものではない。annual descriptorは次の開示まで古くなる; [disclosure_age_summary.csv](metrics/disclosure_age_summary.csv)。同日のDate-only開示は23:59:59 JSTで利用可能と仮定し、翌寄付前に計算。公開時刻は復元不能。','',
      'raw Close×最後の開示shares（自己株式込み）とForecast EPS/raw Closeはsplit/issuance前後のshare basisが一時不整合となり得る。AdjustmentFactorは発生日を記録する診断にだけ読み、SLOWやdescriptorの遡及補正には使わない。B/P・E/Pは元のper-field past finite carryなので報告vintageが混在する場合がある。financial vendor snapshotの過去restatement vintageをDateだけで独立に保証できない。通期ROEは平均Equityベースではなく期末Equity。これらを踏まえてH0/H1を解釈する。','',
      '## Causality / 再現性と完了記録','',
      'Future mutation/truncation:2009-03-31（Growth warmup）、2012-06-29、2015-12-30。financial（値・fiscal metadata）、raw Close/turnover、raw return、PIT listedを個別/一括改変し、suffix行削除・追加も実施。各cutoffでfeature、raw/z、元SLOW、residual score、matching weightをindex/列/dtype/NaN含むfloat64 bitで比較。row shuffle、再build、indexも検証。補助検査では未来の全financial開示Dateを17日後へ移し、同じ3cutoffでbitwise一致、2,523組の年度対応/開示順序とnonnegative disclosure ageを確認した。[disclosure/fiscal audit](audit/disclosure_and_fiscal_audit.json)、[prefix audit](audit/prefix_invariance.json)、[target-free build](audit/target_free_build.json)、[firewall](audit/firewall.json)、[source scan](audit/source_scan.json)。有限cutoffの証拠でありvendor vintageや全入力への数学的証明ではない。','',
      interpretation.get('verification',''),'',
      '初期4runの技術的失敗を保持。1件目は初期期間の空OLS table、2件目はtargetの事前hash-read検出で損益前に停止。3件目は損益計算後のDate列名欠落で停止。4件目は全診断・監査完了後、自作parquetをreportへ複写する際のfirewallで停止した。科学計算元はrun-20261003T132116Zで、run-20261003T132635Zがcode snapshot/config/結果hashを照合して保存を完了。[saved-result finalization](audit/saved_result_finalization.json)。3/4件目のportfolio metrics CSVはbyte-identical。config/descriptor選択・score・matching・OLS定義の結果後変更なし。[technical failures](../../experiments/'+c['experiment_id']+'/technical_failures.json)。performance trial0。','',
      '## 診断の解釈','',*interpretation['observations'],'',
      'この結果から新candidateを作らず終了する。']
    (r/'REPORT.md').write_text('\n'.join(paragraphs)+'\n')
    (r/'interpretation.json').write_text(json.dumps(interpretation,ensure_ascii=False,indent=2)+'\n')
    shutil.copyfile(Path(__file__),run/'code_snapshot/research/experiments/slow_style_report.py')
    dump(run/'audit/report_generation.json',{'source':str(Path(__file__).relative_to(ROOT)),'code_sha256':sha(__file__),
         'interpretation_sha256':sha(args.interpretation),'report_sha256':sha(r/'REPORT.md'),'no_additional_fit_or_evaluation':True})
    shutil.copyfile(run/'audit/report_generation.json',r/'audit/report_generation.json')
    print(r/'REPORT.md')


if __name__=='__main__':main()
