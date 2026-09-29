# DM-20260927-02 — Low-fast-only EWMA 診断

評価期間は既知Trainの2011-01-04〜2016-03-29（1,275営業日）。2016部分期間は2016-01-04〜2016-03-29（59営業日）。Validは参照していない。以下の結果は独立OOS証拠ではない。

## 1. Executive conclusion

**解釈 A（固定仕様の方向性を支持。ただし証拠は弱い）**。

- `D_LOW_FAST_ONLY` は `BOX_ORIGINAL` より年率Gross +0.084ポイント、年率Net +0.067ポイント、Net Sharpe +0.023改善した。Turnoverは0.03185から0.03252/日へ小幅増に留まり、ex-2016 Net Sharpeも+0.026改善した。
- `A_LOW_NO_CARRY` に対してはTurnoverが0.04589から0.03252/日へ低下し、Q1 score-zero weight shareは51.87%から10.13%へ、Shortのzero-score weightは46.86%から8.48%へ低下した。順位安定性もBOXに近い。
- ただしゼロスコア依存はBOX比で減っておらず、ほぼ同水準（Short全体では8.48%対8.05%、Code-order rhoは0.811対0.812）。B00にも同じ変更を行うと改善がより大きく、Box固有の効果ではない。
- 対応付きbootstrapの95%区間はいずれも0を跨ぐ。年別では2014年がBOX比で悪化し、2016部分期間の年率Net returnも低い。したがって固定Train上の小幅な方向性であり、採用やOOS性能の主張には使わない。

## 2. Fixed specification

| 項目 | `D_LOW_FAST_ONLY` / `D_B00_LOW_FAST_ONLY` |
|---|---|
| High EWMA alpha | 0.25（`BOX_ORIGINAL` / `B00_BASE`と同一） |
| Low EWMA alpha | 0.50（今回の唯一の変更） |
| 対象比較 | `B00_BASE`, `BOX_ORIGINAL`, `A_LOW_NO_CARRY`, `C_ASYM_EWMA`, `C_B00_ASYM_EWMA`, `D_LOW_FAST_ONLY`, `D_B00_LOW_FAST_ONLY` |
| 固定 | Event/raw score、Box/Ridge、Universe、foldとpurge、O2O、cost 10bps片道、公式5分位/qcut、normalization、tie-break、execution timing |
| Valid | 未使用 |

実装は[固定診断driver](../../research/experiments/box_asym_ewma_low_fast_only.py)のみを追加した。保存済みalpha=0.25 scoreを既存関数で逆変換し、High/Low raw成分を既存のlisting-segment `ewm(adjust=False)` に通した。DではHigh alphaを0.25、Low alphaを0.50とし、既存評価・ウェイト関数を再利用した。High stateのBOXとの差は両系統ともmax absolute error 0.0。既知5系列のscore、account、weightも再生誤差それぞれ最大0、`1.0e-16`未満、0。side別EWMAの将来prefix不変性、Train firewall、公式quintile一致を確認した。

## 3. Gross comparison

全期間のリターン・寄与は年率。commonとselectionの和がGross returnに一致する（既存評価定義）。

| Strategy | Gross | Gross vol | Gross SR | Common | Selection | Long gross | Short gross | RankIC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `B00_BASE` | 4.608% | 4.662% | 0.988 | 0.050% | 4.558% | 5.942% | -1.334% | 0.01087 |
| `BOX_ORIGINAL` | 4.448% | 4.643% | 0.958 | 0.055% | 4.393% | 5.867% | -1.419% | 0.01103 |
| `A_LOW_NO_CARRY` | 4.167% | 4.071% | 1.024 | 0.089% | 4.078% | 5.711% | -1.544% | 0.01086 |
| `C_ASYM_EWMA` | 4.269% | 4.567% | 0.935 | 0.058% | 4.211% | 5.642% | -1.373% | 0.01104 |
| `C_B00_ASYM_EWMA` | 4.667% | 4.598% | 1.015 | 0.057% | 4.610% | 5.906% | -1.239% | 0.01129 |
| `D_LOW_FAST_ONLY` | 4.532% | 4.593% | 0.987 | 0.064% | 4.467% | 5.880% | -1.348% | 0.01131 |
| `D_B00_LOW_FAST_ONLY` | 4.836% | 4.623% | 1.046 | 0.060% | 4.776% | 6.037% | -1.201% | 0.01143 |

