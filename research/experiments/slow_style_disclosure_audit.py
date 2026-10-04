"""Supplemental target-free Date mutation and exact fiscal-pair audit."""
import argparse
import json
from pathlib import Path
import pandas as pd
from research import firewall,evaluation
from research.experiments import slow_style_descriptors as d
from research.experiments.slow_multifactor import exact,dump,sha
from stock_comp_2026.strategies.dm_slow_multifactor import features as slow

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output).resolve();c=json.loads(Path(args.config).read_text())
    assert c['diagnostic_only'] and not c['valid_evaluation'] and c['data_split']=='train'
    firewall.install()
    inputs={k:slow.canonical(pd.read_parquet(ROOT/c['input_dir']/(k+'_train.parquet'),
            columns=d.FIN_COLUMNS if k=='fins_statements' else cols)) for k,cols in slow.INPUT_COLUMNS.items()}
    f=slow.build_features(inputs,sector=False);r,z,ages,pairs=d.build(f.index,inputs['prices_daily_quotes'],inputs['fins_statements'])
    s=f.size_liquidity.rename('SLOW_CONTROL');res,_=d.neutralize(s,z);w,_=evaluation.weights(s);mw,_=d.matching_weights(w,z.bp,z.sales_growth)
    rows=[]
    for text in c['prefix_cutoffs']:
        cutoff=pd.Timestamp(text);fin=inputs['fins_statements'].copy();dates=fin.index.get_level_values('Date')
        shifted=dates.where(dates<=cutoff,dates+pd.Timedelta(days=17))
        fin.index=pd.MultiIndex.from_arrays([shifted,fin.index.get_level_values('Code')],names=['Date','Code'])
        changed={**inputs,'fins_statements':fin};ff=slow.build_features(changed,sector=False)
        rr,zz,_,_=d.build(ff.index,changed['prices_daily_quotes'],fin);ss=ff.size_liquidity.rename('SLOW_CONTROL')
        ress,_=d.neutralize(ss,zz);ww,_=evaluation.weights(ss);mm,_=d.matching_weights(ww,zz.bp,zz.sales_growth)
        prefix=s.index[s.index.get_level_values('Date')<=cutoff]
        for a,b in [(f,ff),(r,rr),(z,zz),(s,ss),(res,ress),(mw,mm)]:exact(a.loc[prefix],b.loc[prefix])
        rows.append({'cutoff':text,'mutation':'Every future financial disclosure Date shifted forward17calendar days; prefix unchanged',
                     'status':'PASS','bitwise':True,'rows':len(prefix)})
    p=pairs.loc[pairs.matched_previous_fiscal_period]
    assert (p.previous_disclosure<=p.Date).all() and (p.period_end<=p.Date).all()
    assert all(a-pd.DateOffset(years=1)==b for a,b in zip(p.period_start,p.previous_period_start))
    assert all(a-pd.DateOffset(years=1)==b for a,b in zip(p.period_end,p.previous_period_end))
    assert (ages.dropna()<0).sum().sum()==0
    obj={'status':'PASS','financial_date_mutation':rows,'exact_annual_pairs':len(p),
         'events_without_exact_comparator':int((~pairs.matched_previous_fiscal_period).sum()),'same_document_basis':True,
         'period_end_before_disclosure':True,'prior_disclosure_before_current':True,'no_future_carry':True,'negative_disclosure_age':False,
         'code_sha256':{'audit':sha(__file__),'descriptors':sha(d.__file__)},'targets_or_saved_results_read':False,
         'command':['.venv/bin/python','tools/run_bounded.py','--seconds','120','.venv/bin/python','-m',
                    'research.experiments.slow_style_disclosure_audit','--config',args.config,'--output',args.output],
         'opened':sorted(firewall.ACCESSES)}
    for base in [output,ROOT/c['report_dir']]:dump(base/'audit/disclosure_and_fiscal_audit.json',obj)
    print('PASS supplemental disclosure-date mutation and fiscal pairing audit',len(p))


if __name__=='__main__':main()
