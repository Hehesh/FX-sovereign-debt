"""Data-contract checks: python -m unittest discover -s code -p 'test_*.py'."""
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

import run_regressions as regression


class RegressionDataTests(unittest.TestCase):
    def test_shares_accept_percentages_and_fractions_without_filling_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'shares.csv'
            path.write_text('date,us_share\n2014-01-01,15.80%\n'
                            '2014-01-02,0.105\n2014-01-03,NA\n2014-01-04, 0% \n')
            actual = regression.read_csv(path, ['us_share'],
                                         percentage_columns=('us_share',))
        np.testing.assert_allclose(actual.us_share, [.158, .105, np.nan, 0], equal_nan=True)

    def test_invalid_numbers_fail_at_the_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'shares.csv'
            for value in ('unavailable', '15%%', 'inf'):
                with self.subTest(value=value):
                    path.write_text(f'date,us_share\n2014-01-01,{value}\n')
                    with self.assertRaisesRegex(ValueError, 'invalid numeric values in us_share'):
                        regression.read_csv(path, ['us_share'], percentage_columns=('us_share',))

    def test_off_calendar_mapping_excludes_both_sample_boundaries(self):
        flows = pd.DataFrame({'date': pd.to_datetime([
            '2024-01-07', '2024-01-08', '2024-01-13', '2024-01-16'])})
        flows[regression.FLOW_COLS] = 1.
        fx_dates = pd.DatetimeIndex(['2024-01-08', '2024-01-12', '2024-01-15'])
        mapped, audit = regression.move_flows_to_fx_dates(flows, fx_dates, 'next-fx-day')
        self.assertEqual(audit.used.tolist(), [False, True, True, False])
        self.assertEqual(mapped.date.tolist(), [fx_dates[0], fx_dates[2]])
        _, dropped = regression.move_flows_to_fx_dates(flows, fx_dates, 'drop')
        self.assertEqual(dropped.used.tolist(), [False, True, False, False])

    def test_mapping_preserves_incomplete_components(self):
        flows = pd.DataFrame({'date': pd.to_datetime(['2024-01-13', '2024-01-15'])})
        flows[regression.FLOW_COLS] = 1.
        flows.loc[0, 'nom_coupon'] = np.nan
        mapped, _ = regression.move_flows_to_fx_dates(
            flows, pd.DatetimeIndex(['2024-01-12', '2024-01-15']), 'next-fx-day')
        self.assertTrue(pd.isna(mapped.loc[0, 'nom_coupon']))
        self.assertEqual(mapped.loc[0, 'nom_principal'], 2.)

    def test_construct_data_uses_source_signs_and_only_past_shares(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            inputs = base / 'regression'
            inputs.mkdir()
            out = base / 'output'
            (out / 'intermediate').mkdir(parents=True)
            dates = pd.bdate_range('2024-01-08', periods=13)
            fx_values = np.full(len(dates), 1.6)
            fx_values[1] = 2.
            pd.DataFrame({'date': dates, regression.FX_COL: fx_values}).to_csv(
                inputs / 'FX.csv', index=False)
            flows = pd.DataFrame({'date': dates})
            flows[regression.FLOW_COLS] = 0.
            flows.loc[1, ['nom_issuance', 'iib_issuance', 'nom_principal',
                          'nom_coupon', 'nom_buyback']] = [-100, -10, 20, 3, 2]
            flows.to_csv(inputs / 'nz_daily_flows.csv', index=False)
            controls = pd.DataFrame({'date': dates})
            controls[regression.REQUIRED_CONTROLS] = 0.
            controls.to_csv(inputs / 'Controls - Regression Control Panel.csv', index=False)
            shares_path = inputs / 'US_Share_of_New_Zealand_Debt.xlsx - Regression Series.csv'
            pd.DataFrame({'date': dates[[1, 8]], 'us_share': ['10%', '20%']}).to_csv(
                shares_path, index=False)
            raw, _ = regression.construct_data(base, out, 'next-fx-day', 'missing')
            np.testing.assert_allclose(raw.e, 1 / fx_values)
            np.testing.assert_allclose(raw[regression.FX_COL], fx_values)
            self.assertAlmostEqual(raw.loc[1, 'delta_e'], -.125)
            self.assertLess(raw.loc[1, 'log_return_pct'], 0)
            direct_quote, _ = regression.construct_data(
                base, out, 'next-fx-day', 'missing', 'usd-per-nzd')
            np.testing.assert_allclose(direct_quote.e, fx_values)
            self.assertTrue(pd.isna(raw.loc[0, 'us_share']))
            self.assertEqual(raw.loc[7, 'us_share'], .1)
            self.assertEqual(raw.loc[8, 'us_share'], .2)
            self.assertEqual(raw.loc[1, 'nom_issuance'], -100.)
            self.assertEqual(raw.loc[1, 'issuance'], 110.)
            self.assertEqual(raw.loc[1, 'net_flow'], 85.)
            self.assertAlmostEqual(raw.loc[1, 'us_net_flow'], 8.5)
            self.assertAlmostEqual(raw.loc[0, 'us_issuance_k+1'], 11.)
            self.assertAlmostEqual(raw.loc[2, 'us_issuance_k-1'], 11.)
            shares_path.write_text('date,us_share\n2024-01-08,NA\n')
            with self.assertRaisesRegex(ValueError, 'us_share has no usable observations'):
                regression.construct_data(base, out, 'next-fx-day', 'missing')


if __name__ == '__main__':
    unittest.main()
