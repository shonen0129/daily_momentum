# Transform-order matched Sector C-veto ablation

RAW_EWMA_CONTROL: StockMom60 raw neutral0 -> EWMA(.25), without Sector input.
RAW_EWMA_SHORT_VETO: exact prior08 raw C-veto and unavailable-context neutral0 -> EWMA(.25).
Self-inclusive PIT33 common/min5, residual60 skip1, original relisting reset. No rank transformation.
Default predict() returns Veto, Train files only. No fitted model, Freeze or Valid.
Plan/config: experiments/DM-20261002-09. Known Train development evidence.
