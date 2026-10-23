# Regressions for the NZ case study.
#
# Outcome r_nzd: daily NZD/USD log return in %, + = NZD appreciates.
# Flows in NZ$ billions. repay = coupons + principal + buybacks paid to holders.
# issue = cash paid in for new bonds (positive magnitude).
#
# Hypothesis: repayments -> holders sell NZD -> NZD falls (beta_repay < 0).
#             issuance  -> buyers need NZD   -> NZD rises (beta_issue > 0).
#
# Standard errors: Newey-West (HAC), 5 lags.

suppressPackageStartupMessages({
  library(dplyr); library(readr); library(sandwich); library(lmtest); library(ggplot2)
})

panel <- read_csv(file.path("data", "processed", "nz_panel.csv"), show_col_types = FALSE) |>
  mutate(dow = factor(dow, levels = c("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")))
tab_dir <- file.path("output", "tables"); fig_dir <- file.path("output", "figures")
dir.create(tab_dir, showWarnings = FALSE, recursive = TRUE)
dir.create(fig_dir, showWarnings = FALSE, recursive = TRUE)

CONTROLS <- "d_rate_diff + d_vix + us_release"
WINDOW <- -5:5

# OLS with Newey-West standard errors; returns the model and its HAC covariance
fit <- function(data, rhs) {
  m <- lm(as.formula(paste("r_nzd ~", rhs)), data = data)
  list(m = m, V = NeweyWest(m, lag = 5, prewhite = FALSE, adjust = TRUE))
}

tidy <- function(res, name, keep) {
  ct <- coeftest(res$m, vcov. = res$V, df = Inf)
  keep <- intersect(keep, rownames(ct))
  data.frame(model = name, term = keep, coef = ct[keep, 1], se = ct[keep, 2],
             t = ct[keep, 3], p = ct[keep, 4], n = nobs(res$m),
             r2 = summary(res$m)$r.squared, row.names = NULL)
}

# Test a sum of coefficients (e.g. all pre-event leads) with the HAC covariance
lincom <- function(res, terms) {
  b <- coef(res$m); w <- setNames(rep(0, length(b)), names(b)); w[terms] <- 1
  est <- sum(w * b); se <- sqrt(drop(t(w) %*% res$V %*% w))
  data.frame(sum_coef = est, se = se, p = 2 * pnorm(-abs(est / se)))
}

# Leads and lags: tau < 0 means the return happens BEFORE the flow date
add_window <- function(df, var) {
  nms <- character(0)
  for (tau in WINDOW) {
    nm <- paste0(var, "_", ifelse(tau < 0, "m", "p"), abs(tau))
    df[[nm]] <- if (tau < 0) lead(df[[var]], -tau) else if (tau > 0) lag(df[[var]], tau) else df[[var]]
    nms <- c(nms, nm)
  }
  list(df = df, cols = nms)
}

window_sums <- function(res, cols, label) {
  bind_rows(
    cbind(window = "pre (-5..-1)",   lincom(res, cols[1:5])),
    cbind(window = "day 0",          lincom(res, cols[6])),
    cbind(window = "post (+1..+5)",  lincom(res, cols[7:11])),
    cbind(window = "total (-5..+5)", lincom(res, cols))
  ) |> mutate(series = label)
}

since <- function(d) panel |> filter(date >= as.Date(d))

