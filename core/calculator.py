"""
Core calculation engine for synthetic load-profile generation.

All functions in this module are pure Python (no Streamlit dependency)
so they can be reused in a FastAPI backend or CLI tool.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from core.config import (
    INTERVALS_PER_DAY,
    INTERVALS_PER_HOUR,
    INTERVALS_PER_YEAR,
    NOISE_STD_FRACTION,
    RAMP_INTERVALS,
)
from core.models import LoadProfileMeta, Machine, MachineSet


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _operating_mask_day(machine: Machine) -> np.ndarray:
    """
    Return a boolean array of length 96 (one day of 15-min intervals)
    where ``True`` marks intervals during which the machine is operating.

    Handles overnight wrapping (e.g. start_hour=22, operating_hours=8 →
    22:00–06:00 next day).
    """
    mask = np.zeros(INTERVALS_PER_DAY, dtype=bool)
    start_slot = int(machine.start_hour * INTERVALS_PER_HOUR)
    num_slots = int(machine.operating_hours_per_day * INTERVALS_PER_HOUR)

    for i in range(num_slots):
        slot = (start_slot + i) % INTERVALS_PER_DAY
        mask[slot] = True

    return mask


def _apply_ramp(power_array: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Apply linear ramp-up / ramp-down at the edges of the operating window
    to avoid unrealistic step changes.
    """
    result = power_array.copy()
    # Find rising and falling edges
    diff = np.diff(mask.astype(int), prepend=0)
    rise_indices = np.where(diff == 1)[0]
    fall_indices = np.where(diff == -1)[0]

    for idx in rise_indices:
        for r in range(min(RAMP_INTERVALS, len(result) - idx)):
            factor = (r + 1) / (RAMP_INTERVALS + 1)
            if idx + r < len(result):
                result[idx + r] *= factor

    for idx in fall_indices:
        for r in range(min(RAMP_INTERVALS, idx)):
            factor = (r + 1) / (RAMP_INTERVALS + 1)
            if idx - 1 - r >= 0:
                result[idx - 1 - r] *= factor

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_machine_daily_profile(
    machine: Machine,
    add_noise: bool = True,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """
    Generate a 96-element array (one day, 15-min resolution) of kW values
    for a single machine.

    Args:
        machine: Machine with nameplate and usage parameters.
        add_noise: If True, add Gaussian noise (±NOISE_STD_FRACTION).
        rng: Optional numpy random generator for reproducibility.

    Returns:
        np.ndarray of shape (96,) with kW values.
    """
    if rng is None:
        rng = np.random.default_rng()

    mask = _operating_mask_day(machine)
    base_power = machine.effective_power_kw
    profile = np.where(mask, base_power, 0.0)

    # Apply ramp-up/ramp-down
    profile = _apply_ramp(profile, mask)

    # Add noise
    if add_noise and base_power > 0:
        noise = rng.normal(0, base_power * NOISE_STD_FRACTION, size=INTERVALS_PER_DAY)
        profile = np.where(mask, profile + noise, profile)
        profile = np.maximum(profile, 0.0)  # No negative power

    return profile


def generate_machine_weekly_profile(
    machine: Machine,
    add_noise: bool = True,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """
    Generate a 672-element array (7 days × 96 intervals) for one machine.

    Days are indexed 0=Monday … 6=Sunday.  If ``days_per_week < 7``,
    weekend days are zeroed out (5 → Mon–Fri, 6 → Mon–Sat, etc.).
    """
    if rng is None:
        rng = np.random.default_rng()

    weekly = np.zeros(7 * INTERVALS_PER_DAY)
    for day_idx in range(7):
        # Check if this day is an operating day
        if day_idx < machine.days_per_week:
            day_profile = generate_machine_daily_profile(machine, add_noise, rng)
        else:
            day_profile = np.zeros(INTERVALS_PER_DAY)

        start = day_idx * INTERVALS_PER_DAY
        end = start + INTERVALS_PER_DAY
        weekly[start:end] = day_profile

    return weekly


def generate_synthetic_load_profile(
    machine_set: MachineSet,
    year: Optional[int] = None,
    add_noise: bool = True,
    seed: int = 42,
) -> tuple[pd.Series, dict[str, pd.Series]]:
    """
    Generate a full-year synthetic load profile (35,040 intervals) by
    summing the weekly profiles of all machines in the set.

    Args:
        machine_set: Collection of machines.
        year: Calendar year for the datetime index (defaults to machine_set.year).
        add_noise: Whether to add Gaussian noise per machine.
        seed: Random seed for reproducibility.

    Returns:
        A tuple of:
        - ``total``: pd.Series with DatetimeIndex and kW values (plant total).
        - ``per_machine``: dict mapping machine name → pd.Series.
    """
    if year is None:
        year = machine_set.year

    rng = np.random.default_rng(seed)

    # Build datetime index for the full year (15-min intervals)
    start = pd.Timestamp(f"{year}-01-01 00:00:00")
    end = pd.Timestamp(f"{year}-12-31 23:45:00")
    index = pd.date_range(start=start, end=end, freq="15min")

    # Ensure exactly INTERVALS_PER_YEAR entries (handle leap years by truncation)
    if len(index) > INTERVALS_PER_YEAR:
        index = index[:INTERVALS_PER_YEAR]

    total = np.zeros(len(index))
    per_machine: dict[str, pd.Series] = {}

    for machine in machine_set.machines:
        weekly = generate_machine_weekly_profile(machine, add_noise, rng)

        # Tile the weekly profile across the year
        num_weeks = len(index) // (7 * INTERVALS_PER_DAY) + 1
        annual = np.tile(weekly, num_weeks)[:len(index)]

        # Align to actual weekdays: index[0].weekday() gives the weekday
        # of Jan 1.  Our weekly array starts on Monday (day_idx=0).
        # We need to rotate so the array aligns with the calendar.
        jan1_weekday = index[0].weekday()  # 0=Mon … 6=Sun
        shift = jan1_weekday * INTERVALS_PER_DAY
        annual = np.roll(annual, -shift)

        # Re-apply noise on a per-interval level so tiled weeks differ slightly
        if add_noise and machine.effective_power_kw > 0:
            extra_noise = rng.normal(
                0,
                machine.effective_power_kw * NOISE_STD_FRACTION * 0.5,
                size=len(annual),
            )
            annual = annual + extra_noise * (annual > 0).astype(float)
            annual = np.maximum(annual, 0.0)

        series = pd.Series(annual, index=index, name=machine.name)
        per_machine[machine.name] = series
        total += annual

    total_series = pd.Series(total, index=index, name="Gesamtlast")
    return total_series, per_machine


def calculate_summary_stats(profile: pd.Series) -> dict:
    """
    Compute key summary statistics for a load profile.

    Args:
        profile: pd.Series with kW values at 15-min intervals.

    Returns:
        Dictionary with peak_kw, base_kw, annual_kwh, load_factor,
        avg_kw, operating_hours_equivalent.
    """
    peak = float(profile.max())
    base = float(profile.min())
    avg = float(profile.mean())
    annual_kwh = float(profile.sum()) * 0.25  # 15 min = 0.25 h
    load_factor = avg / peak if peak > 0 else 0.0
    operating_hours_eq = annual_kwh / peak if peak > 0 else 0.0

    return {
        "peak_kw": round(peak, 2),
        "base_kw": round(base, 2),
        "avg_kw": round(avg, 2),
        "annual_kwh": round(annual_kwh, 1),
        "load_factor": round(load_factor, 4),
        "operating_hours_equivalent": round(operating_hours_eq, 0),
    }