| 主比較 | Δ Gross | Δ Gross SR | Δ selection | Δ turnover/day | Δ cost | Δ Net | Δ Net SR | Δ ex-2016 Net SR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D_BOX − `BOX_ORIGINAL` | +0.084 pt | +0.0286 | +0.074 pt | +0.00067 | +0.017 pt | +0.067 pt | +0.0231 | +0.0262 |
| D_BOX − `C_ASYM_EWMA` | +0.263 pt | +0.0517 | +0.257 pt | +0.00023 | +0.006 pt | +0.257 pt | +0.0515 | +0.0468 |
| D_BOX − `A_LOW_NO_CARRY` | +0.365 pt | -0.0369 | +0.390 pt | -0.01338 | -0.335 pt | +0.701 pt | +0.0693 | +0.0034 |
| D_B00 − `B00_BASE` | +0.228 pt | +0.0577 | +0.218 pt | +0.00081 | +0.021 pt | +0.208 pt | +0.0518 | +0.0640 |
| D_BOX − D_B00 | -0.304 pt | -0.0595 | -0.309 pt | +0.00053 | +0.013 pt | -0.317 pt | -0.0633 | -0.0681 |

`D_LOW_FAST_ONLY − BOX_ORIGINAL` のGross増分0.084ポイントのうち、selection増分は0.074ポイント、common residual増分は0.010ポイント。したがって既存common/selection定義では、ほとんどが銘柄選択側に出ており、共通残差ドリフトだけでは説明されない。Netは `Gross − cost` で、`+0.084 − 0.017 = +0.067`ポイントとなる。

`A_LOW_NO_CARRY` はBOX比でGross returnが0.281ポイント低下し、selectionが0.315ポイント低下、costが0.352ポイント増加した。DはA比でGross return +0.365ポイント、cost -0.335ポイントとなりNetを+0.701ポイント戻した。一方、AよりGross Sharpeは0.0369低い。Aの問題は連続減衰で緩和されたが、Gross Sharpe改善まで維持したわけではない。

## 4. Cost & rank stability

| Strategy | Turnover/day | Cost/year | Rank AC | Q1 retention | Q1 entrants/exits per day | Q1 wt turnover | Q5 retention | Q5 entrants/exits per day | Q5 wt turnover | Quintile changes/day | Total wt turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `B00_BASE` | 0.03117 | 0.782% | 0.9881 | 98.88% | 1.020 / 1.015 | 0.00752 | 95.92% | 3.720 / 3.714 | 0.02730 | 13.37 | 0.03119 |
| `BOX_ORIGINAL` | 0.03185 | 0.799% | 0.9868 | 98.85% | 1.046 / 1.040 | 0.00772 | 95.82% | 3.804 / 3.798 | 0.02792 | 13.49 | 0.03179 |
| `A_LOW_NO_CARRY` | 0.04589 | 1.151% | 0.9787 | 96.58% | 3.094 / 3.089 | 0.02292 | 95.76% | 3.863 / 3.857 | 0.02836 | 18.91 | 0.04584 |
| `C_ASYM_EWMA` | 0.03229 | 0.810% | 0.9879 | 98.67% | 1.217 / 1.211 | 0.00896 | 96.17% | 3.492 / 3.487 | 0.02562 | 14.01 | 0.03222 |
| `C_B00_ASYM_EWMA` | 0.03189 | 0.800% | 0.9891 | 98.64% | 1.239 / 1.233 | 0.00913 | 96.32% | 3.359 / 3.354 | 0.02464 | 14.03 | 0.03190 |
| `D_LOW_FAST_ONLY` | 0.03252 | 0.816% | 0.9865 | 98.78% | 1.116 / 1.111 | 0.00823 | 95.82% | 3.809 / 3.804 | 0.02797 | 13.79 | 0.03245 |
| `D_B00_LOW_FAST_ONLY` | 0.03199 | 0.803% | 0.9878 | 98.80% | 1.098 / 1.093 | 0.00809 | 95.91% | 3.725 / 3.720 | 0.02734 | 13.75 | 0.03200 |

