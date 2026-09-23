PYTHON ?= .venv/bin/python

.PHONY: help check test check-freeze
help:
	@echo 'check         構成・実験メタデータ・既存Freezeのhash検査（データ読込なし）'
	@echo 'test          全テスト（180秒制限）'
	@echo 'check-freeze  保存済みリリースの提出zipのTrain予測一致検証（120秒制限）'
	@echo '開発手順: WORKSPACE.md'

check:
	$(PYTHON) tools/workspace.py check

test:
	$(PYTHON) tools/run_bounded.py --seconds 180 $(PYTHON) -m pytest -q tests

check-freeze:
	$(PYTHON) tools/run_bounded.py --seconds 120 $(PYTHON) tools/check_freeze.py
