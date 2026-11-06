# Mexico (USD/MXN) event study: R port of the NZ A1r pipeline

Run from the repo root with the .Rproj open there, in order:

    source("R/01_fetch_data.R")      # FRED pulls; Banxico FIX if BANXICO_TOKEN is set
    source("R/01b_merge_banxico.R")  # merge the weekly Banxico exports -> mx_issue_holdings.csv
    source("R/02_build_flows.R")     # Mbono cash-flow calendar with bond-level foreign share
    source("R/03_build_panel.R")     # fixing windows, outcome, controls
    source("R/04_run_regressions.R") # A1r primary + sensitivities, pooled principal, placebo

Packages: dplyr, readr, readxl, tidyr, lubridate, sandwich, lmtest, httr.
Raw and regression CSVs stay local (add `mx_bond_flows/raw/` and `mx_bond_flows/regression/` to .gitignore).

## Inputs to place in mx_bond_flows/raw/ (not fetched by script)

| File | Source | What it is |
|---|---|---|
| `banxico_weekly/*.xls` | https://www.banxico.org.mx/valores/consultasHistoricasSectorizadas.jsp?BMXC_claseIns=GUB&BMXC_lang=es_MX , Instrument = ALL, six months per query | Weekly (Thursday) holdings by sector for every security. `01b_merge_banxico.R` merges them into `mx_issue_holdings.csv` and keeps the Mbono (code M) rows: foreign holdings and outstanding per bond, MXN millions. |
| `mx_bond_terms.csv` | Banxico/SHCP bond characteristics, or the Valmer vector | Two columns: `maturity, coupon_pct`, one row per Mbono. The maturity is the key that links to the weekly file. |
| `banxico_FIX.csv` | SIE series SF43718 via API (01_fetch_data.R) or export from SIE | `date, value` MXN per USD, noon Mexico City. |
| `mx_2y_rate.csv` | Banxico SIE "Vector de precios" / Valmer 2y Mbono yield, or 2y TIIE swap | `date, value` in %. Policy control (MX leg of dPol). |
| `banxico_CA175.xlsx`, `banxico_CA134.xlsx` | SIE cuadros CA175 and CA134, Exportar > XLS, period Todo | Daily aggregate foreign holdings and outstanding, by instrument. Fallback share and a check on the weekly bond-level data. |

FRED series fetched by script: DEXMXUS, VIXCLS, DGS2, DCOILBRENTEU, T10Y2Y, DFII10, DTWEXBGS (broad dollar), DEXBZUS (BRL, peer EM).

## Clock

Settlement assumed 09:00 Mexico City. Primary fixing is Banxico FIX (noon Mexico City), so the event window
is FIX(D-1) -> FIX(D). Sensitivity: FRED H.10 (noon New York = 10:00/11:00 Mexico City), which sits close to the
settlement hour, so expect the `h10_window` spec to be the fragile one. Controls use the latest possible stamp
of each observation and only enter if that stamp is inside or before the window (VIX 16:15 NY, DGS2 16:00 NY,
Brent 23:59 London, MX 2y 23:59 Mexico City). `controls_pre_window` lags everything one more window.

## What changed from NZ

- Foreign share is the specific maturing bond's own non-resident share from the weekly report, not an aggregate US share.
- Issuance and buybacks come from week-over-week changes in each series' outstanding (auctions settle Thursday).
- Controls are window changes; broad dollar and BRL added as sensitivities.
- Pooled principal windows (pre / event / post) replace the 11-coefficient block.
- Placebo p (300 circular shifts) reported beside the HAC p.

## Outputs (mx_bond_flows/output/)

`mx_a1r_coefficients.csv`, `mx_pooled_principal.csv`, `mx_placebo.csv`, `mx_summary.csv`
(summary has the event counts: if `n_principal` is under ~25, say so on the slide before anything else).

## Robustness (R/06_robustness.R)

    source("R/06_robustness.R")   # FIX, EUR/MXN, drop largest maturities, dollar/EM controls; 1000 placebo draws each

Writes `output/mx_robustness.csv` and `output/mx_robustness.png`. Needs `raw/banxico_FIX.csv` (Banxico historical FIX,
`banxico.org.mx/tipcamb/tipCamIHAction.do`, column "Determinación") and `raw/DEXUSEU_fred.csv`. A missing FIX file now
warns: earlier "fix" results were FRED H.10. Holder countries: `output/imf_pip_mexico_lt_debt_by_holder.csv` (IMF PIP).
