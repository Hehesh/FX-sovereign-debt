# PLAN.md — Sovereign debt operations and NZD FX: iterative research protocol

## Mandate

You are a coding/research agent working in an **existing** sovereign-debt/FX practicum repository. Your task is to investigate whether publicly observable New Zealand sovereign debt operations generate measurable FX effects, and—more fundamentally—where the proposed economic transmission mechanism breaks down. Act like you are proving or refuting a narrowly formulated proposition: specify assumptions, derive observable implications, test them, document counterevidence, and stop when the public data cannot identify the claim.

**Current scope: New Zealand only.** Mexico, South Africa, and other countries are research leads, not permission to add a country panel. The human principal is the final reader of successful, well-supported outputs and the provider of publicly available data only when automated access is blocked. Work autonomously on accessible sources. Never claim significance or economic causality merely because a model fits better.

## First action: inspect, preserve, reproduce

1. Inspect repository layout, README, data files, code, execution environment, and the current regression and its outputs. **Follow the repository's current coding style and level of rigor**. Do not assume the directory layout below overrides what is actually present. Prefer short Python functions and existing libraries, not scaffolding, factories, elaborate tests, dashboards, or a model zoo.
2. Preserve all existing code, source files, and results. **Never overwrite or delete** existing artifacts, rename original columns in place, rewrite Git history, or silently change an established baseline. New outputs go into separate, numbered, clearly named attempt folders; new scripts only when needed. If an existing script needs changing, copy to a new file or make an additive backward-compatible change and document it. The one exception is for the time alignment step that will take place first.
3. Reproduce the original regression before diagnosing it. Record actual sample dates, counts, dropped observations, formula, quote direction, flow units, controls, standard errors, R², coefficient tables, and existing file hashes. Do not reinterpret original results without inspecting the actual implementation.
4. Check whether the project already has `ATTEMPTS.md`, a data-source register, and run folders. Extend them without removing earlier entries. If missing, create them with the minimal schemas specified below.
5. Use the current project's paths and CLI conventions. Previously discussed layout: code in `basedir/code/`, inputs in `basedir/regression/`, outputs in `basedir/output/`; verify rather than impose this. Do **not** scatter duplicate data or generate a second framework.

## Research thesis and critical distinctions

Baseline historical specification (verify against actual code):

- Net sovereign cash flow, in NZD: `N_t = I_t - P_t - C_t - B_t`, with issuance `I`, principal repayment `P`, coupon `C`, and buyback `B`. Distinguish **nominal** from **inflation-indexed** bonds; verify inflation indexation, settlement units, and whether the script has combined them appropriately.
- Existing putative foreign flow: `F_t = s_t^foreign N_t` (the ownership share may be interpolated or low-frequency; audit how it is mapped to daily observations).
- Existing outcome: daily changes in the NZD/USD rate, modeled as a function of 5 leads and 5 lags of flows plus risk/policy/growth controls. Previous reported fit: R² < 0.01, not a precise measured result until reproduced.
- Existing data filenames previously mentioned: `nz_daily_flows.csv` (`date,nz_business_day,nom_coupon,nom_principal,nom_issuance,nom_buyback,iib_coupon,...`), `FX.csv` (`date,dexalus,dexjpus,dexnzus,dexszus`), `Controls - Regression Control Panel.csv` (`date,vix,treasury_swap_merged,us_release`). **Inspect actual headers** rather than guessing remaining fields.

**The elephant in the room:** scheduled issuance, coupons, and repayments are accounting cash flows, **not** observed FX order imbalance. Transmission requires foreign holder ownership → portfolio reinvestment versus withdrawal → spot conversion or hedge initiation/roll/settlement → net dealer/intermediary inventory and liquidity → price effect. Large U.S. financial institutions might retain currency exposure or roll the debt; residence is not proof of conversion. Investors may hedge before maturity. FX markets can absorb flow, and public payment schedules can be priced in well before settlement. Thus no fit improvement should be mistaken for recovery of the missing stages.

Additional hypotheses worth examining, not assuming:

