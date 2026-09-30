# Stock Competition 2026: Train-only Momentum研究

作業規約は [AGENTS.md](AGENTS.md)、公式仕様は [コンペREADME](stock_comp_2026/README.md)、
研究仮説は [投資戦略案](docs/投資戦略案.md) を参照。

今回の結果は [Train-only最終レポート](reports/DM-20260908/REPORT.md)。
最終候補は **60日市場残差Momentum＋EWMA α=0.25**。
ML補正の安定した上積みは確認できず、確認期間のNet Sharpeも負であるため、実運用の採用根拠は不足。
Validは未評価。候補と提出コードはFreeze済み。

## 再現

Python3.11とstock_comp_2026/requirements.txtの固定バージョンを使用。

```sh
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements-research.txt
.venv/bin/python tools/run_bounded.py --seconds 180 .venv/bin/python -m pytest -q tests
.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.run_trainonly
.venv/bin/python tools/run_bounded.py --seconds 600 .venv/bin/python -m research.verify_trainonly
.venv/bin/python tools/run_bounded.py --seconds 120 .venv/bin/python -m research.benchmark_submission
.venv/bin/python tools/run_bounded.py --seconds 120 .venv/bin/python -m research.finalize_report
.venv/bin/python tools/run_bounded.py --seconds 120 .venv/bin/python tools/check_freeze.py
```

`research.run_trainonly` は事前に固定した30試行を再現する。確認期間を見た後の調整経路はない。
スコアを再現する場合は新しい作業コピーを使い、Freeze済みの証拠ファイルを保持する。
`verify_trainonly` はTrainだけを配置した一時ディレクトリと末尾2日を除いたTrain targetで公式採点APIを照合する。
公式evaluate_script.pyは引数省略時にValid targetを選ぶため、この研究のsmokeには専用スクリプトを使う。

提出候補: [dm_trainonly](stock_comp_2026/strategies/dm_trainonly/)、[Freeze設定](stock_comp_2026/strategies/dm_trainonly/frozen_config.json)。
ローカルの提出zip作成まで行い、外部への提出・Valid評価は行っていない。
