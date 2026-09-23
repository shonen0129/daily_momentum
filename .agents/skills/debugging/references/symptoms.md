# 症状別診断

該当する節だけを使う。実行はTrain-only firewallと専用stage内で行う。
配布 `evaluate_script.py` は既定でValidを選ぶので、既定入力のまま再現に使わない。

## 提出契約・index不一致

`predict()` は引数なしで数値1列のDataFrameを返し、MultiIndex名は
`['Date', 'Code']`。返却直前の型・列・indexと最初に契約が崩れた処理を確認する。

行不足は読み込み、join、dropna、履歴不足の処理でどこから発生するか追う。
単なるreindexや一律0埋めでcoverageだけを満たさず、仕様上のfallbackを検証する。
対象indexを予測側で得るためにValid targetを読み込まない。

## 全銘柄同値・RankIC未定義・分位例外

同値化の直前の分散と欠損率を確認し、0埋め・誤ったgroupby・join失敗を切り分ける。
全銘柄同値の日はRankICが未定義になり得る。

分位分割だけのtie-breakと予測シグナル自体の改変を区別する。
`rank(method="first")` は行順に依存するので、一律適用で解決した扱いにしない。
公式weight計算・戦略仕様の同値処理に合わせ、入力順を変えた再現例でも確認する。

## Grossに比べNetが悪い・コスト異常

weightのscale、日付alignment、初日の扱い、turnoverの定義、コスト率の単位を照合する。
片道0.1%・平均日次turnover=1.0なら、同じ定義での年率costは
`0.001 × 1.0 × 252 = 0.252`。根拠なく倍にしない。

計算が正しければ成績の弱さを不具合と決めつけない。
平滑化、入替バンド、horizon、ensemble weightの変更は性能比較実験であり、
事前仮説・有限候補・Train-only評価が必要になる。