- Foreign **non-bank** holders may be more marginal/price-sensitive than foreign banks, particularly in emerging markets (Fang, Hardy, Lewis; see Sources). This motivates composition analysis, **not** a claim that NZ non-bank share is known daily or that non-banks must immediately trade spot.
- Financial dollarization / foreign-currency deposit shares (Levy Yeyati) could proxy broad currency preferences across investor economies, but **resident deposit dollarization is neither institutional hedge ratio nor actual sovereign-bond settlement conversion**. Treat only as a sensitivity variable or future cross-country research direction, not a daily NZD regressor.
- Dori's suggestion to study major foreign-holder countries is useful. **Do not assume NZD/USD corresponds only to U.S. investors**: non-U.S. transactions can be executed or intermediated through USD legs. Bilateral holdings identify residency, not the execution currency or ultimate owner.
- Scheduled events might affect *volatility*, conditional *tails*, *bond yields*, or *auction demand* even without predictable daily spot returns. These are separate hypotheses and should not be represented as a successful replication of the original FX-return claim.

## Non-negotiable data and timing discipline

**All regressions must run solely from local datasets.** Download raw publicly accessible files and save immutable versions locally before fitting. Source-fetch scripts (if needed) may access networks; fitting/plotting scripts must not. A clean offline rerun must succeed once data are present. Never call remote APIs from model code.

For every **existing or newly acquired** input, track in a concise source register (e.g. `DATA_SOURCES.md` or `data/sources.csv`):

- Local path, original filename, dataset name, provider, human-navigable **landing page** containing access to its download, direct file/API URL *if actually verified*, download date, format, license/access limitations, file SHA256, original temporal frequency, units/quote direction, date/time zone and **observation/fix/settlement convention**, sample range, important transformations, and specific runs using it.
- If a file was supplied by the team and its public provenance cannot be verified, label `source_unverified`, preserve it, and request the original download page only if material. Do not invent source URLs. If automated access is blocked, create a small **BLOCKED_DATA** entry with URL, exact navigation clicks, required fields/period, reason for block and where the human should save the file. Continue on feasible local alternatives.
- Keep raw and processed files separate. Record the input hashes and transformation script for each processed dataset. Never silently overwrite a downloaded source when the provider revises history.
- No invented intraday prices, investors' trades, currency hedging ratios, auction surprises, or funding flows. Avoid forward-fill that misrepresents publication timing. Flag low-frequency ownership shares used at daily resolution; use last actually available information if the purpose is real-time prediction, and explicitly distinguish a retrospective descriptive analysis.

**Clock audit is the first substantive test**, before adding any economic complexity:

1. Resolve exactly what `dexnzus` means from the local metadata and upstream FRED/Fed series. Check whether the project uses **DEXNZUS** (NZD per USD) or **DEXUSNZ** (USD per NZD), because their inversion changes signs. Do not assume a previous conversation correctly identified the code. The Fed H.10 observations are New York noon buying rates, not London 4 p.m. fixes. Match each column to its provider's published definition.
2. For the NZ government flow data identify **contractual maturity/coupon date**, **actual settlement/value date**, **NZ business-day roll conventions**, and whether activity is dated on tender, announcement, or settlement date. If unknowable, label that uncertainty and test only predeclared plausible conventions.
3. Log date/time zones and actual fixing/closing timestamps of each FX and control series. Use `Pacific/Auckland`, `America/New_York`, and `Europe/London` timezone-aware conversion, including different DST switches. Build a short alignment table of NZ event/settlement moments versus FX observation intervals. A one-day label shift is not a substitute for verified timing.
4. Check U.S. announcement timestamps against FX observation cuts. Do not condition on U.S. releases that occurred **after** the chosen FX observation when claiming predictive inference. In retrospective contemporaneous association models, flag their simultaneity and temporal order instead.
5. Compare existing Fed H.10 FX with **RBNZ B1 daily NZD/USD**, whose local collection/publication convention must be verified from official metadata. Treat them as **alternative observation windows**, not repeated independent observations. Align trading calendars without introducing weekend carryover artifacts.
6. Keep a small timing-audit artifact (CSV/MD), and document the alignment choice in each attempt. **If timestamps cannot be verified, stop claiming event-day identification.**

## Testing order — one economically motivated attempt at a time