# 0. MAIN SPECIFICATION, exactly as assigned:
#    de_t = alpha + sum_{j=-5}^{5} beta_j N_{t+j} + gamma X_t + eps_t
#    de_t = 100 * dlog(NZD per USD), + = NZD weakens.  N = issuance - payments (slide definition).
#    j > 0: flow is j days AFTER the return (anticipation). j < 0: flow was j days BEFORE (delayed response).
#    Expected: beta < 0 (payments, N < 0, weaken NZD; issuance, N > 0, strengthens it).
main_df <- panel |> mutate(de = -r_nzd, N = -net)
main_cols <- character(0)
for (j in -5:5) {
  nm <- paste0("N_j", ifelse(j < 0, "m", "p"), abs(j))
  main_df[[nm]] <- if (j > 0) lead(main_df$N, j) else if (j < 0) lag(main_df$N, -j) else main_df$N
  main_cols <- c(main_cols, nm)
}
main_m <- lm(as.formula(paste("de ~", paste(main_cols, collapse = " + "), "+", CONTROLS)), data = main_df)
main <- list(m = main_m, V = NeweyWest(main_m, lag = 5, prewhite = FALSE, adjust = TRUE))
main_ct <- coeftest(main$m, vcov. = main$V, df = Inf)[main_cols, ]
main_tab <- data.frame(j = -5:5, beta = main_ct[, 1], se = main_ct[, 2], p = main_ct[, 4])
main_sums <- bind_rows(
  cbind(window = "past flows (j = -5..-1)",   lincom(main, main_cols[1:5])),
  cbind(window = "same day (j = 0)",          lincom(main, main_cols[6])),
  cbind(window = "future flows (j = +1..+5)", lincom(main, main_cols[7:11])),
  cbind(window = "all (j = -5..+5)",          lincom(main, main_cols)))
write_csv(main_tab, file.path(tab_dir, "main_spec_coefs.csv"))
write_csv(main_sums, file.path(tab_dir, "main_spec_sums.csv"))

# 1. Core specifications and robustness
specs <- list(
  "1 Net flow"                   = list(panel, paste("net +", CONTROLS)),
  "2 Repay vs issue"             = list(panel, paste("repay + issue +", CONTROLS)),
  "3 Principal vs coupon"        = list(panel, paste("principal + coupon + issue +", CONTROLS)),
  "4 Foreign-held repay (2015+)" = list(since("2015-08-03"), paste("repay_foreign + issue +", CONTROLS)),
  "5 US-held net (2014+)"        = list(since("2014-01-02"), paste("net_us +", CONTROLS)),
  "R1 Excl. Mar-Apr 2020"        = list(filter(panel, covid == 0), paste("repay + issue +", CONTROLS)),
  "R2 + AUD return"              = list(panel, paste("repay + issue +", CONTROLS, "+ r_aud")),
  "R3 + day-of-week FE"          = list(panel, paste("repay + issue +", CONTROLS, "+ dow")),
  "R4 Unscaled, 2015+"           = list(since("2015-08-03"), paste("repay + issue +", CONTROLS))
)
fits <- lapply(specs, function(s) fit(s[[1]], s[[2]]))
keep <- c("net", "repay", "issue", "principal", "coupon", "repay_foreign", "net_us",
          "d_rate_diff", "d_vix", "us_release", "r_aud")
core <- bind_rows(Map(function(r, n) tidy(r, n, keep), fits, names(fits)))
write_csv(core, file.path(tab_dir, "core_regressions.csv"))

# Netting test, H0: beta_repay + beta_issue = 0 (equal and opposite effects)
netting <- lincom(fits[["2 Repay vs issue"]], c("repay", "issue"))

# 2. Event window, full sample
w1 <- add_window(panel, "repay"); w2 <- add_window(w1$df, "issue")
ev <- fit(w2$df, paste(c(w1$cols, w2$cols, CONTROLS), collapse = " + "))
path <- bind_rows(lapply(list(repay = w1$cols, issue = w2$cols), function(cols) {
  ct <- coeftest(ev$m, vcov. = ev$V, df = Inf)[cols, ]
  data.frame(tau = WINDOW, coef = ct[, 1], se = ct[, 2], p = ct[, 4])
}), .id = "series")
write_csv(path, file.path(tab_dir, "event_window_coefs.csv"))
sums <- bind_rows(window_sums(ev, w1$cols, "repay"), window_sums(ev, w2$cols, "issue"))
write_csv(sums, file.path(tab_dir, "event_window_sums.csv"))

