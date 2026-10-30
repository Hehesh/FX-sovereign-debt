# DATA_SOURCES.md — append-only provenance register

Paths relative to `nz_bond_flows/`. Hashes are SHA256. Entries are only appended; corrections go in a new dated line.
Register started 2026-10-30 at git `9d6d431`.

## Team-supplied regression inputs (`regression/`)

Provenance statement from the user (2026-10-30): "already verified"; FX from WRDS; Controls a streamline of team members' work; US share from team members' work. No landing page or download date recorded -> `source_unverified` where marked, until the team supplies one.

| ID | Path | Provider / dataset | Freq | Units / quote | Timing convention | Range | SHA256 | Status / notes |
|---|---|---|---|---|---|---|---|---|
| S01 | `regression/FX.csv` | WRDS (Fed H.10). Cols dexalus, dexjpus, dexnzus, dexszus | daily | `dexnzus` = NZD per USD (= 1/FRED DEXUSNZ) | **Verified:** `1/dexnzus` equals FRED DEXUSNZ to 2e-16 on all 6,294 dates (same dates; see S10). H.10 = noon buying rate, New York. Other `dex*` columns are not used. | 2000-01-03 to 2025-02-07 | `daea8340765bebd80780782e11c3438336b569555bdcad600b5ea9286a67de73` | quote and H.10 origin verified; WRDS landing page not recorded |
| S02 | `regression/nz_daily_flows.csv` | Built by `code/build.py`+`write.py` from S05-S09 | daily (calendar days) | NZ$ millions; issuance negative, repayments positive (investor receives = +) | Dated by **NZ settlement date**: tender/repurchase date + 3 NZ business days (`TENDER_LAG`, an assumption in build.py), syndication/LSAP/non-market use the file's settlement date, coupons/principal use scheduled date rolled to next NZ business day | 2000-02-01 to (see file) | `3602fbb14b515d891064a645b77082d11bb7d13d1d6e6bbf1e357fc2d43ed61e` | derived; `TENDER_LAG=3` is unverified against Treasury settlement terms |
| S03 | `regression/Controls - Regression Control Panel.csv` | team compilation: `vix`, `treasury_swap_merged`, `us_release` | daily | vix index points; `treasury_swap_merged` range -1.08..5.41, definition unknown; `us_release` 0/1 | **Unverified.** VIX close is 16:15 ET so a date-D value post-dates the NY-noon fix on D. `us_release` hits fall on Fri (383), Wed (117), Thu (74), Tue (68), consistent with morning ET releases but release list unknown | 2000-01-03 to 2026-10-14 | `9314cc56e48d9a14ca1a1ddd75bdb22825399bf37b2ccd08b9287251c01fc745` | `source_unverified` for construction of `treasury_swap_merged` and `us_release` |
| S04 | `regression/US_Share_of_New_Zealand_Debt.xlsx - Regression Series.csv` | team work (likely from IMF/Arslanalp-Tsuda holdings; unconfirmed) | daily rows, only 23 distinct values | fraction held by US (text "15.80%") | **Unknown measurement date and publication lag.** Joined backward as-of on FX date, which is look-ahead if the share is a period-end value published later | 2014-01-01 to (see file) | `cc18152c04097289846b697de267d98589553833e8502430224efc2d69d7073c` | `source_unverified`: ask team for holdings reference date and series |

## Raw flow-builder inputs (`raw/`) — hashes recorded 2026-10-30, provenance per `docs/RUN.txt`

| ID | File | SHA256 |
|---|---|---|
| S05 | `raw/onissue.xlsx` | `3f294fc9a88305e320006722864b851210b9d8b66dbb417d66bbb729b31831c6` |
| S06 | `raw/hd31.xlsx` | `18912e9d9d8c2dc4ec186ba33ad2f581247ab0b72a19edc9dd761ff6b6836615` |
| S07 | `raw/iib.xlsx` | `3ea423c96e1ea9a5c389dd4885ea32fba5a506af3f99cba8a4ed5b909908011e` |
| S08 | `raw/tender.xlsx` | `638b5371c4efe839818e18c4750ce981045ac1a747852e0c2ce9d49f73c56d12` |
| S09a | `raw/syndication.xlsx` | `288cd67991462f66b1a2390d38c0a7eda917067473efa34daadf74cbbd20affe` |
| S09b | `raw/repurchase.xlsx` | `e2e5288288d8b43da2bf0642c011111d9def2d913da64117cf4e3b5edab78155` |
| S09c | `raw/nonmarket.xlsx` | `195b9f03f1801f57b14388e95b7edf11a3b7deeaddee5260902724a7af2dee7c` |
| S09d | `raw/cpi_oecd_fred.csv` | `0c287322536fa58455a139f658b4f1ddc01627d5c5f20255bb5b2ddbfbeaa477` |
| S09e | `raw/IMF Counterparty Data.csv` | `de215e2eb3b61f78558d0d70e64a966ada65bc935cc779dfb33dc08cda75ec44` |

