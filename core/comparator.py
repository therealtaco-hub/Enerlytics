"""
Deviation analysis and RLM CSV parsing (Scenario B).

Compares a synthetic load profile against a real measured RLM profile
and calculates deviation metrics.
"""

from __future__ import annotations

from io import BytesIO, StringIO
from typing import Optional, Union

import numpy as np
import pandas as pd

from core.config import DEVIATION_THRESHOLD_PCT, INTERVALS_PER_HOUR
from core.models import DeviationReport


# ---------------------------------------------------------------------------
# CSV Parsing — supports multiple common RLM export formats
# ---------------------------------------------------------------------------

# Known column name patterns for the power value
_POWER_COLUMNS = [
    "wert", "kw", "leistung", "power", "value", "verbrauch",
    "wirkleistung", "p_kw", "last", "demand",
]

# Known date/time column patterns
_DATETIME_COLUMNS = [
    "zeitstempel", "timestamp", "datum", "date", "zeit", "time",
    "von", "ab", "start", "beginn",
]

# Common date formats in German RLM exports
_DATE_FORMATS = [
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M",
]


def _detect_delimiter(sample: str) -> str:
    """Guess CSV delimiter from a sample of the file."""
    semicolons = sample.count(";")
    commas = sample.count(",")
    tabs = sample.count("\t")
    if semicolons > commas and semicolons > tabs:
        return ";"
    if tabs > commas:
        return "\t"
    return ","


def _find_column(columns: list[str], patterns: list[str]) -> Optional[str]:
    """Find the first column whose lowercase name contains a known pattern."""
    lower_cols = {c.lower().strip(): c for c in columns}
    for pattern in patterns:
        for lc, original in lower_cols.items():
            if pattern in lc:
                return original
    return None


def parse_rlm_csv(
    file: Union[BytesIO, StringIO, str],
    year: Optional[int] = None,
) -> tuple[pd.Series, str]:
    """
    Parse an RLM load profile from a CSV file.

    Handles:
    - Semicolon, comma and tab delimiters
    - German decimal notation (comma as decimal separator)
    - Various column naming conventions (Netze BW, Bayernwerk, generic)
    - Multiple date formats

    Args:
        file: File-like object or file path.
        year: If provided, filter data to this year only.

    Returns:
        Tuple of (pd.Series with DatetimeIndex in kW, format_description).

    Raises:
        ValueError: If the file cannot be parsed or validated.
    """
    # Read raw content
    if isinstance(file, str):
        with open(file, "r", encoding="utf-8-sig") as f:
            raw = f.read()
    elif isinstance(file, BytesIO):
        raw = file.read().decode("utf-8-sig")
        file.seek(0)
    else:
        raw = file.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8-sig")

    delimiter = _detect_delimiter(raw[:2000])

    # Parse CSV
    df = pd.read_csv(
        StringIO(raw),
        sep=delimiter,
        engine="python",
        dtype=str,
        skip_blank_lines=True,
    )

    # Strip whitespace from column names
    df.columns = [c.strip() for c in df.columns]

    # --- Find datetime column ---
    dt_col = _find_column(df.columns.tolist(), _DATETIME_COLUMNS)
    if dt_col is None:
        # Try using the first column as datetime
        dt_col = df.columns[0]

    # Parse datetime
    dt_series = None
    for fmt in _DATE_FORMATS:
        try:
            dt_series = pd.to_datetime(df[dt_col], format=fmt)
            break
        except (ValueError, TypeError):
            continue

    if dt_series is None:
        # Fallback: let pandas infer
        try:
            dt_series = pd.to_datetime(df[dt_col], dayfirst=True)
        except Exception:
            raise ValueError(
                f"Datumsformat in Spalte '{dt_col}' konnte nicht erkannt werden. "
                f"Unterstützte Formate: {_DATE_FORMATS}"
            )

    # --- Find power column ---
    power_col = _find_column(df.columns.tolist(), _POWER_COLUMNS)
    if power_col is None:
        # Try second column (common pattern: datetime | value)
        numeric_cols = [c for c in df.columns if c != dt_col]
        if numeric_cols:
            power_col = numeric_cols[0]
        else:
            raise ValueError("Leistungsspalte (kW) konnte nicht gefunden werden.")

    # Parse power values (handle German decimals: 1.234,56 → 1234.56)
    power_raw = df[power_col].astype(str)
    # Remove thousand separators (dots before comma)
    power_raw = power_raw.str.replace(".", "", regex=False)
    # Replace comma decimal separator with dot
    power_raw = power_raw.str.replace(",", ".", regex=False)
    power_values = pd.to_numeric(power_raw, errors="coerce")

    # Build series
    result = pd.Series(power_values.values, index=dt_series, name="Real_kW")
    result = result.dropna().sort_index()

    # Filter by year if specified
    if year is not None:
        result = result[result.index.year == year]

    if len(result) == 0:
        raise ValueError("Keine gültigen Datenpunkte nach dem Parsen gefunden.")

    # Detect format
    format_desc = f"Spalten: {dt_col} | {power_col}, Trennzeichen: '{delimiter}'"

    return result, format_desc


