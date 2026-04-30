"""
Tariff recommendation engine.

Rules-based recommender that suggests SLP vs. RLM metering and
flags load-shifting opportunities.  All logic is pure Python.
"""

from __future__ import annotations

from core.config import LOAD_FACTOR_WARNING, RLM_THRESHOLD_KWH
from core.models import TariffRecommendation, TariffType


def recommend_tariff(
    annual_kwh: float,
    load_factor: float,
    peak_kw: float,
) -> TariffRecommendation:
    """
    Determine the recommended tariff type and optimisation hints.

    Args:
        annual_kwh: Estimated or measured annual consumption in kWh.
        load_factor: Ratio of average power to peak power (0-1).
        peak_kw: Maximum demand in kW.

    Returns:
        TariffRecommendation with reasoning in German.
    """
    reasoning: list[str] = []
    load_shifting = False

    if annual_kwh > RLM_THRESHOLD_KWH:
        tariff = TariffType.RLM
        reasoning.append(
            f"Jahresverbrauch {annual_kwh:,.0f} kWh > "
            f"{RLM_THRESHOLD_KWH:,.0f} kWh: RLM empfohlen."
        )
    else:
        tariff = TariffType.SLP
        reasoning.append(
            f"Jahresverbrauch {annual_kwh:,.0f} kWh < "
            f"{RLM_THRESHOLD_KWH:,.0f} kWh: SLP ausreichend."
        )

    if load_factor < LOAD_FACTOR_WARNING:
        load_shifting = True
        reasoning.append(
            f"Last-Faktor {load_factor:.1%} ist niedrig "
            f"(Spitze {peak_kw:.1f} kW). "
            f"Lastverschiebung pruefen."
        )
    else:
        reasoning.append(
            f"Last-Faktor {load_factor:.1%} ist akzeptabel."
        )

    if peak_kw > 50:
        reasoning.append(
            f"Spitzenlast {peak_kw:.1f} kW: "
            f"Peak-Shaving pruefen."
        )

    return TariffRecommendation(
        recommended_tariff=tariff,
        reasoning=reasoning,
        load_shifting_recommended=load_shifting,
        annual_kwh=round(annual_kwh, 1),
        load_factor_ratio=round(load_factor, 4),
        peak_kw=round(peak_kw, 2),
    )
