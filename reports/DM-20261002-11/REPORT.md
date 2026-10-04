# DM-20261002-11 — Sector17 granularity robustness

**粒度robustnessの結論: Coverageの改善は確認できたが、Turnover低下やNet改善にはつながらず、IND17_MOM_WITHIN_REV20をREJECTする。** 追加探索は実施しない。

前回と同じ2011–2015＋2016partialの1,275営業日・576,535銘柄日で比較した。新規trialは1本、Sector33とMOM60は前回保存scoreの変更なしのcontrol replay。初回runは保存parquetのNaN符号bit差による照合失敗で、Train targetロード前・0performance trialsとして保存し、戦略・plan/configを変えずに技術復旧した。累積の新規performance trialは1本。Parent10の76証拠hashは不変。

**1. Coverageは改善。** Combined/Withinのraw finite coverageは94.214%→98.468%、+4.254pp。IndustryMom20単独のraw coverageは95.022%→99.316%、Stock20は99.132%で不変。評価行でminimum5-member failureは28,704→3,943行に減少し、broader groupsによるsparse-group問題の縮小と整合する。最低銘柄数は5のまま。raw coverage95%gateは17版ではPASS、neutral0後のfinite predictionは両版とも全Train809,636行100%であり、それとは区別する。

**2. Turnover低下は確認できない。** 0.122539→0.127287/日、差+0.004748（約3.9%増）。MOM600.063418の約2.01倍、0.08/dayおよびMOM60×1.25gateとも未達。Annualcostは3.068%→3.187%、+0.120pp。Rank自己相関は0.987438→0.987805と僅かに上がるが、mean absolute percentile changeは0.031646→0.032493へ増加、quintile retentionは85.31%→84.74%、mean tail spellは12.96→12.52sessionsに低下。Signal安定性は指標により混在し、実際のbook/costを安定化したとは言えない。

**3. Industry continuationの正方向は維持、強さは低下。** Raw stock-row ICは+0.010381/t2.322→+0.008588/t1.969、ex2016も+0.009106/t2.045で正。Joint-finite17/33の同じ銘柄日上では33+0.010363/t2.316、17+0.008918/t2.001で、coverage母集団差だけで説明できない弱まりがある。Cross-industry ICは+0.018104/t1.974→+0.013525/t1.253。ただし17/33の分類数・観測母集団が異なるのでcross-industry tだけを直接の改善判定に使わない。Own-finite industryICは両版とも2011–2015で4/5年正、2013のIC/tが最も強い。方向維持を、経済的Net alphaの安定性や独立OOSの確認とは呼ばない。

**4. Within reversalは改善せず、結合bookのShort損失だけ小幅縮小。** Raw Within reversal ICは−0.000958/t−0.338→−0.001371/t−0.456、joint-finiteで17−0.001916対33−0.000958。2011–2015の正ICは両版1/5年のみ。Withinの有効性が強まった証拠ではない。17のShort annual Gross/Netは−2.474%/−4.072%、33比+0.216pp/+0.151pp。Short cost増+0.066ppがGross改善の一部を消す。MOM60のShort Gross/Net−2.233%/−3.026%には届かず、Short netは全5年負のまま。総合bookのShort改善をWithin reversal単独の因果効果には帰属しない。

Long netは2.841%→2.670%、−0.170ppと悪化し、Short net改善+0.151ppを上回る。Totalannual Grossは+1.686%→+1.786%（+0.100pp）、Annualcost差+0.120ppで、Totalannual Netは−1.382%→−1.401%（−0.020pp）。coverageが改善しても、両側を合わせたコスト控除後の増分は負。

**5. NetSRは33とMOM60の両方を下回る。** Pooled17/33/MOM60=-0.560651/-0.539263/0.308092。17−33差−0.021388、paired20-day95%CI[−0.416967,+0.368628]は0を跨ぎ、僅差の悪化を統計的に確定したとは言わない。ex2016差−0.068976、CI[−0.467100,+0.335218]でも改善は確認できない。17−MOM60差−0.868743、CI[−2.197696,+0.429771]。17は33のfull-year NetSRを3/5年で上回る一方、MOM60改善は2/5で元の4/5gate未達。Grossが正のfull-yearも2/5へ減少し、3/5gate未達。2016partialは改善しているが、2011–2015のNet改善を支持する根拠に置き換えない。

