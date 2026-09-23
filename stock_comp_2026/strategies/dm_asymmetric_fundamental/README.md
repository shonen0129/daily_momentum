# dm_asymmetric_fundamental

非対称Momentum / Fundamental ShortのTrain-only一次選別用実装。
研究計画は [DM-20260909-01](../../../experiments/DM-20260909-01/plan.md)。
採用・Freeze済み戦略ではない。`research_config.json` は事前固定のA heavy / λ0.5例であり、実験結果から選択した提出設定ではない。

- Long: 既存60行市場残差Momentum、skip1、EWMA .25。
- Short: 財務悪化×WeakPrice、段階的Vacuum/Participation、別系統のCFO負転Event。
- 財務は開示翌営業日から、同一期間・同一会計区分の比較。比率を開示単位で生成し450暦日で失効。
- `core.py` は旧戦略から独立コピーした計算。旧戦略・旧リリースは変更しない。
- BLASの行数依存丸めを避け、FD合成とImpact予測の加算順序を固定。日時列も固定型としてbitwise prefix-invarianceを検査する。
- 推論は自己完結。研究用driverやtargetには依存しない。公式の引数なし`predict()`はDate/Code indexとReturn1列を返す。

研究では次の明示的Train経路だけを使う。

```python
from stock_comp_2026.strategies.dm_asymmetric_fundamental.submission import predict
prediction = predict('TRAIN_ONLY_STAGE', split='train')
```

実験ドライバは `python -m research.experiments.asymmetric_fundamental --config <prepared run/config.json> --output <prepared run>`。
先に `tools/workspace.py prepare-run DM-20260909-01` で新規runを予約する。既存runは上書きしない。
正式な結果・全試行・停止理由は `reports/DM-20260909-01/` を参照。
