import unittest

import pandas as pd

import timing as T


class TimingTests(unittest.TestCase):
    def test_noon_ny_in_nz_time_follows_both_dst_rules(self):
        h = lambda d: T.stamp([d], T.NY, 12)[0].tz_convert(T.NZ).strftime('%H:%M')
        self.assertEqual(h('2024-01-10'), '06:00')  # NZDT +13, EST -5
        self.assertEqual(h('2024-07-10'), '04:00')  # NZST +12, EDT -4
        self.assertEqual(h('2024-03-20'), '05:00')  # NZDT +13, EDT -4

    def test_settlement_window_is_ny_noon_to_noon_for_any_hour_between_06_and_13(self):
        dates = pd.bdate_range('2024-03-04', '2024-03-15')
        fix = T.stamp(dates, T.NY, 12)
        for hour in (7, 10, 12):
            j = T.window_index(T.stamp(['2024-03-12'], T.NZ, hour), fix)[0]
            self.assertEqual(dates[j], pd.Timestamp('2024-03-12'))

    def test_changes_never_use_observations_after_window_end(self):
        dates = pd.bdate_range('2024-03-04', '2024-03-08')
        fix = T.stamp(dates, T.NY, 12)
        vix = pd.Series([1., 2., 3., 4., 5.], index=dates)
        ch = T.window_changes(vix, T.stamp(dates, T.NY, 16, 15), fix)  # close is after that day's noon fix
        self.assertEqual(list(ch[2:]), [1., 1., 1.])  # window ending Wed noon uses Tue close minus Mon close
        self.assertTrue(pd.isna(ch[0]) and pd.isna(ch[1]))


if __name__ == '__main__':
    unittest.main()
