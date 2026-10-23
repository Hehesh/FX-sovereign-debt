# FX Sovereign Debt

ECON 181 FinTech Practicum: Sovereign Debt Payment Flows and FX Responses. New Zealand is the first case study.

## Objective

Test whether scheduled NZ government bond cash flows move NZD/USD beyond what policy, growth and risk explain.

    Δe_t = α + Σ_{j=−5}^{5} β_j · N_{t+j} + γ · X_t + ε_t

- `Δe_t`: 100 × daily change in log NZD per USD (+ = NZD weakens)
- `N_t`: net flow in NZ$ billions = issuance − coupons − principal − buybacks
- `j > 0`: flow comes after the return (anticipation); `j < 0`: flow came before (delayed response)
- `X_t`: controls (Δ NZ–US 2y rate differential, ΔVIX, US release day)
- Hypothesis: β < 0. Payments (N < 0) weaken NZD; issuance (N > 0) strengthens it

`run_regressions.R` runs this main specification first, then splits repayment from issuance and runs robustness checks. Those use `r_nzd` (+ = NZD strengthens) and positive repayment flows, so read their signs accordingly.

Three questions: does NZD move before the flow, do issuance and repayment differ, does any early move reverse?

## Repo layout

    FX-sovereign-debt.Rproj   open this in RStudio
    data/raw/                 source files (do not edit)
    data/processed/           nz_panel.csv, built by R/build_panel.R
    R/install_packages.R      run once
    R/build_panel.R           merges flows, FX, controls, US share onto NZD/USD trading days
    R/run_regressions.R       regressions, tables, figure
    output/tables/            regression CSVs
    output/figures/           event_window.png

## Run

Open `FX-sovereign-debt.Rproj` in RStudio, then in the console:

    source("R/install_packages.R")   # first time only
    source("R/build_panel.R")
    source("R/run_regressions.R")

## Data

| File | Source | Coverage | Notes |
|---|---|---|---|
| nz_daily_flows.csv | NZDM / RBNZ, built by Brayden | 2000-02 to 2026-09, calendar days | NZ$m. + paid to holders, − issuance. `nonres_payments` (foreign-held) from 2015-08 |
| fx.csv | FRED H.10, noon NY | 2000-01 to 2025-02-07 | Foreign currency per USD. Returns inverted so + = foreign currency up |
| controls.csv | FRED, RBNZ, BLS | 2000-01 to 2026-10 | VIX, NZ 2y swap − US 2y (pp), US release-day dummy |
| us_share.csv | Team | 2014-01 to 2026-01, semiannual | Share of NZ govt debt held by US investors |

Timing: flows are assigned to the first NY fixing on or after the NZ payment date. NZ is 16 to 18 hours ahead, so a day-t NZ payment settles before the day-t NY noon fix. Flows on US holidays roll forward.

Standard errors: Newey-West, 5 lags.
