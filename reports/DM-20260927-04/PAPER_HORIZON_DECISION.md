# Paper horizon decision

## H1

**SUPPORTED — retain as fixed reference.** The existing H1 control reproduces saved SN1 scores exactly and passes target maturity/prefix checks. This is a continuation decision, not proof H1 is universally best.

## H5

**MIXED.** Train gross/Net is fractionally worse. Old Valid Net improves about 7.3 bp annualized, but uncertainty includes zero, longer-window RankIC does not repeat, and turnover/cost rise slightly.

## H20

**MIXED.** Full Train improves, but ex-2016 is essentially flat to slightly below H1 and most pooled uplift is the 59-session 2016 partial. Old Valid improves only about 5.3 bp annualized with intervals spanning zero. Turnover/cost do not improve; old-Valid 1–20/21–40 RankIC is weak.

## Paper challenger

**None. Keep H1.**

## Why

1. H1 reproduces the current implementation, and its label matures before each fold.
2. H5/H20 barely change rank persistence or sleeve membership; forecast-quality gains do not repeat.
3. Longer targets do not reduce turnover/cost, Long gains are tiny, and paired intervals include zero.

## Remaining uncertainty

1. Train and historical Valid are development history; no independent paper OOS exists yet.
2. Typical sleeve membership is much longer than the H1 label, but H5/H20 alone do not close this gap.
3. Year-level behavior is mixed and 2016 partials affect pooled estimates.

## Next action

Start fixed-H1 paper collection and accumulate at least 6–12 months.
