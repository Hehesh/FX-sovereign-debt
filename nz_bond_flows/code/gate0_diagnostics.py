#!/usr/bin/env python3
"""Gate 0 diagnostics and clock audit for the unchanged baseline regression.

Reads only local files; imports the baseline functions without modifying them.
Writes to output/attempts/00_gate0_baseline/ and output/attempts/00_clock_audit/.
Example: python code/gate0_diagnostics.py
"""
from __future__ import annotations

import hashlib
import logging
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from statsmodels.stats.outliers_influence import variance_inflation_factor

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_regressions as rr  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
G0 = BASE / 'output' / 'attempts' / '00_gate0_baseline'
CA = BASE / 'output' / 'attempts' / '00_clock_audit'
OUTCOME = 'log_return_pct'
SCALE = 1000.0  # NZ$ million -> NZ$ billion
MDE_MULT = 1.96 + 0.84  # 5% two-sided test, 80% power


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_inputs() -> None:
    files = sorted((BASE / 'regression').glob('*')) + sorted((BASE / 'raw').glob('*.*')) \
        + sorted((BASE / 'raw' / 'public').glob('*'))
    rows = [{'path': str(f.relative_to(BASE)), 'sha256': sha256(f)} for f in files if f.is_file()]
    pd.DataFrame(rows).to_csv(G0 / 'input_hashes.csv', index=False)


def coefficient_tables(raw: pd.DataFrame) -> dict:
    results, rows, diag = {}, [], []
    for target in ('delta_e', OUTCOME):
        for name in ('Net flows', 'Disaggregated'):
            res, frame, cond = rr.fit(raw, name, target, 10)
            results[(name, target)] = (res, frame)
            ci = res.conf_int()
            rows.append(pd.DataFrame({'model': name, 'outcome': target, 'term': res.params.index,
                                      'coef': res.params.values, 'hac_se': res.bse.values,
                                      'ci95_lo': ci[0].values, 'ci95_hi': ci[1].values,
                                      'p': res.pvalues.values}))
            d = rr.regression_diagnostics(res, 10)
            diag += [{'model': name, 'outcome': target, 'test': k, 'stat': v[0], 'p': v[1]}
                     for k, v in d.items()]
    pd.concat(rows).to_csv(G0 / 'coefficients.csv', index=False, float_format='%.6g')
    pd.DataFrame(diag).to_csv(G0 / 'residual_diagnostics.csv', index=False, float_format='%.6g')
    return results