D preserves Q1 rank persistence near BOX and cuts A's daily Q1 entrants from 3.09 to 1.12 and total turnover from 0.04589 to 0.03252/day. D turnover remains close to BOX, though +0.00067/day higher. Annual cost therefore rises slightly versus BOX (+0.017 point) and falls materially versus A (-0.335 point). The daily rank autocorrelation uses common-listed-name score ranks; quintile changes count changed names, and tail weight turnover is the absolute change in that sleeve's official weights.

## 5. Portfolio composition

### Short sleeve: stock-day share / gross-weight share

各セルはShort sleeve内の `% stock-day / % gross weight`。score-zeroはCode-order tie-breakで割当てられたtailと、それ以外のquintile内保有を分ける。

| Strategy | High day | High age 1–4 | High age 5+ | Low day | Low age 1–4 | Low age 5+ | Zero tail tie | Zero non-tail tie |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `B00_BASE` | 0.00 / 0.00 | 0.00 / 0.00 | 36.72 / 30.24 | 1.34 / 1.72 | 3.85 / 4.89 | 54.31 / 58.66 | 3.06 / 4.01 | 0.72 / 0.47 |
| `BOX_ORIGINAL` | 0.00 / 0.00 | 0.00 / 0.00 | 36.73 / 30.25 | 1.32 / 1.70 | 3.86 / 4.90 | 50.81 / 55.09 | 4.75 / 6.33 | 2.53 / 1.72 |
| `A_LOW_NO_CARRY` | 0.00 / 0.00 | 0.00 / 0.00 | 54.70 / 50.73 | 1.86 / 2.41 | 0.00 / 0.00 | 0.00 / 0.00 | 25.59 / 34.65 | 17.86 / 12.21 |
| `C_ASYM_EWMA` | 0.00 / 0.00 | 0.00 / 0.00 | 42.93 / 37.38 | 1.53 / 1.98 | 4.03 / 5.13 | 43.56 / 46.63 | 5.29 / 7.05 | 2.66 / 1.82 |
| `C_B00_ASYM_EWMA` | 0.00 / 0.00 | 0.00 / 0.00 | 44.28 / 38.62 | 1.54 / 2.00 | 4.02 / 5.12 | 45.71 / 48.95 | 3.63 / 4.76 | 0.81 / 0.55 |
| `D_LOW_FAST_ONLY` | 0.00 / 0.00 | 0.00 / 0.00 | 39.10 / 32.82 | 1.53 / 1.98 | 4.03 / 5.13 | 47.76 / 51.59 | 5.08 / 6.77 | 2.51 / 1.71 |
| `D_B00_LOW_FAST_ONLY` | 0.00 / 0.00 | 0.00 / 0.00 | 39.35 / 33.06 | 1.54 / 2.00 | 4.02 / 5.12 | 51.16 / 55.01 | 3.40 / 4.46 | 0.52 / 0.35 |

BOX → A → C → Dで、DはLow aged exposureを一部残し（Low age 1+ weight 56.72%）、AでゼロになったLow carryを戻す。Aで50.73%だったaged HighのShort比率はDで32.82%となり、BOXの30.25%に近い。Short score-zero weightはA 46.86%からD 8.48%へ下がるが、BOX 8.05%より0.43ポイント高い。従ってDはAの急な置換を抑えたが、BOXよりtie依存を改善したとは言えない。

Shortの年率Net P/L寄与は、BOX→DでLow event dayが+0.189→+0.188%、Low age 1–4が-0.198→-0.200%、Low age 5+が-0.317→-0.173%となった。High age 5+ Shortは-1.120→-1.223%へ悪化。低値aged寄与の改善とShort中のaged High流入の増加が相殺し、Short全体の年率Net寄与は-1.649→-1.591%の小幅改善に留まる。AではShort score-zero tie tail/non-tailのNet寄与がそれぞれ-0.714% / +0.057%で、Dでは-0.140% / -0.044%。

### Long sleeve

High alpha/stateはDとBOXで完全一致する。Long順位の競合で実保有と比率はわずかに変わる。

| Strategy | High event weight / net contribution / turnover share | High age 1–4 weight / net contribution / turnover share | High age 5+ weight / net contribution / turnover share |
|---|---:|---:|---:|
| `BOX_ORIGINAL` | 5.94% / -0.161% / 41.08% | 16.42% / +0.808% / 15.18% | 73.21% / +4.531% / 40.66% |
| `C_ASYM_EWMA` | 4.97% / -0.185% / 37.46% | 14.74% / +0.705% / 12.95% | 77.15% / +4.574% / 46.14% |
| `D_LOW_FAST_ONLY` | 5.94% / -0.162% / 40.88% | 16.42% / +0.808% / 15.08% | 74.12% / +4.638% / 40.96% |