# Event window with foreign-held repayments, 2015+
f1 <- add_window(since("2015-08-03"), "repay_foreign"); f2 <- add_window(f1$df, "issue")
evf <- fit(f2$df, paste(c(f1$cols, f2$cols, CONTROLS), collapse = " + "))
sums_f <- window_sums(evf, f1$cols, "repay_foreign (2015+)")
write_csv(sums_f, file.path(tab_dir, "event_window_sums_foreign.csv"))

# 3. Large maturities: principal >= NZ$2bn, raw and AUD-adjusted cumulative returns
big <- bind_rows(lapply(which(panel$principal >= 2), function(i) {
  if (i - 5 < 1 || i + 5 > nrow(panel)) return(NULL)
  w <- panel[(i - 5):(i + 5), ]; x <- w$r_nzd - w$r_aud
  data.frame(date = panel$date[i], principal_bn = panel$principal[i],
             pre = sum(w$r_nzd[1:5]), day0 = w$r_nzd[6], post = sum(w$r_nzd[7:11]),
             pre_vs_aud = sum(x[1:5]), day0_vs_aud = x[6], post_vs_aud = sum(x[7:11]))
}))
write_csv(big, file.path(tab_dir, "large_maturities.csv"))
big_t <- sapply(big[, -(1:2)], function(v) c(mean = mean(v), t = mean(v) / (sd(v) / sqrt(length(v)))))

# 4. Figure: daily and cumulative event-window effects per NZ$1bn
plot_df <- path |> group_by(series) |> arrange(tau, .by_group = TRUE) |>
  mutate(cum = cumsum(coef),
         series = factor(recode(series, repay = "Repayment (coupon + principal + buyback)", issue = "Issuance"),
                         levels = c("Repayment (coupon + principal + buyback)", "Issuance")))
p <- ggplot(plot_df, aes(tau)) +
  geom_hline(yintercept = 0, colour = "grey50") +
  geom_vline(xintercept = 0, colour = "grey50", linetype = "dashed") +
  geom_pointrange(aes(y = coef, ymin = coef - 1.96 * se, ymax = coef + 1.96 * se), colour = "steelblue") +
  geom_line(aes(y = cum), colour = "darkorange", linewidth = 1) +
  facet_wrap(~ series, scales = "free_y") +
  scale_x_continuous(breaks = WINDOW) +
  labs(x = "Trading days relative to flow", y = "NZD/USD return, % per NZ$1bn (+ = NZD up)",
       caption = "Points: daily effect with 95% CI. Line: cumulative effect.") +
  theme_minimal()
ggsave(file.path(fig_dir, "event_window.png"), p, width = 11, height = 4, dpi = 200)

# 5. Print summary
options(width = 160)
cat(sprintf("MAIN SPEC: de_t on N_{t+j}, j = -5..5, n = %d\n", nobs(main$m)))
print(main_tab |> mutate(across(where(is.numeric), ~ round(.x, 4))), row.names = FALSE)
print(main_sums |> mutate(across(where(is.numeric), ~ round(.x, 4))), row.names = FALSE)
cat("\nCORE REGRESSIONS (flow coefficients, % NZD/USD per NZ$1bn)\n")
print(core |> filter(term %in% c(keep[1:7], "r_aud")) |> mutate(across(where(is.numeric), ~ round(.x, 4))), row.names = FALSE)
cat("\nControls in spec 2:\n")
print(core |> filter(model == "2 Repay vs issue", term %in% c("d_rate_diff", "d_vix", "us_release")) |>
        mutate(across(where(is.numeric), ~ round(.x, 4))), row.names = FALSE)
cat(sprintf("\nNetting test, H0: beta_repay + beta_issue = 0 -> sum=%.4f, p=%.3f\n", netting$sum_coef, netting$p))
cat("\nEVENT WINDOW SUMS\n")
print(bind_rows(sums, sums_f) |> mutate(across(where(is.numeric), ~ round(.x, 4))), row.names = FALSE)
cat(sprintf("\nLARGE MATURITIES (principal >= NZ$2bn, n=%d), cumulative %% NZD/USD\n", nrow(big)))
print(round(t(big_t), 3))