def sample_accounting(raw: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """Where the 6,294 FX days go before the complete-case sample of the main model."""
    cols = rr.columns_for_model('Disaggregated')
    ok = raw[OUTCOME].notna()
    steps = [('FX days', len(raw)), ('with return', int(ok.sum()))]
    for label, mask in [('us_share available', raw.us_share.notna()),
                        ('controls complete', raw[rr.REQUIRED_CONTROLS].notna().all(axis=1)),
                        ('all lead/lag flow regressors', raw[cols].notna().all(axis=1))]:
        ok &= mask
        steps.append((f'+ {label}', int(ok.sum())))
    steps.append(('estimation sample (M2 log return)', len(frame)))
    return pd.DataFrame(steps, columns=['step', 'n'])


def event_overlap(raw: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """Event counts and how much the +-5 session windows overlap, within the estimation sample."""
    pos = raw.reset_index(drop=True)
    in_sample = pos.date.isin(frame.date)
    rows = []
    for label, series in [('principal>0', pos.us_principal), ('issuance>0', pos.us_issuance),
                          ('coupon>0', pos.us_coupon), ('buyback>0', pos.us_buyback)]:
        idx = np.flatnonzero((series.fillna(0) > 0) & in_sample)
        gaps = np.diff(idx)
        covered = np.zeros(len(pos), bool)
        for i in idx:
            covered[max(0, i - rr.HORIZON):i + rr.HORIZON + 1] = True
        rows.append({'event': label, 'n_events': len(idx),
                     'median_gap_sessions': float(np.median(gaps)) if len(gaps) else np.nan,
                     'share_gaps_le_10': float((gaps <= 2 * rr.HORIZON).mean()) if len(gaps) else np.nan,
                     'sessions_in_any_window': int((covered & in_sample.to_numpy()).sum())})
    return pd.DataFrame(rows)


def effect_sizes(res) -> pd.DataFrame:
    """Sum of lead (H1) and lag (H3) principal coefficients in % per NZ$bn of US-weighted principal."""
    rows = []
    for label, ks in [('sum k=+1..+5 (pre-event, H1)', range(1, 6)), ('k=0 (event day)', [0]),
                      ('sum k=-5..-1 (post-event, H3)', range(-5, 0))]:
        c = rr.contrast(res, {f'us_principal_k{k:+d}': 1.0 for k in ks}, label)
        rows.append({'quantity': label, 'est_pct_per_NZbn': c['estimate'] * SCALE,
                     'se': c['se'] * SCALE, 'ci95_lo': c['ci95_lower'] * SCALE,
                     'ci95_hi': c['ci95_upper'] * SCALE, 'mde_80pct_power': MDE_MULT * c['se'] * SCALE})
    return pd.DataFrame(rows)


def multicollinearity(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    x = np.column_stack([np.ones(len(frame)), frame[cols].to_numpy()])
    vif = [variance_inflation_factor(x, i + 1) for i in range(len(cols))]
    return pd.DataFrame({'term': cols, 'vif': vif}).sort_values('vif', ascending=False)


def placebo_h1(raw: pd.DataFrame, n_draw: int = 300, seed: int = 0) -> pd.DataFrame:
    """Circularly shift the US principal series by m sessions (|m| >= 40) and refit M2.
    Gives the null distribution of the H1 pre-event sum under arbitrary event dates."""
    rng = np.random.default_rng(seed)
    out = []
    for m in rng.choice(np.r_[-250:-40, 41:251], n_draw, replace=False):
        r = raw.copy()
        r['us_principal'] = raw['us_principal'].shift(int(m))
        for k in range(-rr.HORIZON, rr.HORIZON + 1):
            r[f'us_principal_k{k:+d}'] = r['us_principal'].shift(-k)
        try:
            res, _, _ = rr.fit(r, 'Disaggregated', OUTCOME, 10)
        except ValueError:
            continue
        c = rr.contrast(res, {f'us_principal_k{k:+d}': 1.0 for k in range(1, 6)}, 'placebo')
        out.append({'shift': int(m), 'sum_pre': c['estimate'] * SCALE, 'z': c['statistic']})
    return pd.DataFrame(out)


def alignment_table() -> pd.DataFrame:
    """Auckland-local extent of the H.10 return dated D, per DST regime, 2014-2025 weekdays."""
    akl, ny, lon = ZoneInfo('Pacific/Auckland'), ZoneInfo('America/New_York'), ZoneInfo('Europe/London')
    rows = []
    for d in pd.bdate_range('2014-01-02', '2025-02-07'):
        noon_prev = pd.Timestamp(d.date() - pd.Timedelta(days=1), tz=ny) + pd.Timedelta(hours=12)
        noon = pd.Timestamp(d.date(), tz=ny) + pd.Timedelta(hours=12)
        a_day = pd.Timestamp(d.date(), tz=akl)
        rows.append({
            'example_date': d.date(), 'nz_utc_offset_h': a_day.utcoffset().total_seconds() / 3600,
            'ny_utc_offset_h': noon.utcoffset().total_seconds() / 3600,
            'uk_utc_offset_h': pd.Timestamp(d.date(), tz=lon).utcoffset().total_seconds() / 3600,
            'window_start_akl': noon_prev.tz_convert(akl).strftime('%a %H:%M'),
            'window_end_akl': noon.tz_convert(akl).strftime('%a %H:%M'),
            'start_hour_akl_on_D': noon_prev.tz_convert(akl).hour + noon_prev.tz_convert(akl).minute / 60
            + 24 * (noon_prev.tz_convert(akl).date() - d.date()).days,
            'london_4pm_in_akl': (pd.Timestamp(d.date(), tz=lon) + pd.Timedelta(hours=16)).tz_convert(akl)
            .strftime('%H:%M'),
            'akl_0900_in_ny': (a_day + pd.Timedelta(hours=9)).tz_convert(ny).strftime('%a %H:%M'),
            'akl_1700_in_ny': (a_day + pd.Timedelta(hours=17)).tz_convert(ny).strftime('%a %H:%M'),
            'vix_close_1615ET_in_akl': (pd.Timestamp(d.date(), tz=ny) + pd.Timedelta(hours=16, minutes=15))
            .tz_convert(akl).strftime('%a %H:%M'),
        })
    t = pd.DataFrame(rows)
    keys = ['nz_utc_offset_h', 'ny_utc_offset_h', 'uk_utc_offset_h', 'window_start_akl', 'window_end_akl',
            'london_4pm_in_akl', 'akl_0900_in_ny', 'akl_1700_in_ny', 'vix_close_1615ET_in_akl']
    return (t.groupby(keys, as_index=False)
            .agg(n_weekdays=('example_date', 'size'), example_date=('example_date', 'first')))


def mapping_summary(audit_path: Path) -> pd.DataFrame:
    a = pd.read_csv(audit_path, parse_dates=['original_flow_date', 'assigned_fx_date'])
    flow_cols = [c for c in rr.FLOW_COLS if c in a.columns]
    active = a[flow_cols].fillna(0).abs().sum(axis=1) > 0
    rows = [('flow rows (all calendar days)', len(a)), ('rows with any nonzero flow', int(active.sum())),
            ('nonzero rows on non-NZ business day', int((active & ~a.nz_business_day).sum())),
            ('nonzero rows moved to later FX date', int((active & a.moved).sum())),
            ('  of which NZ business day (US/FX-calendar roll)', int((active & a.moved & a.nz_business_day).sum())),
            ('nonzero rows dropped (used = False)', int((active & ~a.used).sum()))]
    gap = (a.assigned_fx_date - a.original_flow_date).dt.days[active & a.moved]
    rows.append(('median roll length, calendar days (nonzero moved rows)', float(gap.median()) if len(gap) else np.nan))
    return pd.DataFrame(rows, columns=['item', 'value'])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    G0.mkdir(parents=True, exist_ok=True)
    CA.mkdir(parents=True, exist_ok=True)
    hash_inputs()
    with tempfile.TemporaryDirectory() as tmp:  # construct_data writes its panel; the baseline copy is in output/intermediate
        (Path(tmp) / 'intermediate').mkdir()
        raw, _ = rr.construct_data(BASE, Path(tmp), 'next-fx-day', 'missing')
    results = coefficient_tables(raw)
    res, frame = results[('Disaggregated', OUTCOME)]
    sample_accounting(raw, frame).to_csv(G0 / 'sample_accounting.csv', index=False)
    event_overlap(raw, frame).to_csv(G0 / 'event_overlap.csv', index=False)
    effect_sizes(res).to_csv(G0 / 'effect_sizes_m2_logreturn.csv', index=False, float_format='%.5g')
    multicollinearity(frame, rr.columns_for_model('Disaggregated')).to_csv(G0 / 'vif_m2.csv', index=False)
    plc = placebo_h1(raw)
    plc.to_csv(G0 / 'placebo_h1.csv', index=False, float_format='%.5g')
    actual = rr.contrast(res, {f'us_principal_k{k:+d}': 1.0 for k in range(1, 6)}, 'H1')
    logging.info('H1 sum z=%.3f; placebo |z| share >= actual: %.3f (n=%d)', actual['statistic'],
                 (plc.z.abs() >= abs(actual['statistic'])).mean(), len(plc))
    alignment_table().to_csv(CA / 'alignment_table.csv', index=False)
    mapping_summary(BASE / 'output' / 'intermediate' / 'flow_date_mapping_audit.csv').to_csv(
        CA / 'flow_mapping_summary.csv', index=False)
    r = raw.dropna(subset=[OUTCOME])
    acf = [r[OUTCOME].autocorr(k) for k in range(1, 6)]
    pd.DataFrame({'lag': range(1, 6), 'autocorr_logret': acf}).to_csv(G0 / 'return_autocorr.csv', index=False)
    logging.info('Done. Outputs in %s and %s', G0, CA)


if __name__ == '__main__':
    main()
