"""
Generate a realistic sample RLM load profile for a metalworking company.

Output: data/sample_rlm.csv with 35,040 rows (15-min intervals, full year).

Profile characteristics:
- ~240,000 kWh/year
- Two shifts: 06:00-14:00, 14:00-22:00 (weekdays)
- Weekend base load only
- Gaussian noise + occasional load spikes
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd


def generate_sample_rlm(
    year: int = 2025,
    annual_target_kwh: float = 240_000.0,
    seed: int = 123,
    output_path: str | None = None,
) -> pd.DataFrame:
    """
    Generate a realistic sample RLM CSV.

    Returns:
        DataFrame with columns ['Zeitstempel', 'Wert'].
    """
    rng = np.random.default_rng(seed)

    start = pd.Timestamp(f"{year}-01-01 00:00:00")
    end = pd.Timestamp(f"{year}-12-31 23:45:00")
    index = pd.date_range(start=start, end=end, freq="15min")

    # Truncate to standard year length
    if len(index) > 35040:
        index = index[:35040]

    n = len(index)
    power = np.zeros(n)

    # Base load: ~5 kW (always on: IT, emergency lighting, standby)
    base_load = 5.0

    for i, ts in enumerate(index):
        hour = ts.hour + ts.minute / 60.0
        weekday = ts.weekday()  # 0=Mon, 6=Sun

        load = base_load

        if weekday < 5:  # Weekday
            # Shift 1: 06:00-14:00 — higher load
            if 6.0 <= hour < 14.0:
                load += 38.0  # production machines
                # Ramp up (06:00-06:30)
                if hour < 6.5:
                    load *= (hour - 6.0) / 0.5
            # Shift 2: 14:00-22:00 — slightly lower
            elif 14.0 <= hour < 22.0:
                load += 32.0
                # Ramp down (21:30-22:00)
                if hour >= 21.5:
                    load *= (22.0 - hour) / 0.5
            # Night: some auxiliary (compressor cycles)
            else:
                load += 3.0 * rng.random()

            # Lunch dip (12:00-12:30)
            if 12.0 <= hour < 12.5:
                load *= 0.7

        elif weekday == 5:  # Saturday — reduced operation
            if 7.0 <= hour < 13.0:
                load += 15.0
            else:
                load += 2.0 * rng.random()

        else:  # Sunday — base load only
            load += 1.5 * rng.random()

        power[i] = load

    # Add Gaussian noise (~8%)
    noise = rng.normal(0, 0.08, size=n)
    power = power * (1 + noise)

    # Add occasional spikes (3-5 per month)
    n_spikes = rng.integers(36, 61)
    spike_indices = rng.choice(n, size=n_spikes, replace=False)
    spike_magnitudes = rng.uniform(1.3, 2.0, size=n_spikes)
    for idx, mag in zip(spike_indices, spike_magnitudes):
        # Spike lasts 1-4 intervals
        duration = rng.integers(1, 5)
        end_idx = min(idx + duration, n)
        power[idx:end_idx] *= mag

    # Ensure non-negative
    power = np.maximum(power, 0.0)

    # Scale to hit annual target
    current_annual = power.sum() * 0.25
    if current_annual > 0:
        scale = annual_target_kwh / current_annual
        power *= scale

    # Round to 2 decimals
    power = np.round(power, 2)

    df = pd.DataFrame({
        "Zeitstempel": index.strftime("%d.%m.%Y %H:%M"),
        "Wert": [f"{v:.2f}".replace(".", ",") for v in power],  # German decimals
    })

    if output_path:
        df.to_csv(output_path, index=False, sep=";", encoding="utf-8-sig")
        print(f"Generated {len(df)} rows -> {output_path}")
        print(f"Annual energy: {power.sum() * 0.25:,.0f} kWh")
        print(f"Peak: {power.max():.1f} kW, Base: {power.min():.1f} kW")

    return df


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(script_dir, "sample_rlm.csv")
    generate_sample_rlm(output_path=out)
