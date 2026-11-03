# 02_build_flows.R - daily Mbono cash-flow calendar (MXN millions) with the foreign share bond by bond.
# Inputs (placed by hand in mx_bond_flows/raw/, see README):
#   mx_bond_terms.csv      one row per Mbono series: series, isin, issue_date, maturity, coupon_pct
#   mx_issue_holdings.csv  weekly (Thursday) issue-by-issue sectorized report, long format:
#                          date, series, outstanding, foreign  (MXN millions, nominal)
#   banxico_CA175.xlsx     daily foreign holdings by instrument (aggregate fallback)
#   banxico_CA134.xlsx     daily Bonos outstanding (aggregate fallback)
source("R/00_config.R")

terms <- read_csv(file.path(RAW, "mx_bond_terms.csv"), show_col_types = FALSE) %>%
  mutate(issue_date = as.Date(issue_date), maturity = as.Date(maturity))
hold  <- read_csv(file.path(RAW, "mx_issue_holdings.csv"), show_col_types = FALSE) %>%
  mutate(date = as.Date(date)) %>% arrange(series, date)

# 1. Coupons: Mbonos pay every 182 days counted back from maturity, face 100, coupon = rate/100*182/360*100
coupons <- terms %>% rowwise() %>% do({
  t <- .; d <- seq(t$maturity, t$issue_date, by = "-182 days")
  tibble(series = t$series, date = sort(d[d > t$issue_date]), type = "coupon",
         per100 = t$coupon_pct / 100 * 182 / 360 * 100)
}) %>% ungroup()

# 2. Principal: full outstanding on the maturity date (buybacks/switches reduce it beforehand)
# 3. Issuance and buybacks: week-over-week change in outstanding per series. Auctions settle on the
#    Thursday the report is dated, so a positive change is issuance settled that day; a negative
#    change before maturity is a buyback or switch (SHCP permutas), dated the same Thursday.
chg <- hold %>% group_by(series) %>%
  mutate(d_out = outstanding - lag(outstanding), share = foreign / outstanding) %>% ungroup()
issuance <- chg %>% filter(d_out > 0) %>% transmute(series, date, type = "issuance", amount = d_out)
buyback  <- chg %>% inner_join(terms %>% select(series, maturity), by = "series") %>%
  filter(d_out < 0, date < maturity - 7) %>% transmute(series, date, type = "buyback", amount = -d_out)
principal <- hold %>% inner_join(terms %>% select(series, maturity), by = "series") %>%
  filter(date <= maturity) %>% group_by(series) %>% slice_max(date, n = 1) %>% ungroup() %>%
  transmute(series, date = maturity, type = "principal", amount = outstanding)
coupon_amt <- coupons %>% inner_join(hold %>% select(series, date_h = date, outstanding), by = "series",
                                     relationship = "many-to-many") %>%
  filter(date_h <= date) %>% group_by(series, date) %>% slice_max(date_h, n = 1) %>% ungroup() %>%
  transmute(series, date, type, amount = outstanding * per100 / 100)

flows <- bind_rows(issuance, buyback, principal, coupon_amt) %>% filter(amount > 0)

# 4. Foreign share of the specific bond, as of the last weekly report at or before the flow date
#    (position-date valid: no look-ahead). Aggregate CA175/CA134 share is the fallback for new series.
share_asof <- function(s, d) {
  h <- hold %>% filter(series == s, date <= d) %>% slice_max(date, n = 1)
  if (nrow(h) == 0 || is.na(h$outstanding) || h$outstanding == 0) NA_real_ else h$foreign / h$outstanding
}
flows <- flows %>% rowwise() %>% mutate(share = share_asof(series, date)) %>% ungroup()

daily <- flows %>% group_by(date, type) %>%
  summarise(amount = sum(amount), f_amount = sum(amount * share, na.rm = TRUE), .groups = "drop") %>%
  tidyr::pivot_wider(names_from = type, values_from = c(amount, f_amount), values_fill = 0)

write_csv(flows, file.path(REG, "mx_flows_long.csv"))
write_csv(daily, file.path(REG, "mx_daily_flows.csv"))
cat("flows:", nrow(flows), "rows;", n_distinct(principal$date), "principal dates;",
    n_distinct(issuance$date), "issuance dates;", n_distinct(coupon_amt$date), "coupon dates\n")