D対BOXではHigh age 5+の比率が73.21%から74.12%、年率Net寄与が+4.531%から+4.638%へ動いた。これはHigh stateの変化ではなく、Low state変更後の断面順位との競合による。D対CではLong gross +5.880%対+5.642%、Long net +5.307%対+5.093%、High age 5+のNet寄与+4.638%対+4.574%。High alphaを0.15から0.25に戻した差はLong側の改善方向に出た。

### score-zero・同点・Sector

| Strategy | Q1 zero stock / weight | Q5 zero stock / weight | Zero-code rho | Q1 sector max / HHI | Q5 sector max / HHI |
|---|---:|---:|---:|---:|---:|
| `B00_BASE` | 6.10% / 6.01% | 0.00% / 0.00% | 0.731 | 14.60% / 0.0729 | 14.91% / 0.0775 |
| `BOX_ORIGINAL` | 9.46% / 9.48% | 0.68% / 0.70% | 0.812 | 15.28% / 0.0768 | 14.90% / 0.0778 |
| `A_LOW_NO_CARRY` | 51.01% / 51.87% | 0.68% / 0.70% | 0.903 | 16.36% / 0.0873 | 14.78% / 0.0775 |
| `C_ASYM_EWMA` | 10.56% / 10.55% | 0.68% / 0.70% | 0.755 | 15.33% / 0.0752 | 14.88% / 0.0779 |
| `C_B00_ASYM_EWMA` | 7.24% / 7.12% | 0.00% / 0.00% | 0.677 | 14.54% / 0.0713 | 14.90% / 0.0780 |
| `D_LOW_FAST_ONLY` | 10.13% / 10.13% | 0.68% / 0.70% | 0.811 | 15.25% / 0.0757 | 14.85% / 0.0777 |
| `D_B00_LOW_FAST_ONLY` | 6.78% / 6.68% | 0.00% / 0.00% | 0.657 | 14.50% / 0.0720 | 14.88% / 0.0775 |

Zero-code rhoは、score=0銘柄内のCode順ordinalとquintile番号の日次Spearman相関の平均。値が高いほどCode順が分位割当に強く結びつく。DはAの0.903から0.811へ戻るがBOXの0.812とほぼ同じであり、Code順への依存は残る。DのQ1 HHIはAより低下しBOXよりもわずかに低い。

## 6. Net comparison: full / ex-2016 / year

全期間とex-2016の指標。Max DDは既存account関数のadditive drawdown。

| Strategy | Gross | Net | Gross vol | Gross SR | Net SR | Turn/day | Cost/year | ex-2016 Net | ex-2016 Net SR | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `B00_BASE` | 4.608% | 3.826% | 4.662% | 0.988 | 0.820 | 0.03117 | 0.782% | 3.163% | 0.705 | -6.988% |
| `BOX_ORIGINAL` | 4.448% | 3.649% | 4.643% | 0.958 | 0.785 | 0.03185 | 0.799% | 3.009% | 0.675 | -6.225% |
| `A_LOW_NO_CARRY` | 4.167% | 3.015% | 4.071% | 1.024 | 0.739 | 0.04589 | 1.151% | 2.784% | 0.698 | -6.130% |
| `C_ASYM_EWMA` | 4.269% | 3.459% | 4.567% | 0.935 | 0.757 | 0.03229 | 0.810% | 2.877% | 0.654 | -6.073% |
| `C_B00_ASYM_EWMA` | 4.667% | 3.866% | 4.598% | 1.015 | 0.840 | 0.03189 | 0.800% | 3.265% | 0.736 | -6.604% |
| `D_LOW_FAST_ONLY` | 4.532% | 3.716% | 4.593% | 0.987 | 0.808 | 0.03252 | 0.816% | 3.098% | 0.701 | -6.149% |
| `D_B00_LOW_FAST_ONLY` | 4.836% | 4.033% | 4.623% | 1.046 | 0.872 | 0.03199 | 0.803% | 3.430% | 0.769 | -6.301% |

