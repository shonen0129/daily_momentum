# DM-20260910-02: Full Daily Return Information Long / Short

Status: planned。設定の正本は `config.json`、戦略仕様正本は
`docs/strategies/投資戦略仮説0910-02.md`。公式ルールおよび `AGENTS.md` を最優先する。

## Hypothesis

Cakici et al. (2026) の Daily Return Information (DRI) を、過去21営業日の時系列return vectorと同じreturnの昇順vector（計42特徴量）から翌営業日残差returnを予測するElastic Netとして日次competitionへ適応する。High DRIをLong、Low DRIをShortとする単一の全universe rankingが、現Champion H0（M60 Long + equal FD Short）をLong側、Short側、Totalのコスト控除後で置換できるかを検証する。これは原論文の月次予測の直接replicationではない。

## Why it should work / Why it may persist

直近日次returnの順序は短期の価格圧力・流動性状態を、値の分布は極端なreturnと行動的歪みを表す可能性がある。二つを固定線形モデルで同時に使うことで、手作業の短期reversalやMAXの関数形を仮定せずに残存する断面差を捉える仮説である。全銘柄共通の市場成分を引いたRES版も、残差targetとの整合性を確認する限定比較とする。

## Why it should survive t+1 open

`raw_return[t]` は公式README上、t−1 Openからt Openまでの既知returnである。従ってt時点の21日vectorは全て利用可能であり、targetはt+1 Openからt+2 Openである。短期価格圧力・投資家反応・裁定制約がt+1寄付までに完全に解消しない場合にのみ効果が残る。t+1以降のreturn、target、raw targetはfeatureには使用しない。

## Expected turnover impact / Leakage risk / Complexity cost

日次DRIは月次の原論文より高回転になるおそれがある。D1でgross edge、turnover、cost、netを分離し、固定EWMA(0.25)のD2/D3でのみ抑制を確認する。21観測が欠ける行・上場直後・再上場後は0.0のneutral scoreで残し、途中欠損もcomplete-window要件で同様に扱う。特徴量はraw return、beta、TOPIXだけを過去方向rollingで使い、年次scaler/modelは当年より前かつt+2実現済みのlabelだけでfitする。CPU Elastic Net、42列、年次fitであり外部通信/GPUは不要である。

## Baselineと変更点

H0はDM-20260909-02 T1を現Championとしてexact reproductionする。D1=RAW DRI、D2=D1にEWMA 0.25、D3=RES DRIにEWMA 0.25。official 5分位、weights、片道10bps、252年率化は変更しない。Momentum、Fundamental、Liquidity、Size、industry、他window、別平滑化、hybrid、非線形modelは一切追加しない。

SSRN原論文は年次expanding再推定を確認できたが、安全に再現できる詳細なpenalty選択手順は取得できなかった。そのため仕様第12節に従い、RAW/RESごとに2008–2010 initial historyだけを使う2個の日時系列validation blockで、固定l1_ratio=0.5および事前登録した5 alphaからMSE最小を一回選ぶ。以後の年次fit・候補選択で変更しない。

## Train-only期間・有限候補・採否基準

Trainは2008-11-04–2016-03-31。開発foldは2011–2014の4年、各年末でt+2が越境する最後の2営業日をpurgeする。fitは各評価年の1月1日以前のavailable labelだけを使うexpanding windowとする。D1/D2/D3はH0に対する4 scoring trialで、累積known scoring trialsは56から60となる。

Full replacementにはTotal pooled Net Sharpe > H0かつNet Sharpe改善が3/4 fold以上を要求する。Long replacementにはpooled Long NetとLong Net SharpeがH0超、Long改善3/4以上を要求する。Short replacementにはpooled Short Net > H0、Short改善3/4以上、median ΔShort Net >0を要求する。2015–2016-03はこれらの判定を保存後だけ、同一specの記述的確認に使う。既読Trainでありindependent OOSとは呼ばない。

## 既知データ・確認期間・過去の失敗

2011–2014は既に複数研究で参照済みであり、本実験は事前固定DRI adaptationの有限比較である。DM-20260909-03のfundamental拡張、DM-20260910-01のvaluation/quality/MAX shortは各々事前基準不通過で却下済み。今回の結果後にDRI+M60、DRI+FD、別return変換、別window・alpha・modelを追加しない。

## 検証・実行コマンド

`tests/strategies/dm_dri_long_short/` のcomplete-window、neutral、tie/決定性、静的source firewallを実行する。driverはraw/beta/TOPIXの3 cutoff future-mutation/truncationでDRI vectors、annual model prediction、final scoreのprefix-invarianceを確認し、target access/annual cutoff/scaler/coverage/Long-Short cost allocationをauditする。`make test` 後、`tools/run_bounded.py --seconds 1800 .venv/bin/python -m research.experiments.dri_long_short --config artifacts/DM-20260910-02/<run>/config.json --output artifacts/DM-20260910-02/<run>` を実行する。Valid/raw targetは読まない。Freeze、submission、Valid評価は今回の範囲外。
