#!/usr/bin/env python3
"""Attempt 3: state-dependent local projection of foreign-held debt pressure; see ATTEMPTS.md, A3.

Local files only. Writes (overwrites) output/attempts/03_local_projection/.
Example: python code/attempt3.py
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
from statsmodels.stats.multitest import multipletests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import attempt1r as A  # noqa: E402  (fixings, controls, read_fred)
import load as L  # noqa: E402
import run_regressions as rr  # noqa: E402
import timing as T  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / 'output' / 'attempts' / '03_local_projection'
HORIZONS = [0, 1, 3, 5]
PRIMARY_H = 1
SAMPLE = ('2015-08-03', '2025-02-07')
SCALE = 0.1  # report effects per 0.1 percentage point of outstanding
TERMS = ['ZI', 'ZIxS', 'ZP', 'ZPxS', 'S', 'dlnVIX_l', 'dPol_l', 'rBrent_l']


def month_end_key(dates: pd.Series) -> pd.Series:
    """Last month-end strictly before the calendar month of each date."""
    d = pd.DatetimeIndex(dates)
    return pd.Series((d + pd.offsets.MonthEnd(0)) - pd.offsets.MonthEnd(1), index=dates.index)


def ownership_share(kind: str, dates: pd.Series) -> pd.Series:
    if kind == 'nonresident':  # RBNZ D31, monthly, position-date valid
        d = L.d31().groupby('month_end')[['nonres_d31', 'private_d31']].sum()
        s = d.nonres_d31 / d.private_d31
        return month_end_key(dates).map(s)
    share = rr.read_csv(BASE / 'regression' / 'US_Share_of_New_Zealand_Debt.xlsx - Regression Series.csv',
                        ['us_share'], percentage_columns=('us_share',))
    return pd.merge_asof(pd.DataFrame({'date': dates.to_numpy()}), share, on='date', direction='backward')['us_share']


def pressure(share_kind: str) -> pd.DataFrame:
    """Per NZ calendar date: issuance and principal pressure in % of debt outstanding, with settlement instant."""
    f = rr.read_csv(BASE / 'regression' / 'nz_daily_flows.csv', rr.FLOW_COLS)
    for c in ('issuance', 'principal'):
        f[c] = f[[f'nom_{c}', f'iib_{c}']].sum(axis=1, min_count=2) * (-1 if c == 'issuance' else 1)
    out = L.onissue().groupby('month_end').total.sum()
    f['outstanding'] = month_end_key(f.date).map(out)
    f['share'] = ownership_share(share_kind, f.date).to_numpy()
    for c, z in (('issuance', 'ZI'), ('principal', 'ZP')):
        f[z] = 100 * f.share * f[c] / f.outstanding
    f['settle_utc'] = T.stamp(f.date, T.NZ, A.SETTLE_HOUR_NZ)
    return f


def build(share_kind: str = 'nonresident', start: str = SAMPLE[0]) -> pd.DataFrame:
    e, fix = A.fixings('h10')
    f = pressure(share_kind)
    f['j'] = T.window_index(pd.DatetimeIndex(f.settle_utc), fix)
    f = f[f.j >= 0]
    z = f.groupby('j')[['ZI', 'ZP']].apply(lambda g: g.sum(min_count=1).where(~g.isna().any()))
    w = pd.DataFrame({'date': e.index}).join(z.reindex(range(len(e))).reset_index(drop=True))
    lne = pd.Series(np.log(e.to_numpy()))
    for h in HORIZONS:
        w[f'y{h}'] = 100 * (lne.shift(-h) - lne.shift(1))
    w['y_pre'] = 100 * (lne.shift(1) - lne.shift(4))  # falsification: return before the window
    vix = A.read_fred('VIXCLS')
    win_start = fix.to_series().shift(1)
    win_start.iloc[0] = fix[0]
    lvl = T.level_at(np.log(vix), T.stamp(vix.index, T.NY, 16, 15), pd.DatetimeIndex(win_start))
    w['S'] = lvl
    c = A.controls(fix)[['dlnVIX', 'dPol', 'rBrent']].shift(1)
    w[['dlnVIX_l', 'dPol_l', 'rBrent_l']] = c.to_numpy()
    w = w[(w.date >= start) & (w.date <= SAMPLE[1])].reset_index(drop=True)
    w['S'] = (w.S - w.S.mean()) / w.S.std()
    w['ZIxS'], w['ZPxS'] = w.ZI * w.S, w.ZP * w.S
    return w


def fit(w: pd.DataFrame, y: str, lags: int, terms: list[str] = TERMS):
    d = w[['date', y, *terms]].replace([np.inf, -np.inf], np.nan).dropna()
    res = sm.OLS(d[y], sm.add_constant(d[terms])).fit(cov_type='HAC', cov_kwds={'maxlags': lags}, use_t=False)
    return res, d


def rows(res, spec: str, h) -> list[dict]:
    ci = res.conf_int()
    out = [{'spec': spec, 'h': h, 'term': t, 'coef': res.params[t], 'se': res.bse[t], 'ci_lo': ci.loc[t, 0],
            'ci_hi': ci.loc[t, 1], 'p': res.pvalues[t], 'n': int(res.nobs)} for t in res.params.index]
    for lab, wts in (('ZI+ZIxS (S=+1sd)', {'ZI': 1, 'ZIxS': 1}), ('ZP+ZPxS (S=+1sd)', {'ZP': 1, 'ZPxS': 1})):
        c = rr.contrast(res, wts, lab)
        out.append({'spec': spec, 'h': h, 'term': lab, 'coef': c['estimate'], 'se': c['se'], 'ci_lo': c['ci95_lower'],
                    'ci_hi': c['ci95_upper'], 'p': c['p_value'], 'n': int(res.nobs)})
    return out


def isolated(w: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    """Windows with no other issuance within +-k windows (isolated events and quiet windows)."""
    has = (w.ZI.fillna(0) > 0).astype(int)
    near = has.rolling(2 * k + 1, center=True, min_periods=1).sum() - has
    return w[near == 0]


def placebo(w: pd.DataFrame, n_draw: int = 300, seed: int = 3) -> pd.DataFrame:
    rng, out = np.random.default_rng(seed), []
    for m in rng.choice(np.r_[-250:-40, 41:251], n_draw, replace=False):
        p = w.copy()
        p['ZI'], p['ZP'] = w.ZI.shift(int(m)), w.ZP.shift(int(m))
        p['ZIxS'], p['ZPxS'] = p.ZI * p.S, p.ZP * p.S
        res, _ = fit(p, f'y{PRIMARY_H}', 10 + PRIMARY_H)
        out.append({'shift': int(m), 'bI': res.params['ZI'], 'dI': res.params['ZIxS'], 'z_dI': res.tvalues['ZIxS'],
                    'dP': res.params['ZPxS'], 'z_dP': res.tvalues['ZPxS']})
    return pd.DataFrame(out)


def leave_one_event_out(w: pd.DataFrame) -> pd.DataFrame:
    """Refit the primary horizon dropping +-5 windows around each principal event, one event at a time."""
    rows_ = []
    for i in np.flatnonzero(w.ZP.fillna(0) > 0):
        res, _ = fit(w.drop(index=range(max(0, i - 5), i + 6)), f'y{PRIMARY_H}', 10 + PRIMARY_H)
        rows_.append({'dropped_event': str(w.date[i].date()), 'dP': res.params['ZPxS'], 'z_dP': res.tvalues['ZPxS'],
                      'bP': res.params['ZP']})
    return pd.DataFrame(rows_)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    w = build()
    allrows = []
    for h in HORIZONS:
        res, d = fit(w, f'y{h}', 10 + h)
        allrows += rows(res, 'primary', h)
    res, d = fit(w, 'y_pre', 10)
    allrows += rows(res, 'pre_window_falsification', -3)
    ev = d[(d.ZI > 0)]
    stats = {'n_windows': len(d), 'n_issuance_windows': int((d.ZI > 0).sum()), 'n_principal_windows': int((d.ZP > 0).sum()),
             'ZI_nonzero_mean': ev.ZI.mean(), 'ZI_nonzero_sd': ev.ZI.std(), 'ZI_nonzero_max': ev.ZI.max(),
             'first': str(d.date.min().date()), 'last': str(d.date.max().date())}
    for lags in (5, 20):
        allrows += rows(fit(w, f'y{PRIMARY_H}', lags)[0], f'hac{lags}', PRIMARY_H)
    iso = isolated(w)
    stats['n_isolated_issuance_windows'] = int((iso.ZI > 0).sum())
    if stats['n_isolated_issuance_windows'] >= 30:
        allrows += rows(fit(iso, f'y{PRIMARY_H}', 10 + PRIMARY_H)[0], 'isolated_issuance', PRIMARY_H)
    wus = build('us', '2014-01-02')
    for h in HORIZONS:
        allrows += rows(fit(wus, f'y{h}', 10 + h)[0], 'us_share_2014+', h)
    co = pd.DataFrame(allrows)
    co.to_csv(OUT / 'coefficients.csv', index=False, float_format='%.6g')
    plc = placebo(w)
    plc.to_csv(OUT / 'placebo.csv', index=False, float_format='%.5g')
    loo = leave_one_event_out(w)
    loo.to_csv(OUT / 'leave_one_principal_event_out.csv', index=False, float_format='%.5g')
    prim = co[(co.spec == 'primary') & (co.term == 'ZIxS')].set_index('h')
    actual = prim.loc[PRIMARY_H]
    holm = multipletests(prim.p.to_numpy(), method='holm')[1]
    stats.update({'placebo_p_dI_h1': float((plc.dI.abs() >= abs(actual.coef)).mean()),
                  'placebo_p_dP_h1': float((plc.dP.abs() >= abs(co[(co.spec == 'primary') & (co.term == 'ZPxS') & (co.h == PRIMARY_H)].coef.iloc[0])).mean()),
                  'loo_dP_h1_range': (round(loo.dP.min() * SCALE, 4), round(loo.dP.max() * SCALE, 4)),
                  'holm_p_dI_by_h': dict(zip(HORIZONS, np.round(holm, 3))),
                  'pre_window_ZI_p': float(co[(co.spec == 'pre_window_falsification') & (co.term == 'ZI')].p.iloc[0]),
                  'pre_window_ZIxS_p': float(co[(co.spec == 'pre_window_falsification') & (co.term == 'ZIxS')].p.iloc[0])})
    pd.Series(stats).to_csv(OUT / 'summary.csv', header=['value'])
    # one figure: effect per 0.1 pp of outstanding, average state and S = +1 sd
    fig, ax = plt.subplots(figsize=(6.8, 4))
    for term, lab, dx in (('ZI', 'average state', -0.1), ('ZI+ZIxS (S=+1sd)', 'high stress (+1 sd VIX)', 0.1)):
        s = co[(co.spec == 'primary') & (co.term == term)].set_index('h')
        ax.errorbar(np.array(HORIZONS) + dx, s.coef * SCALE, yerr=[(s.coef - s.ci_lo) * SCALE, (s.ci_hi - s.coef) * SCALE],
                    fmt='o-', capsize=3, label=lab)
    ax.axhline(0, color='k', lw=.8)
    ax.set_xlabel('horizon h (sessions after the settlement window)')
    ax.set_ylabel('% return per 0.1 pp of outstanding')
    ax.set_title('A3: response to issuance pressure (95% HAC CI)')
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / 'lp_paths.png', dpi=160)
    pd.set_option('display.width', 220)
    print(pd.Series(stats))
    keep = ['ZI', 'ZIxS', 'ZP', 'ZPxS', 'S', 'ZI+ZIxS (S=+1sd)']
    t = co[co.term.isin(keep) & co.spec.isin(['primary', 'pre_window_falsification', 'hac5', 'hac20',
                                               'isolated_issuance', 'us_share_2014+'])].copy()
    for c in ('coef', 'se', 'ci_lo', 'ci_hi'):
        t[c] = t[c] * np.where(t.term.isin(['S']), 1, SCALE)
    print(t.round(4).to_string(index=False))


if __name__ == '__main__':
    main()
