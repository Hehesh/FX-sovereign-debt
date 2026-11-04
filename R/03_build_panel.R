# 03_build_panel.R - timestamped fixing windows (port of A1r window_frame).
# Outcome r = 100 * dlog(USD per MXN) between consecutive fixings; positive = peso appreciation.
# Flow N = foreign-weighted net issuance (issuance - principal - coupon - buyback), MXN billions,
# assigned to the window (last fixing before settlement, first fixing after).
source("R/00_config.R")

fixings <- function(source = c("fix", "h10")) {
  source <- match.arg(source)
  if (source == "fix" && !file.exists(file.path(RAW, "banxico_FIX.csv"))) {
    message("banxico_FIX.csv not found; using FRED H.10 (noon New York) as the fixing instead")
    source <- "h10"
  }
  if (source == "fix") {
    f <- read_csv(file.path(RAW, "banxico_FIX.csv"), show_col_types = FALSE) %>%
      transmute(date = as.Date(date), e = 1 / value) %>% filter(!is.na(e))      # USD per MXN
    list(e = f, utc = stamp(f$date, TZ_MX, FIX_HOUR_MX))
  } else {
    f <- read_fred_csv("DEXMXUS") %>% transmute(date, e = 1 / value)
    list(e = f, utc = stamp(f$date, TZ_NY, 12))
  }
}

controls <- function(fix_utc) {
  vix <- read_fred_csv("VIXCLS"); ust2 <- read_fred_csv("DGS2"); brent <- read_fred_csv("DCOILBRENTEU")
  mx2_file <- file.path(RAW, "mx_2y_rate.csv")
  mx2 <- if (file.exists(mx2_file)) read_csv(mx2_file, show_col_types = FALSE) %>% mutate(date = as.Date(date)) else {
    message("mx_2y_rate.csv not found; dPol uses the US 2y change only until it is added")
    tibble(date = as.Date(character()), value = numeric())
  }
  chg <- function(d, tz, h, m = 0) window_changes(d$value, stamp(d$date, tz, h, m), fix_utc)
  tibble(
    dlnVIX = 100 * chg(mutate(vix, value = log(value)), TZ_NY, 16, 15),
    dPol   = (if (nrow(mx2)) chg(mx2, TZ_MX, 23, 59) else 0) - chg(ust2, TZ_NY, 16),  # MX-US 2y differential change (NA before the MX series starts)
    dTIIE  = if (file.exists(file.path(RAW, "mx_tiie28.csv")))
               chg(read_csv(file.path(RAW, "mx_tiie28.csv"), show_col_types = FALSE) %>% mutate(date = as.Date(date)), TZ_MX, 23, 59) else NA_real_,
    rBrent = 100 * chg(mutate(brent, value = log(ifelse(value > 0, value, NA))), TZ_LON, 23, 59),
    dUST2  = chg(ust2, TZ_NY, 16),
    dT10Y2Y = chg(read_fred_csv("T10Y2Y"), TZ_NY, 16),
    dBroadUSD = 100 * chg(mutate(read_fred_csv("DTWEXBGS"), value = log(value)), TZ_NY, 16),
    rBRL = 100 * chg(mutate(read_fred_csv("DEXBZUS"), value = -log(value)), TZ_NY, 12)  # peer EM FX
  )
}

settlements <- function() {
  d <- read_csv(file.path(REG, "mx_daily_flows.csv"), show_col_types = FALSE) %>% mutate(date = as.Date(date))
  g <- function(x) if (x %in% names(d)) d[[x]] else 0
  d %>% mutate(
    N  = (g("f_amount_issuance") - g("f_amount_principal") - g("f_amount_coupon") - g("f_amount_buyback")) / 1000,
    P  = g("f_amount_principal") / 1000,
    I  = g("f_amount_issuance") / 1000,
    settle_utc = stamp(date, TZ_MX, SETTLE_HOUR_MX))
}

window_frame <- function(source = "fix", shift_controls = FALSE) {
  fx <- fixings(source); s <- settlements()
  s$j <- window_index(s$settle_utc, fx$utc)
  s <- s %>% filter(!is.na(j)) %>% group_by(j) %>% summarise(N = sum(N), P = sum(P), I = sum(I), .groups = "drop")
  w <- tibble(date = fx$e$date, r = c(NA, 100 * diff(log(fx$e$e))))
  w$N0 <- s$N[match(seq_len(nrow(w)), s$j)]; w$P0 <- s$P[match(seq_len(nrow(w)), s$j)]
  w$I0 <- s$I[match(seq_len(nrow(w)), s$j)]
  w <- w %>% mutate(across(c(N0, P0, I0), ~ tidyr::replace_na(.x, 0)), N1 = lead(N0), P1 = lead(P0))
  cc <- controls(fx$utc); if (shift_controls) cc <- mutate(cc, across(everything(), lag))
  bind_cols(w, cc) %>% filter(date >= SAMPLE[1], date <= SAMPLE[2])
}

if (!isTRUE(getOption("mx.no_main"))) {
  w <- window_frame("fix")
  write_csv(w, file.path(REG, "mx_panel.csv"))
  cat("panel:", nrow(w), "windows;", sum(w$P0 > 0), "principal windows;", sum(w$I0 > 0), "issuance windows\n")
}
