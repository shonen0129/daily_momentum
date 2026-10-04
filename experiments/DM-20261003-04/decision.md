# DM-20261003-04: A — Structural Size/Liquidity（測定したstyleに限る）

[診断レポート](../../reports/DM-20261003-04/REPORT.md)。固定Train-only diagnostic、performance candidate0、採用/提出なし。

LongはShortよりB/Pが高い（z spread+0.285）。直接Growth exposureは小さいか負。B/P・Sales/Operating/Profit GrowthのLow/Mid/High全bucketでpooled SLOW spreadが残る。B/P×Sales Growth matchingのGrossSR2.138は元2.179を概ね維持。同一銘柄集合で元SLOW1.921、style residual2.004、2016除外でも1.928→1.976。Small Growth regimeだけで説明するH1はこの固定測定では支持されない。

2013のstyle共変動、Growth coverage82–90%/OLS共通集合77.4%、赤字前年/会計変更の欠損、期待Growthと実績Growthの差、raw Close/PIT shares/EPSのcorporate-action不整合、vendor financial vintageとDate-only開示時刻の限界を残す。H0の因果的証明や未観測style/regime影響ゼロの証明ではない。matchingのNet低下は仮想構成のturnover/cost増を伴い、改善候補として扱わない。

Scientific source: artifacts/DM-20261003-04/run-20261003T132116Z。Finalization: artifacts/DM-20261003-04/run-20261003T132635Z。初期技術的失敗4runを保持し、計算済み全結果をhash照合して保存完了。config/descriptor選択の結果後変更なし。

元SLOW/official parity、関連36test、future mutation/truncation18case、開示Date mutation3case、row shuffle、deterministic rebuild、exact index、fiscal comparability PASS。make checkは既存DM-20261002-04の非対応kindで停止。本実験configと旧Freeze129hashは個別PASS。

新candidate/filter/blend/Long-only/regime switching/Valid/提出物を作らず、この診断で終了。
