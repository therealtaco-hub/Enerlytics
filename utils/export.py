"""
Excel export utilities.

Generates downloadable .xlsx reports from load profiles and machine data.
"""

from __future__ import annotations

from io import BytesIO
from typing import Optional

import pandas as pd

from core.models import MachineSet, TariffRecommendation


def export_scenario_a_excel(
    profile_series: pd.Series,
    per_machine: dict[str, pd.Series],
    stats: dict,
    machine_set: MachineSet,
    recommendation: Optional[TariffRecommendation] = None,
) -> BytesIO:
    """
    Export Scenario A results to an Excel workbook.

    Sheets:
        - Zusammenfassung: summary KPIs
        - Lastprofil: full time-series data
        - Maschinen: input parameters
        - Empfehlung: tariff recommendation

    Returns:
        BytesIO buffer containing the .xlsx file.
    """
    buf = BytesIO()

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # -- Zusammenfassung --
        summary_df = pd.DataFrame([
            {"Kennzahl": "Spitzenlast (kW)", "Wert": stats["peak_kw"]},
            {"Kennzahl": "Grundlast (kW)", "Wert": stats["base_kw"]},
            {"Kennzahl": "Durchschnittslast (kW)", "Wert": stats["avg_kw"]},
            {"Kennzahl": "Jahresverbrauch (kWh)", "Wert": stats["annual_kwh"]},
            {"Kennzahl": "Last-Faktor", "Wert": stats["load_factor"]},
            {"Kennzahl": "Benutzungsstunden", "Wert": stats["operating_hours_equivalent"]},
            {"Kennzahl": "Betrieb", "Wert": machine_set.plant_name},
            {"Kennzahl": "Branche", "Wert": machine_set.industry_type},
        ])
        summary_df.to_excel(writer, sheet_name="Zusammenfassung", index=False)

        # -- Lastprofil --
        profile_df = profile_series.to_frame("Gesamtlast_kW")
        profile_df.index.name = "Zeitstempel"
        for name, s in per_machine.items():
            profile_df[name] = s.values
        profile_df.to_excel(writer, sheet_name="Lastprofil")

        # -- Maschinen --
        machines_data = []
        for m in machine_set.machines:
            machines_data.append({
                "Name": m.name,
                "Nennleistung (kW)": m.rated_power_kw,
                "Betriebsstunden/Tag": m.operating_hours_per_day,
                "Tage/Woche": m.days_per_week,
                "Gleichzeitigkeitsfaktor": m.simultaneity_factor,
                "Lastfaktor": m.load_factor,
                "Startzeit": f"{m.start_hour:.1f}",
                "Kategorie": m.category.value,
                "Effektive Leistung (kW)": round(m.effective_power_kw, 2),
            })
        machines_df = pd.DataFrame(machines_data)
        machines_df.to_excel(writer, sheet_name="Maschinen", index=False)

        # -- Empfehlung --
        if recommendation:
            rec_data = [
                {"Punkt": "Empfohlener Tarif", "Details": recommendation.recommended_tariff.value},
                {"Punkt": "Lastverschiebung empfohlen", "Details": "Ja" if recommendation.load_shifting_recommended else "Nein"},
            ]
            for i, r in enumerate(recommendation.reasoning, 1):
                rec_data.append({"Punkt": f"Begruendung {i}", "Details": r})
            rec_df = pd.DataFrame(rec_data)
            rec_df.to_excel(writer, sheet_name="Empfehlung", index=False)

    buf.seek(0)
    return buf


def export_scenario_b_excel(
    synthetic_series: pd.Series,
    real_series: pd.Series,
    deviation_series: pd.Series,
    stats_synthetic: dict,
    stats_real: dict,
    deviation_report: "DeviationReport",
    machine_set: MachineSet,
    recommendation: Optional[TariffRecommendation] = None,
) -> BytesIO:
    """
    Export Scenario B comparison results to an Excel workbook.

    Sheets:
        - Zusammenfassung: KPIs for both profiles + deviations
        - Vergleich: side-by-side time series
        - Abweichungen: deviation analysis
        - Maschinen: input parameters
        - Empfehlung: tariff recommendation
    """
    from core.models import DeviationReport as _DR  # avoid circular

    buf = BytesIO()

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # -- Zusammenfassung --
        summary_rows = [
            {"Kennzahl": "Synthetisch - Spitzenlast (kW)", "Wert": stats_synthetic["peak_kw"]},
            {"Kennzahl": "Synthetisch - Jahresverbrauch (kWh)", "Wert": stats_synthetic["annual_kwh"]},
            {"Kennzahl": "Real - Spitzenlast (kW)", "Wert": stats_real["peak_kw"]},
            {"Kennzahl": "Real - Jahresverbrauch (kWh)", "Wert": stats_real["annual_kwh"]},
            {"Kennzahl": "MAPE (%)", "Wert": deviation_report.mape},
            {"Kennzahl": "Max. Abweichung (kW)", "Wert": deviation_report.max_deviation_kw},
            {"Kennzahl": "Max. Abweichung (%)", "Wert": deviation_report.max_deviation_pct},
            {"Kennzahl": "Unerklaerte Grundlast (kW)", "Wert": deviation_report.unexplained_base_load_kw},
            {"Kennzahl": "Anomalie-Intervalle", "Wert": deviation_report.anomaly_count},
        ]
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Zusammenfassung", index=False)

        # -- Vergleich --
        compare_df = pd.DataFrame({
            "Synthetisch_kW": synthetic_series.values,
            "Real_kW": real_series.values,
            "Abweichung_kW": deviation_series.values,
        }, index=synthetic_series.index)
        compare_df.index.name = "Zeitstempel"
        compare_df.to_excel(writer, sheet_name="Vergleich")

        # -- Maschinen --
        machines_data = []
        for m in machine_set.machines:
            machines_data.append({
                "Name": m.name,
                "Nennleistung (kW)": m.rated_power_kw,
                "Betriebsstunden/Tag": m.operating_hours_per_day,
                "Tage/Woche": m.days_per_week,
                "Gleichzeitigkeitsfaktor": m.simultaneity_factor,
                "Lastfaktor": m.load_factor,
            })
        pd.DataFrame(machines_data).to_excel(writer, sheet_name="Maschinen", index=False)

        # -- Empfehlung --
        if recommendation:
            rec_data = [
                {"Punkt": "Empfohlener Tarif", "Details": recommendation.recommended_tariff.value},
                {"Punkt": "Lastverschiebung empfohlen", "Details": "Ja" if recommendation.load_shifting_recommended else "Nein"},
            ]
            for i, r in enumerate(recommendation.reasoning, 1):
                rec_data.append({"Punkt": f"Begruendung {i}", "Details": r})
            pd.DataFrame(rec_data).to_excel(writer, sheet_name="Empfehlung", index=False)

    buf.seek(0)
    return buf
