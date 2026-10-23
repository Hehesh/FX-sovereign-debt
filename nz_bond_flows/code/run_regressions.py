#!/usr/bin/env python3
"""NZD/USD sovereign cash-flow regressions; run from basedir/code/.

Dependencies: pandas, numpy, scipy, statsmodels, matplotlib, and a system `pdflatex`.
Example: python run_regressions.py
Optional: --weekend-policy drop --missing-flow zero --hac-lags 10
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm
import statsmodels.api as sm
from statsmodels.stats.diagnostic import (acorr_breusch_godfrey, acorr_ljungbox,
                                           het_breuschpagan, het_white)
from statsmodels.stats.stattools import durbin_watson, jarque_bera

FLOW_COLS = [f'{prefix}_{component}' for prefix in ('nom', 'iib')
             for component in ('issuance', 'principal', 'coupon', 'buyback')]
COMPONENTS = ('issuance', 'principal', 'coupon', 'buyback')
REQUIRED_CONTROLS = ['vix', 'treasury_swap_merged', 'us_release']
FX_COL = 'dexnzus'  # Supplied FX.csv stores NZD per USD, despite the FRED-style name.
HORIZON = 5


def read_csv(path: Path, required: list[str], *,
             percentage_columns: tuple[str, ...] = ()) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f'Missing input file: {path}')
    df = pd.read_csv(path, na_values=['.', 'NA', 'N/A', 'null', ''])
    df.columns = df.columns.str.strip()
    absent = sorted(set(['date', *required]) - set(df.columns))
    if absent:
        raise ValueError(f'{path.name} is missing columns: {absent}')
    df['date'] = pd.to_datetime(df['date'], errors='raise').dt.normalize()
    if df['date'].isna().any() or df['date'].duplicated().any():
        raise ValueError(f'{path.name}: null or duplicate dates in source (must resolve before merging)')
    for c in required:
        source = df[c]
        if c in percentage_columns:
            text = source.astype('string').str.strip()
            percent = text.str.endswith('%', na=False)
            numeric = pd.to_numeric(text.str.removesuffix('%').str.strip(), errors='coerce').astype(float)
            numeric = numeric.where(~percent, numeric / 100)
        else:
            numeric = pd.to_numeric(source, errors='coerce')
        invalid = source.notna() & (numeric.isna() | numeric.isin([np.inf, -np.inf]))
        if invalid.any():
            examples = source.loc[invalid].head(3).tolist()
            raise ValueError(f'{path.name}: invalid numeric values in {c}: {examples}')
        df[c] = numeric.astype(float)
    return df.sort_values('date').reset_index(drop=True)


def save_csv(df: pd.DataFrame, stem: Path, index: bool = False) -> None:
    """Save an internal data product without creating presentation clutter."""
    df.to_csv(stem.with_suffix('.csv'), index=index, float_format='%.9g')


def latex_escape(value: object) -> str:
    text = str(value).replace('–', '--').replace('—', '---').replace('×', r'$\times$')
    replacements = {
        '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_',
        '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}',
    }
    return ''.join(replacements.get(char, char) for char in text)


def compile_latex(body: list[str], path: Path, title: str, *, landscape: bool = False) -> None:
    """Wrap body lines in a standalone article and compile it with pdflatex."""
    options = ('landscape,' if landscape else '') + 'margin=0.7in'
    lines = [
        r'\documentclass[10pt]{article}',
        rf'\usepackage[{options}]{{geometry}}',
        r'\usepackage[T1]{fontenc}',
        r'\usepackage{lmodern}',
        r'\usepackage{amsmath}',
        r'\usepackage{array}',
        r'\usepackage{longtable}',
        r'\usepackage{booktabs}',
        r'\setlength{\parindent}{0pt}',
        r'\renewcommand{\arraystretch}{1.12}',
        r'\begin{document}',
        r'\begin{center}\large\textbf{' + latex_escape(title) + r'}\end{center}',
        *body,
        r'\end{document}', '',
    ]
    path.write_text('\n'.join(lines), encoding='utf-8')
    try:
        subprocess.run([
            'pdflatex', '-interaction=nonstopmode', '-halt-on-error',
            '-output-directory', str(path.parent), str(path),
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError('pdflatex is required to render the report PDFs') from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f'Could not render {path.name}:\n{exc.stdout[-3000:]}') from exc
    for suffix in ('.aux', '.log', '.fls', '.fdb_latexmk', '.synctex.gz'):
        path.with_suffix(suffix).unlink(missing_ok=True)


def choose_format(values) -> tuple[str, int]:
    """One notation for a block of numbers so decimal points line up (fixed vs. scientific)."""
    mags = [abs(float(v)) for v in values if pd.notna(v) and np.isfinite(v) and v != 0]
    if not mags:
        return 'fixed', 3
    if min(mags) < 1e-3 or max(mags) >= 1e5:
        return 'sci', 3
    return 'fixed', int(np.clip(3 - np.floor(np.log10(min(mags))), 2, 6))


def tex_num(x: object, fmt: tuple[str, int]) -> str:
    """Math-mode number with a phantom minus so signed and unsigned values stay aligned."""
    if x is None or pd.isna(x) or not np.isfinite(x):
        return ''
    kind, dec = fmt
    pad = '' if x < 0 else r'\phantom{-}'
    if x == 0:
        return rf'${pad}0$'
    if kind == 'sci':
        mantissa, exp = f'{x:.{dec}e}'.split('e')
        return rf'${mantissa if x < 0 else pad + mantissa}\!\times\!10^{{{int(exp)}}}$'
    return rf'${pad}{abs(x):.{dec}f}$' if x >= 0 else rf'${x:.{dec}f}$'


def tex_p(p: object) -> str:
    if p is None or pd.isna(p):
        return ''
    return r'$<\!0.001$' if p < .001 else rf'${p:.3f}$'


def tex_stars(p: object) -> str:
    if p is None or pd.isna(p):
        return ''
    return '***' if p < .01 else ('**' if p < .05 else ('*' if p < .1 else ''))


STARS_NOTE = r'{\footnotesize $^{*}\,p<0.10,\;^{**}\,p<0.05,\;^{***}\,p<0.01$ (two-sided where applicable).}'


def clear_report_outputs(out: Path) -> None:
    """Remove prior presentation outputs so each run has exactly five reports."""
    for folder in (out / 'tables', out / 'hypothesis_tests'):
        folder.mkdir(parents=True, exist_ok=True)
        for path in folder.iterdir():
            if path.is_file() and (path.suffix in {'.csv', '.html', '.tex', '.pdf', '.png',
                                                   '.aux', '.log', '.fls', '.fdb_latexmk'}
                                   or path.name.endswith('.synctex.gz')
                                   or path.name == 'table_notes.txt'):
                path.unlink()


def clear_latex_auxiliary(out: Path) -> None:
    for folder in (out / 'tables', out / 'hypothesis_tests'):
        for path in folder.iterdir():
            if path.is_file() and (path.suffix in {'.aux', '.log', '.fls', '.fdb_latexmk'}
                                   or path.name.endswith('.synctex.gz')):
                path.unlink()


def move_flows_to_fx_dates(flows: pd.DataFrame, fx_dates: pd.DatetimeIndex,
                           policy: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Next FX date mapping applies to ALL off-calendar records, not just weekends.
    No flows before the first or after the last FX day are admitted.
    """
    record = flows.copy().rename(columns={'date': 'original_flow_date'})
    pos = fx_dates.searchsorted(record['original_flow_date'].to_numpy(), side='left')
    valid = ((pos < len(fx_dates))
             & record['original_flow_date'].ge(fx_dates[0]).to_numpy())
    assigned = pd.Series(pd.NaT, index=record.index, dtype='datetime64[ns]')
    assigned.loc[valid] = fx_dates.take(pos[valid]).to_numpy()
    record['assigned_fx_date'] = assigned
    record['moved'] = record['original_flow_date'].ne(record['assigned_fx_date'])
    if policy == 'drop':
        record['used'] = valid & (~record['moved'])
    else:
        record['used'] = valid
    logging.info('Off-calendar flow rows: %s; dropped rows: %s',
                 int(record['moved'].sum()), int((~record['used']).sum()))
    selected = record.loc[record['used']].copy()
    if selected[FLOW_COLS].isna().any().any():
        logging.warning('Incomplete flow components on %s source rows; aggregated totals remain NA where incomplete.',
                        int(selected[FLOW_COLS].isna().any(axis=1).sum()))
    # min_count ensures an entirely missing component is not zero by default.
    agg = selected.groupby('assigned_fx_date')[FLOW_COLS].sum(min_count=1)
    # If multiple source days mapped to one FX day, prevent partial summation.
    incomplete = selected.groupby('assigned_fx_date')[FLOW_COLS].apply(lambda g: g.isna().any())
    agg = agg.mask(incomplete)
    agg.index.name = 'date'
    return agg.reset_index(), record