**Q1–Q5 / concentration。** 17版Q1〜Q5平均targetは+1.71/+2.51/+2.76/+3.62/+3.29bp/day、Q5−Q1は1.58bp（33:1.96、MOM60:3.12）。順位単調性Spearman0.9はPASSでも、Q5がQ4より高い厳密な単調増加ではない。Q1targetも正で、低score銘柄のShort自体が正Grossとは読めない。

Common PIT17 partitionで17bookと33bookを比べるとLong/Short HHIは0.1315/0.1241対0.1219/0.1164、最大業種side weightの平均22.75%/21.34%対21.27%/20.51%。粗い業種単位の集中は増える。同じPIT33 partitionでは17book HHI0.0884/0.0884対33book0.0922/0.0927へ下がる。したがって「集中が改善した」と一括しない。共通17分類のGross上位2sector10/9依存は85.0%（33book78.6%、MOM6036.5%）、共通33分類でも72.9%（33book67.0%）。LOSO診断は17/33どちらのpartitionでも17bookNetが全て負。分布・年別・Q1/Q5 exposureと元book寄与はsector17/sector33へ保存し、sector exclusionは作らない。

**検証・制約。** 全284tests（新規24）、全Train入力3cutoff/18future-mutation・truncation、row shuffle/決定性、exact index/finite output、同一分類を与えたparent builderとの全feature/history/final bitwise parity、未変更residual/Stock20/MOM60、adapterと独立no-argument smoke、公式weight/P/L、2-session maturity/purge、source/Train firewall、親experiment hashはPASS。科学run61.17秒/peakRSS1.96GiB、独立smoke2.31秒/1.04GiB。make checkは既存DM-20261002-04のmetadata kindで停止したが、新metadataと既存Freeze129hashは別途PASS、既存metadataは変更していない。

保存parquetはWithin33Rev20のNaN符号bitを正規化していた（56,940missing rows、有限値差0、欠測mask差0）。保存raw featureの照合だけはfinite値bitwise＋NaN mask exactとし、この範囲をaudit/prior_control_parityに明示。In-memory全feature/history prefix・決定性・分類-only parityはNaNを含めuint64厳密一致、保存control最終scoreと前回dailyaccountも全bitwise一致。許容差を広げて因果性検査をPASSにしたものではない。動的検査は実施入力での証拠で、全入力の証明ではない。既知Train・borrowcostなし・独立OOS未評価であり、Validや実zip提出は行わない。

**IND17_MOM_WITHIN_REV20: REJECT**。新規performance trialは1本で終了。Sector33→17以外は固定、parent10の採否・証拠は不変。Known Train development evidence、独立OOSではない。Valid・rescue・追加candidate・Freeze・外部提出なし。

Run `artifacts/DM-20261002-11/run-20261002T094523Z`。

| strategy | rankic | rankic_t_hac5 | gross_sharpe | net_sharpe | annual_gross | annual_net | annual_cost | turnover | annual_long_net | annual_short_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IND17_MOM_WITHIN_REV20 | 0.002461 | 0.979159 | 0.715122 | -0.560651 | 0.017861 | -0.014014 | 0.031875 | 0.127287 | 0.026704 | -0.040718 |
| IND33_MOM_WITHIN_REV20 | 0.003222 | 1.270265 | 0.659250 | -0.539263 | 0.016863 | -0.013815 | 0.030679 | 0.122539 | 0.028408 | -0.042223 |
| MOM60 | 0.007590 | 1.567643 | 0.613360 | 0.308092 | 0.032108 | 0.016128 | 0.015981 | 0.063418 | 0.046391 | -0.030263 |

1. Raw coverage: 17=98.468%、33=94.214%、差+4.254pp。Neutral0後の100%finite predictionとは分ける。

2. Turnover: 17=0.127287/日、33=0.122539/日、差+0.004748。MOM60=0.063418。Annualcost差+0.120pp。

3. Industry continuation raw stock-row RankIC: 17=0.008588、33=0.010381。HAC5・年別・cross-industryと同じjoint-finite raw rows上のICをcomponent_rankic.csvに保存。分類数変更でcross-industry ICの母集団も変わるため、単純な有意性比較は避ける。

4. Within raw reversal IC: 17=-0.001371、33=-0.000958。17 Short gross/net=-2.474%/-4.072%、33差+0.216pp/+0.151pp。MOM60差-0.240pp/-1.045pp。Withinのみの追加portfolioは作らない。

