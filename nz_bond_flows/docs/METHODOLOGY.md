# NZD/USD and New Zealand Sovereign Cash Flows — Regression Memo

## Purpose and sample

Estimate whether New Zealand sovereign financing cash flows are associated with changes in NZD/USD, and test (i) anticipation of principal repayments, (ii) issuance–repayment asymmetry, and (iii) post-payment reversal. The dependent variable is the daily level change $\Delta e_t=e_t-e_{t-1}$, where $e_t$ is **USD per NZD**, so an increase denotes NZD appreciation. The supplied `FX.csv` stores **NZD per USD** in its `dexnzus` column; the script takes its reciprocal by default (`--fx-quote nzd-per-usd`). Use `--fx-quote usd-per-nzd` for an input already quoted as USD per NZD. The source column is preserved in the intermediate panel. A robustness regression uses $100\Delta\log(e_t)$, an approximate daily percentage return. One lag or lead is **one observed FX trading session**, not one calendar day.

## Cash-flow construction

Combine nominal (`nom_*`) and inflation-indexed (`iib_*`) flows separately for issuance $I_t$, principal repayment $R_t$, coupon repayment $C_t$, and buybacks $B_t$, without mixing in the alternative `*_face` columns. The daily-flow builder exports issuance as negative and repayments as positive; negate the summed issuance columns to obtain the positive magnitude $I_t$. Source columns retain their original signs in the intermediate panel. Construct

$$
N_t=I_t-R_t-C_t-B_t,\qquad
Z_t^{US}=s_t^{US}Z_t,\quad Z\in\{N,I,R,C,B\}.
$$

Here $s_t^{US}$ is `us_share` on a 0–1 scale. The reader accepts fractions such as `0.158` and explicitly marked percentages such as `15.80%`, converting the latter to `0.158`. Bare values above 1, malformed numbers and entirely missing shares raise an error. The series weights cash flows by estimated **US holdings**, **not total foreign holdings**, and is not a direct measurement of USD conversions. Verify that all flow component units are comparable before interpreting a coefficient in economic units. The code does **not** rescale flow units automatically.

## Estimated models

**M1 — net-flow benchmark**

$$
\Delta e_t=\alpha+\sum_{k=-5}^{5}\beta_k N_{t+k}^{US}+\gamma^\top X_t+\epsilon_t.
$$

**M2 — disaggregated primary specification**

$$
\Delta e_t=\alpha+\sum_{k=-5}^{5}\beta_k^I I_{t+k}^{US}
+\sum_{k=-5}^{5}\beta_k^R R_{t+k}^{US}
+\delta_C C_t^{US}+\delta_B B_t^{US}+\gamma^\top X_t+\epsilon_t.
$$

$X_t$ contains `vix`, `treasury_swap_merged`, and `us_release`, as provided. All cash-flow magnitudes $I,R,C,B$ enter as nonnegative amounts, so the hypothesis of a symmetric response to issuance and repayment has an **opposite-sign coefficient** restriction. With $N_{t+k}$, $I_{t+k}$, and $R_{t+k}$, **positive $k$ describes FX movement before the event**; negative $k$, movement after it. Models are estimated using OLS with heteroskedasticity/autocorrelation-consistent Newey–West (HAC) covariance (default lag bandwidth: 10 sessions). Correlation is not necessarily causation.

## Hypothesis tests (M2)

| Question | Statistic/restriction | Interpretation |
|---|---|---|
| **H1 Anticipation** | Joint Wald $H_0:\beta_1^R=\cdots=\beta_5^R=0$; one-sided test $A=\sum_{k=1}^5\beta_k^R>0$. | Joint significance detects a pre-event response; a positive $A$ specifically supports NZD appreciation. |
| **H2 Asymmetry** | Event-day Wald $H_0:\beta_0^I+\beta_0^R=0$; supplementary full-window Wald $H_0:\sum_{k=-5}^{5}(\beta_k^I+\beta_k^R)=0$. | Rejecting either restriction indicates departure from symmetric, equal-and-opposite issuance/repayment effects. |
| **H3 Reversal** | Joint Wald $H_0:\beta_{-5}^R=\cdots=\beta_{-1}^R=0$; one-sided test $P=\sum_{k=-5}^{-1}\beta_k^R<0$. | Negative $P$ identifies post-event depreciation. |
| **H3 Complete offset (supplementary)** | Wald $H_0:A+P=0$, and a 95% CI for $A+P$. | Non-rejection alone **does not establish** complete reversal; examine both the sign tests and CI precision. |