Original NZ Treasury landing pages for S05-S09c not recorded in the repo: `source_unverified` (candidate landing: https://debtmanagement.treasury.govt.nz/investor-resources/data). Ask the team only if a later attempt depends on them.

## Newly acquired public files

| ID | Path | Provider / dataset | Landing page | Verified direct URL | Downloaded | Format | Freq | Units / quote | Observation convention | Range | SHA256 | Used by |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S10 | `raw/public/DEXUSNZ_fred.csv` | FRED series DEXUSNZ (Board of Governors, H.10) | https://fred.stlouisfed.org/series/DEXUSNZ | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSNZ` (HTTP 200 on 2026-10-30) | 2026-10-30 12:35 UTC | CSV, `.` = missing | daily | USD per NZD | H.10 noon buying rate, New York | 1971-01-04 to download date | `cf7628782c7d5996fe4326a9eeaf4c50c3b4466cbc48f7bbcecf6b1dee6a5472` | CA-0, G0 |

## BLOCKED_DATA

### B1 / B2 — RBNZ daily NZD/USD and government bond yields
- URL: https://www.rbnz.govt.nz/statistics/series/data-file-index-page
- Reason: HTTP 403 "Website unavailable" bot check on automated fetch (2026-10-30). Not circumvented.
- Human steps: open the URL in a browser; under Exchange and interest rates choose B1 "Exchange rates and the Trade Weighted Index" (daily) and B2 "Wholesale interest rates" (daily); download the XLSX/CSV that includes the series description/metadata sheets.
- Needed fields: B1 daily NZD/USD with its stated observation time (needed for the alternative-window check, plan clock-audit item 5); B2 daily 2/5/10-year government bond yields, full history incl. the Aug 2025 methodology note (needed for Attempt 5).
- Save to: `nz_bond_flows/raw/public/` with original filenames.
- Impact: blocks the B1 cross-check and Attempt 5(b); does not block Gate 0 or Attempts 1-4.

## Appended 2026-10-30 (second batch)

Human-supplied (saved by the user into `raw/public/`, original filenames kept; landing pages https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/exchange-rates-and-the-trade-weighted-index and .../wholesale-interest-rates, index https://www.rbnz.govt.nz/statistics/series/data-file-index-page). Provider RBNZ (source line in files: Reserve Bank of New Zealand, Reuters, NZFMA); license note in files: free to copy/adapt. Table descriptions give no observation time. Series ids are in each file's `Series Definitions` sheet.

| ID | Path | Series used | Range | Units | SHA256 |
|---|---|---|---|---|---|
| S11a | `raw/public/hb1-daily-1999-2017.xlsx` | B1 `EXR.DS11.D06` NZD/USD (quoted per NZ$ = USD per NZD) | 1999-01-05 to 2017-12-29 | USD per NZD, daily | `c81b3dd2f372a106f4eecc235319342ef9cdfe78164b0926ccd46553677c7c76` |
| S11b | `raw/public/hb1-daily-2018-current.xlsx` | same, current file | 2018-01-03 to 2026-10-30 | same | `61d228617e2f0ac258d7efd2a25bf3a06d1331e0be6297c6accb86ec9524a539` |
| S12a | `raw/public/hb2-daily-close-1985-2017.xlsx` | B2 `INM.DS02.NZZC` 2-year swap close (from 2011-01-05); also govt yields `INM.DG10x.NZZCF` | 1985-2017 | % pa | `6320f6f2a793976e12da8abbbd51e89dc0245d22e3968307acd1e41c0559c3e2` |
| S12b | `raw/public/hb2-daily-close-2018-current.xlsx` | same, current file | 2018-01-03 to 2026-10-29 | % pa | `b2bd17a2abc3c4a4cf93debc2998b8c7f7d5aeba8a7d7c42397f698f200e27aa` |

**B1 observation time: not documented in the files.** Inferred from data (B1 daily return regressed on adjacent H.10 returns; grid search over NZ-local time, 2014-2025, N=1,793 days): best fit 13:00 NZ local, sum of squares flat between 11:30 and 14:30; 16:00 fits 7% worse. Third-party pages (not RBNZ) say about 15:00. Treat as `inferred, unverified`. B2 "close" time of day also undocumented; stamped at the latest possible instant (23:59 NZ) so no look-ahead is possible. The Aug 2025 B2 yield-source change is not yet audited (swap series only used here).

FRED downloads (fetch script `code/fetch_fred.py`, 2026-10-30 13:10 UTC, URL pattern `https://fred.stlouisfed.org/graph/fredgraph.csv?id=<ID>`, landing `https://fred.stlouisfed.org/series/<ID>`, CSV with `.` = missing):

| ID | Path | Series | Time stamp used | SHA256 |
|---|---|---|---|---|
| S13 | `raw/public/VIXCLS_fred.csv` | CBOE VIX close | 16:15 New York | `1cdbbe4643427b9915cf1c53c50f9eb9e327717d89a6bd3e101d3726f56f5cec` |
| S14 | `raw/public/DGS2_fred.csv` | US 2y Treasury CMT (H.15), % | 16:00 New York (data as of about 15:30 per Treasury methodology, not verified here) | `f41850fd89160bc5d71e28e92dca5368f191c83f31c6c24c7f4092255afd1991` |
| S15 | `raw/public/DCOILBRENTEU_fred.csv` | Brent spot, USD/bbl (EIA) | 23:59 London (EIA fixing time not verified) | `f3ad22ec3aa8800fc5edfa638d364ae388a5612ed895d233f0b2af67c807a393` |
| S16 | `raw/public/T10Y2Y_fred.csv` | US 10y-2y spread, sensitivity only | 16:00 New York | `168630f0dff30b11627bbda9b1d246e47c4a73f4715df5a3b92f3151272a9f7e` |
| S17 | `raw/public/DFII10_fred.csv` | US 10y TIPS yield, sensitivity only | 16:00 New York | `77de242a43c9b6be67b1c2a85d607fc89d02606bef47d76840516914957f33f2` |
| S18 | `raw/public/NASDAQCOM_fred.csv` | Nasdaq composite, screen only | n/a | `1f14a143eb6d2913f65cc9879ec608cf5df6601f4fd022a5fbfed927d3be4e64` |
| S19 | `raw/public/DTWEXBGS_fred.csv` | Broad USD index, downloaded, not used | n/a | `8080a7d962c8e8976e4394a5dbdb2e4a2ddb984c1c5aefc581aa42b715fd6932` |

Team-file provenance, clarified by the user (2026-10-30) and checked against the workbooks:
- `raw/Controls.xlsx` (SHA256 see `output/attempts/00_gate0_baseline/input_hashes.csv` after rerun of `gate0_diagnostics.py`): `treasury_swap_merged` = NZ 2y swap (RBNZ B2) minus US 2y (FRED DGS2) from 2011-01-05, spliced with the 11am NZ 2y government yield (legacy B2) before 2011; `us_release` = US CPI or payrolls release date (ALFRED vintage dates). Sources and caveats in the workbook sheets `Notes` and `Summary`. Superseded for A1r by window-change controls built from S12, S13-S15.
- `raw/US_Share_of_New_Zealand_Debt.xlsx`: IMF Portfolio Investment Positions by Counterpart Economy, half-yearly. Verified in sheet `Calcs and Graphs`: the value dated 2014-01-01 is the 2014-S1 position (US 14,994.2 / NZ-announced debt 94,886.99 = 0.158022), i.e. a period-end position applied from the start of that half-year, and held constant until the next half-year. Publication lag of the IMF release is not recorded; position-date look-ahead up to 6 months.
- Hashes of the team workbooks: `raw/Controls.xlsx` `c261fd7ab487122ab1584e818df912cea5e463112ecc25abcf5106a9b2625ff0`; `raw/US_Share_of_New_Zealand_Debt.xlsx` `180a4c4ee99380a66abd44d5be6d3b8414ab3b9810ac90b17f7a92d4564bd824` (recorded 2026-10-30; both are source files of S03/S04, `source` = team work).

## Status update 2026-10-30 (cleanup)

- BLOCKED_DATA B1/B2: **resolved** by the human on 2026-10-30; files are S11a/b and S12a/b above. The 403 on automated access still applies, so refreshes need the same manual download.
- S19 (`DTWEXBGS_fred.csv`) and S18 (`NASDAQCOM_fred.csv`) are registered for provenance but unused by any model; S18 was used only in the control screen.
