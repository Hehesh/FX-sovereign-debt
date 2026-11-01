#!/usr/bin/env python3
"""Attempt 7 (A7): A1r specification with principal split out and a +-h-window principal block; see ATTEMPTS.md.

Imports attempt1r (not modified, its outputs are not written). Writes output/attempts/07_principal_window/.
Example: python code/attempt7_principal_window.py
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
import attempt1r as a1  # noqa: E402
import run_regressions as rr  # noqa: E402
import timing as T  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / 'output' / 'attempts' / '07_principal_window'
SAMPLE_US = a1.SAMPLE
SAMPLE_LONG = ('2000-01-04', '2025-02-07')
CONTROLS = ['dlnVIX', 'dPol', 'rBrent']
CONTROLS_LONG = ['dlnVIX', 'rBrent']  # dPol (NZ swap leg) starts 2011
HALF = 2


def window_sum(f: pd.DataFrame, col: str, n_windows: int) -> pd.Series:
    """Sum per window; NaN if any component is NaN (no partial sums, as in A1r)."""
    g = f.groupby('j')[col]
    s = g.sum(min_count=1).where(~g.apply(lambda x: x.isna().any()))
    return s.reindex(range(n_windows))


def build(weighted: bool = True, share_lag_months: int = 0, sample=SAMPLE_US) -> pd.DataFrame:
    """Window frame with principal P0 and non-principal Q0, Q1 (NZ$ bn); leads of P are added by design()."""
    e, fix = a1.fixings('h10')
    f = a1.settlements(share_lag_months)
    scale = (f.us_share if weighted else 1.0) / 1000.0
    f['P'] = f.principal * scale
    f['Q'] = (f.net + f.principal) * scale  # issuance - coupon - buyback
    f['j'] = T.window_index(pd.DatetimeIndex(f.settle_utc), fix)
    f = f[f.j >= 0]
    w = pd.DataFrame({'date': e.index, 'r': 100 * np.log(e.to_numpy())})
    w['r'] = w.r.diff()
    w['P0'] = window_sum(f, 'P', len(w)).to_numpy()
    w['Q0'] = window_sum(f, 'Q', len(w)).to_numpy()
    w['Q1'] = w.Q0.shift(-1)
    w = pd.concat([w, a1.controls(fix)], axis=1)
    # A1r's validity rule is on N = Q - P; the same windows are valid here
    return w[(w.date >= sample[0]) & (w.date <= sample[1])].reset_index(drop=True)


def design(w: pd.DataFrame, half: int) -> tuple[pd.DataFrame, list[str]]:
    """Add P_k = principal in window j+k for k = -half..+half (k > 0: event in the future)."""
    w = w.copy()
    cols = []
    for k in range(-half, half + 1):
        c = f'P{k:+d}'
        w[c] = w.P0.shift(-k)
        cols.append(c)
    return w, cols


def fit(w: pd.DataFrame, cols: list[str], lags: int = 10):
    d = w[['date', 'r', *cols]].replace([np.inf, -np.inf], np.nan).dropna()
    res = sm.OLS(d.r, sm.add_constant(d[cols])).fit(cov_type='HAC', cov_kwds={'maxlags': lags}, use_t=False)
    return res, d


def contrasts(res, pcols: list[str], half: int) -> dict[str, dict]:
    k = lambda ks: {f'P{i:+d}': 1.0 for i in ks if abs(i) <= half}
    out = {'S_total': k(range(-half, half + 1)), 'event_k0': k([0]), 'a1r_analogue_k0_k1': k([0, 1]),
           'pre_k+1..': k(range(1, half + 1)), 'post_k-1..': k(range(-half, 0))}
    return {n: rr.contrast(res, wts, n) for n, wts in out.items() if wts}


def summarize(label: str, res, d, pcols, half, frame) -> list[dict]:
    rows = []
    n_ev = int((frame.P0.fillna(0) != 0).sum())
    for name, c in contrasts(res, pcols, half).items():
        rows.append({'spec': label, 'half_width': half, 'contrast': name, 'estimate': c['estimate'], 'hac_se': c['se'],
                     'ci95_lo': c['ci95_lower'], 'ci95_hi': c['ci95_upper'], 'p_hac': c['p_value'],
                     'mde_80pct': 2.8 * c['se'], 'n': int(res.nobs), 'n_event_windows_in_frame': n_ev})
    return rows


def run_spec(label, w, controls, half, lags=10, store=None):
    ww, pc = design(w, half)
    cols = [*pc, 'Q0', 'Q1', *controls]
    res, d = fit(ww, cols, lags)
    if store is not None:
        store[label] = res
    return res, d, pc, ww


def placebo(w: pd.DataFrame, controls, n_draw: int = 300, seed: int = 1) -> pd.DataFrame:
    """Circular shift of the principal series (all P_k together); Q and controls stay in place."""
    rng, rows = np.random.default_rng(seed), []
    for m in rng.choice(np.r_[-250:-40, 41:251], n_draw, replace=False):
        p = w.copy()
        p['P0'] = np.roll(w.P0.to_numpy(), int(m))
        res, _, pc, _ = run_spec('plc', p, controls, HALF)
        cs = contrasts(res, pc, HALF)
        rows.append({'shift': int(m), 'S_total': cs['S_total']['estimate'], 'z': cs['S_total']['statistic'],
                     'event_k0': cs['event_k0']['estimate'], 'pre': cs['pre_k+1..']['estimate'],
                     'post': cs['post_k-1..']['estimate']})
    return pd.DataFrame(rows)


def leave_one_out(w: pd.DataFrame, controls) -> pd.DataFrame:
    rows = []
    for i in w.index[w.P0.fillna(0) != 0]:
        drop = set(range(i - HALF - 2, i + HALF + 3))  # event window plus Q1 / HAC edge
        res, _, pc, _ = run_spec('loo', w[~w.index.isin(drop)].reset_index(drop=True), controls, HALF)
        c = rr.contrast(res, {x: 1.0 for x in pc}, 'loo')
        rows.append({'dropped_event': str(w.date[i].date()), 'S_total': c['estimate'], 'hac_se': c['se'],
                     'ci95_lo': c['ci95_lower'], 'ci95_hi': c['ci95_upper'], 'n': int(res.nobs)})
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    w = build()
    w6 = build(share_lag_months=6)
    wu = build(weighted=False)
    wl = build(weighted=False, sample=SAMPLE_LONG)
    wp = build(weighted=False, sample=(SAMPLE_LONG[0], '2013-12-31'))
    summ, coefs, fits = [], [], {}
    # (label, frame, controls, half, lags); primary first, width comparison next, sensitivities after
    specs = [('primary_h2', w, CONTROLS, 2, 10), ('width_h1', w, CONTROLS, 1, 10), ('width_h5', w, CONTROLS, 5, 10),
             ('hac5', w, CONTROLS, 2, 5), ('hac20', w, CONTROLS, 2, 20), ('share_lag_6m', w6, CONTROLS, 2, 10),
             ('unweighted_2014_h2', wu, CONTROLS, 2, 10), ('unweighted_2000_h2', wl, CONTROLS_LONG, 2, 10),
             ('unweighted_2000_2013_h2', wp, CONTROLS_LONG, 2, 10),  # post hoc: pre-2014 events only
             ('unweighted_2000_h1', wl, CONTROLS_LONG, 1, 10), ('unweighted_2000_h5', wl, CONTROLS_LONG, 5, 10)]
    for label, frame, ctl, half, lags in specs:
        res, d, pc, ww = run_spec(label, frame, ctl, half, lags, fits)
        summ += summarize(label, res, d, pc, half, frame)
        ci = res.conf_int()
        coefs.append(pd.DataFrame({'spec': label, 'term': res.params.index, 'coef': res.params.values,
                                   'hac_se': res.bse.values, 'ci95_lo': ci[0].values, 'ci95_hi': ci[1].values,
                                   'p': res.pvalues.values, 'n': int(res.nobs)}))
    pd.concat(coefs).to_csv(OUT / 'coefficients.csv', index=False, float_format='%.6g')
    s = pd.DataFrame(summ)
    plc = placebo(w, CONTROLS)
    plc.to_csv(OUT / 'placebo.csv', index=False, float_format='%.5g')
    prim = s[(s.spec == 'primary_h2') & (s.contrast == 'S_total')].iloc[0]
    s['placebo_p'] = np.where((s.spec == 'primary_h2') & (s.contrast == 'S_total'),
                              float((plc.S_total.abs() >= abs(prim.estimate)).mean()), np.nan)
    # post hoc (added after seeing the primary run): placebo p for each secondary contrast
    for name, col in (('event_k0', 'event_k0'), ('pre_k+1..', 'pre'), ('post_k-1..', 'post')):
        act = s[(s.spec == 'primary_h2') & (s.contrast == name)].iloc[0].estimate
        s.loc[(s.spec == 'primary_h2') & (s.contrast == name), 'placebo_p'] = float((plc[col].abs() >= abs(act)).mean())
    s.to_csv(OUT / 'summary.csv', index=False, float_format='%.5g')
    loo = leave_one_out(w, CONTROLS)
    loo.to_csv(OUT / 'leave_one_event_out.csv', index=False, float_format='%.5g')
    # event listing
    ev = w[w.P0.fillna(0) != 0][['date', 'P0']].rename(columns={'P0': 'us_weighted_principal_nzd_bn'})
    ev.to_csv(OUT / 'events.csv', index=False, float_format='%.5g')
    # path figure: primary vs +-5
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    for lab, off, col in (('primary_h2', -0.08, 'C0'), ('width_h5', 0.08, 'C1')):
        c = pd.concat(coefs).query("spec == @lab and term.str.startswith('P')", engine='python')
        k = c.term.str[1:].astype(int)
        ax.errorbar(k + off, c.coef, yerr=[c.coef - c.ci95_lo, c.ci95_hi - c.coef], fmt='o', color=col, capsize=2,
                    label=lab)
    ax.axhline(0, color='0.5', lw=0.8)
    ax.set_xlabel('k (k > 0: principal settles in a later window)')
    ax.set_ylabel('% per NZ$bn US-weighted principal')
    ax.set_title('A7: principal coefficients by lead/lag')
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / 'principal_path.png', dpi=160)
    pd.set_option('display.width', 220)
    print(s.round(3).to_string())
    print('placebo sd', plc.S_total.std(), 'p', float((plc.S_total.abs() >= abs(prim.estimate)).mean()))
    print(loo.round(3).to_string())
    print(ev.to_string())


if __name__ == '__main__':
    main()
