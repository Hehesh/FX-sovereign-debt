#!/usr/bin/env python3
"""Attempt 1: minimal {0,+1} net-flow window with information-set-valid controls (see ATTEMPTS.md, A1).

Reads the panel rebuilt by gate0_diagnostics.py; writes to output/attempts/01_aligned/.
Example: python code/attempt1_aligned.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_regressions as rr  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
PANEL = BASE / 'output' / 'attempts' / '00_gate0_baseline' / 'rebuilt' / 'intermediate' / 'merged_constructed_panel.csv'
G0_COEF = BASE / 'output' / 'attempts' / '00_gate0_baseline' / 'coefficients.csv'
OUT = BASE / 'output' / 'attempts' / '01_aligned_a1_superseded'  # A1r (attempt1r.py) owns 01_aligned
Y = 'log_return_pct'
PRIMARY = ['N0', 'N1', 'vix_l2', 'us_release']


def prepare(panel: pd.DataFrame, flow: pd.Series | None = None) -> pd.DataFrame:
    p = panel.copy()
    n = (p['us_net_flow'] if flow is None else flow) / 1000.0  # NZ$ billion
    p['N0'], p['N1'] = n, n.shift(-1)
    p['vix_l2'] = p['vix'].shift(2)
    p['swap_l2'] = p['treasury_swap_merged'].shift(2)
    return p


def fit(p: pd.DataFrame, cols: list[str], lags: int = 10, dates: pd.Series | None = None):
    frame = p[['date', Y, *cols]].replace([np.inf, -np.inf], np.nan).dropna()
    if dates is not None:
        frame = frame[frame.date.isin(dates)]
    res = sm.OLS(frame[Y], sm.add_constant(frame[cols])).fit(
        cov_type='HAC', cov_kwds={'maxlags': lags}, use_t=False)
    return res, frame


def table(res, label: str) -> pd.DataFrame:
    ci = res.conf_int()
    t = pd.DataFrame({'spec': label, 'term': res.params.index, 'coef': res.params.values,
                      'hac_se': res.bse.values, 'ci95_lo': ci[0].values, 'ci95_hi': ci[1].values,
                      'p': res.pvalues.values, 'n': int(res.nobs)})
    c = rr.contrast(res, {'N0': 1, 'N1': 1}, 'b0+b1')
    return pd.concat([t, pd.DataFrame([{
        'spec': label, 'term': 'b0+b1', 'coef': c['estimate'], 'hac_se': c['se'],
        'ci95_lo': c['ci95_lower'], 'ci95_hi': c['ci95_upper'], 'p': c['p_value'], 'n': int(res.nobs)}])])


def placebo(panel: pd.DataFrame, n_draw: int = 300, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for m in rng.choice(np.r_[-250:-40, 41:251], n_draw, replace=False):
        p = prepare(panel, panel['us_net_flow'].shift(int(m)))
        try:
            res, _ = fit(p, PRIMARY)
        except ValueError:
            continue
        c = rr.contrast(res, {'N0': 1, 'N1': 1}, 'placebo')
        rows.append({'shift': int(m), 'b0_plus_b1': c['estimate'], 'z': c['statistic']})
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(PANEL, parse_dates=['date'])
    p = prepare(panel)
    g0_dates = pd.read_csv(BASE / 'output' / 'intermediate' / 'sample_dates_net_flows_log_return_pct.csv',
                           parse_dates=['date']).date
    tables = []
    primary, frame = fit(p, PRIMARY)
    tables.append(table(primary, 'primary'))
    restricted, _ = fit(p, PRIMARY, dates=g0_dates)
    tables.append(table(restricted, 'g0_sample'))
    for lags in (5, 20):
        tables.append(table(fit(p, PRIMARY, lags)[0], f'hac{lags}'))
    tables.append(table(fit(p, PRIMARY + ['swap_l2'])[0], 'plus_swap_l2'))
    pd.concat(tables).to_csv(OUT / 'coefficients.csv', index=False, float_format='%.6g')

    c = rr.contrast(primary, {'N0': 1, 'N1': 1}, 'b0+b1')
    plc = placebo(panel)
    plc.to_csv(OUT / 'placebo.csv', index=False, float_format='%.5g')
    p_placebo = float((plc.b0_plus_b1.abs() >= abs(c['estimate'])).mean())
    mde = (1.96 + 0.84) * c['se']

    # Side by side with G0 M1 (11-term window, contemporaneous controls), per NZ$bn.
    g0 = pd.read_csv(G0_COEF)
    g0 = g0[(g0.model == 'Net flows') & (g0.outcome == Y)].set_index('term')
    side = []
    for term, g0term in [('N0', 'us_net_flow_k+0'), ('N1', 'us_net_flow_k+1')]:
        a = table(primary, 'primary').set_index('term').loc[term]
        side.append({'term': term, 'g0_coef_per_bn': g0.loc[g0term, 'coef'] * 1000,
                     'g0_se': g0.loc[g0term, 'hac_se'] * 1000, 'a1_coef_per_bn': a.coef, 'a1_se': a.hac_se,
                     'g0_n': 2671, 'a1_n': int(primary.nobs)})
    pd.DataFrame(side).to_csv(OUT / 'side_by_side_vs_g0.csv', index=False, float_format='%.5g')

    pd.DataFrame([{'b0_plus_b1': c['estimate'], 'se': c['se'], 'ci95_lo': c['ci95_lower'],
                   'ci95_hi': c['ci95_upper'], 'p_hac': c['p_value'], 'placebo_p': p_placebo,
                   'placebo_sd': plc.b0_plus_b1.std(), 'mde_80pct': mde, 'n': int(primary.nobs),
                   'n_nonzero_flow_sessions': int((frame.N0 != 0).sum()),
                   'first': str(frame.date.min().date()), 'last': str(frame.date.max().date()),
                   'adj_r2': primary.rsquared_adj}]).to_csv(OUT / 'summary.csv', index=False, float_format='%.5g')

    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.hist(plc.b0_plus_b1, bins=30, color='0.7')
    ax.axvline(c['estimate'], color='C3', label=f"actual {c['estimate']:.3f}")
    ax.set_xlabel('b0+b1, % return per NZ$bn US-weighted net issuance')
    ax.set_title('A1: circular-shift placebo distribution')
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / 'placebo_hist.png', dpi=160)
    print(pd.read_csv(OUT / 'summary.csv').T)
    print(pd.read_csv(OUT / 'side_by_side_vs_g0.csv'))
    print(pd.read_csv(OUT / 'coefficients.csv').query("spec in ['primary','g0_sample','hac5','hac20','plus_swap_l2'] and term in ['N0','N1','b0+b1']"))


if __name__ == '__main__':
    main()
