# Build the daily regression panel for the NZ case study.
#
# Inputs (data/raw/):
#   nz_daily_flows.csv  Daily private-holder cash flows, NZ$ millions, calendar days.
#                       + = cash paid to holders (coupon, principal, buyback), - = issuance.
#   fx.csv              FRED H.10 noon New York rates, foreign currency per USD.
#   controls.csv        vix, treasury_swap_merged (NZ 2y swap - US 2y Treasury, pp), us_release.
#   us_share.csv        Share of NZ government debt held by US investors, semiannual, held daily.
#
# Output: data/processed/nz_panel.csv, one row per NZD/USD trading day.
#
# Timing: a NZ payment on calendar date d settles before NY noon on d (NZ is 16-18 hours
# ahead), so it is assigned to the first FX date on or after d. US-holiday flows roll forward.

suppressPackageStartupMessages({ library(dplyr); library(readr) })

raw <- function(f) file.path("data", "raw", f)

# Carry the last value forward up to `limit` rows (matches pandas ffill(limit = 2))
ffill_limit <- function(x, limit) {
  last <- NA; gap <- 0
  for (i in seq_along(x)) {
    if (!is.na(x[i])) { last <- x[i]; gap <- 0 }
    else if (!is.na(last) && gap < limit) { x[i] <- last; gap <- gap + 1 }
  }
  x
}

flows <- read_csv(raw("nz_daily_flows.csv"), show_col_types = FALSE)
fx    <- read_csv(raw("fx.csv"), show_col_types = FALSE)
ctrl  <- read_csv(raw("controls.csv"), show_col_types = FALSE)
us    <- read_csv(raw("us_share.csv"), show_col_types = FALSE) |>
  mutate(date = as.Date(date, format = "%m/%d/%Y"),
         us_share = as.numeric(sub("%", "", us_share)) / 100)

# FX trading days and returns in %, + = foreign currency appreciates vs USD
fx <- fx |> filter(!is.na(dexnzus)) |> arrange(date) |>
  mutate(r_nzd = -100 * c(NA, diff(log(dexnzus))),
         r_aud = -100 * c(NA, diff(log(dexalus))),
         r_jpy = -100 * c(NA, diff(log(dexjpus))),
         r_chf = -100 * c(NA, diff(log(dexszus))),
         nzdusd = 1 / dexnzus)

# Flow variables
f <- flows |>
  mutate(repay     = nom_coupon + nom_principal + nom_buyback + iib_coupon + iib_principal + iib_buyback,
         principal = nom_principal + iib_principal + nom_buyback + iib_buyback,
         coupon    = nom_coupon + iib_coupon,
         issue     = -(nom_issuance + iib_issuance),     # positive magnitude
         net       = net_flow_private,                    # repay - issue
         repay_foreign = nonres_payments) |>              # NA before 2015-08
  left_join(us, by = "date") |>
  mutate(repay_us = repay * us_share, net_us = net * us_share)

# Map each calendar-day flow to the first FX date on or after it
idx <- findInterval(f$date, fx$date, left.open = TRUE) + 1
f$fx_date <- fx$date[ifelse(idx > nrow(fx), NA, idx)]

flow_cols <- c("repay", "principal", "coupon", "issue", "net", "repay_foreign", "repay_us", "net_us")
sum_na <- function(x) if (all(is.na(x))) NA_real_ else sum(x, na.rm = TRUE)
fa <- f |> filter(!is.na(fx_date)) |> group_by(date = fx_date) |>
  summarise(across(all_of(flow_cols), sum_na), .groups = "drop") |>
  mutate(across(all_of(flow_cols), ~ .x / 1000))           # NZ$ billions

panel <- fx |> left_join(fa, by = "date") |>
  mutate(across(c(repay, principal, coupon, issue, net), ~ coalesce(.x, 0)),
         repay_foreign = ifelse(date >= as.Date("2015-08-03"), coalesce(repay_foreign, 0), repay_foreign),
         in_us = date >= as.Date("2014-01-02") & date <= as.Date("2026-06-30"),
         repay_us = ifelse(in_us, coalesce(repay_us, 0), repay_us),
         net_us   = ifelse(in_us, coalesce(net_us, 0), net_us))

# Controls: changes for continuous series, dummies as is
ctrl <- ctrl |> arrange(date) |>
  mutate(vix = ffill_limit(vix, 2), rate_diff = ffill_limit(treasury_swap_merged, 2)) |>
  select(date, vix, rate_diff, us_release)

panel <- panel |> left_join(ctrl, by = "date") |>
  mutate(d_vix = c(NA, diff(vix)),
         d_rate_diff = c(NA, diff(rate_diff)),
         covid = as.integer(date >= as.Date("2020-03-01") & date <= as.Date("2020-04-30")),
         dow = factor(weekdays(date), levels = c("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"))) |>
  select(date, nzdusd, r_nzd, r_aud, r_jpy, r_chf, all_of(flow_cols),
         vix, d_vix, rate_diff, d_rate_diff, us_release, covid, dow) |>
  slice(-1)                                                 # first row has no return

dir.create(file.path("data", "processed"), showWarnings = FALSE, recursive = TRUE)
write_csv(panel, file.path("data", "processed", "nz_panel.csv"))

# Reconciliation: every NZ$ of flow inside the FX window should land in the panel
raw_net <- sum(f$net[!is.na(f$fx_date) & f$date > fx$date[1]]) / 1000
cat(sprintf("Panel: %d trading days, %s to %s\n", nrow(panel), min(panel$date), max(panel$date)))
cat(sprintf("Net flow reconciliation (NZ$bn): raw %.3f vs panel %.3f\n", raw_net, sum(panel$net)))
cat(sprintf("Days with repayment: %d, with issuance: %d\n", sum(panel$repay > 0), sum(panel$issue > 0)))
