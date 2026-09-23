# DM-20260909-01: 非対称Momentum / Fundamental Short 一次選別

事前登録: 2026-09-09。ユーザー承認済み計画を実装。設定の正本は config.json。
仮説: docs/strategies/投資戦略仮説0909.md。公式ルールとAGENTS.mdが優先。

## 仮説・リスク・範囲

財務悪化の段階的反映が翌寄付以降にも残り、FD×WeakPriceがMomentum Shortを改善するか検証する。
Liquidity vacuumによる一時的下落は反転、十分な売買参加を伴う下落は継続、CFO前年比負転後はドリフト、という各仮説を公式t+1 Open→t+2 Open残差targetで直接検証する。
財務の低速更新は低turnoverを期待するが、日次rank・WeakPrice・liquidity・event開始終了はturnoverを増やしうる。
PIT・訂正・累計期間混在・古い財務・年次impact学習・再上場が主なリークリスク。
固定式主体、impactは既存年次ridge、CPUのみ。計算複雑性を抑え、ML統合・hysteresis・S4/S5・Long追加因子は除外。
成果は継続研究/保留/却下。Validとraw_targetは開かず、提出用Freezeを行わない。

## 定義

Longは既存res60s1 centered rank→EWMA .25をbitwise再現。M60はraw_return−beta×topixの前60観測行和、min60、skip1、既存segment reset。
財務は実績1Q/2Q/3Q/FY、標準期間長80–100/170–195/260–285/350–380日（終了−開始）。開示日の翌営業日から使用する。
YoYは同一期間種別・連結区分・会計基準、前年対応開始/終了/期間長の差各7日以内。未来の訂正版を遡及しない。
CFO/AssetsとNetCashProxyは各々同一開示の必要項目から計算。450暦日で失効、欠損開示では鮮度更新せず再上場でreset。
D=rank(-CFOAssets YoY差)、W=rank(-CFOAssets)は当日×期間種別、F=rank(-(Cash-(Assets-Equity))/Assets)は当日で順位化。
FDは(.5,.3,.2)または等重み。欠損成分0・重み再配分なし。WeakPrice=rank(-M60)。S0=FD×WeakPrice、Momentum不足は0。
B: S1=S0(1−γVacuum)。Vacuum=I(residual[t]<0)×正値内rank(impact[t])×正値内rank(-LiquidityShock[t−1])。
C: S2=S1(1+δParticipation)。Participationはresidual[t]<0、VolumeShock[t−1]>0、LiquidityShock[t−1]>=0、impact[t]<=0の全条件。
Impactは既存の前年までfitするridge推定を踏襲。活動入力lag1、未成熟時は過去60日平均。欠損確認情報は0。
Event: 比較可能な前年比CFOAssetsが非負→負。age0–20=1、21–40=.5、41–60=.25、以後0。S3=event×decay×WeakPrice。
最新比較可能決算がnonbadなら解除。同一イベントの訂正でageを更新しない。
基本合成L−λS。合成後平滑化候補はEWMA(raw Momentum rank−λS)でLongを二重平滑化しない。

## 期間・予算・段階

Train2008-11-04–2016-03-31、開発2011/2012/2013/2014の4fold。t+2が各foldを跨ぐ末尾2営業日をPL統計から除く。建玉/コストは連続系列上で計算し、年境界で再初期化しない。
2015–2016-03は既読再確認。候補設定を保存してから各family代表とbaselineだけを評価し、再選択しない。末尾2日は予測coverageのみ。
上限18本: baseline1、A重み2×λ(.25,.5,.75,1)8、選択raw Aの合成後EWMA1、B γ(.25,.5)2、C δ(.25,.5)2、Event λ4。
A通過時のみB、B通過時のみC。Eventは独立。後段で前段設定を固定。未実行枠を転用しない。
旧研究30 scoring trialsと既読Train期間を累積探索履歴として明示。新たな未使用holdoutは存在しない。

## 診断・判定

ラベルを開く前にcoverage/前年比較/freshness/期間/会計基準を監査。
財務成分・FD、FD×WeakPrice3×3、weak momentum内FD高低、有効財務で揃えた比較、PIT業種/期間/開示ageを診断。
公式5分位weight、片道.001、年率252。Long/Shortの正負weight変化から別々のcostを計算し総額一致を検査。欠損targetで落ちる公式costと全建玉costを併記。
Long固定補助診断: baseline positive weights固定、残余をShort S降順・baseline rank昇順・Code昇順で既存Short枠に割り当てる。公式scoreと明確に区別。
全fold/年でGross/Net SR、Gross/Net PL、cost、turnover、加算/複利DD、RankIC/HAC5/hit、Long/Short別PL/SR/turnover、Q1–Q5単調性、上下decile、構成重複、baseline/前段差分を保存。
一次選別: 同時ΔNetSR>0かつΔShortNetPL>0が3/4fold、medianΔNetSR>=.05、worstΔNetSR>=−.25、median turnover比<=1.25、medianΔLong年率NetPL>=−.005、Short高20%target<低20%が3/4fold。
tail母集団はMomentum有効かつ財務1成分以上有効。高20%はS>0も要求、tie平均rank。Eventも同じ母集団。空tailは通過扱いにしない。
通過を優先し、改善fold数→medianΔNetSR、.05以内なら単純さ→小さいλ/γ/δ→turnover。固定raw A代表1本のfinal EWMAも比較。
Bootstrap20日block/1000回/seed20260909。同日対応、95%CI。一次基準通過でも下限<=0なら保留、下限>0なら継続研究。B/C移行はCI前の一次基準による。
一次基準不通過は今回定義を却下（無効果の証明ではない）。確認期間は判断の再選択に使わない。

## 実装・検査・再現

新strategyとresearch/experiments/asymmetric_fundamental.pyを実装。CLIは--config/--output。
source scan、全入力future-mutation/truncation、PIT訂正/休日/変則/鮮度/欠損/ゼロ/再上場/Event境界、index/有限coverage/決定性/研究推論一致、baseline一致、公式会計照合を実行。
実Trainのcutoffは2010-12-30/2012-06-29/2014-12-30。各監査はlabel-free、全入力変更。全特徴・全候補のprefixをbitwise比較。
make check、make test、make check-freeze。prepare-run後に次を実行:

```sh
.venv/bin/python tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.asymmetric_fundamental --config artifacts/DM-20260909-01/<run_id>/config.json --output artifacts/DM-20260909-01/<run_id>
```

実行snapshot、hash、versions、audit、予測、全試行、失敗run、PL、bootstrap、採否をrunへ保存。人向けレポートはreports/DM-20260909-01、採否は本実験decision.md、却下理由はGRAVEYARDへ記録。