All one-sided tests are asymptotic normal tests using the same HAC covariance; joint tests use asymptotic chi-squared Wald tests. These are overlapping hypotheses and their p-values are not multiple-testing-adjusted. The principal repayment variable is a magnitude rather than a signed net cash flow.

## Calendar/data conventions and assumptions

- Begin with dates with an observed `dexnzus` exchange rate. Non-FX-date cash-flow rows are, by default, **assigned to the next available observed FX session** (`--weekend-policy next-fx-day`). Alternative: `--weekend-policy drop`. Dates assigned across holidays/weekends are recorded in `flow_date_mapping_audit.csv`; this is a reporting convention, not proof that execution or settlement occurred that day.
- Flow records before the first or after the last observed FX session are excluded under either calendar policy.
- If an FX date has **no flow record**, the default is to keep the event variables missing and use complete-case regression (`--missing-flow missing`). An optional `--missing-flow zero` asserts *absence means zero*: use only after confirming the cash-flow dataset is a complete payment calendar. Missing component values *within* a present record remain missing.
- Use a **backward as-of join** on `us_share` (latest dated share at or before the FX date). No future share is used. This amounts to assuming share stability between observations; revise if its measurement horizon suggests otherwise.
- Controls are joined by **exact date**, not forward-filled. Any incomplete observation used by a model is excluded from that model's sample, but leads and lags are constructed on the intact FX-session calendar before exclusion.
- Contemporaneous controls may not be strictly predetermined. The coefficients quantify conditional associations and do not establish causal FX conversions; a fully causal analysis would need a credible identification strategy.

## Implementation and files

From `basedir/code/`, run:

```bash
python -m pip install numpy pandas scipy statsmodels matplotlib jinja2
python run_regressions.py
```

From the Practicum workspace, use `python nz_bond_flows/code/run_regressions.py`. Select the existing **Trading** Python environment, which contains the dependencies; the Homebrew `python3` interpreter may use a different environment. Run the data-contract tests from `nz_bond_flows/` with `python -m unittest discover -s code -p 'test_*.py'`.

Required inputs in `basedir/regression/`: `FX.csv`, `nz_daily_flows.csv`, `Controls - Regression Control Panel.csv`, and `US_Share_of_New_Zealand_Debt.xlsx - Regression Series.csv`.

Outputs in `basedir/output/`:

- `intermediate/merged_constructed_panel.csv`: merged source series, constructed flows, and all lead–lag regressors; plus `flow_date_mapping_audit.csv`, complete-case sample dates, and missingness diagnostics.
- `tables/`: two complete Stata-style LaTeX regression reports and their rendered PDFs, one for each model (`regression_net_flows` and `regression_disaggregated`). Each report contains coefficient estimates, HAC standard errors, z statistics, p-values, 95% confidence intervals, R-squared, adjusted R-squared, F statistics, AIC/BIC, and heteroskedasticity, autocorrelation, normality, and Durbin--Watson diagnostics.
- `hypothesis_tests/`: three complete LaTeX hypothesis reports and their rendered PDFs for anticipation (H1), issuance–repayment asymmetry (H2), and post-event response (H3).
- `run.log` and `run_metadata.json`: choices and warnings.

**Before publication:** validate flow unit definitions, share frequency/meaning, calendar conventions, contemporaneous versus scheduled information, and whether enough complete observations exist relative to the 22 lead–lag coefficients in M2.
