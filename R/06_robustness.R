# 06_robustness.R - does the principal-window result (P_evt) survive
#   (a) another peso pair (EUR/MXN), (b) Banxico FIX instead of FRED H.10, (c) dropping the largest maturities?
# Plus one diagnostic: the same-window EUR/USD and BRL moves as controls (is it the peso, or the dollar / EM that day?).
# Each spec is the pooled regression r ~ P_pre + P_evt + P_post + VIX + US 2y + Brent, HAC(10),
# with a placebo that puts the real repayment amounts on random non-event windows (1000 draws).
source("R/00_config.R"); options(mx.no_main = TRUE, mx.lib_only = TRUE)
source("R/03_build_panel.R"); source("R/04_run_regressions.R")

CTRL <- c("dlnVIX", "dUST2", "rBrent")
N_DRAW <- 1000

# Remove windows -5..+5 around dropped events, so their FX moves leave the sample entirely.
drop_around <- function(w, idx) { for (i in idx) w$r[max(1, i - 5):min(nrow(w), i + 5)] <- NA; w }

evaluate <- function(w, label, drop_idx = integer(0), ctrl = CTRL) {
  base <- w; base$P0[drop_idx] <- 0
  pw <- drop_around(pooled_frame(base), drop_idx)
  f <- fit_hac(pw, c("P_pre", "P_evt", "P_post", ctrl))
  ev <- setdiff(which(w$P0 > 0), drop_idx); amt <- w$P0[ev]
  ok <- is.finite(pw$r)
  pool <- which(w$P0 == 0 & ok & seq_len(nrow(w)) > 10 & seq_len(nrow(w)) < nrow(w) - 10)
  set.seed(7)
  draws <- replicate(N_DRAW, {
    fake <- w; fake$P0 <- 0; fake$P0[sample(pool, length(ev))] <- amt
    fp <- drop_around(pooled_frame(fake), drop_idx); fp$r[!ok] <- NA
    fit_hac(fp, c("P_pre", "P_evt", "P_post", ctrl))$ct["P_evt", 1]
  })
  b <- f$ct["P_evt", 1]; se <- f$ct["P_evt", 2]
  tibble(spec = label, P_evt = b, hac_se = se, hac_p = f$ct["P_evt", 4], ci_lo = b - 1.96 * se, ci_hi = b + 1.96 * se,
         placebo_p = mean(abs(draws) >= abs(b)), n_events = length(ev), n_windows = f$n)
}

usd <- window_frame("h10"); ev <- which(usd$P0 > 0); big <- ev[order(-usd$P0[ev])]
eu  <- read_fred_csv("DEXUSEU") %>% arrange(date) %>% transmute(date, rEURUSD = 100 * (log(value) - log(lag(value))))
usd_x <- usd %>% left_join(eu, by = "date")
jun13 <- ev[usd$date[ev] == as.Date("2013-06-20")]

res <- bind_rows(
  evaluate(usd, "USD/MXN, H.10 (baseline)"),
  evaluate(window_frame("fix"), "USD/MXN, Banxico FIX"),
  evaluate(window_frame("h10_eur"), "EUR/MXN"),
  evaluate(usd, "drop largest maturity", drop_idx = big[1]),
  evaluate(usd, "drop 3 largest", drop_idx = big[1:3]),
  evaluate(usd, "drop 5 largest", drop_idx = big[1:5]),
  evaluate(usd, "drop 20 June 2013 only", drop_idx = jun13),
  evaluate(usd_x, "+ EUR/USD and BRL moves", ctrl = c(CTRL, "rEURUSD", "rBRL")))
write_csv(res, file.path(OUT, "mx_robustness.csv"))
print(res %>% mutate(across(where(is.numeric), ~ signif(.x, 3))), width = 200)

png(file.path(OUT, "mx_robustness.png"), width = 1600, height = 900, res = 180)
par(mar = c(4.5, 13, 3, 6)); y <- rev(seq_len(nrow(res))); col <- ifelse(y == max(y), "firebrick", "black")
plot(res$P_evt, y, xlim = range(c(res$ci_lo, res$ci_hi)), yaxt = "n", pch = 19, col = col, bty = "l", ylab = "",
     xlab = "P_evt: % change in foreign currency per MXN, per MXN 1bn foreign-held principal",
     main = "Payment-window coefficient across specifications (HAC 95% intervals)")
abline(v = 0, col = "grey50"); arrows(res$ci_lo, y, res$ci_hi, y, angle = 90, code = 3, length = 0.03, col = col)
axis(2, at = y, labels = res$spec, las = 1, cex.axis = 0.8, tick = FALSE)
mtext(sprintf("placebo p = %.2f", res$placebo_p), side = 4, at = y, las = 1, line = 0.5, cex = 0.7)
dev.off()