def construct_data(base: Path, out: Path, weekend_policy: str,
                   missing_flow: str, fx_quote: str = 'nzd-per-usd') -> tuple[pd.DataFrame, pd.DataFrame]:
    datadir = base / 'regression'
    fx = read_csv(datadir / 'FX.csv', [FX_COL])
    fx = fx.dropna(subset=[FX_COL]).copy()
    if fx.empty or (fx[FX_COL] <= 0).any():
        raise ValueError('FX dataset has no usable positive NZD/USD observations')
    fx_dates = pd.DatetimeIndex(fx['date'])
    flow = read_csv(datadir / 'nz_daily_flows.csv', FLOW_COLS)
    controls = read_csv(datadir / 'Controls - Regression Control Panel.csv', REQUIRED_CONTROLS)
    share = read_csv(datadir / 'US_Share_of_New_Zealand_Debt.xlsx - Regression Series.csv',
                     ['us_share'], percentage_columns=('us_share',))
    if share['us_share'].notna().sum() == 0:
        raise ValueError('us_share has no usable observations')
    if share['us_share'].dropna().gt(1).any() or share['us_share'].dropna().lt(0).any():
        raise ValueError('us_share must be on a 0–1 scale or explicitly marked as a percentage')

    # build.py/write.py export government-to-investor cash flows: issuance is
    # negative; repayments are positive. Keep source columns intact and convert
    # issuance to a positive magnitude below for the model's sign convention.
    for c in FLOW_COLS:
        invalid = flow[c].gt(0) if c.endswith('_issuance') else flow[c].lt(0)
        if invalid.any():
            raise ValueError(f'{c}: expected negative/zero issuance and positive/zero repayments '
                             'from the daily-flow builder')

    mapped, audit = move_flows_to_fx_dates(flow, fx_dates, weekend_policy)
    audit.to_csv(out / 'intermediate' / 'flow_date_mapping_audit.csv', index=False)
    raw = fx[['date', FX_COL]].merge(mapped, on='date', how='left', indicator='_flow_match')
    raw['flow_observed'] = raw['_flow_match'].eq('both')
    raw = raw.drop(columns=['_flow_match'])
    if missing_flow == 'zero':
        logging.warning('ASSUMPTION: absent flow dates are zero, not missing. Review flow_date_mapping_audit.csv.')
        raw.loc[~raw['flow_observed'], FLOW_COLS] = 0.0
    raw = raw.merge(controls[['date', *REQUIRED_CONTROLS]], on='date', how='left', validate='one_to_one')
    # Shares are point-in-time values. Only use observations at or before each FX date.
    raw = pd.merge_asof(raw.sort_values('date'), share[['date', 'us_share']].sort_values('date'),
                        on='date', direction='backward')
    if fx_quote not in ('nzd-per-usd', 'usd-per-nzd'):
        raise ValueError(f'Unknown FX input quote: {fx_quote}')
    raw['e'] = 1 / raw[FX_COL] if fx_quote == 'nzd-per-usd' else raw[FX_COL]
    raw['delta_e'] = raw['e'].diff()
    raw['log_return_pct'] = 100 * np.log(raw['e']).diff()
    for component in COMPONENTS:
        cols = [f'nom_{component}', f'iib_{component}']
        raw[component] = raw[cols].sum(axis=1, min_count=2)
        if component == 'issuance':
            raw[component] = -raw[component]
        raw[f'us_{component}'] = raw[component] * raw['us_share']
    raw['net_flow'] = raw['issuance'] - raw['principal'] - raw['coupon'] - raw['buyback']
    raw['us_net_flow'] = raw['us_share'] * raw['net_flow']
    # Model convention: issuances and repayments are positive magnitudes.
    # k>0 => today's return regressed against a future event (PRE-event response).
    for family in ('us_net_flow', 'us_issuance', 'us_principal'):
        for k in range(-HORIZON, HORIZON + 1):
            raw[f'{family}_k{k:+d}'] = raw[family].shift(-k)
    raw.to_csv(out / 'intermediate' / 'merged_constructed_panel.csv', index=False,
               float_format='%.12g')
    return raw, audit