年別Net年率 / Net Sharpe：

| Strategy | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 partial |
|---|---:|---:|---:|---:|---:|---:|
| `B00_BASE` | 0.706% / 0.154 | 6.161% / 1.275 | 4.812% / 0.962 | 4.197% / 1.527 | -0.106% / -0.022 | 17.476% / 2.331 |
| `BOX_ORIGINAL` | -0.158% / -0.034 | 6.119% / 1.263 | 4.894% / 0.997 | 4.161% / 1.521 | -0.021% / -0.004 | 16.841% / 2.220 |
| `A_LOW_NO_CARRY` | -1.088% / -0.295 | 6.834% / 1.786 | 4.656% / 0.959 | 3.643% / 1.362 | -0.187% / -0.041 | 7.792% / 1.372 |
| `C_ASYM_EWMA` | -0.406% / -0.089 | 6.655% / 1.413 | 5.001% / 1.019 | 3.496% / 1.286 | -0.416% / -0.088 | 15.445% / 2.115 |
| `C_B00_ASYM_EWMA` | 1.195% / 0.263 | 6.548% / 1.412 | 4.767% / 0.947 | 3.970% / 1.447 | -0.206% / -0.042 | 16.251% / 2.250 |
| `D_LOW_FAST_ONLY` | 0.039% / 0.008 | 6.392% / 1.344 | 5.017% / 1.025 | 4.007% / 1.468 | -0.017% / -0.003 | 16.463% / 2.223 |
| `D_B00_LOW_FAST_ONLY` | 1.517% / 0.331 | 6.635% / 1.391 | 4.976% / 0.998 | 4.039% / 1.469 | -0.070% / -0.015 | 16.472% / 2.255 |

DはBOX比で2011、2012、2013、2015が非負改善方向、2014は-0.154ポイント / Net SR -0.053、2016部分のNet年率は-0.378ポイント / Net SR +0.003。2011・2015の一方だけに依存した改善ではない。ex-2016ではNet +0.089ポイント、Net SR +0.026で改善方向だが、2015はほぼ横ばい。B00版はB00_BASE比でfull Net +0.208ポイント / Net SR +0.052、ex-2016 Net +0.266ポイント / Net SR +0.064。

公式Long/Short sleeveの年率Net寄与はDで+5.307% / -1.591%、BOXで+5.297% / -1.649%。平均gross/net exposureは両方1.0017 / -0.00058。Long−Short Net P/L相関はD -0.590、BOX -0.584。順位面ではRankICがD 0.01131、BOX 0.01103。DのNet差は、ネットロング化や共通残差ドリフトの大幅増加ではなく、主にselection寄与差と小幅なShort損失縮小から生じた。

## 7. B00 control

同一alpha pairのB00 controlも改善方向（B00_BASE比Gross +0.228ポイント、Net +0.208ポイント、Net SR +0.052、ex-2016 Net SR +0.064）。D_BOXはD_B00に対してNet -0.317ポイント、Net SR -0.063であり、B00側の増分の方が大きい。従って、今回の固定Low-fast persistenceがBOXに特有の改善を生んだとは言えない。全て既知Trainなので、B00の点推定も採択根拠やOOS証拠ではない。

## 8. Paired circular block bootstrap

既存 `research.evaluation.bootstrap_delta` を再利用。20日 circular block、1,000回、seed 20260925。Net Sharpe差の区間は既知Train上の記述値。

| Candidate − baseline | Δ Net SR | 95% interval | bootstrap positive ratio |
|---|---:|---:|---:|
| `D_LOW_FAST_ONLY` − `BOX_ORIGINAL` | +0.0231 | [-0.0313, +0.0846] | 0.780 |
| `D_B00_LOW_FAST_ONLY` − `B00_BASE` | +0.0518 | [-0.0299, +0.1508] | 0.874 |
| `D_LOW_FAST_ONLY` − `D_B00_LOW_FAST_ONLY` | -0.0633 | [-0.1663, +0.0269] | 0.096 |

全区間が0を跨いでいるため、小さなNet Sharpe差の符号は統計的に確定しない。既知Train上の手順内再標本化であり、OOS証明ではない。

## 9. Interpretation / 診断への回答

