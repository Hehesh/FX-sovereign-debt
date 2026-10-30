"""Clock helpers: every observation gets a UTC timestamp; NZ settlements are anchored to Pacific/Auckland."""
from __future__ import annotations

import numpy as np
import pandas as pd

NZ, NY, LON = 'Pacific/Auckland', 'America/New_York', 'Europe/London'


def stamp(dates, tz: str, hour: int, minute: int = 0) -> pd.DatetimeIndex:
    """UTC instants for local wall-clock hh:mm on each date (DST handled by the tz database)."""
    local = pd.DatetimeIndex(pd.to_datetime(dates)).normalize() + pd.Timedelta(hours=hour, minutes=minute)
    return local.tz_localize(tz, nonexistent='shift_forward').tz_convert('UTC')


def window_index(event_utc: pd.DatetimeIndex, fix_utc: pd.DatetimeIndex) -> np.ndarray:
    """j such that fix[j-1] < event <= fix[j] (last fixing before, first fixing at/after); -1 if outside."""
    pos = fix_utc.searchsorted(event_utc, side='left')
    return np.where((pos >= 1) & (pos < len(fix_utc)), pos, -1)


def window_changes(values: pd.Series, obs_utc: pd.DatetimeIndex, fix_utc: pd.DatetimeIndex) -> np.ndarray:
    """Change over each fixing window: last observation stamped <= window end minus last <= window start.
    Observations after the end fixing are never used. NaN observations (holidays) are skipped."""
    keep = values.notna().to_numpy()
    v, st = values.to_numpy()[keep], obs_utc[keep]
    pos = st.searchsorted(fix_utc, side='right') - 1
    level = np.where(pos >= 0, v[np.clip(pos, 0, None)], np.nan)
    return np.r_[np.nan, np.diff(level)]


def level_at(values: pd.Series, obs_utc: pd.DatetimeIndex, at_utc: pd.DatetimeIndex) -> np.ndarray:
    """Last observation stamped at or before each instant (NaN observations skipped)."""
    keep = values.notna().to_numpy()
    v, st = values.to_numpy()[keep], obs_utc[keep]
    pos = st.searchsorted(at_utc, side='right') - 1
    return np.where(pos >= 0, v[np.clip(pos, 0, None)], np.nan)
