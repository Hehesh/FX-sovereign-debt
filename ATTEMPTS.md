# ATTEMPTS.md — append-only journal of every specification

Conventions: FX `e` = USD per NZD (higher = NZD appreciation). Flow units NZ$ millions. `us_*` = flow × `us_share`. Repo-relative paths from `Practicum/`. Source IDs refer to `DATA_SOURCES.md`.

---

## CA-0 — Clock audit (precedes Attempt 1)

- **Date / status:** 2026-10-30 / running
- **Question:** On which FX return does an NZ-dated cash flow land, and which regressors are inside the information set of that return?
- **Why:** The baseline joins on calendar date with no time zones (`move_flows_to_fx_dates`, `run_regressions.py`).
- **Method:** `nz_bond_flows/code/gate0_diagnostics.py` builds a timezone-aware table (`Pacific/Auckland`, `America/New_York`, `Europe/London`) of H.10 return windows (NY noon D-1 to NY noon D) against Auckland day D, across all DST regimes 2014-2025, and counts mapping cases from `flow_date_mapping_audit.csv`. Outputs: `nz_bond_flows/output/attempts/00_clock_audit/`.
- **Data:** S01, S10 (quote check done), S02 (settlement rule from `build.py`), S03, S04. B1 comparison is **blocked** (see BLOCKED_DATA B1).
- **Prediction / decision rule:** Not a model. Outcome is a documented mapping rule. If a flow date cannot be placed in a window, say so and drop that claim.
- **Results so far (pre-fit reasoning, to be confirmed by the table):**
  1. `dexnzus` = 1/DEXUSNZ exactly (max abs diff 2.2e-16, 6,294/6,294 dates match). The code's reciprocal gives USD per NZD, so signs are right.
  2. H.10 return dated D spans NY noon D-1 to NY noon D = Auckland about 04:00-06:00 on D to 04:00-06:00 on D+1 (offsets vary with DST). Auckland business hours on D (09:00-17:00) fall wholly inside the return dated D, so `k=0` is the defensible same-session mapping for settlement-dated flows. The next-FX-day roll is also coherent when NY is closed.
  3. Settlement-time of day inside NZ day D is unknown, so activity before about 05:00 Auckland would belong to return D-1. Treated as an uncertainty, not tested.
  4. **VIX** (16:15 ET close on D) is after the noon fix on D, so contemporaneous `vix_D` is not in the information set of return D. `vix_{D-1}` is inside the window, `vix_{D-2}` is strictly prior. `us_release` (mostly Fri, morning ET) is inside the window and contemporaneous. `treasury_swap_merged` timing is unknown.
  5. `us_share` is joined backward by FX date, but its reference date and publication lag are unknown, so it may use post-date information.
- **Decision:** pending table.

---

## G0 — Baseline replication and diagnosis