def columns_for_model(name: str) -> list[str]:
    if name == 'Net flows':
        return [f'us_net_flow_k{k:+d}' for k in range(-HORIZON, HORIZON + 1)] + REQUIRED_CONTROLS
    return ([f'us_issuance_k{k:+d}' for k in range(-HORIZON, HORIZON + 1)]
            + [f'us_principal_k{k:+d}' for k in range(-HORIZON, HORIZON + 1)]
            + ['us_coupon', 'us_buyback'] + REQUIRED_CONTROLS)


def fit(raw: pd.DataFrame, name: str, outcome: str, hac_lags: int):
    cols = columns_for_model(name)
    frame = raw[['date', outcome, *cols]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < len(cols) + 2:
        raise ValueError(f'{name} / {outcome}: only {len(frame)} complete observations for '
                         f'{len(cols)} regressors. Inspect intermediate panel and missingness. '
                         'Try --missing-flow zero ONLY if missing input rows really mean no flows.')
    X = sm.add_constant(frame[cols], has_constant='add')
    result = sm.OLS(frame[outcome], X).fit(cov_type='HAC', cov_kwds={'maxlags': hac_lags},
                                          use_t=False)
    cond = float(np.linalg.cond(X.to_numpy()))
    if not np.isfinite(cond) or cond > 1e10:
        logging.warning('%s %s: ill-conditioned regressors (condition number %.3g)', name, outcome, cond)
    return result, frame, cond


def regression_diagnostics(result, hac_lags: int) -> dict[str, object]:
    """Standard residual diagnostics reported alongside each regression."""
    resid, exog = result.resid, result.model.exog
    bp_lm, bp_lm_p, bp_f, bp_f_p = het_breuschpagan(resid, exog)
    try:
        white_lm, white_lm_p, white_f, white_f_p = het_white(resid, exog)
    except ValueError:
        white_lm = white_lm_p = white_f = white_f_p = np.nan
    bg_lm, bg_lm_p, bg_f, bg_f_p = acorr_breusch_godfrey(result, nlags=hac_lags)
    lb = acorr_ljungbox(resid, lags=[hac_lags], return_df=True).iloc[0]
    jb, jb_p, skew, kurt = jarque_bera(resid)
    return {
        'Breusch–Pagan LM (heteroskedasticity)': (bp_lm, bp_lm_p),
        'White LM (heteroskedasticity)': (white_lm, white_lm_p),
        f'Breusch–Godfrey LM ({hac_lags} lags; autocorrelation)': (bg_lm, bg_lm_p),
        f'Ljung–Box Q ({hac_lags} lags; autocorrelation)': (float(lb['lb_stat']), float(lb['lb_pvalue'])),
        'Jarque–Bera (normality)': (jb, jb_p),
        'Durbin–Watson': (durbin_watson(resid), np.nan),
    }


def contrast(result, weights: dict[str, float], name: str, alternative: str = 'two-sided') -> dict:
    """Linear HAC robust Wald / normal tests of L'beta=0.
    Two-sided: Wald chi-square(1); one-sided: signed normal z-test.
    """
    cols = list(result.params.index)
    L = np.zeros(len(cols))
    for key, value in weights.items():
        if key not in cols:
            raise ValueError(f'Unknown term in {name}: {key}')
        L[cols.index(key)] = value
    estimate = float(L @ result.params.to_numpy())
    variance = float(L @ result.cov_params().to_numpy() @ L)
    se = float(np.sqrt(max(variance, 0)))
    z = estimate / se if se > 0 else np.nan
    if alternative == 'greater':
        p = norm.sf(z)
    elif alternative == 'less':
        p = norm.cdf(z)
    else:
        p = 2 * norm.sf(abs(z))
    return {'test': name, 'type': 'linear contrast (HAC)', 'null': 'L beta = 0 (boundary for one-sided)',
            'alternative': alternative, 'estimate': estimate, 'se': se, 'statistic': z,
            'distribution': 'standard normal z', 'df': np.nan, 'p_value': p,
            'ci95_lower': estimate - 1.96 * se, 'ci95_upper': estimate + 1.96 * se}


def joint_wald(result, keys: list[str], name: str) -> dict:
    idx = list(result.params.index)
    R = np.zeros((len(keys), len(idx)))
    for j, key in enumerate(keys):
        R[j, idx.index(key)] = 1.
    test = result.wald_test(R, scalar=True)
    return {'test': name, 'type': 'joint Wald (HAC)', 'null': 'All listed coefficients = 0',
            'alternative': 'at least one nonzero', 'estimate': np.nan, 'se': np.nan,
            'statistic': float(test.statistic), 'distribution': 'chi-square', 'df': len(keys),
            'p_value': float(test.pvalue), 'ci95_lower': np.nan, 'ci95_upper': np.nan}


def hypothesis_tests(result) -> pd.DataFrame:
    pre = [f'us_principal_k{k:+d}' for k in range(1, HORIZON + 1)]
    post = [f'us_principal_k{k:+d}' for k in range(-HORIZON, 0)]
    pre_w = dict.fromkeys(pre, 1.0)
    post_w = dict.fromkeys(post, 1.0)
    rows = [
        joint_wald(result, pre, 'H1: pre-event joint zero'),
        contrast(result, pre_w, 'H1: cumulative pre-event appreciation', 'greater'),
        contrast(result, {'us_issuance_k+0': 1, 'us_principal_k+0': 1},
                 'H2: event-day equal/opposite effect', 'two-sided'),
        contrast(result, {**{f'us_issuance_k{k:+d}': 1 for k in range(-5, 6)},
                          **{f'us_principal_k{k:+d}': 1 for k in range(-5, 6)}},
                 'H2: full-window equal/opposite effect', 'two-sided'),
        joint_wald(result, post, 'H3: post-event joint zero'),
        contrast(result, post_w, 'H3: cumulative post-event depreciation', 'less'),
        contrast(result, {**pre_w, **post_w}, 'H3: complete pre/post offset', 'two-sided'),
    ]
    return pd.DataFrame(rows)


def fmt_coef(b: float, p: float) -> str:
    stars = '***' if p < .01 else ('**' if p < .05 else ('*' if p < .1 else ''))
    return f'{b:.4g}{stars}'


OUTCOME_LABELS = {
    'Level change': 'Level change in e (USD per NZD)',
    'Log return (%)': '100 x log change in e (USD per NZD)',
}


def stata_block(result, model: dict, outcome: str, model_name: str) -> list[str]:
    """One Stata-like regression display: header statistics, coefficient table, diagnostics."""
    k = len(result.params) - 1
    restriction = np.zeros((k, k + 1))
    restriction[:, 1:] = np.eye(k)
    wald = result.wald_test(restriction, scalar=True)
    root_mse = float(np.sqrt(result.ssr / result.df_resid))
    left = [
        ('Specification', model_name),
        ('Dependent variable', OUTCOME_LABELS[outcome]),
        ('Sample', f"{model['first_date']} to {model['last_date']}"),
        ('Std. errors', f"HAC (Newey--West), {model['hac_lags']} lags"),
        ('Condition no.', f"{model['design_condition_number']:.4g}"),
        ('AIC / BIC', f"{result.aic:.1f} / {result.bic:.1f}"),
    ]
    right = [
        ('Number of obs', f'{int(result.nobs):,}'),
        (f'Wald chi2({k})', f'{float(wald.statistic):.2f}'),
        ('Prob $>$ chi2', f'{float(wald.pvalue):.4f}'),
        ('R-squared', f'{result.rsquared:.4f}'),
        ('Adj R-squared', f'{result.rsquared_adj:.4f}'),
        ('Root MSE', tex_num(root_mse, choose_format([root_mse])).strip()),
    ]
    out = [r'\noindent\begin{tabular}{@{}l l @{\hspace{3em}} l r@{}}']
    for (l1, l2), (r1, r2) in zip(left, right):
        out.append(f'{l1} & {l2} & {r1} & {r2} \\\\')
    out += [r'\end{tabular}', r'\vspace{0.8em}', '']

    ci = result.conf_int(alpha=.05)
    fmt = choose_format(np.concatenate([result.params, result.bse, ci.to_numpy().ravel()]))
    # Stata convention: slope terms first in model order, constant last; blank rule between groups.
    order = [v for v in result.params.index if v != 'const'] + ['const']
    groups, previous = [], None
    for variable in order:
        group = re.sub(r'_k[+-]\d+$', '', variable) if '_k' in variable else 'ctrl'
        if variable == 'const':
            group = 'const'
        groups.append((variable, group != previous and previous is not None))
        previous = group
    out += [r'\noindent\begin{tabular}{@{}l|r@{}l rrr rr@{}}', r'\hline',
            r' & \multicolumn{2}{c}{Coef.} & HAC Std. Err. & $z$ & $P>|z|$ '
            r'& \multicolumn{2}{c}{[95\% Conf. Interval]} \\', r'\hline']
    for variable, new_group in groups:
        if new_group:
            out.append(r'\addlinespace[0.3em]')
        out.append(' & '.join([
            latex_escape(pretty_variable(variable)),
            tex_num(result.params[variable], fmt),
            rf'\textsuperscript{{{tex_stars(result.pvalues[variable])}}}',
            tex_num(result.bse[variable], fmt),
            tex_num(result.tvalues[variable], ('fixed', 2)),
            tex_p(result.pvalues[variable]),
            tex_num(ci.loc[variable, 0], fmt),
            tex_num(ci.loc[variable, 1], fmt),
        ]) + r' \\')
    out += [r'\hline', r'\end{tabular}', r'\\[0.2em]', STARS_NOTE, r'\vspace{0.9em}', '']

    out += [r'\noindent\textbf{Residual diagnostics}\\[0.3em]',
            r'\begin{tabular}{@{}l|rr l@{}}', r'\hline',
            r'Test & Statistic & $p$-value & Null hypothesis \\', r'\hline']
    for test, (statistic, p_value) in regression_diagnostics(result, model['hac_lags']).items():
        null = DIAGNOSTIC_NULLS.get(test.split(' (')[0].split(' ')[0], '')
        out.append(f'{latex_escape(test)} & {tex_num(statistic, ("fixed", 3))} & '
                   f'{tex_p(p_value)} & {null} \\\\')
    out += [r'\hline', r'\end{tabular}']
    return out


DIAGNOSTIC_NULLS = {
    'Breusch–Pagan': 'homoskedastic residuals', 'White': 'homoskedastic residuals',
    'Breusch–Godfrey': 'no serial correlation', 'Ljung–Box': 'no serial correlation',
    'Jarque–Bera': 'normal residuals', 'Durbin–Watson': 'DW $\\approx 2$: no first-order autocorrelation',
}


def export_results(results: dict, out: Path, diagnostics: list[dict]) -> None:
    """Export one Stata-style report (one regression per page) for each specification."""
    for model_name, stem in (('Net flows', 'regression_net_flows'),
                             ('Disaggregated', 'regression_disaggregated')):
        body = []
        for i, outcome in enumerate(('Level change', 'Log return (%)')):
            key = f'{model_name} — {outcome}'
            model = next(row for row in diagnostics if row['model'] == key)
            if i:
                body.append(r'\newpage')
            body += stata_block(results[key], model, outcome, model_name)
        compile_latex(body, out / 'tables' / f'{stem}.tex', f'{model_name}: OLS with HAC standard errors')


def pretty_variable(variable: str) -> str:
    if variable == 'const':
        return 'Constant'
    labels = {'vix': 'VIX', 'treasury_swap_merged': 'Treasury swap', 'us_release': 'US release',
              'us_coupon': 'US coupon', 'us_buyback': 'US buyback'}
    if variable in labels:
        return labels[variable]
    match = re.fullmatch(r'us_(net_flow|issuance|principal)_k([+-]\d+)', variable)
    if match:
        component = {'net_flow': 'Net flow', 'issuance': 'Issuance', 'principal': 'Principal'}[match.group(1)]
        k = int(match.group(2))
        timing = 'pre' if k > 0 else ('post' if k < 0 else 'event')
        return f'US {component} (k={k:+d}, {timing})'
    return variable


ALTERNATIVES = {'greater': r'$>0$', 'less': r'$<0$', 'two-sided': r'$\neq 0$',
                'at least one nonzero': r'any $\neq 0$'}


def export_hypothesis_reports(test_frames: dict[str, pd.DataFrame], out: Path) -> None:
    names = {
        'H1': ('H1: anticipation (pre-event appreciation)', 'h1_anticipation'),
        'H2': ('H2: issuance-repayment asymmetry', 'h2_asymmetry'),
        'H3': ('H3: post-event response (reversal)', 'h3_reversal'),
    }
    for prefix, (title, stem) in names.items():
        body = []
        for outcome, frame in test_frames.items():
            selected = frame[frame['test'].str.startswith(prefix)]
            fmt = choose_format(np.concatenate([selected[c].to_numpy(dtype=float)
                                                for c in ('estimate', 'se', 'ci95_lower', 'ci95_upper')]))
            body += [rf'\noindent\textbf{{{latex_escape(OUTCOME_LABELS[outcome])}}}\\[0.3em]',
                     r'\begin{tabular}{@{}>{\raggedright\arraybackslash}p{2.9in}|r@{}l rrcr rr@{}}', r'\hline',
                     r'Test & \multicolumn{2}{c}{Estimate} & HAC Std. Err. & Statistic & $H_a$ & $p$-value & '
                     r'\multicolumn{2}{c}{[95\% Conf. Interval]} \\',
                     r'\hline']
            for row in selected.itertuples(index=False):
                dist = '$z$' if row.distribution == 'standard normal z' else rf'$\chi^2({int(row.df)})$'
                out_cells = [
                    latex_escape(row.test.split(': ', 1)[1]),
                    tex_num(row.estimate, fmt), '',
                    tex_num(row.se, fmt),
                    rf'{tex_num(row.statistic, ("fixed", 3))} {dist}',
                    ALTERNATIVES.get(row.alternative, ''),
                    rf'{tex_p(row.p_value)}\textsuperscript{{{tex_stars(row.p_value)}}}',
                    tex_num(row.ci95_lower, fmt), tex_num(row.ci95_upper, fmt),
                ]
                body.append(' & '.join(out_cells) + r' \\')
            body += [r'\hline', r'\end{tabular}', r'\vspace{1em}', '']
        body += [STARS_NOTE,
                 r'{\footnotesize\\ Joint tests use a robust Wald $\chi^2$; contrasts use a normal $z$ test '
                 r'(one-sided where $H_a$ is $>0$ or $<0$). Estimates are sums of coefficients; '
                 r'confidence intervals are two-sided 95\%.}']
        compile_latex(body, out / 'hypothesis_tests' / f'{stem}.tex', title, landscape=True)


def plot_principal(result, out: Path) -> None:
    dates = np.arange(-HORIZON, HORIZON + 1)
    # Horizontal axis: event-time day (negative = before). k=-event_time.
    b = np.array([result.params[f'us_principal_k{-int(j):+d}'] for j in dates])
    s = np.array([result.bse[f'us_principal_k{-int(j):+d}'] for j in dates])
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    ax.errorbar(dates, b, yerr=1.96 * s, fmt='o-', capsize=3, linewidth=1.5)
    ax.axhline(0, color='black', linewidth=.8)
    ax.axvline(0, color='gray', linewidth=.8, linestyle='--')
    ax.set_xticks(dates)
    ax.set_xlabel('Trading days relative to principal repayment (0 = event)')
    ax.set_ylabel('Coefficient on US-share-weighted principal repayment')
    ax.set_title('NZD/USD response to scheduled principal repayment (95% HAC intervals)')
    fig.tight_layout()
    fig.savefig(out / 'tables' / 'principal_event_time_coefficients.png', dpi=220)
    fig.savefig(out / 'tables' / 'principal_event_time_coefficients.pdf')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-dir', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--hac-lags', type=int, default=10)
    parser.add_argument('--weekend-policy', choices=['next-fx-day', 'drop'], default='next-fx-day',
                        help='Off-FX-calendar event dates: map to next observed FX session, or drop')
    parser.add_argument('--missing-flow', choices=['missing', 'zero'], default='missing',
                        help='Missing flow date: keep missing (default) or explicitly assume zero')
    parser.add_argument('--fx-quote', choices=['nzd-per-usd', 'usd-per-nzd'], default='nzd-per-usd',
                        help='Input dexnzus quote (default: nzd-per-usd for the supplied FX.csv); '
                             'outcomes always use USD per NZD')
    args = parser.parse_args()
    if args.hac_lags < 0:
        parser.error('--hac-lags must be nonnegative')
    base = args.base_dir.expanduser().resolve()
    out = base / 'output'
    for sub in ('intermediate', 'tables', 'hypothesis_tests'):
        (out / sub).mkdir(parents=True, exist_ok=True)
    clear_report_outputs(out)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(out / 'run.log', mode='w')])
    logging.info('Base=%s; weekend=%s; missing-flow=%s; input FX=%s',
                 base, args.weekend_policy, args.missing_flow, args.fx_quote)
    raw, audit = construct_data(base, out, args.weekend_policy, args.missing_flow, args.fx_quote)
    cols = ['date', 'flow_observed', FX_COL, 'delta_e', 'us_share', *REQUIRED_CONTROLS,
            'issuance', 'principal', 'coupon', 'buyback', 'net_flow', 'us_net_flow']
    counts = raw[cols].isna().sum().rename('missing_count').reset_index().rename(columns={'index': 'variable'})
    save_csv(counts, out / 'intermediate' / 'missingness_summary')
    outcomes = [('delta_e', 'Level change'), ('log_return_pct', 'Log return (%)')]
    results, diagnostics = {}, []
    for target, tag in outcomes:
        for name in ('Net flows', 'Disaggregated'):
            fit_res, frame, cond = fit(raw, name, target, args.hac_lags)
            key = f'{name} — {tag}'
            results[key] = fit_res
            frame[['date']].to_csv(out / 'intermediate' /
                                   f'sample_dates_{name.lower().replace(" ", "_")}_{target}.csv', index=False)
            diagnostics.append({'model': key, 'n_obs': int(fit_res.nobs),
                                'first_date': str(frame.date.iloc[0].date()),
                                'last_date': str(frame.date.iloc[-1].date()),
                                'r_squared': fit_res.rsquared, 'adj_r_squared': fit_res.rsquared_adj,
                                'aic': fit_res.aic, 'bic': fit_res.bic,
                                'design_condition_number': cond, 'hac_lags': args.hac_lags})
            logging.info('%s: n=%d, adj R2=%.4f', key, int(fit_res.nobs), fit_res.rsquared_adj)
    export_results(results, out, diagnostics)
    test_frames = {}
    for target, tag in outcomes:
        key = f'Disaggregated — {tag}'
        testdf = hypothesis_tests(results[key])
        test_frames[tag] = testdf
    export_hypothesis_reports(test_frames, out)
    clear_latex_auxiliary(out)
    metadata = {'base_dir': str(base), 'weekend_policy': args.weekend_policy,
                'missing_flow_policy': args.missing_flow, 'hac_lags': args.hac_lags,
                'n_fx_days': len(raw), 'n_source_flow_dates_mapped': int(audit.used.sum()),
                'n_flow_rows_moved': int(audit.moved.sum()),
                'n_fx_dates_missing_flow_records': int((~raw.flow_observed).sum()),
                'us_share_handling': 'backward as-of / last observed share; no backfill',
                'us_share_input': '0–1 fractions or explicitly marked percentages, converted to 0–1',
                'fx_input_quote': args.fx_quote, 'fx_outcome_quote': 'usd-per-nzd',
                'flow_sign_handling': 'source issuance negative, repayments positive; model uses positive magnitudes; '
                                      'net flow = issuance - principal - coupon - buyback',
                'unit_handling': 'cash flow units unchanged from input; no automatic division by 1e9',
                'date_handling': 'leads/lags count observed FX sessions, not calendar days',
                'interpretation_warning': 'US-holder weighted is not all foreign-held; associations not causal.'}
    (out / 'run_metadata.json').write_text(json.dumps(metadata, indent=2))
    logging.info('Finished. All outputs: %s', out)


if __name__ == '__main__':
    main()
