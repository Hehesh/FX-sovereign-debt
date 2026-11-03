# 04_run_regressions.R - A1r specification on Mexico, plus the pooled principal window and placebo.
#   primary:  r = a + b0*N0 + b1*N1 + g'controls,  HAC (Newey-West, 10 lags), estimand b0+b1
#   pooled:   principal only, P_pre (windows -5..-1), P0 (0..+1), P_post (+2..+5) summed -> 3 coefficients
#   placebo:  shift the flow series by |m| >= 40 windows, 300 draws, empirical p for b0+b1
source("R/00_config.R"); options(mx.no_main = TRUE); source("R/03_build_panel.R")

fit_hac <- function(w, cols, lags = HAC_LAGS) {
  d <- w %>% select(date, r, all_of(cols))
  d <- d[is.finite(d$r) & is.finite(rowSums(as.matrix(d[cols]))), ]
  m <- lm(reformulate(cols, "r"), data = d)
  V <- NeweyWest(m, lag = lags, prewhite = FALSE, adjust = TRUE)
  list(model = m, V = V, n = nrow(d), ct = coeftest(m, vcov. = V))
}
contrast <- function(f, weights) {       # linear combination of coefficients with HAC se
  b <- coef(f$model)[names(weights)]; w <- unlist(weights)
  est <- sum(w * b); se <- sqrt(as.numeric(t(w) %*% f$V[names(weights), names(weights)] %*% w))
  z <- est / se; tibble(estimate = est, se = se, z = z, p = 2 * pnorm(-abs(z)),
                        ci_lo = est - 1.96 * se, ci_hi = est + 1.96 * se)
}
tidy_fit <- function(f, label) {
  bind_rows(
    tibble(spec = label, term = rownames(f$ct), coef = f$ct[, 1], hac_se = f$ct[, 2], p = f$ct[, 4], n = f$n),
    contrast(f, list(N0 = 1, N1 = 1)) %>% transmute(spec = label, term = "b0+b1", coef = estimate, hac_se = se, p, n = f$n))
}

placebo <- function(w, cols = PRIMARY, n_draw = 300, seed = 1) {
  set.seed(seed); shifts <- sample(c(-250:-40, 41:250), n_draw)
  bind_rows(lapply(shifts, function(m) {
    p <- w; p$N0 <- if (m > 0) lag(w$N0, m) else lead(w$N0, -m); p$N1 <- lead(p$N0)
    f <- fit_hac(p, cols); contrast(f, list(N0 = 1, N1 = 1)) %>% mutate(shift = m)
  }))
}

# ---- pooled principal windows (fix for "too few events": 3 coefficients instead of 11) ----
pooled_frame <- function(w) {
  # Event-time k: principal settling k windows after this one. k>0 = pre-event (anticipation).
  w %>% mutate(P_pre  = Reduce(`+`, lapply(1:5, function(k) lead(P0, k))),   # k = +1..+5 (before the payment)
               P_evt  = P0 + lag(P0, 1),                                      # k = 0, -1 (payment window and the next)
               P_post = Reduce(`+`, lapply(2:5, function(k) lag(P0, k))))     # k = -2..-5 (after)
}

main <- function() {
  w  <- window_frame("fix")
  res <- bind_rows(
    tidy_fit(fit_hac(w, PRIMARY), "primary_fix"),
    tidy_fit(fit_hac(w, PRIMARY, 5), "hac5"),
    tidy_fit(fit_hac(w, PRIMARY, 20), "hac20"),
    tidy_fit(fit_hac(w, c("N0", "N1", "dlnVIX", "dPol", "dBroadUSD")), "sub_broadUSD_for_Brent"),
    tidy_fit(fit_hac(w, c("N0", "N1", "dlnVIX", "dPol", "rBrent", "rBRL")), "add_peer_BRL"),
    tidy_fit(fit_hac(window_frame("fix", shift_controls = TRUE), PRIMARY), "controls_pre_window"),
    tidy_fit(fit_hac(window_frame("h10"), PRIMARY), "h10_window"))
  write_csv(res, file.path(OUT, "mx_a1r_coefficients.csv"))

  pw <- pooled_frame(w)
  pf <- fit_hac(pw, c("P_pre", "P_evt", "P_post", "dlnVIX", "dPol", "rBrent"))
  write_csv(tibble(term = rownames(pf$ct), coef = pf$ct[, 1], hac_se = pf$ct[, 2], p = pf$ct[, 4], n = pf$n),
            file.path(OUT, "mx_pooled_principal.csv"))

  pl <- placebo(w); actual <- contrast(fit_hac(w, PRIMARY), list(N0 = 1, N1 = 1))
  summ <- tibble(actual = actual$estimate, hac_se = actual$se, hac_p = actual$p,
                 placebo_sd = sd(pl$estimate), placebo_p = mean(abs(pl$estimate) >= abs(actual$estimate)),
                 n_principal = sum(w$P0 > 0), n_issuance = sum(w$I0 > 0), n_windows = nrow(w))
  write_csv(pl, file.path(OUT, "mx_placebo.csv")); write_csv(summ, file.path(OUT, "mx_summary.csv"))
  print(res %>% filter(spec == "primary_fix")); print(summ)
}
main()
