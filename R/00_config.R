# 00_config.R - paths, clocks, constants for the Mexico (USD/MXN) event study.
# Mirrors Brayden's A1r spec (nz_bond_flows/code/attempt1r.py) in R.
suppressPackageStartupMessages({
  library(dplyr); library(readr); library(readxl); library(lubridate)
  library(sandwich); library(lmtest); library(httr)
})

BASE <- getwd()   # open the .Rproj at the repo root so mx_bond_flows/ is a subfolder
stopifnot(dir.exists(file.path(BASE, "mx_bond_flows")))
RAW  <- file.path(BASE, "mx_bond_flows", "raw")
REG  <- file.path(BASE, "mx_bond_flows", "regression")
OUT  <- file.path(BASE, "mx_bond_flows", "output")
dir.create(OUT, showWarnings = FALSE, recursive = TRUE)

TZ_MX  <- "America/Mexico_City"   # no DST since 2022-10-30; tz database handles earlier years
TZ_NY  <- "America/New_York"
TZ_LON <- "Europe/London"

SETTLE_HOUR_MX <- 9     # assumed settlement time of Mbono cash flows, Mexico City local
FIX_HOUR_MX    <- 12    # Banxico FIX is determined from quotes 9:00-12:00 and published at noon
SAMPLE <- as.Date(c("2010-01-04", "2025-12-31"))   # start at WGBI inclusion; extend back if share is stable
HAC_LAGS <- 10
PRIMARY <- c("N0", "N1", "dlnVIX", "dPol", "rBrent")

# ---- clock helpers (ports of timing.py) ----
stamp <- function(dates, tz, hour, minute = 0) {
  with_tz(force_tz(as_datetime(as.Date(dates)) + hours(hour) + minutes(minute), tz), "UTC")
}
# j such that fix[j-1] < event <= fix[j]; NA if outside the fixing range
window_index <- function(event_utc, fix_utc) {
  pos <- findInterval(as.numeric(event_utc), as.numeric(fix_utc), left.open = TRUE) + 1
  ifelse(pos >= 2 & pos <= length(fix_utc), pos, NA_integer_)
}
# change over each fixing window: last obs stamped <= window end minus last obs <= window start
window_changes <- function(values, obs_utc, fix_utc) {
  ok <- !is.na(values); v <- values[ok]; st <- as.numeric(obs_utc[ok])
  pos <- findInterval(as.numeric(fix_utc), st)      # count of obs <= each fixing instant
  level <- ifelse(pos >= 1, v[pmax(pos, 1)], NA_real_)
  c(NA_real_, diff(level))
}
read_fred_csv <- function(id) {
  d <- read_csv(file.path(RAW, paste0(id, "_fred.csv")), na = ".", show_col_types = FALSE)
  names(d) <- c("date", "value"); d %>% mutate(date = as.Date(date)) %>% filter(!is.na(value))
}