**Gate 0 — Baseline replication and diagnosis.** Reproduce existing regression as-is; record all outputs. Compute daily log return `r_t = ln(USD per NZD)_t - ln(USD per NZD)_{t-1}` using the correctly identified quote. Do not conflate level differences, pips, percent, and basis points. Report confidence intervals, effect sizes per economically interpretable flow shock, sample coverage, autocorrelation, overlap of 11-day event windows (events roughly every six days was a preliminary estimate), multicollinearity and model residual diagnostics. Calculate a defensible minimum detectable effect under declared assumptions or report confidence-interval bounds. A small R² alone is **not** a failure criterion in daily FX.

**Attempt 1 — Correct alignment, parsimonious FX baseline.** With the **same economic variables**, estimate a minimal contemporaneous flow specification and a small prespecified timing window based on the audit (e.g. 0/+1, if justified). Use log returns. Keep existing controls only where temporally valid. Compare coefficients, standard errors, and supported causal ordering against Gate 0. Do not search offsets for minimum p-value. Any alternate alignment must have ex ante timing justification.

**Attempt 2 — Split gross flows / economic asymmetry.** Test whether issuance and principal redemption have distinct effects: separate nonnegative `I_t`, `P_t`, `C_t`, `B_t` and foreign-holder-weighted versions only if shares are defensibly defined. Gross activity can be large even when netting cancels. Prefer a minimal issuance/principal model first; add coupons/buybacks only if exposure and frequency justify them. Predeclare expected sign **conditional on conversion** and report ambiguity due to hedges/reinvestment. Separate IIB and nominal flows only when material and correctly measured.

**Attempt 3 — State-dependent local projection (priority structural revision).** Model cumulative FX response across prespecified horizons `h ∈ {0,1,3,5}` (reduce if sample/event counts demand) rather than an 11-coefficient distributed-lag regression. For each horizon, estimate:

`log(e[t+h]) - log(e[t-1]) = alpha_h + beta_h Z[t] + delta_h Z[t]*S[t-1] + gamma_h' X[t-1] + error[t,h]`

- `e`: **USD per NZD**, so higher means NZD appreciation. `Z[t]`: **signed, scaled, clearly named potential foreign-held debt pressure**, preferably constructed separately for principal redemption and issuance: e.g. `(foreign_share[t-1] * principal[t]) / outstanding_NZ_government_debt[t-1]`. **Do not call it realized FX flow**; principal has a different economic sign than issuance. If no accurate debt-outstanding denominator, use a prespecified within-sample scale and justify it without fitting to FX.
- `S[t-1]`: **one** predeclared state, e.g. lagged VIX (global stress) or an independently sourced NZ financial-liquidity proxy. Lag state variables to prevent mechanical contemporaneous contamination. State interaction should test an actual theory (market absorption deteriorates under stress), not arbitrary control permutations.
- `X[t-1]`: small, economically justified control set from locally available series, respecting information time. Use HAC/Newey–West or other justified serial-dependence-robust errors for overlapping cumulative returns. Specify lag bandwidth. No country fixed effects/time fixed effects for the NZ-only phase.
- Overlapping outcome windows and close-settled events require explicit sensitivity or an isolated-event subset. Provide coefficient **paths with confidence intervals**; joint/predeclared tests as appropriate. LP is **descriptive** unless an exogenous shock is identified.

**Attempt 4 — Large isolated maturities / liquidity conditioning, only if powered.** Inspect full distribution of principal maturities, coupon sizes, nearby issuance and repurchases. Predefine `large` (e.g., top decile of positive principal across sample, with count), isolation window, and relevant state before looking at FX. Compare event-window cumulative FX returns against reasonable date/weekday/macro-risk benchmarks; preserve overlap and sparse-event cautions. If fewer than enough independent large events to estimate meaningful intervals, log `underpowered` and stop—do not move thresholds until significant.

