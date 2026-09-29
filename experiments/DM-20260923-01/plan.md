# DM-20260923-01: 高値近接度ファクターによるモメンタム戦略の高度化計画

Status: planned。事前固定完了。

## Hypothesis

従来の60日残差モメンタム戦略（Champion: DM-20260908, `res60s1` + EWMA 0.25）に対して、George & Hwang (2004) 等の学術研究で実証されている「高値近接度（High Proximity / 52-Week High Anomaly）」をファクターとして導入し、モメンタムの質的向上と上値抵抗の排除を図る。

## Why it should work / Why it may persist

* 投資家のアンカー効果と含み損ホルダーのやれやれ売り（買値撤退売り）によって、過去高値から大きく下落した銘柄には強い上値抵抗が存在する。
* 過去高値に近接している銘柄（High Proximity）は、この戻り売り圧力が薄く、モメンタムの持続性（Continuation）が高まる。
* 単純な二値ブレイクアウトではなく、過去高値に対する現在値の比率を連続スコア化（Centered Rank）することで、日次売買の急激なOn/Offを防ぎ、Turnoverを低く維持できる。

## Why it should survive t+1 open

* 高値近接度（$Close_t / \max High$）は株価水準の構造的レジスタンスに関わる中期的状態量であり、日次のわずかな寄り付きギャップで完全に消滅するマイクロストラクチャー情報とは異なる。
* 二値ブレイクアウト（翌朝の寄り天リスク）と異なり、連続的なランク情報であるため、翌営業日寄付（$Open_{t+1}$）から翌々営業日寄付（$Open_{t+2}$）の残差リターンにおいても正の予測力を持つと期待される。

## Expected turnover impact / Leakage risk / Complexity cost

* **Turnover / Cost**:
  高値近接度は連続値で、かつEWMA(alpha=0.25)で平滑化するため、急激な銘柄入れ替えは発生しない。H0 baselineのTurnover（約0.06〜0.08）と同等レベルを維持することを期待。
* **Leakage risk**:
  シグナル日 $t$ 引け時点の $Close_t$ および当日までの過去 $W$ 日の $High$ のみを使用する。
  `Adjustment*` は一切使用せず、生（raw）の OHLCV のみを使用する。
  未来参照、`bfill`、`center=True`、未来ターゲットの読み込みは一切行わない。
* **Complexity**:
  機械学習モデルではなく、決定論的な線形加重和およびゲート型のルールベース合成。自由度は低く、過学習リスクは最小限。

## Baselineと変更点

* **Baseline**: H0 (Champion DM-20260908, 60日残差モメンタム `res60s1` + EWMA 0.25)
* **変更点**:
  1. raw `prices_daily_quotes` から $W$ 日高値近接度比率 $R_{W, t} = Close_t / \max(High_{t-W+1 \dots t})$ を算出。
  2. $R_{W, t}$ を日次Centered Rank（[-1, 1]）に変換。
  3. モメンタムと高値近接度を合成（ブレンド、チルト、ゲート）し、EWMA(0.25)を適用。

## Train-only期間・有限候補・採否基準

* **データ範囲**:
  * Train期間: 2008-11-04 〜 2016-03-31（完全Train-only）
  * 初期ウォームアップ: 2008 〜 2010
  * 開発評価期間: 2011, 2012, 2013, 2014（4 fold）
  * 確認期間: 2015-01-05 〜 2016-03-31（記述的確認のみ、再選択には使わない）
  * Purge: 2営業日（$t+2$ ラベルの境界跨ぎ防止）
* **有限候補（全7 trials）**:
  * `H0`: Baseline Champion（`res60s1` EWMA 0.25）
  * `P60`: 60日高値近接度単体（$S_{60}$ EWMA 0.25）
  * `C1`: 短期ブレンド（$0.5 \cdot \text{res60s1} + 0.5 \cdot S_{20}$ EWMA 0.25）
  * `C2`: 中期ブレンド（$0.5 \cdot \text{res60s1} + 0.5 \cdot S_{60}$ EWMA 0.25）
  * `C3`: 52週ブレンド（$0.5 \cdot \text{res60s1} + 0.5 \cdot S_{250}$ EWMA 0.25）
  * `C4`: チルト（$\text{res60s1} + 0.25 \cdot S_{60}$ EWMA 0.25）
  * `C5`: 相互作用ゲート（$\text{res60s1} \times (1.0 + 0.5 \cdot S_{60})$ EWMA 0.25）
* **採否基準**:
  * Primary: 開発4 foldのうち3 fold以上で H0 より Net Sharpe が改善、かつ中央値 $\Delta \text{Net Sharpe} > 0$、かつ通算 Net Sharpe $> H0$。
  * Turnover制御: H0の1.5倍を超えないこと。
  * 停止条件: 7候補の評価完了をもって終了。結果を見てからの追加チューニング（p-hacking）は行わない。

## 既知データ・確認期間・過去の失敗

* 2011〜2014年および2015〜2016-03のデータは過去研究（DM-20260908〜DM-20260911-03）ですでに使用されており、真の未使用OOSとは呼ばない。
* 過去の実験（DM-20260909-01〜DM-20260911-03）では、日次リターンベクトルの正則化（DRI）や日次Turnover（DTI）、歪度などがTurnover過大またはfold一貫性不足で却下されている。
* 本実験は高次モデリングではなく、頑健な価格アノマリー（George & Hwang）の増分効果を検証する。

## 検証・実行コマンド

1. 静的リーク監査・Prefix-Invarianceテスト:
   `.venv/bin/python -m pytest -q tests/strategies/dm_high_proximity_momentum`
2. 実行環境準備:
   `.venv/bin/python tools/workspace.py prepare-run DM-20260923-01`
3. 実験実行（リミット付き）:
   `tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.high_proximity_momentum --config artifacts/DM-20260923-01/<run_id>/config.json --output artifacts/DM-20260923-01/<run_id>`
