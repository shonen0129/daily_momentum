# 戦略ごとのテスト

新しい戦略のテストは `<strategy_slug>/test_*.py` に置き、`make test` で収集する。
各戦略についてsource scan、future-mutation prefix-invariance、index/NaN/coverage、
決定性、研究と提出の予測一致、smokeを検査する。
既存のルート `tests/test_*.py` はdm_trainonlyの回帰検証用。凍結当時の原本はリリースsnapshotに保存されている。