**Attempt 5 — Alternative observable outcomes, if original spot claim remains unidentified.** Using local public datasets, test **(a)** absolute or squared daily FX log returns against gross settlement exposures (conditional heteroskedasticity is not directional alpha), and/or **(b)** change in NZ government 2/5/10-year secondary-market yields against sovereign operations. Prefer the most proximate outcome supported by data. RBNZ B2 changed its government-bond-yield source/observation convention in **August 2025**; document this potential break before combining historical and modern yields. Fixed-income effects are a **different** outcome, not evidence of FX effects.

**Attempt 6 — Auction-demand information, only with identifiable data.** Check NZ Debt Management tender data for bid-to-cover, issuance/tender amount, accepted yield, cut-off yield, settlement date, and pre-auction secondary yields. If possible, define and validate an auction demand/tail proxy using information available **before** the outcome measurement. Auction tail/demand is not automatically exogenous; do not label it an `unexpected shock` unless a defensible expectation benchmark and timing exist. Start with bond yields, FX downstream. Do not build this model merely because the data contain columns.

**Composition/context branch — not an indiscriminate additional model.** Use IMF PIP (formerly CPIS) to profile **bilateral NZ-issued debt-security holdings** by investor residence; isolate sovereign/government issuer where the sector coverage allows, and do not substitute all NZ debt securities without labeling the difference. Display largest holder countries, shares, missing reporting economies, relevant currency denominations, and the years for which the information is available. If categories exist, distinguish bank, non-bank private, and official holdings; use Fang–Hardy–Lewis data for broad composition benchmarks, not invented daily series. Investigate Yeyati dollarization data only as a **documented contextual sensitivity** on foreign-currency preferences, not a proxy for NZD bond conversion, and only if a public dataset can be verified. A different FX cross (NZD/AUD, NZD/EUR, NZD/JPY) is a **predeclared robustness check**, not another independent sample. Crosses are triangulated; report this dependency. Do not multiply NZD/USD by the U.S.-held debt fraction and call it USD order flow.

## Attempt contract and recursive decision rule

For **every** attempted model—including failed/blocked ones—append an entry to `ATTEMPTS.md` **before fitting** containing:

1. Unique ID, date, status (`proposed`, `running`, `completed`, `invalid`, `underpowered`, `blocked`, `rejected`), clear economic hypothesis, and why the previous attempt is insufficient.
2. **Exact equation**, dependent variable/units/quote direction, each regressor's precise economic definition, units, positive sign convention, observation/fixing and event settlement timestamp, lag/lead convention, ownership frequency, sample, filtering, transformations, missing-value policy, fixed effects (if any), standard-error method, and the **one** key substantive difference from prior attempt.
3. Data source IDs, specific local file paths/hashes, preprocessing/script path and expected output directory; identify any outstanding data limitations.
4. A priori predicted behavior (or explicitly sign-ambiguous mechanism), primary estimand, effect-size units, primary inference, at least one falsification or sensitivity test, and predefined decision condition. **Never choose a specification based on the realized p-value.**

After fitting, **append to the same attempt**: exact command, run timestamp, git commit if available, input hashes, N and event count, missing/drop summary, effect sizes, standard errors, 95% CIs, p-values, (adjusted) R² only where meaningful, joint tests where prespecified, residual/overlap concerns, sensitivity/falsification outcomes, economic interpretation, limitations, and short decision (`retain`, `revise`, `reject`, `indeterminate`). Link to saved regression table and a **single useful figure** where relevant. Document failed attempts without hiding them. Do not claim a hypothesis `proven`; use supported/unsupported/inconclusive conditional on assumptions.

**Recursive workflow**: inspect evidence → state one hypothesis → write ATTEMPTS specification → verify local data and timing → run → diagnose → log → choose **at most one** defensible next attempt. Each next attempt must repair an identified weakness or test a distinct economic mechanism. If an attempt is blocked, exhaust feasible free primary-source options; request human input only with an exact source link and desired file. No control-grid searching, indiscriminate lags, multiple definitions chosen after seeing the dependent variable, or ML model zoo. If multiple tests address the same family of claims, report multiplicity and keep exploratory versus confirmatory status clear.

