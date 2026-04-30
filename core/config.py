"""
Central configuration for thresholds, constants, and defaults.

All magic numbers live here so they can be tuned without touching
business logic.  When migrating to FastAPI, these can be read from
environment variables or a settings file.
"""

# ---------------------------------------------------------------------------
# Time resolution
# ---------------------------------------------------------------------------
INTERVALS_PER_HOUR: int = 4            # 15-minute intervals
INTERVALS_PER_DAY: int = 96            # 24 × 4
INTERVALS_PER_WEEK: int = 672          # 7 × 96
HOURS_PER_YEAR: int = 8_760
INTERVALS_PER_YEAR: int = 35_040       # 8760 × 4

# ---------------------------------------------------------------------------
# Tariff thresholds
# ---------------------------------------------------------------------------
RLM_THRESHOLD_KWH: float = 100_000.0   # Annual kWh above which RLM is recommended
LOAD_FACTOR_WARNING: float = 0.3        # Below this → flag high peak-to-average ratio

# ---------------------------------------------------------------------------
# Deviation analysis (Scenario B)
# ---------------------------------------------------------------------------
DEVIATION_THRESHOLD_PCT: float = 20.0   # Flag intervals deviating more than this (%)

# ---------------------------------------------------------------------------
# Synthetic profile generation
# ---------------------------------------------------------------------------
NOISE_STD_FRACTION: float = 0.05        # ±5 % Gaussian noise on effective power
RAMP_INTERVALS: int = 2                 # 2 × 15 min ramp-up/ramp-down per shift

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
VR_GREEN: str = "#00843D"
VR_DARK: str = "#1a1a2e"
VR_ACCENT: str = "#16a34a"
COMPANY_NAME: str = "VR Energieservice GmbH"

# ---------------------------------------------------------------------------
# Default sample machines (metalworking demo)
# ---------------------------------------------------------------------------
SAMPLE_MACHINES: list[dict] = [
    {
        "name": "CNC-Fräsmaschine",
        "rated_power_kw": 15.0,
        "operating_hours_per_day": 16.0,
        "days_per_week": 5,
        "simultaneity_factor": 0.75,
        "load_factor": 0.70,
        "start_hour": 6.0,
        "category": "production",
    },
    {
        "name": "Hydraulikpresse",
        "rated_power_kw": 22.0,
        "operating_hours_per_day": 16.0,
        "days_per_week": 5,
        "simultaneity_factor": 0.60,
        "load_factor": 0.65,
        "start_hour": 6.0,
        "category": "production",
    },
    {
        "name": "Schweißstation",
        "rated_power_kw": 8.0,
        "operating_hours_per_day": 16.0,
        "days_per_week": 5,
        "simultaneity_factor": 0.50,
        "load_factor": 0.80,
        "start_hour": 6.0,
        "category": "production",
    },
    {
        "name": "Kompressor",
        "rated_power_kw": 11.0,
        "operating_hours_per_day": 24.0,
        "days_per_week": 7,
        "simultaneity_factor": 0.80,
        "load_factor": 0.60,
        "start_hour": 0.0,
        "category": "auxiliary",
    },
    {
        "name": "Förderband",
        "rated_power_kw": 4.0,
        "operating_hours_per_day": 16.0,
        "days_per_week": 5,
        "simultaneity_factor": 0.90,
        "load_factor": 0.55,
        "start_hour": 6.0,
        "category": "production",
    },
    {
        "name": "Beleuchtung / HLK",
        "rated_power_kw": 6.0,
        "operating_hours_per_day": 24.0,
        "days_per_week": 7,
        "simultaneity_factor": 1.0,
        "load_factor": 0.45,
        "start_hour": 0.0,
        "category": "building_services",
    },
]
