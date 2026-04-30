"""
Pydantic models for the Lastgang vs. Typenschild tool.

These models define the data contracts used across the application.
They are intentionally free of any UI dependencies so the same models
can be reused in a future FastAPI backend.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MachineCategory(str, Enum):
    """Broad category for grouping consumers in reports."""
    production = "production"
    auxiliary = "auxiliary"
    building_services = "building_services"


class TariffType(str, Enum):
    """German electricity metering / tariff types."""
    SLP = "SLP"   # Standardlastprofil
    RLM = "RLM"   # Registrierende Leistungsmessung


# ---------------------------------------------------------------------------
# Machine
# ---------------------------------------------------------------------------

class Machine(BaseModel):
    """
    A single electrical consumer described by its nameplate data
    and estimated usage pattern.

    Attributes:
        name: Human-readable label (e.g. "CNC-Fräsmaschine").
        rated_power_kw: Nameplate rated power in kW.
        operating_hours_per_day: Expected daily runtime in hours.
        days_per_week: Number of operating days per week (1–7).
        simultaneity_factor: Fraction of time the machine is actually
            running during its operating window (0.0–1.0).
        load_factor: Average fraction of rated power drawn while
            the machine is running (0.0–1.0).
        start_hour: Hour of day when operation begins (0.0–24.0).
        category: Grouping for reporting purposes.
    """

    name: str = Field(..., min_length=1, max_length=120)
    rated_power_kw: float = Field(..., gt=0, le=10_000)
    operating_hours_per_day: float = Field(..., gt=0, le=24)
    days_per_week: int = Field(..., ge=1, le=7)
    simultaneity_factor: float = Field(1.0, ge=0.0, le=1.0)
    load_factor: float = Field(1.0, ge=0.0, le=1.0)
    start_hour: float = Field(6.0, ge=0.0, lt=24.0)
    category: MachineCategory = MachineCategory.production

    # -- Computed helpers (not stored, but useful) --------------------------

    @property
    def effective_power_kw(self) -> float:
        """Average electrical draw during active operation."""
        return self.rated_power_kw * self.simultaneity_factor * self.load_factor

    @property
    def end_hour(self) -> float:
        """Hour of day when operation ends (may wrap past midnight)."""
        return (self.start_hour + self.operating_hours_per_day) % 24.0

    @property
    def estimated_annual_kwh(self) -> float:
        """Rough annual energy estimate (simplified, no holidays)."""
        weeks_per_year = 52
        daily_kwh = self.effective_power_kw * self.operating_hours_per_day
        return daily_kwh * self.days_per_week * weeks_per_year


# ---------------------------------------------------------------------------
# MachineSet
# ---------------------------------------------------------------------------

class MachineSet(BaseModel):
    """
    A collection of machines representing a single plant / site.

    Attributes:
        machines: Ordered list of Machine objects.
        plant_name: Name of the plant or company.
        industry_type: Free-text industry descriptor (e.g. "Metallverarbeitung").
        year: Reference year for the synthetic profile.
    """

    machines: list[Machine] = Field(default_factory=list, min_length=0)
    plant_name: str = Field("Musterbetrieb", min_length=1)
    industry_type: str = Field("Metallverarbeitung")
    year: int = Field(2025, ge=2000, le=2100)

    @property
    def total_rated_power_kw(self) -> float:
        return sum(m.rated_power_kw for m in self.machines)

    @property
    def total_effective_power_kw(self) -> float:
        return sum(m.effective_power_kw for m in self.machines)

    @property
    def estimated_annual_kwh(self) -> float:
        return sum(m.estimated_annual_kwh for m in self.machines)


# ---------------------------------------------------------------------------
# Load-profile wrapper
# ---------------------------------------------------------------------------

class LoadProfileMeta(BaseModel):
    """
    Lightweight metadata wrapper for a time-series load profile.

    The heavy ``pd.Series`` data is **not** stored inside the Pydantic
    model to avoid serialisation overhead.  Instead, consumer code creates
    this metadata object alongside a plain ``pd.Series``.
    """

    peak_kw: float = Field(..., ge=0)
    base_kw: float = Field(..., ge=0)
    annual_kwh: float = Field(..., ge=0)
    load_factor_ratio: float = Field(..., ge=0, le=1.0)
    intervals: int = Field(..., gt=0)

    @classmethod
    def from_series(cls, series: pd.Series) -> "LoadProfileMeta":
        """Derive metadata from a kW time series with 15-min intervals."""
        peak = float(series.max())
        base = float(series.min())
        # Each interval covers 0.25 h → energy = sum(kW) × 0.25
        annual_kwh = float(series.sum()) * 0.25
        load_factor = float(series.mean() / peak) if peak > 0 else 0.0
        return cls(
            peak_kw=round(peak, 2),
            base_kw=round(base, 2),
            annual_kwh=round(annual_kwh, 2),
            load_factor_ratio=round(load_factor, 4),
            intervals=len(series),
        )


# ---------------------------------------------------------------------------
# Deviation report (Scenario B)
# ---------------------------------------------------------------------------

class DeviationReport(BaseModel):
    """
    Result of comparing a synthetic profile against a real RLM profile.
    """

    mape: float = Field(..., ge=0, description="Mean Absolute Percentage Error (%)")
    max_deviation_kw: float = Field(..., ge=0)
    max_deviation_pct: float = Field(..., ge=0)
    unexplained_base_load_kw: float = Field(
        0.0, ge=0,
        description="Base-load difference that may indicate unknown consumers",
    )
    anomaly_count: int = Field(0, ge=0)
    anomaly_intervals: list[str] = Field(
        default_factory=list,
        description="ISO-formatted timestamps of intervals exceeding the deviation threshold",
    )
    summary_text: str = ""


# ---------------------------------------------------------------------------
# Tariff recommendation
# ---------------------------------------------------------------------------

class TariffRecommendation(BaseModel):
    """Structured tariff / optimisation recommendation."""

    recommended_tariff: TariffType
    reasoning: list[str] = Field(default_factory=list)
    load_shifting_recommended: bool = False
    annual_kwh: float = 0.0
    load_factor_ratio: float = 0.0
    peak_kw: float = 0.0