# ---------------------------------------------------------------------------
# Profile alignment
# ---------------------------------------------------------------------------

def align_profiles(
    synthetic: pd.Series,
    real: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """
    Align synthetic and real profiles to a common time axis.

    Uses an inner join on the DatetimeIndex so only overlapping
    intervals are compared.
    """
    combined = pd.DataFrame({
        "synthetic": synthetic,
        "real": real,
    }).dropna()

    return combined["synthetic"], combined["real"]


# ---------------------------------------------------------------------------
# Deviation analysis
# ---------------------------------------------------------------------------

def calculate_deviations(
    synthetic: pd.Series,
    real: pd.Series,
    threshold_pct: float = DEVIATION_THRESHOLD_PCT,
) -> tuple[DeviationReport, pd.Series]:
    """
    Calculate deviation metrics between synthetic and real profiles.

    Args:
        synthetic: Aligned synthetic profile (kW).
        real: Aligned real profile (kW).
        threshold_pct: Flag intervals deviating more than this (%).

    Returns:
        Tuple of (DeviationReport, deviation_series in kW).
    """
    deviation = real - synthetic  # positive = real exceeds synthetic
    abs_dev = deviation.abs()

    # MAPE (avoid division by zero)
    nonzero_mask = real.abs() > 0.1  # ignore near-zero intervals
    if nonzero_mask.sum() > 0:
        mape = float((abs_dev[nonzero_mask] / real[nonzero_mask].abs()).mean() * 100)
    else:
        mape = 0.0

    # Peak deviation
    max_dev_idx = abs_dev.idxmax()
    max_dev_kw = float(abs_dev.max())
    real_at_max = float(real.loc[max_dev_idx]) if real.loc[max_dev_idx] != 0 else 1.0
    max_dev_pct = float(max_dev_kw / abs(real_at_max) * 100) if real_at_max != 0 else 0.0

    # Unexplained base load
    base_real = float(real.min())
    base_synth = float(synthetic.min())
    unexplained = max(0.0, base_real - base_synth)

    # Anomaly detection
    pct_dev = pd.Series(0.0, index=real.index)
    safe_mask = real.abs() > 0.1
    pct_dev[safe_mask] = abs_dev[safe_mask] / real[safe_mask].abs() * 100
    anomaly_mask = pct_dev > threshold_pct
    anomaly_timestamps = real.index[anomaly_mask].strftime("%Y-%m-%d %H:%M").tolist()

    # Limit stored anomaly timestamps to 500 for serialisation
    anomaly_count = int(anomaly_mask.sum())
    stored_timestamps = anomaly_timestamps[:500]

    # Summary text
    summary = (
        f"MAPE: {mape:.1f}% | Max. Abweichung: {max_dev_kw:.1f} kW ({max_dev_pct:.1f}%) | "
        f"Unerklärte Grundlast: {unexplained:.1f} kW | "
        f"Anomalie-Intervalle (>{threshold_pct:.0f}%): {anomaly_count}"
    )

    report = DeviationReport(
        mape=round(mape, 2),
        max_deviation_kw=round(max_dev_kw, 2),
        max_deviation_pct=round(max_dev_pct, 2),
        unexplained_base_load_kw=round(unexplained, 2),
        anomaly_count=anomaly_count,
        anomaly_intervals=stored_timestamps,
        summary_text=summary,
    )

    return report, deviation