1. **A_LOW_NO_CARRYの主な失敗要因:** Gross return/selection低下（BOX比 -0.281 / -0.315ポイント）と、Turnover増によるcost増（+0.352ポイント）の両方。Gross Sharpeだけは低volにより上がったが、Gross/Net returnは下がった。
2. **Continuous fast decayが解決したか:** `A_LOW_NO_CARRY`のQ1 turnover急増とscore-zero依存を大きく抑えた。Q1 retentionは96.58%から98.78%、Short zero-score weightは46.86%から8.48%、総turnoverは0.04589から0.03252/dayへ回復。BOX比ではほぼ元の安定性だが、tie依存はわずかに増えた。
3. **Low persistence短縮でGross alphaは改善したか:** BOX比でGross +0.084ポイント、selection +0.074ポイント。A比ではGross +0.365ポイントだが、DのGross SRはAより低い。
4. **Netで改善したか:** BOX比のfull Net +0.067ポイント / Net SR +0.023、ex-2016 Net +0.089ポイント / Net SR +0.026。点推定では改善方向、bootstrap区間は0を跨ぐ。
5. **BOX固有か:** いいえ。D_B00のB00_BASE比改善が大きく、同じalpha ruleはB00側にも作用している。
6. **このTrain系列を続けるか:** 固定した低速化候補の診断は完了。方向性はAだが差は小さく不確実で、追加alpha探索はしない。結果から採用や独立OOSの主張は行わない。

## 10. Supplemental: Long/Short × 昼夜のSharpe

追加の帰属診断。昼は`t+1 Open→t+1 Close`、夜は`t+1 Close→t+2 Open`。複利交差項と`beta[t+2] × TOPIX[t+2]`市場調整を昼夜に半分ずつ配分し、Long/Short別turnover costも半分ずつ配分した。公式Netへの4区分合計誤差は`1.02e-17`。日中・夜間単独の売買戦略ではない。

| L/S sleeve | 年率Gross | Gross SR | 年率Net | Net SR |
|---|---:|---:|---:|---:|
| Long | +5.880% | +1.127 | +5.307% | +1.017 |
| Short | -1.348% | -0.274 | -1.591% | -0.324 |

| L/S × session | 年率Gross寄与 | 年率cost配賦 | 年率Net寄与 | 単体Net SR |
|---|---:|---:|---:|---:|
| Long × Day | -0.681% | 0.287% | -0.967% | -0.187 |
| Long × Night | +6.561% | 0.287% | +6.275% | +0.986 |
| Short × Day | +4.014% | 0.122% | +3.892% | +0.767 |
| Short × Night | -5.362% | 0.122% | -5.483% | -0.872 |

セルごとのSharpeは各Net寄与系列を単独で年率化した値で、4セル間で加算できない。また、市場調整を昼夜に等配分した帰属であり、昼夜別の公式残差リターンではない。

詳細CSV: `metrics/ls_day_night_D_LOW_FAST_ONLY.csv`, `metrics/ls_day_night_by_year_D_LOW_FAST_ONLY.csv`, `metrics/ls_day_night_daily_D_LOW_FAST_ONLY.csv`; 照合情報: `audit/ls_day_night_D_LOW_FAST_ONLY.json`。

## 11. Supplemental: Short × Night source attribution

`Short × Night`を実保有のイベント年齢・zero-score tie-break区分に配賦した。年率Gross/Netは公式袖の損益に対する各sourceの寄与ポイントであり、表のSharpeは当該sourceの配賦済み日次Net寄与系列を単独で年率化した値。source Sharpeや寄与は独立戦略の成績ではない。score成分は既存方式の絶対寄与比で配賦し、turnover costは旧・新保有sourceへ既存方式で配賦後、夜へ半分を割り当てた。gross weight / stock-days shareはShort袖全体に対する当該sourceの配賦比率。