**Stopping conditions**: (i) a necessary series is unavailable publicly; (ii) event time/ownership cannot be identified at the required resolution; (iii) adequate confidence intervals rule out the predefined economic magnitude; (iv) intervals are too wide to inform trading and plausible public data cannot narrow them; (v) model fails falsification or depends on ex post specification selection. Escalate from spot returns to an intermediate market outcome rather than continuing to tune controls. A positive result needs temporal plausibility, stable sign/magnitude, adequate inference, and an economically credible mechanism—not just significance.

## Deliverables and human handoff

- `PLAN.md` (this file): persistent agent instructions. Do not rewrite it without the user's request.
- `ATTEMPTS.md`: append-only methodological and result journal; this is the canonical history of every investigated specification.
- `DATA_SOURCES.md` (or compact CSV): append-only provenance register, navigable download landing pages, hashes and timing metadata for **all** source files, including unhelpful sources.
- Per-attempt output folders in the existing output tree, minimally containing a short text/MD results note, a machine-readable coefficient/CI table, and relevant figures only. Retain intermediate aligned datasets when useful for reproduction; do not generate redundant report formats.
- `FINDINGS.md` or a short final synthesis **only after** enough tests: tested mechanisms, what public data could/could not identify, strongest effect-size bounds, contradictory evidence, and a prioritized list of missing data that would materially alter the inference.
- Human handoff is an **evidence packet**, not a stream of speculative updates: hypothesis, exact equation, local commands, sources, principal result and interval, robustness, reason to accept/reject, and the precise next decision. Present a useful null just as prominently as a positive result.

## Public source entry points (verify metadata and download routes; log actual acquired files)

These are **landing pages**, not assumed direct-download endpoints. Existing public team datasets take precedence if their provenance and definitions check out.

| Source | Use | Navigable access |
|---|---|---|
| NZ Debt Management — Data | NZ issuance, tenders, outstanding securities, repurchases, possible auction variables | https://debtmanagement.treasury.govt.nz/investor-resources/data |
| NZ Debt Management — Archive | Historical tender/repurchase data and instrument coverage | https://debtmanagement.treasury.govt.nz/resource/archive |
| RBNZ B1 | NZD/USD and alternate NZD crosses, daily observation-window comparison | https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/exchange-rates-and-the-trade-weighted-index |
| RBNZ B2 | Daily secondary-market NZ government bond yields and short rates; **audit Aug 2025 methodology break** | https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates |
| RBNZ statistical data file index | Official links to B1/B2 downloadable XLSX (verify current links) | https://www.rbnz.govt.nz/statistics/series/data-file-index-page |
| FRED/Fed H.10 DEXUSNZ | USD per NZD New York noon rate; independently identify every existing local `dex*` code | https://fred.stlouisfed.org/series/DEXUSNZ |
| IMF PIP (formerly CPIS) | Bilateral portfolio debt holdings, investor/issuer sector where published, frequency and coverage caveats | https://data.imf.org/datasets/IMF.STA%3APIP |
| Fang, Hardy & Lewis — NBER | Investor composition hypothesis, data appendix (original 2022, updated 2024; published article 2025) | https://www.nber.org/papers/w30087 |
| Fang, Hardy & Lewis — BIS | Paper plus indicated public XLSX dataset | https://www.bis.org/publications/working-paper-1099-who-holds-sovereign-debt-and-why-it-matters |
| Levy Yeyati (2021) — paper | Financial dollarization taxonomy and cited dataset description; **locate/verify an actual accessible dataset before use** | https://rednie.eco.unc.edu.ar/files/DT/2021-38.pdf |

**Do not silently conflate:** currency denomination and issuer residence; nonresident positions and conversion flows; scheduled maturity dates and FX execution times; holdings snapshots and purchases; nominal value and market value; positive issuance and negative redemption; USD/NZD and NZD/USD; bond yields at NZ close and H.10 FX at NY noon; retrospective explanation and executable real-time prediction.

## First handoff checkpoint

Execute Gate 0 and the clock audit, populate `ATTEMPTS.md` and the source register, then run Attempt 1 only if actual local inputs support it. Produce a compact side-by-side baseline vs correctly aligned result, showing exactly which observations/coefficients change. If no credible time mapping can be established, document the blocker and shift to identifying an estimable observable intermediate stage rather than fabricating alignment. Continue iteratively only when the next economic question is justified by the observed limitations.
