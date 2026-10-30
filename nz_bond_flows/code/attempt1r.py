#!/usr/bin/env python3
"""Attempt 1 rerun (A1r): timestamped event windows and replacement controls; see ATTEMPTS.md.

Local files only. Writes (overwrites) output/attempts/01_aligned/.
Example: python code/attempt1r.py
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
import timing as T  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
PUB = BASE / 'raw' / 'public'
OUT = BASE / 'output' / 'attempts' / '01_aligned'
SETTLE_HOUR_NZ = 10   # assumed settlement time, NZ local (ATTEMPTS.md A1r)
B1_HOUR_NZ = 13       # inferred B1 observation time, NZ local; unverified
SAMPLE = ('2014-01-02', '2025-02-07')
A1_REF = {'b0': 0.1186, 'b1': 0.2923, 'sum': 0.4109, 'se': 0.4153, 'n': 2762}  # journal values of A1
PRIMARY = ['N0', 'N1', 'dlnVIX', 'dPol', 'rBrent']


def read_rbnz(pattern: str, column: str) -> pd.Series:
    """Stitch the two RBNZ files (1985-2017 and 2018-current) for one series id; header row 5 holds ids."""
    parts = []
    for f in sorted(PUB.glob(pattern)):
        d = pd.read_excel(f, sheet_name='Data', header=None)
        col = list(d.iloc[4]).index(column)
        s = pd.Series(pd.to_numeric(d.iloc[5:, col], errors='coerce').to_numpy(),
                      index=pd.to_datetime(d.iloc[5:, 0]))
        parts.append(s)
    return pd.concat(parts).loc[lambda s: ~s.index.duplicated()].sort_index().dropna()


def read_fred(sid: str) -> pd.Series:
    d = pd.read_csv(PUB / f'{sid}_fred.csv', parse_dates=['observation_date'], na_values='.')
    return d.set_index('observation_date').iloc[:, 0].dropna()


def fixings(source: str) -> tuple[pd.Series, pd.DatetimeIndex]:
    """USD-per-NZD series and the UTC instant of each fixing."""
    if source == 'h10':
        fx = rr.read_csv(BASE / 'regression' / 'FX.csv', [rr.FX_COL]).dropna(subset=[rr.FX_COL])
        e = pd.Series(1 / fx[rr.FX_COL].to_numpy(), index=fx.date)
        return e, T.stamp(e.index, T.NY, 12)
    e = read_rbnz('hb1-daily-*.xlsx', 'EXR.DS11.D06')  # NZD/USD, quoted per NZ$ = USD per NZD
    return e, T.stamp(e.index, T.NZ, B1_HOUR_NZ)


def controls(fix: pd.DatetimeIndex) -> pd.DataFrame:
    """Window changes of each control; stamps are the latest possible time of each observation."""
    nz2 = read_rbnz('hb2-daily-close-*.xlsx', 'INM.DS02.NZZC')
    ust2, vix, brent = read_fred('DGS2'), read_fred('VIXCLS'), read_fred('DCOILBRENTEU')
    chg = lambda s, tz, h, m=0: T.window_changes(s, T.stamp(s.index, tz, h, m), fix)
    out = pd.DataFrame({
        'dlnVIX': chg(np.log(vix), T.NY, 16, 15),
        'dPol': chg(nz2, T.NZ, 23, 59) - chg(ust2, T.NY, 16),
        'rBrent': 100 * chg(np.log(brent.where(brent > 0)), T.LON, 23, 59),
        'dT10Y2Y': chg(read_fred('T10Y2Y'), T.NY, 16),
        'dRealY10': chg(read_fred('DFII10'), T.NY, 16),
        'dUST2': chg(ust2, T.NY, 16),
    })
    out['dlnVIX'] *= 100
    return out


def settlements(share_lag_months: int = 0) -> pd.DataFrame:
    """Net US-weighted flow per NZ calendar date (NZ$ billion) with its assumed settlement instant."""
    f = rr.read_csv(BASE / 'regression' / 'nz_daily_flows.csv', rr.FLOW_COLS)
    for c in rr.COMPONENTS:
        f[c] = f[[f'nom_{c}', f'iib_{c}']].sum(axis=1, min_count=2) * (-1 if c == 'issuance' else 1)
    f['net'] = f.issuance - f.principal - f.coupon - f.buyback
    share = rr.read_csv(BASE / 'regression' / 'US_Share_of_New_Zealand_Debt.xlsx - Regression Series.csv',
                        ['us_share'], percentage_columns=('us_share',))
    key = f.date - pd.DateOffset(months=share_lag_months)  # lag = position date at least this much earlier
    f['us_share'] = pd.merge_asof(pd.DataFrame({'key': key}).reset_index(), share.rename(columns={'date': 'key'}),
                                  on='key', direction='backward').set_index('index')['us_share']
    f['N'] = f.net * f.us_share / 1000.0
    f['settle_utc'] = T.stamp(f.date, T.NZ, SETTLE_HOUR_NZ)
    return f


def window_frame(source: str = 'h10', share_lag_months: int = 0, shift_controls: bool = False) -> pd.DataFrame:
    e, fix = fixings(source)
    f = settlements(share_lag_months)
    f['j'] = T.window_index(pd.DatetimeIndex(f.settle_utc), fix)
    f = f[f.j >= 0]
    g = f.groupby('j')['N']
    n = g.sum(min_count=1).where(~g.apply(lambda x: x.isna().any()))  # no partial sums, as in the baseline
    w = pd.DataFrame({'date': e.index, 'r': 100 * np.log(e.to_numpy())})
    w['r'] = w.r.diff()
    w['N0'] = n.reindex(range(len(w))).to_numpy()
    w['N1'] = w.N0.shift(-1)
    c = controls(fix)
    w = pd.concat([w, c.shift(1) if shift_controls else c], axis=1)
    return w[(w.date >= SAMPLE[0]) & (w.date <= SAMPLE[1])].reset_index(drop=True)


def fit(w: pd.DataFrame, cols: list[str], lags: int = 10):
    d = w[['date', 'r', *cols]].replace([np.inf, -np.inf], np.nan).dropna()
    res = sm.OLS(d.r, sm.add_constant(d[cols])).fit(cov_type='HAC', cov_kwds={'maxlags': lags}, use_t=False)
    return res, d


def table(res, label: str) -> pd.DataFrame:
    ci = res.conf_int()
    t = pd.DataFrame({'spec': label, 'term': res.params.index, 'coef': res.params.values,
                      'hac_se': res.bse.values, 'ci95_lo': ci[0].values, 'ci95_hi': ci[1].values,
                      'p': res.pvalues.values, 'n': int(res.nobs)})
    c = rr.contrast(res, {'N0': 1, 'N1': 1}, 'b0+b1')
    t.loc[len(t)] = [label, 'b0+b1', c['estimate'], c['se'], c['ci95_lower'], c['ci95_upper'], c['p_value'],
                     int(res.nobs)]
    return t


def placebo(w: pd.DataFrame, n_draw: int = 300, seed: int = 1) -> pd.DataFrame:
    rng, rows = np.random.default_rng(seed), []
    for m in rng.choice(np.r_[-250:-40, 41:251], n_draw, replace=False):
        p = w.copy()
        p['N0'] = w.N0.shift(int(m))
        p['N1'] = p.N0.shift(-1)
        res, _ = fit(p, PRIMARY)
        c = rr.contrast(res, {'N0': 1, 'N1': 1}, 'placebo')
        rows.append({'shift': int(m), 'b0_plus_b1': c['estimate'], 'z': c['statistic']})
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    w = window_frame()
    old = w.assign(vix_l2=old_vix_l2(w))
    specs = [('primary', w, PRIMARY, 10), ('hac5', w, PRIMARY, 5), ('hac20', w, PRIMARY, 20),
             ('old_vix_l2_only_new_alignment', old, ['N0', 'N1', 'vix_l2'], 10),
             ('sub_T10Y2Y_for_Brent', w, ['N0', 'N1', 'dlnVIX', 'dPol', 'dT10Y2Y'], 10),
             ('sub_RealY10_for_Brent', w, ['N0', 'N1', 'dlnVIX', 'dPol', 'dRealY10'], 10),
             ('share_lag_6m', window_frame(share_lag_months=6), PRIMARY, 10),
             ('controls_pre_window', window_frame(shift_controls=True), PRIMARY, 10),
             ('b1_window', window_frame('b1'), PRIMARY, 10)]
    tabs, fits = [], {}
    for label, frame, cols, lags in specs:
        fits[label], _ = fit(frame, cols, lags)
        tabs.append(table(fits[label], label))
    pd.concat(tabs).to_csv(OUT / 'coefficients.csv', index=False, float_format='%.6g')
    res, d = fits['primary'], fit(w, PRIMARY)[1]
    c = rr.contrast(res, {'N0': 1, 'N1': 1}, 'b0+b1')
    plc = placebo(w)
    plc.to_csv(OUT / 'placebo.csv', index=False, float_format='%.5g')
    summary = {'b0_plus_b1': c['estimate'], 'se': c['se'], 'ci95_lo': c['ci95_lower'], 'ci95_hi': c['ci95_upper'],
               'p_hac': c['p_value'], 'placebo_p': float((plc.b0_plus_b1.abs() >= abs(c['estimate'])).mean()),
               'placebo_sd': plc.b0_plus_b1.std(), 'mde_80pct': 2.8 * c['se'], 'n': int(res.nobs),
               'n_nonzero_flow_windows': int((d.N0 != 0).sum()), 'first': str(d.date.min().date()),
               'last': str(d.date.max().date()), 'adj_r2': res.rsquared_adj}
    pd.DataFrame([summary]).to_csv(OUT / 'summary.csv', index=False, float_format='%.5g')
    pd.DataFrame([{'version': 'A1 (calendar-date join, old controls)', 'b0': A1_REF['b0'], 'b1': A1_REF['b1'],
                   'sum': A1_REF['sum'], 'se': A1_REF['se'], 'n': A1_REF['n']},
                  {'version': 'A1r primary', 'b0': res.params['N0'], 'b1': res.params['N1'],
                   'sum': c['estimate'], 'se': c['se'], 'n': int(res.nobs)}]).to_csv(
        OUT / 'side_by_side_vs_a1.csv', index=False, float_format='%.5g')
    w[['date', 'r', 'N0', 'N1', *PRIMARY[2:], 'dT10Y2Y', 'dRealY10']].to_csv(
        OUT / 'aligned_dataset.csv', index=False, float_format='%.8g')
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.hist(plc.b0_plus_b1, bins=30, color='0.7')
    ax.axvline(c['estimate'], color='C3', label=f"actual {c['estimate']:.3f}")
    ax.set_xlabel('b0+b1, % return per NZ$bn US-weighted net issuance')
    ax.set_title('A1r: circular-shift placebo distribution')
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / 'placebo_hist.png', dpi=160)
    pd.set_option('display.width', 200)
    print(pd.read_csv(OUT / 'summary.csv').T)
    print(pd.read_csv(OUT / 'coefficients.csv').query("term in ['N0','N1','b0+b1']").to_string())
    print(res.params.round(4).to_dict(), res.pvalues.round(3).to_dict())


def old_vix_l2(w: pd.DataFrame) -> pd.Series:
    """A1's control: VIX level two sessions back (exact-date join), kept only for the old-controls comparison."""
    vix = rr.read_csv(BASE / 'regression' / 'Controls - Regression Control Panel.csv', ['vix']).set_index('date').vix
    return pd.Series(w.date.map(vix).to_numpy()).shift(2)


if __name__ == '__main__':
    main()