- **Date / status:** 2026-10-30 / running (replication already executed once, below)
- **Hypothesis (team's):** Daily NZD/USD changes respond to US-share-weighted NZ sovereign cash flows around the event date; principal repayments are anticipated (H1), issuance and repayment are asymmetric (H2), and repayment effects reverse (H3). Sign is ambiguous without the conversion stages.
- **Why no prior attempt:** this is the baseline. Nothing precedes it.
- **Exact equations (as implemented, `code/run_regressions.py`):**
  - M1: `Δe_t = a + Σ_{k=-5..5} b_k N^US_{t+k} + g' X_t + u_t`
  - M2: `Δe_t = a + Σ_k bI_k I^US_{t+k} + Σ_k bR_k R^US_{t+k} + dC C^US_t + dB B^US_t + g' X_t + u_t`
  - Outcome variants: level change `Δe_t`, and `100·Δln e_t` (the plan's return).
  - `N = I - R - C - B`; nominal + IIB cash summed with `min_count=2`; issuance sign-flipped to positive; `Z^US = us_share·Z`.
  - `k>0` = event in the future (pre-event). Leads/lags count FX sessions.
  - `X_t` = `vix`, `treasury_swap_merged`, `us_release`, all contemporaneous (D).
  - Flows rolled to next FX date (policy `next-fx-day`; 3,465 rows moved, 600 dropped). `us_share` backward as-of. OLS with Newey-West 10 lags, no fixed effects, complete cases only.
- **Data / hashes:** S01-S04 (hashes in `DATA_SOURCES.md`); panel `nz_bond_flows/output/intermediate/merged_constructed_panel.csv` SHA256 `ed81489a8501b3c08a1e50e133d42780ebcfb7f151d5e173063f7ed7117b2e4f`, reproduced byte-identical on 2026-10-30.
- **Command:** `~/.pyenv/versions/3.12.9/envs/Trading/bin/python nz_bond_flows/code/run_regressions.py` (git 9d6d431). Diagnostics: `.../python nz_bond_flows/code/gate0_diagnostics.py` writing `nz_bond_flows/output/attempts/00_gate0_baseline/`.
- **Predictions:** none beyond the team's; all hypotheses reported as the team stated them. Primary estimand: `Σ_{k=1..5} bR_k` (H1) in % per NZ$ million of US-weighted principal. Falsification: placebo shift of the event dates by +-30 sessions and a placebo event count matched in size.
- **Decision condition (set now):** G0 is informative if the 95% CI of the H1 sum excludes or bounds a declared effect of 0.1% (10 bp) per NZ$1bn of US-weighted principal. Otherwise log as `underpowered`. Chosen before diagnostics.
- **Results of replication (executed):** n=2,671 complete cases for all four fits (2014-01-02 onward; share limited), adj R² 0.0020 / 0.0029 (level, M1/M2) and 0.0025 / 0.0036 (log return, M1/M2). Only **8** principal-repayment dates with positive US share exist in the estimation window (2015-04-15, 2016-02-16, 2017-12-15, 2019-03-15, 2020-04-15, 2021-05-17, 2023-04-17, 2024-05-15). H1-H3 therefore rest on 8 events, 88 FX sessions inside their ±5 windows.
- **Diagnostics, effect sizes, MDE, overlap:** appended below after `gate0_diagnostics.py` runs.

---

## CA-0 — results appended 2026-10-30 (status: completed, partial; B1 blocked)

- **Command:** `~/.pyenv/versions/3.12.9/envs/Trading/bin/python nz_bond_flows/code/gate0_diagnostics.py` (git 9d6d431 plus uncommitted new files). Outputs: `nz_bond_flows/output/attempts/00_clock_audit/alignment_table.csv`, `flow_mapping_summary.csv`.
- **Window table (confirmed):** the H.10 return dated D covers Auckland [D 04:00-06:00, D+1 04:00-06:00] depending on DST (offsets NZ +12/+13, NY -4/-5). Auckland 09:00-17:00 on D is New York 15:00-17:00 on D-1 to 23:00-01:00 on D, i.e. wholly inside the return dated D. London 4pm fix is 03:00-05:00 Auckland on D, i.e. before the NZ business day, so it is not the same window. VIX close (16:15 ET on D) is 08:15-10:15 Auckland on D+1, after the return dated D ends.
- **Flow mapping (correction to my first-pass concern):** of 1,202 calendar days with a nonzero flow, 0 fall on a non-NZ business day. 130 are rolled to a later FX date, all NZ business days with no H.10 fix (US holidays), median roll 1 calendar day. The 3,465 "moved" rows are mostly zero-flow weekends, harmless. 111 nonzero rows are dropped (outside the FX sample range). So the next-FX-day rule is defensible; same-date `k=0` is the right primary alignment for settlement-dated flows.
- **Remaining uncertainties:** (a) settlement time of day inside NZ day D, (b) `TENDER_LAG=3` is an assumption, (c) `us_share` reference date, (d) `treasury_swap_merged` definition, (e) RBNZ B1 not obtained (blocked).
- **Decision:** `retain` k=0 same-session mapping; `revise` controls: contemporaneous `vix_D` must be replaced by `vix_{D-2}` (strictly before the window start) for any predictive claim, or flagged as simultaneous. `indeterminate` for `treasury_swap_merged` and `us_share` timing until the team supplies definitions.

---

## G0 — results appended 2026-10-30 (status: completed)

- **Outputs:** `nz_bond_flows/output/attempts/00_gate0_baseline/` (`coefficients.csv`, `residual_diagnostics.csv`, `sample_accounting.csv`, `event_overlap.csv`, `effect_sizes_m2_logreturn.csv`, `vif_m2.csv`, `placebo_h1.csv`, `return_autocorr.csv`, `input_hashes.csv`). Baseline report PDFs remain in `output/tables`, `output/hypothesis_tests`, unchanged apart from timestamps.
- **Sample accounting:** 6,294 FX days -> 6,293 returns -> 2,774 with `us_share` (2014 on) -> 2,679 with controls -> **2,671** with complete leads/lags. Loss is almost entirely the share series starting 2014.
- **Events (estimation sample):** principal 8 (median gap 273 sessions, 84 sessions in any ±5 window); issuance 445 (median gap 5 sessions, 91% of gaps <=10, so 2,429 of 2,671 sessions sit in some ±5 window: windows overlap almost completely); coupon 135; buyback 52.
- **Multicollinearity:** max VIF in M2 about 1.1 (lead/lag terms are not collinear). Condition number is not an issue. Overlap is a dependence problem for inference, not a collinearity one.
- **M2 log-return effect sizes (% return per NZ$1bn US-weighted principal, HAC 10 lags):**
  - pre-event sum k=+1..+5 (H1): +0.65, 95% CI [-0.25, +1.55], MDE (80% power) 1.28
  - event day k=0: -0.23, CI [-0.86, +0.40], MDE 0.90
  - post-event sum k=-5..-1 (H3): +0.67, CI [-0.20, +1.54], MDE 1.24
  - Daily NZD/USD sd is 0.67%. A typical principal event has about NZ$0.65bn US-weighted, so the H1 CI translates to about -0.16% to +1.0% per event.
- **Other coefficients (M2 log return):** `vix` -0.0056 (p=0.074), `us_release` +0.054 (p=0.29), `treasury_swap_merged` -0.006 (p=0.54), `us_coupon`, `us_buyback` insignificant. M1 event-day net flow +0.00014 per NZ$m (p=0.48).
- **Residual diagnostics (M2 log return):** heteroskedasticity strongly rejected (BP p~7e-31), non-normal (JB p~1e-53), mild serial correlation (BG p=0.004, LB p=0.004), DW 2.10; return autocorrelations at lags 1-5 are all within ±0.04. Adjusted R² 0.0036.
- **Falsification (circular-shift placebo, 300 shifts, |shift| >= 40 sessions):** placebo H1-sum sd 0.85 (larger than the reported HAC SE 0.46), and 48% of placebo sums are at least as large in magnitude as the actual +0.65. The actual H1 statistic is not distinguishable from arbitrary event dates; HAC SEs with 8 events probably understate uncertainty.
- **Against the declared decision condition (CI must bound 0.1% per NZ$1bn):** not met. CI half-width is about 0.9, nine times the bound. Status of the H1-H3 claims: **inconclusive / underpowered** (8 principal events).
- **Interpretation:** the baseline cannot support or reject the anticipation/asymmetry/reversal story. Issuance events (445) have enough count but overlap heavily, and no stage between ownership share and spot conversion is observed.
- **Limitations:** `us_share` is US-only and low-frequency; share and control timing unverified; only nominal-versus-IIB sum is checked, not reconciled against Treasury outstanding.
- **Decision:** `indeterminate` for H1-H3; `retain` as the baseline of record. Next attempt per plan: Attempt 1 (aligned, parsimonious).

---

## A1 — Aligned, parsimonious contemporaneous FX baseline

- **Date / status:** 2026-10-30 / proposed -> running
- **Hypothesis:** Net US-share-weighted NZ sovereign cash flow settled on NZ day D (N>0 means net issuance to the private market) moves the H.10 return dated D. If foreign holders convert at settlement and are unhedged, net issuance requires NZD purchase, so the sign is **non-negative conditional on conversion**; hedging, rolling, or pre-pricing make it ambiguous or zero. A zero is informative about absorption, not about the mechanism.
- **Why G0 is insufficient:** G0 uses 11 coefficients per family on 8 principal events and contemporaneous controls that post-date the fix (`vix_D`). CA-0 supports a same-session mapping, so a minimal window using only timing-justified terms is the cleanest comparison.
- **Single key difference from G0:** the model uses only the timing-justified window {0, +1} and information-set-valid controls; everything else (variables, share, sample start, HAC) is the same.
- **Equation:** `r_t = a + b0·N^US_t + b1·N^US_{t+1} + g1·vix_{t-2} + g2·us_release_t + u_t`, with
  - `r_t = 100·(ln e_t - ln e_{t-1})`, `e` = USD per NZD = 1/`dexnzus`; observation = H.10 NY noon; t = observed FX session.
  - `N^US_t = us_share_t × (I - P - C - B)` at NZ settlement date mapped to the same or next FX session; unit NZ$ billion (source NZ$m / 1000); positive = net issuance. `us_share` as-of backward (timing unverified, flagged).
  - `N^US_{t+1}` = the next session's flow. Justification for including it: settlement hour inside NZ day D is unknown and the first Auckland hours of D+1 (about 00:00-05:00) fall inside the return dated D (CA-0). It is not a free-search lead; no other lead/lag is tested.
  - `vix_{t-2}`: closing level two sessions before; strictly before the window start (CA-0). `us_release_t`: scheduled morning-ET release dummy, inside window and known ex ante. `treasury_swap_merged` is excluded from the primary spec (definition and timing unknown); it enters only as a sensitivity (lag 2).
  - No fixed effects. Missing: complete case. Sample: FX sessions from 2014-01-02 (share start) to 2025-02-07; the same sessions as G0 reported separately.
  - SE: Newey-West, 10 lags (same as G0); sensitivity 5 and 20.
- **Data:** S01-S04, derived panel `nz_bond_flows/output/attempts/00_gate0_baseline/rebuilt/intermediate/merged_constructed_panel.csv`. Script `nz_bond_flows/code/attempt1_aligned.py`; outputs `nz_bond_flows/output/attempts/01_aligned/`. Limitation: share timing, control definitions.
- **Predicted behavior / estimand:** primary estimand `b0` and `b0+b1` in % per NZ$1bn US-weighted net issuance; expected sign >= 0 conditional on conversion, ambiguous otherwise. Report MDE.
- **Falsification / sensitivity:** (1) circular-shift placebo of N^US (|shift| >= 40, 300 draws) for the empirical null of `b0+b1`; (2) HAC bandwidths 5/10/20; (3) G0 sample restriction; (4) controls with `treasury_swap_merged`.
- **Decision condition (set now):** `retain` as informative if the 95% CI for `b0+b1` excludes 0 and the placebo two-sided p < 0.05; `reject` the claim at the effect size 0.1% per NZ$1bn if the CI lies inside [-0.1, +0.1]; otherwise `indeterminate`. Not chosen on realized p.

---

## A1 — results appended 2026-10-30 (status: completed)

- **Command:** `~/.pyenv/versions/3.12.9/envs/Trading/bin/python nz_bond_flows/code/attempt1_aligned.py` (git 9d6d431 plus uncommitted new files). Inputs: panel rebuilt in G0 (hash chain in `output/attempts/00_gate0_baseline/input_hashes.csv`). Outputs: `nz_bond_flows/output/attempts/01_aligned/` (`coefficients.csv`, `side_by_side_vs_g0.csv`, `summary.csv`, `placebo.csv`, `placebo_hist.png`).
- **Sample:** 2014-01-02 to 2025-02-06, N=2,762 (G0 had 2,671; the 91 extra sessions come from dropping the ±5 leads/lags and `treasury_swap_merged`); 603 sessions with nonzero US-weighted net flow. Restricting to the G0 sample (N=2,660) leaves estimates unchanged to 3 decimals.
- **Estimates (% return per NZ$1bn US-weighted net issuance, HAC 10 lags):**
  - b0 = +0.119 (SE 0.199, CI [-0.27, +0.51]); b1 = +0.292 (SE 0.318, CI [-0.33, +0.92])
  - **b0+b1 = +0.411, SE 0.415, 95% CI [-0.40, +1.22], p = 0.32; placebo p = 0.18; MDE (80%) 1.16;** adj R² 0.0003.
- **Against G0 M1 (same variables, 11-term window, contemporaneous controls):** b0 0.141 -> 0.119, b1 0.343 -> 0.292, SEs unchanged (0.200 -> 0.199; 0.320 -> 0.318). Changing alignment and controls and dropping nine unused terms did not move the answer.
- **Sensitivity:** HAC bandwidth 5/20: SE 0.413/0.420, p 0.32/0.33. Adding `swap_l2`: b0+b1 = +0.343 (SE 0.422). Placebo sd 0.31 is below the HAC SE of 0.42, so HAC is not understating uncertainty here, unlike in the 8-event G0 principal test.
- **Economic scale (descriptive, not a new test):** a typical US-weighted net-issuance day is about NZ$0.06bn, so the CI corresponds to roughly -2.5 bp to +7.6 bp of NZD/USD on a typical day, versus a daily return sd of 67 bp. The largest day (NZ$0.82bn) would map to about -33 bp to +100 bp. The data therefore rule out large moves from ordinary-size flows but not large moves from the rare large flows.
- **Decision condition:** CI includes 0 and is not inside [-0.1, +0.1] per NZ$1bn, so the rule gives `indeterminate`. Interpretation: no evidence of a same-session or +1 net-flow effect; the sign is positive as the conversion story predicts but not distinguishable from noise.
- **Limitations:** the flow is US-share-weighted accounting flow, not observed FX order flow; scheduled issuance may be priced earlier; share and `treasury_swap_merged` timing unverified; one-sided hedging/rolling cannot be separated.
- **Next (at most one):** A2, the issuance/principal split. Caveat set now: principal has only 8 events, so A2 is expected to be `underpowered` for principal and informative only for issuance.

---

## A1r — Attempt 1 rerun: fixing-timestamped event windows and replacement controls

- **Date / status:** 2026-10-30 / proposed -> running. Supersedes the A1 results folder `nz_bond_flows/output/attempts/01_aligned/` (overwritten at the user's instruction; the A1 numbers stay in this journal above: b0+b1 = +0.411, CI [-0.40, +1.22], N=2,762).
- **Hypothesis:** same as A1. Net US-share-weighted cash flow settled on NZ day D (N>0 = net issuance) moves NZD/USD across the window that contains settlement; sign >= 0 conditional on unhedged conversion, otherwise ambiguous.
- **Why A1 is insufficient (identified weaknesses):** (1) controls were levels (VIX, spliced NZ-US 2y differential, release dummy) in a returns regression; the differential's pre-2011 leg is an 11am government-bond yield and the sample only starts 2014 anyway; the growth control was a weak dummy. (2) Alignment was by calendar date, not by timestamp. (3) The share series applies each IMF half-year position (2014-S1 = end-June 2014) from the first day of that half-year, i.e. position-date look-ahead of up to 6 months (verified in `raw/US_Share_of_New_Zealand_Debt.xlsx`, sheet `Calcs and Graphs`).
- **Clock (anchored to NZ local time, `Pacific/Auckland`):**
  - Settlement of NZ date D is assumed at **10:00 NZ local**. Documented assumption; settlement time of day is unknown. Windows are identical for any assumed time in [06:00, 13:00) NZ for both FX sources below, so the assumption only matters if settlement is after 13:00.
  - Primary FX fixings: Fed H.10 noon New York, converted to UTC and NZ local with DST rules (NZ local 04:00-06:00 on the next calendar date, see CA-0). Event window = (last fixing before settlement, first fixing after). With S = 10:00 on D this is H10(D-1 NY) -> H10(D NY), i.e. 05:00-06:00 NZ on D to the same time on D+1.
  - Alternate source (robustness, not independent): RBNZ B1 NZD/USD (S12, S13). Observation time is **not documented** in the files; inferred from the data as about 13:00 NZ local (grid search of B1 returns on adjacent H.10 returns, best at 13:00, SSE flat from 11:30 to 14:30; third-party pages say about 15:00). Label `inferred, unverified`.
  - Flow date D uses its NZ calendar date; flows on dates with no H.10 fixing in the window ending that day roll into the next window by the same rule.
- **Equation:** `r_j = a + b0·N^US_j + b1·N^US_{j+1} + g1·dlnVIX_j + g2·dPol_j + g3·rBrent_j + u_j`
  - `r_j = 100·(ln e_j - ln e_{j-1})` over the H.10 window j, `e` = USD per NZD (= 1/`dexnzus`).
  - `N^US_j` = us_share × (I - P - C - B) for settlements assigned to window j, NZ$ billion. `N^US_{j+1}` = next window (same reason as A1: unknown time of day within D).
  - **Controls (replace vix level, spliced differential level, us_release):** each is the change over window j of the last observation stamped at or before the window end minus the last at or before the window start, so nothing after the end fixing is used. Stamps are deliberately late (latest possible) to rule out look-ahead:
    - Risk `dlnVIX`: change in ln VIX close (FRED VIXCLS, CBOE close 16:15 New York).
    - Policy `dPol`: change in (NZ 2y swap close, RBNZ B2 `INM.DS02.NZZC`, stamped 23:59 NZ local) minus (US 2y Treasury, FRED DGS2, stamped 16:00 New York). Swap leg exists from 2011, so the 2014+ sample is clear of the pre-2011 bond-yield splice.
    - Real growth `rBrent`: 100·change in ln Brent spot (FRED DCOILBRENTEU, stamped 23:59 London). Global-demand/commodity proxy; imperfect (oil also has supply shocks).
  - **Why this triplet (fixed from coverage, timing and mutual correlation only, no FX return used):** candidates screened were dlnVIX, dUST2, dRealY10 (DFII10), rBrent, rNasdaq (NASDAQCOM), dT10Y2Y over 2014-2025. Equity return is redundant with VIX (rho -0.71). The 10y real yield is excluded because rho 0.64 with the US 2y leg of the policy variable. Brent has |rho| <= 0.19 with the others. dT10Y2Y and DFII10 are reported as sensitivities, not alternatives chosen on fit.
  - Sample: windows ending 2014-01-02 to 2025-02-07 (share start to FX end); complete cases. SE: Newey-West 10 lags; sensitivity 5/20. No fixed effects.
- **Data (IDs in `DATA_SOURCES.md`):** S01-S04; new S11 (B1), S12 (B2), S13-S19 (FRED). Script `nz_bond_flows/code/attempt1r.py` with `code/timing.py`; fetch script `code/fetch_fred.py`. Outputs `nz_bond_flows/output/attempts/01_aligned/`.
- **Predicted behavior / estimand:** `b0+b1` in % per NZ$1bn US-weighted net issuance; sign >= 0 conditional on conversion. Primary inference: HAC 95% CI plus circular-shift placebo p.
- **Falsification / sensitivity (all declared now):** (1) placebo shifts of the flow series (300, |shift| >= 40 windows); (2) the old A1 controls under the new alignment, to isolate the effect of the control change; (3) B1-window outcome with B1-timed controls; (4) share lagged one half-year (position-date-valid); (5) controls shifted one more window (strictly pre-window); (6) swap in dT10Y2Y / DFII10 for Brent; (7) HAC 5/20.
- **Decision condition (unchanged from A1):** `retain` if the CI for b0+b1 excludes 0 and placebo p < 0.05; `reject` the claim at 0.1% per NZ$1bn if the CI lies inside [-0.1, +0.1]; else `indeterminate`.

---

## A1r — results appended 2026-10-30 (status: completed)

- **Command:** `~/.pyenv/versions/3.12.9/envs/Trading/bin/python -W ignore nz_bond_flows/code/attempt1r.py` (git 9d6d431 plus uncommitted new files; `code/timing.py`, `code/test_timing.py`, `code/fetch_fred.py`). Outputs overwritten in `nz_bond_flows/output/attempts/01_aligned/` (`coefficients.csv`, `summary.csv`, `side_by_side_vs_a1.csv`, `aligned_dataset.csv`, `placebo.csv`, `placebo_hist.png`). Inputs and hashes in `DATA_SOURCES.md` (S01-S04, S11-S17).
- **Correction to the spec above:** the claim that windows are identical for any settlement hour in [06:00, 13:00) is wrong at the lower edge. NY noon is 06:00 NZ local in NZDT/EST, so a 06:00 settlement is not strictly after the fixing. Verified numerically: S = 08, 10, 12 give identical window assignments (0 differences), S = 06 differs on 2,196 rows. The correct invariance range is (06:00, 13:00) NZ local; `test_timing.py` uses 07:00.
- **Sample:** windows ending 2014-01-02 to 2025-02-06, N = 2,773 (A1: 2,762), 607 windows with nonzero flow. Flow assignment reproduces the A1 count of event windows.
- **Primary result (% return per NZ$1bn US-weighted net issuance, HAC 10 lags):** b0 = +0.123 (SE 0.192), b1 = +0.285 (SE 0.318); **b0+b1 = +0.408, SE 0.395, 95% CI [-0.367, +1.183], p = 0.30; placebo p = 0.18 (placebo sd 0.30); MDE (80% power) 1.11.** A1 gave +0.411 (SE 0.415, CI [-0.40, +1.22]). The flow estimate did not move.
- **Controls (primary):** `dlnVIX` -0.0083 per 1% VIX change (p < 0.001, correct risk-off sign); `dPol` +2.47 per 1pp rise in the NZ-minus-US 2y differential (p < 0.001, correct sign); `rBrent` +0.0068 (p = 0.16). Adj R² rises from 0.0003 (A1) to **0.037**. Flow N0 has correlation 0.03, 0.02 and -0.01 with the three controls, so the controls explain returns but do not confound the flow coefficient.
- **Sensitivity (b0+b1):** HAC 5 / 20: +0.408 (p 0.30 / 0.31). Old VIX-level control under new alignment: +0.409 (SE 0.417). Brent replaced by dT10Y2Y: +0.454 (p 0.25); by DFII10: +0.406 (p 0.30). Share lagged 6 months (N = 2,648): +0.392 (p 0.31). Controls shifted one more window (strictly pre-window): +0.423 (p 0.31).
- **B1 window (exploratory):** b0 +0.457 (p 0.064), b1 +0.032, b0+b1 +0.489, CI [-0.005, +0.983], p 0.053, placebo p 0.077. One of nine sensitivities, B1 fix time inferred and not documented, so this is not a confirmatory result. Pattern differs from H.10 (mass on b0 rather than b1), consistent with the 10:00-NZ settlement falling shortly before the roughly 13:00 B1 fix. Multiplicity: nine specifications, none a prespecified test of a different hypothesis; the B1 result would not survive any correction.
- **Decision condition:** CI contains 0 and is not inside [-0.1, +0.1] per NZ$1bn, so by the rule the result is `indeterminate`. Interpretation: replacing the controls and moving to fixing-timestamped windows does not change the answer; the flow coefficient is robust to control choice, so the earlier null was not caused by bad controls. Typical-day scale from A1 still holds (about -2 to +7 bp per NZ$0.06bn).
- **Limitations:** settlement time of day assumed; B1 time inferred; Brent and DGS2 stamps are conservative assumptions; the real-growth proxy is imperfect; share and flow are accounting quantities; `dPol` combines a NZ close stamped late and a US 16:00 stamp, so the policy change spans about 24h with only part inside the window.
- **Next (at most one):** the A2 issuance/principal split remains underpowered for principal (8 events); the data cannot narrow the interval by changing controls. Candidate next steps are A3 state-dependent local projection (needs an outstanding-debt denominator from Treasury data) or moving to an intermediate outcome (B2 government yields, Attempt 5) because B2 is now available locally.
- **Housekeeping (2026-10-30):** `code/attempt1_aligned.py` (the A1 script) now writes to `output/attempts/01_aligned_a1_superseded/` so a rerun cannot overwrite A1r's `01_aligned/`. No other change to it.

---

## Housekeeping — repository cleanup, 2026-10-30

- Policy (user): detailed history lives here; every other artifact keeps only the latest version of its attempt.
- A1 collapsed into A1r. `code/attempt1_aligned.py` was removed (recoverable from git commit ad897e7); the entry above that says the A1 script writes to `01_aligned_a1_superseded/` is obsolete. `output/attempts/01_aligned/` holds A1r only; the stale A1 file `side_by_side_vs_g0.csv` was deleted before commit. A1's numbers (b0+b1 = +0.411, CI [-0.40, +1.22], N = 2,762) remain in the A1 results entry as the historical record.
- `output/attempts/00_gate0_baseline/rebuilt/` (a 3 MB duplicate of `output/intermediate/merged_constructed_panel.csv`) was deleted; `gate0_diagnostics.py` now uses a temporary directory. Only the A1 script used that folder.
- Verified after cleanup: the unit tests pass (8) and reruns of `gate0_diagnostics.py` and `attempt1r.py` leave all committed outputs unchanged.
- The five baseline report PDFs regenerated by the G0 replication were restored to the committed versions (only embedded creation timestamps differed).

---

## A3 — State-dependent local projection of potential foreign-held debt pressure

- **Date / status:** 2026-10-30 / proposed -> running
- **Hypothesis (descriptive LP, not causal):** Settlement-day **issuance pressure** (foreign-held share of new supply relative to debt outstanding) raises NZD/USD cumulatively over the following sessions, and the response is larger when global stress is high because dealer/intermediary absorption deteriorates. Principal-redemption pressure should do the opposite (foreign holders reconvert), but is expected to be underpowered. Both are conditional on conversion and no hedging; sign ambiguity is reported.
- **Why A1r is insufficient:** A1r used a net-flow variable weighted by a US-only, half-yearly share, scaled in NZ$ rather than relative to debt outstanding, with a fixed {0,+1} window and no state dependence. Its CI is far too wide to inform absorption conditions. A3 targets the plan's priority revision: scaled pressure, separate issuance/principal, cumulative responses, one theory-driven state.
- **Single key difference from A1r:** the response is a local projection across horizons with a one-state interaction. Two supporting changes are required by the plan: the flow variable is scaled by outstanding debt, and the ownership share is the RBNZ non-resident share (below). Both are reported with their A1r-style counterpart as a sensitivity so their separate effects are visible.
- **Equation (for h in {0, 1, 3, 5}):**
  `y_{j,h} = a_h + bI_h·ZI_j + dI_h·ZI_j·S_j + bP_h·ZP_j + dP_h·ZP_j·S_j + k_h·S_j + g_h'·X_j + e_{j,h}`
  - `y_{j,h} = 100·(ln e_{j+h} - ln e_{j-1})`: cumulative return from the fixing before window j (settlement assumed 10:00 NZ local on D, H.10 NY-noon fixings, windows from `code/timing.py`) to the fixing h sessions later. `e` = USD per NZD.
  - `ZI_j = 100 · s_m · I_j / O_m`, `ZP_j` likewise with principal `P_j`. `I_j`, `P_j` = private-holder issuance and principal cash settling in window j (NZ$ m, from `nz_daily_flows.csv`: nominal + IIB, issuance sign-flipped). `s_m` = RBNZ D31 non-resident share = sum of non-resident holdings / sum of total in market over bonds (`load.d31()`), at the last month-end **before the settlement's calendar month**. `O_m` = total NZ government bonds on issue at that month-end (`load.onissue()`, NZ$ m). Units: percent of debt outstanding held abroad-weighted ("pressure"), not realized FX flow. Positive for both.
  - `S_j` = ln VIX at the last close stamped at or before the start fixing of window j, standardized over the estimation sample. Single state, lagged by construction.
  - `X_j` = the three A1r controls (`dlnVIX`, `dPol`, `rBrent`) measured over the **previous** window, i.e. only information before the window start.
  - Coupons and buybacks are excluded (declared; frequency/exposure not material to the issuance/principal question).
  - Sample: windows ending 2015-08-03 (D31 start, first full month with a prior month-end) to 2025-02-06; complete cases. No fixed effects. SE: Newey-West with `10 + h` lags to cover overlapping outcomes.
- **Data:** S01, S02, S10-S17, `raw/hd31.xlsx` (`S06`), `raw/onissue.xlsx` (`S05`); script `nz_bond_flows/code/attempt3.py` (uses `code/timing.py`, `code/load.py`); outputs `nz_bond_flows/output/attempts/03_local_projection/`. Limitations: D31 publication lag (about mid following month) not verified, so month-end shares are position-date valid but possibly not publication-date valid; the aggregate share is applied to new issuance although actual allotment by holder is unobserved; aggregate share is applied to principal although the maturing bond's own non-resident share is known and differs (e.g. 69.6% for GB1217 vs the 56-70% aggregate), which affects only the underpowered principal terms.
- **Predictions / estimands:** sign `bI_h >= 0`, `dI_h >= 0` (stress amplifies price impact); `bP_h <= 0`, `dP_h <= 0`. **Primary:** `bI_1` and `dI_1` (h = 1 matches A1r's {0, +1} window; chosen now, not by fit). Effect unit: % return per 0.1 percentage point of outstanding; also per 1 sd of nonzero `ZI` and the stressed effect `bI_h + dI_h` at S = +1 sd. Full coefficient paths with 95% CIs for all four horizons; Holm adjustment across the four `dI_h`.
- **Falsification / sensitivity (declared now):** (1) pre-window outcome `y = 100·(ln e_{j-1} - ln e_{j-4})` on the same regressors: significant `ZI` here would signal pre-pricing or confounding; (2) circular-shift placebo of ZI and ZP together (300 shifts, |shift| >= 40 windows) for the empirical null of `dI_1`; (3) US-share version: replace `s_m` by the team's IMF US share, sample from 2014-01-02; (4) isolated-issuance subset: windows with no other issuance within +-5 windows (count reported; dropped if fewer than 30); (5) HAC bandwidth 5/20 above the default.
- **Decision condition (set now):** `retain` stress amplification if the 95% CI of `dI_1` lies above 0, placebo p < 0.05 and the pre-window test has p > 0.05. `reject` a practically relevant effect if the CIs of `bI_1` and of `bI_1 + dI_1` (S = +1 sd) both lie inside +-0.05 percentage points of return per 0.1 pp of outstanding (5 bp). Otherwise `indeterminate`. Principal terms: report only; `underpowered` if fewer than 10 principal events (expected: 7).

---

## A3 — results appended 2026-10-30 (status: completed)

- **Command:** `~/.pyenv/versions/3.12.9/envs/Trading/bin/python -W ignore nz_bond_flows/code/attempt3.py` (git b9d727d plus the commit adding the script). Outputs `nz_bond_flows/output/attempts/03_local_projection/` (`coefficients.csv` long format, unscaled: coefficient per 1 percentage point of outstanding; `summary.csv`, `placebo.csv`, `leave_one_principal_event_out.csv`, `lp_paths.png`). Inputs: S01, S02, S05, S06, S10-S17 (hashes in `DATA_SOURCES.md`).
- **Deviation from the spec and fixes:** none to the specification. Two coding errors were fixed before the reported run: a sample-start argument ignored for the US-share sensitivity, and a variable-name clash in the VIX-state timing. The `holidays` import in `load.py` was made lazy so the D31 and on-issue readers work in the Trading env.
- **Sample:** 2,377 windows ending 2015-08-03 to 2025-02-07. 410 windows with issuance pressure (`ZI` mean 0.25 pp of outstanding, sd 0.39, max 4.2); only 7 principal windows (2016-02-16, 2017-12-15, 2019-03-15, 2020-04-15, 2021-05-17, 2023-04-17, 2024-05-15). Isolated issuance windows (no other issuance within ±5 windows): 17, below the declared 30, so the isolated-subset sensitivity was not run.
- **Primary, issuance (all numbers: % return per 0.1 pp of outstanding, HAC `10+h` lags, 95% CI):**

  | h | b_I (average state) | d_I (x 1 sd VIX) | b_I + d_I (S = +1 sd) |
  |---|---|---|---|
  | 0 | +0.0048 [-0.013, +0.023] | +0.0047 [-0.006, +0.016] | +0.0095 [-0.003, +0.022] |
  | **1 (primary)** | **-0.0014 [-0.023, +0.020]** | **-0.0045 [-0.019, +0.010]** | **-0.0059 [-0.024, +0.012]** |
  | 3 | -0.0071 [-0.034, +0.019] | +0.0018 [-0.017, +0.020] | -0.0053 [-0.027, +0.017] |
  | 5 | -0.0077 [-0.040, +0.025] | +0.0098 [-0.015, +0.034] | +0.0021 [-0.025, +0.029] |

  A typical issuance event is 2.5 units (0.25 pp), so the h = 1 CI for `b_I` is about -5.7 bp to +5.0 bp per typical event; the largest event (4.2 pp, 42 units) would map to about -96 bp to +84 bp. Holm-adjusted p-values for `d_I` across the four horizons are all 1.0. Placebo p for `d_I` at h = 1: 0.74.
- **Falsification:** pre-window outcome (return over the three sessions before the window): `ZI` p = 0.43, `ZI x S` p = 0.24 (the stressed sum `ZI + ZI x S` has p = 0.067 and `ZP x S` p = 0.052: close to, but not past, the declared 0.05 line for the tests named in the condition). No evidence of pre-pricing or confounding for issuance.
- **Sensitivity:** HAC 5 and 20 give the same h = 1 coefficients with SEs within 5%. US-share version (2014-01-02 on, N = 2,774; effects per 0.1 pp of US-weighted pressure): h = 1 `b_I` +0.008 [-0.074, +0.089], `d_I` -0.022 [-0.073, +0.029]; no horizon is significant. Same conclusion with a coarser share.
- **Principal (report only; 7 events, `underpowered`):** `d_P` (principal pressure x stress) is negative at h = 0, 1, 5 (-0.023, -0.023, -0.032 per 0.1 pp; HAC p 0.000, 0.004, 0.002), the sign the stress-reconversion story predicts. Do not rely on it: the circular-shift placebo p at h = 1 is 0.14 (HAC p 0.004, so HAC understates uncertainty with 7 events, as in G0); leave-one-event-out keeps the sign in all seven fits (range -0.009 to -0.032 per 0.1 pp, z from -1.6 to -4.1), so no single event drives it, but the estimate is a seven-point cross-event slope on VIX. The average-state `b_P` is about 0 at every horizon. Exploratory, not confirmatory; the principal-only analysis cannot be made adequate with public data (7 events).
- **Decision condition:** `retain` fails (`d_I,1` CI [-0.019, +0.010] does not lie above 0; placebo p 0.74). `reject` a practically relevant effect holds at h = 1: the CIs of `b_I` [-0.023, +0.020] and of `b_I + d_I` at S = +1 sd [-0.024, +0.012] both lie inside the declared ±0.05 bound. The bound is a judgment set before fitting; it excludes effects of 5 bp per 0.1 pp of outstanding, not effects on rare very large events. Status: **no detectable issuance-pressure effect or stress amplification at the declared magnitude (supported null, conditional on assumptions); principal terms inconclusive.**
- **Interpretation:** scaling by outstanding debt, using the measured non-resident share and allowing stress dependence does not reveal an FX response to issuance. This is consistent with absorption by FX intermediaries or with pre-pricing and hedging, but the data cannot separate these. It does not test conversion because none of the transmission stages is observed.
- **Limitations:** aggregate non-resident share applied to new issuance (actual allotment by holder unobserved) and to principal (the maturing bond's own share is known and differs); D31 publication lag unverified; one state variable; no horizon beyond five sessions; ZI is an accounting scale, with correlation to supply announcements unmodeled.
- **Next (at most one):** A5(b), NZ government 2/5/10-year yields from B2 against the same pressure variables, because the proximate market effect of issuance is yield/price, and the B2 files are local. Check the Aug 2025 B2 methodology change first (sample ends 2025-02, so before the break).

---

## Direction note — 2026-10-30 (after A3)

- **User direction:** the objective is predicting FX level, change or volume. NZ-only evidence so far: G0 and A1r indeterminate (CI too wide to inform), A3 a supported null for issuance pressure at the declared bound, principal underpowered (7-8 events). The user considers NZ possibly a dead end and expansion to other currency pairs a candidate conclusion.
- **Consequences recorded:** (1) A5(b) (NZ yield outcome) is deprioritized, since it is not an FX outcome; it remains available. (2) PLAN.md restricts scope to NZ and says other countries are research leads, so any cross-country or cross-currency-pair work needs an explicit user scope change first; nothing was started. (3) Cross rates of NZD (AUD, JPY, EUR) remain a plan-sanctioned robustness check, dependent on NZD/USD, not an independent sample.
- **What a cross-country extension would reuse:** `code/timing.py` (fixing windows), the window-change controls in `code/attempt1r.py`, and the pressure construction in `code/attempt3.py`. What it would need: country-specific settlement calendars and times, holder-composition data (IMF PIP, `data/` folder), debt outstanding and daily flow schedules, and fixing sources per currency (`FX.csv` already holds dexalus, dexjpus, dexszus = AUD, JPY, CHF per FRED naming; H.10 also publishes other currencies such as Mexico and South Africa, not yet downloaded).
- **Status of repository:** all attempts through A3 committed; tests pass (8); outputs hold only the latest version per attempt.