| Strategy | Short × Night source | 年率Gross寄与 | 年率Net寄与 | 単体Net SR | Short gross weight | Short stock-days |
|---|---|---:|---:|---:|---:|---:|
| BOX_ORIGINAL | low_event_day | +0.037% | +0.015% | +0.011 | 1.70% | 1.32% |
| BOX_ORIGINAL | low_age_1_4 | -0.329% | -0.330% | -0.232 | 4.90% | 3.86% |
| BOX_ORIGINAL | low_age_5_plus | -2.894% | -2.927% | -0.769 | 55.09% | 50.81% |
| BOX_ORIGINAL | high_age_5_plus | -1.662% | -1.713% | -0.708 | 30.25% | 36.73% |
| BOX_ORIGINAL | score_zero_tail_tie_break | -0.451% | -0.454% | -0.835 | 6.33% | 4.75% |
| BOX_ORIGINAL | score_zero_non_tail_tie_break | -0.160% | -0.165% | -0.279 | 1.72% | 2.53% |
| D_LOW_FAST_ONLY | low_event_day | +0.046% | +0.022% | +0.015 | 1.98% | 1.53% |
| D_LOW_FAST_ONLY | low_age_1_4 | -0.383% | -0.384% | -0.268 | 5.13% | 4.03% |
| D_LOW_FAST_ONLY | low_age_5_plus | -2.641% | -2.673% | -0.735 | 51.59% | 47.76% |
| D_LOW_FAST_ONLY | high_age_5_plus | -1.777% | -1.833% | -0.721 | 32.82% | 39.10% |
| D_LOW_FAST_ONLY | score_zero_tail_tie_break | -0.455% | -0.458% | -0.837 | 6.77% | 5.08% |
| D_LOW_FAST_ONLY | score_zero_non_tail_tie_break | -0.152% | -0.157% | -0.266 | 1.71% | 2.51% |

6区分の合計は、BOX_ORIGINALが年率Gross寄与 -5.459%、cost配賦 +0.115%、Net寄与 -5.574%（既存全体Short × Night Net SR 約 -0.882）、D_LOW_FAST_ONLYがGross -5.362%、cost +0.121%、Net -5.483%（全体Net SR -0.872）。全sourceを含む再照合誤差はGross/Netともに`4e-18`未満、評価日数は1,275日。Validは未使用。

### 解釈

- 最大の単独損失sourceは両戦略とも`low_age_5_plus`。DではShort gross weightの51.59%を占め、年率Net寄与は-2.673%。次が`high_age_5_plus`の-1.833%。
- Low-fastで`low_age_5_plus`の損失はBOX比+0.254ポイント改善した。Low区分合計でも+0.207ポイント改善した一方、`high_age_5_plus`はShortへの流入比率が30.25%から32.82%へ増え、損失寄与が0.120ポイント悪化した。zero-score合計のNet寄与はほぼ横ばい（-0.619%から-0.616%）。結果、Short × Night全体の改善は+0.091ポイントに留まる。
- よってShort × Night損失の主因はaged Low、次点はShortに入ったaged High。Low-fastは古いLowの寄与を一部改善したが、順位競合によるaged Highへの置換を含む損失は残った。この帰属だけから「EMAだけで解決できる」とは言えず、Low EMA変更は部分改善に留まる。昼夜・source attributionは既存保有の帰属診断で、独立した取引成績や反実仮想を表さない。

詳細値: `artifacts/DM-20260927-02/run-20260926T174234Z/metrics/short_night_source_attribution.csv`。全sourceの再照合: `artifacts/DM-20260927-02/run-20260926T174234Z/metrics/short_night_source_attribution_all_categories.csv` と `artifacts/DM-20260927-02/run-20260926T174234Z/audit/short_night_source_attribution.json`。

## 再現情報

- Experiment/config: [DM-20260927-02](../../experiments/DM-20260927-02/plan.md)、[config.json](../../experiments/DM-20260927-02/config.json)
- Run: `artifacts/DM-20260927-02/run-20260926T174234Z/`
- Code commit: `0b8341c3c0051db4b1a54040a6c4d85847bca8ec`（実行時worktree dirty。対象コードとTrain data/artifactのSHA256、Python/numpy/pandas versionはrun.jsonに保存）
- Key outputs: `metrics/period_metrics.csv`, `paired_period_differences.csv`, `rank_diagnostics_period.csv`, `annual_category_attribution.csv`, `category_by_year.csv`, `paired_circular_bootstrap.csv`, `predictions/holdings_audit.parquet`, `audit/low_fast_only_audit.json`, `audit/firewall.json`。
- Checks: focused tests 7 passed; `make check` 30 experiments / 129 frozen file hashes passed; bounded Train run 72.2 seconds / exit 0; coverage 809,636 rows per score, PIT sector coverage 100%; Valid access false.
