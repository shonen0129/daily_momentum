# DM-20260910-02: 採否記録

- 対象run / report: `run-20260909T161108Z` / `reports/DM-20260910-02/REPORT.md`
- 実行日 / 実試行数 / 累積known scoring trial数: 2026-09-10 / 4 / 60
- Hypothesis / Change from baseline: 21日RAW/RES returnの時系列・昇順vectorをElastic Netに入力し、単一DRI rankingでLong/Short両側をH0（M60 Long + equal FD Short）と置換できるかを比較した。
- Feature Set / Model / Parameters: 42特徴量、complete 21 observations、途中欠損は0.0 neutral。RAW/RES別のStandardScaler + ElasticNet、l1_ratio=0.5、2008–2010だけの日時系列CVでalpha=0.001を一回選択、年次expanding fit。D2/D3のみEWMA=0.25。
- Train Window / Evaluation Window: 2008-11-04–2016-03-31 Train。2011–2014の順方向4 fold、年末t+2越境2営業日purge。2015–2016-03は採否後の記述的確認のみ。

## 結果と判定

| Trial | Total Net SR | Long annual Net | Long Net SR | Short annual Net | Short Net SR | Turnover | 判定 |
|---|---:|---:|---:|---:|---:|---:|---|
| H0 | +0.7839 | +4.41% | +0.8423 | -1.04% | -0.2326 | 0.0584 | Reference |
| D1 RAW | -0.9916 | +2.70% | +0.6129 | -5.49% | -1.2738 | 0.0016 | Reject |
| D2 RAW EWMA | -0.9749 | +2.71% | +0.6189 | -5.43% | -1.2601 | 0.0020 | Reject |
| D3 RES EWMA | -0.9560 | +2.66% | +0.6032 | -5.34% | -1.2451 | 0.0020 | Reject |

RAW/RESの初期履歴CVはいずれも事前登録gridの最大alpha=0.001を選び、2011–2016の各annual fitで42本の係数はすべてゼロになった。したがってD1は年ごとのintercept以外のDRI cross-sectional rankingを持たず、D2/D3も年境界近傍のEWMA以外に実質的なcross-sectional edgeを持たなかった。

- Total Net Sharpe改善: D1/D2/D3とも0/4 fold（H0より各-1.7756/-1.7589/-1.7399 pooled）。
- Long改善: 各1/4 fold、pooled ΔLong annual Netは各-1.71pt/-1.69pt/-1.75pt。
- Short改善・Short annual Net正: 各0/4 fold・0/4 fold。pooled ΔShort annual Netは各-4.45pt/-4.39pt/-4.30pt。
- D1からD2へのEWMAはNet SRを+0.0167、D2からD3への残差入力は+0.0189改善したが、いずれも絶対値は負で採否基準に遠く及ばない。
- block bootstrapのH0差のTotal Net SR 95%区間はD1 `[-3.1960,-0.3347]`、D2 `[-3.1240,-0.3388]`、D3 `[-3.0952,-0.3335]`。既読Trainの診断であり、独立OOSの検定とは扱わない。

**Decision: D1/D2/D3を全てReject。** Full DRI replacement、DRI Long replacement、DRI Short replacementの事前基準を満たす候補はない。grid境界で全係数ゼロになったことは、この事前固定したdaily adaptation/penalty選択の失敗として記録する。結果後のalpha grid拡張、別window、別target、hybrid、非線形modelは実行しない。Champion H0を維持し、Freeze・submission・Valid評価は行わない。

## Required evidence

- H0は既存DM-20260910-01 artifactの809,636行予測とbitwise一致。
- raw return / beta / TOPIXのfuture mutationおよびtruncationに対し、2010-12-30、2012-06-29、2014-12-30 cutoffまでの86特徴量とD1/D2/D3予測はbitwise prefix-invariant。
- 各annual modelは当年1月1日より前、かつt+2実現済みのlabelだけでfit（12/12 `past_only=true`）。
- Long/Short cost allocationとP/L allocationは日次でTotalと一致。全対象予測はfinite、coverageは行削除なし。
- runtime firewallはTrain inputs、Train target、明示許可された過去H0 artifact、自run artifactのみを記録し、Valid/raw target readは0。
- `make test`: 51 passed。`run_bounded.py --seconds 1800` はexit 0、elapsed 121.95秒。初回のimport-path失敗run `run-20260909T161028Z` はラベル読込前に停止した失敗証跡として保持する。