5. NetSR:17=-0.560651、33=-0.539263、MOM60=0.308092。17−33=-0.021388、17−MOM60=-0.868743。Year/fold/EX2016・bootstrapを併せて判定する。

2011–2015 full-yearと2016 partialを分離。Chronological expanding history、fitなし、fold末2exchange sessions purge/t+2 maturity検証。全期間book/costを先に計算してから評価日を抽出し、前日保有を維持。

| strategy | scope | rankic | gross_sharpe | net_sharpe | annual_net | annual_long_net | annual_short_net | turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| IND17_MOM_WITHIN_REV20 | 2011 | 0.000497 | -0.024738 | -1.271769 | -0.034007 | 0.033980 | -0.067987 | 0.133082 |
| IND17_MOM_WITHIN_REV20 | 2012 | -0.003058 | -0.065264 | -1.257211 | -0.033647 | -0.014457 | -0.019190 | 0.127246 |
| IND17_MOM_WITHIN_REV20 | 2013 | 0.013327 | 2.620007 | 1.484260 | 0.038856 | 0.042315 | -0.003459 | 0.119554 |
| IND17_MOM_WITHIN_REV20 | 2014 | -0.008601 | -1.096427 | -2.740749 | -0.053928 | 0.004749 | -0.058677 | 0.129035 |
| IND17_MOM_WITHIN_REV20 | 2015 | 0.008451 | 1.747465 | 0.384650 | 0.008852 | 0.053125 | -0.044273 | 0.124520 |
| IND17_MOM_WITHIN_REV20 | 2016 | 0.009604 | 1.209430 | 0.076770 | 0.002366 | 0.085747 | -0.083381 | 0.139627 |
| IND33_MOM_WITHIN_REV20 | 2011 | 0.005766 | 0.275193 | -0.876289 | -0.024410 | 0.039385 | -0.063795 | 0.128034 |
| IND33_MOM_WITHIN_REV20 | 2012 | -0.003932 | -0.365177 | -1.556195 | -0.040576 | -0.017993 | -0.022582 | 0.123769 |
| IND33_MOM_WITHIN_REV20 | 2013 | 0.013853 | 2.685760 | 1.691634 | 0.048058 | 0.049043 | -0.000986 | 0.113180 |
| IND33_MOM_WITHIN_REV20 | 2014 | -0.007449 | -1.242363 | -2.844405 | -0.054386 | 0.009373 | -0.063759 | 0.122082 |
| IND33_MOM_WITHIN_REV20 | 2015 | 0.007583 | 1.513983 | 0.191722 | 0.004485 | 0.052110 | -0.047624 | 0.122688 |
| IND33_MOM_WITHIN_REV20 | 2016 | 0.004662 | 0.354836 | -0.686422 | -0.022092 | 0.072539 | -0.094631 | 0.134600 |
| MOM60 | 2011 | 0.005071 | 0.789398 | 0.506792 | 0.029635 | 0.075618 | -0.045983 | 0.065571 |
| MOM60 | 2012 | 0.011737 | 1.026104 | 0.636144 | 0.026788 | 0.013081 | 0.013708 | 0.065148 |
| MOM60 | 2013 | 0.005413 | 0.340451 | 0.081809 | 0.005051 | 0.038139 | -0.033088 | 0.063355 |
| MOM60 | 2014 | 0.009638 | 1.414193 | 0.910504 | 0.027522 | 0.050474 | -0.022952 | 0.060468 |
| MOM60 | 2015 | 0.005213 | 0.170703 | -0.099053 | -0.005742 | 0.045884 | -0.051626 | 0.062057 |
| MOM60 | 2016 | 0.010987 | 0.305757 | 0.067276 | 0.004639 | 0.084217 | -0.079579 | 0.065295 |

固定gate（parent10と同じMOM60基準）:

```json
{
  "candidate": "IND17_MOM_WITHIN_REV20",
  "decision": "REJECT",
  "unchanged_parent_gates": true,
  "feasibility": {
    "pooled_rankic_positive": true,
    "pooled_gross_positive": true,
    "ex2016_gross_positive": true,
    "gross_positive_3of5": false,
    "raw_coverage_ge95pct": true,
    "turnover_le008": false
  },
  "combined_adoption": {
    "pooled_netSR_beats_MOM60": false,
    "ex2016_netSR_beats_MOM60": false,
    "netSR_improvements_4of5": false,
    "bootstrap_lower_positive": false,
    "annual_net_beats_MOM60": false,
    "turnover_le125_MOM60": false,
    "long_net_positive": true,
    "short_net_ge_MOM60": false,
    "Q_monotonicity_positive": true
  },
  "failed_checks": [
    "gross_positive_3of5",
    "turnover_le008",
    "pooled_netSR_beats_MOM60",
    "ex2016_netSR_beats_MOM60",
    "netSR_improvements_4of5",
    "bootstrap_lower_positive",
    "annual_net_beats_MOM60",
    "turnover_le125_MOM60",
    "short_net_ge_MOM60"
  ],
  "raw_coverage": 0.9846826298490118,
  "full_year_gross_positive": 2,
  "full_year_netSR_improvements_vs_MOM60": 2
}
```

Paired circular moving-block20eligible sessions/2000reps/seed20261002/95%percentile ΔNetSR。Primary17−33、reference17−MOM60、pooledとex2016。purge gapsを除いたeligible sessionsを連結、multiplicity correction/OOS保証なし。

```json
{
  "POOLED:IND17_MOM_WITHIN_REV20-IND33_MOM_WITHIN_REV20": {
    "low": -0.416967178643672,
    "high": 0.368627861839914,
    "bootstrap_positive_fraction": 0.4675,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "days": 1275,
    "point_delta": -0.021387565427739452,
    "primary": true
  },
  "POOLED:IND17_MOM_WITHIN_REV20-MOM60": {
    "low": -2.1976962588704247,
    "high": 0.4297710830763339,
    "bootstrap_positive_fraction": 0.094,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "days": 1275,
    "point_delta": -0.868743309700713,
    "primary": false
  },
  "EX2016:IND17_MOM_WITHIN_REV20-IND33_MOM_WITHIN_REV20": {
    "low": -0.46709959063271383,
    "high": 0.3352175221250329,
    "bootstrap_positive_fraction": 0.374,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "days": 1216,
    "point_delta": -0.06897582513570766,
    "primary": false
  },
  "EX2016:IND17_MOM_WITHIN_REV20-MOM60": {
    "low": -2.3711904960153705,
    "high": 0.4875821543656399,
    "bootstrap_positive_fraction": 0.094,
    "reps": 2000,
    "block": 20,
    "seed": 20261002,
    "days": 1216,
    "point_delta": -0.9240720486994018,
    "primary": false
  }
}
```

Same residual raw_return−beta×TOPIX、skip1/20observations、daily historical PIT finite mean min5 incl own、missing history NaN保持、current-date PITから完成済みhistoryを参照。Within=Stock−Industry、Reversal=−Within。Separate centered component ranks→1:1 sum→centered rank→EWMA(.25)。Relisting>20gap resetも同じ。33builderへ17分類だけを与えるreference parityは全feature/history bitwise一致し、sourceも分類識別子変更と未使用standalone score exports削除だけ。元33builderとsaved scores/daily accountsのparityも検証。

Official5quintiles/Code ties/Q2Q4、one-way0.1%cost、sampleSD Sharpe×sqrt252、annual arithmetic mean×252、HAC5 Bartlett、Q1low/Q5high/monotonicity、additive/compound DD、period sums。Missing-target cost omission follows official score; net_all_cost conservative diagnostic also saved. Short residual signed P/L excludes borrow costs.2016 annualized values are not a realized full-year return.

Concentrationは全3bookを共通PIT17と共通PIT33の両partitionで測定し、side HHI/max/Q1Q5/exposure/top2をsector17/sector33へ保存。共通helperの列名Sector33Codeへ17を一時投影するが、値はexact contemporaneous PIT17のまま。分類が粗くなるだけでHHIが増える効果と、position変化を区別する。LOSOは元bookのsector寄与とcostを減算する記述診断のみ、rerank/exclusionなし。Rank persistence/quintile retention/spells/percentile changesはparentと同じ定義。Full observed spellsが評価期と交差する場合を集計、gap reset/境界censorを保存。

Audit: source scan、runtime Train firewall/dedicated stage、3cutoff18全入力future-mutation/truncationのIndustry history/raw/final scores bitwise検査、row shuffle/決定性、exact index/finite coverage、classification-only parity、unchanged primitive/MOM60と33saved source/control-account parity、research/adapterと独立no-argument smoke、公式会計/purge、parent evidence hash preservation。Python firewallはbest-effort、動的監査は実施入力での証拠。Independent OOS/actual zip deploymentは本研究の範囲外。
