"""
Streamlit UI for Scenario B — Comparison with real RLM data (Bestandskunde).

Allows uploading a real RLM load profile CSV, defining machines,
and comparing synthetic vs. measured load profiles.
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from core.calculator import calculate_summary_stats, generate_synthetic_load_profile
from core.comparator import align_profiles, calculate_deviations, parse_rlm_csv
from core.config import DEVIATION_THRESHOLD_PCT, SAMPLE_MACHINES
from core.models import Machine, MachineSet
from core.recommender import recommend_tariff
from ui.components import (
    render_comparison_chart,
    render_deviation_chart,
    render_summary_cards,
    render_tariff_recommendation,
)
from utils.export import export_scenario_b_excel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_session_state_b() -> None:
    if "machines_b" not in st.session_state:
        st.session_state["machines_b"] = [dict(m) for m in SAMPLE_MACHINES]
    if "plant_name_b" not in st.session_state:
        st.session_state["plant_name_b"] = "Musterbetrieb Metallverarbeitung"
    if "industry_b" not in st.session_state:
        st.session_state["industry_b"] = "Metallverarbeitung"
    if "year_b" not in st.session_state:
        st.session_state["year_b"] = 2025


def _machine_editor_b() -> list[dict]:
    """Machine input form for Scenario B (reuses same logic as A)."""
    machines = st.session_state["machines_b"]

    st.markdown("#### ⚙️ Verbraucher (Typenschild)")

    col_add, col_remove, _ = st.columns([1, 1, 3])
    with col_add:
        if st.button("➕ Maschine hinzufügen", key="add_machine_b", width="stretch"):
            machines.append({
                "name": f"Neue Maschine {len(machines) + 1}",
                "rated_power_kw": 10.0,
                "operating_hours_per_day": 8.0,
                "days_per_week": 5,
                "simultaneity_factor": 0.8,
                "load_factor": 0.7,
                "start_hour": 6.0,
                "category": "production",
            })
            st.session_state["machines_b"] = machines
            st.rerun()
    with col_remove:
        if len(machines) > 1:
            if st.button("➖ Letzte entfernen", key="remove_machine_b", width="stretch"):
                machines.pop()
                st.session_state["machines_b"] = machines
                st.rerun()

    updated: list[dict] = []
    categories = {"production": "Produktion", "auxiliary": "Hilfsbetrieb", "building_services": "Gebäudetechnik"}
    cat_keys = list(categories.keys())
    cat_labels = list(categories.values())

    for i, m in enumerate(machines):
        with st.expander(f"🔧 {m.get('name', f'Maschine {i+1}')}", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Name", value=m.get("name", ""), key=f"bname_{i}")
                rated = st.number_input("Nennleistung (kW)", value=m.get("rated_power_kw", 10.0), min_value=0.1, max_value=10000.0, step=0.5, key=f"brated_{i}")
                hours = st.number_input("Betriebsstunden / Tag", value=m.get("operating_hours_per_day", 8.0), min_value=0.25, max_value=24.0, step=0.5, key=f"bhours_{i}")
                days = st.number_input("Betriebstage / Woche", value=m.get("days_per_week", 5), min_value=1, max_value=7, step=1, key=f"bdays_{i}")
            with c2:
                sim = st.slider("Gleichzeitigkeitsfaktor", 0.0, 1.0, m.get("simultaneity_factor", 0.8), 0.05, key=f"bsim_{i}")
                lf = st.slider("Lastfaktor", 0.0, 1.0, m.get("load_factor", 0.7), 0.05, key=f"blf_{i}")
                start = st.number_input("Startzeit (Uhr)", value=m.get("start_hour", 6.0), min_value=0.0, max_value=23.75, step=0.25, key=f"bstart_{i}")
                cat_idx = cat_keys.index(m.get("category", "production")) if m.get("category") in cat_keys else 0
                cat = st.selectbox("Kategorie", cat_labels, index=cat_idx, key=f"bcat_{i}")

            updated.append({
                "name": name,
                "rated_power_kw": rated,
                "operating_hours_per_day": hours,
                "days_per_week": int(days),
                "simultaneity_factor": sim,
                "load_factor": lf,
                "start_hour": start,
                "category": cat_keys[cat_labels.index(cat)],
            })

    st.session_state["machines_b"] = updated
    return updated


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render_scenario_b() -> None:
    """Render the full Scenario B page."""
    _init_session_state_b()

    st.markdown(
        """
        ## 📋 Szenario B — Vergleich mit realem Lastgang (Bestandskunde)
        Laden Sie einen gemessenen RLM-Lastgang hoch und vergleichen Sie ihn
        mit dem synthetischen Profil aus den Typenschilddaten.
        """
    )

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### 🏭 Betriebsdaten")
        st.session_state["plant_name_b"] = st.text_input("Betriebsname", value=st.session_state["plant_name_b"], key="plant_input_b")
        st.session_state["industry_b"] = st.text_input("Branche", value=st.session_state["industry_b"], key="industry_input_b")
        st.session_state["year_b"] = st.number_input("Referenzjahr", value=st.session_state["year_b"], min_value=2000, max_value=2100, key="year_input_b")

        st.markdown("---")
        st.markdown("### ⚙️ Analyse-Parameter")
        threshold = st.slider(
            "Abweichungs-Schwelle (%)",
            5.0, 50.0, DEVIATION_THRESHOLD_PCT, 1.0,
            key="threshold_b",
        )

    # --- File upload ---
    st.markdown("#### 📂 RLM-Lastgang hochladen")
    col_upload, col_sample = st.columns([3, 1])

    with col_upload:
        uploaded_file = st.file_uploader(
            "CSV-Datei auswählen (15-min Intervalle)",
            type=["csv", "txt"],
            key="rlm_upload",
        )

    with col_sample:
        st.markdown("")
        st.markdown("")
        sample_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sample_rlm.csv")
        if os.path.exists(sample_path):
            with open(sample_path, "rb") as f:
                st.download_button(
                    "📥 Beispiel-CSV",
                    data=f.read(),
                    file_name="sample_rlm.csv",
                    mime="text/csv",
                )
        else:
            st.caption("Beispiel-CSV nicht gefunden.")

    # --- Machine editor ---
    st.markdown("---")
    machine_dicts = _machine_editor_b()

    st.divider()

    # --- Calculate ---
    if st.button("🔄 Vergleich starten", type="primary", width="stretch", key="calc_b"):
        if uploaded_file is None:
            st.error("Bitte laden Sie zunächst eine RLM-CSV-Datei hoch.")
            return

        with st.spinner("Analyse läuft..."):
            try:
                # Parse uploaded CSV
                from io import BytesIO
                raw_bytes = BytesIO(uploaded_file.getvalue())
                real_series, fmt = parse_rlm_csv(raw_bytes, year=st.session_state["year_b"])
                st.info(f"📄 Format erkannt: {fmt} — {len(real_series):,} Datenpunkte geladen.")

                # Build machine set & synthetic profile
                machines = [Machine(**md) for md in machine_dicts]
                machine_set = MachineSet(
                    machines=machines,
                    plant_name=st.session_state["plant_name_b"],
                    industry_type=st.session_state["industry_b"],
                    year=st.session_state["year_b"],
                )
                synth_total, _ = generate_synthetic_load_profile(machine_set)

                # Align & compare
                synth_aligned, real_aligned = align_profiles(synth_total, real_series)

                if len(synth_aligned) == 0:
                    st.error("Keine überlappenden Zeitstempel gefunden. Stimmt das Referenzjahr?")
                    return

                report, dev_series = calculate_deviations(synth_aligned, real_aligned, threshold)

                stats_synth = calculate_summary_stats(synth_aligned)
                stats_real = calculate_summary_stats(real_aligned)
                rec = recommend_tariff(stats_real["annual_kwh"], stats_real["load_factor"], stats_real["peak_kw"])

                st.session_state["result_b"] = {
                    "synth": synth_aligned,
                    "real": real_aligned,
                    "dev": dev_series,
                    "report": report,
                    "stats_synth": stats_synth,
                    "stats_real": stats_real,
                    "rec": rec,
                    "machine_set": machine_set,
                }

            except Exception as e:
                st.error(f"Fehler bei der Analyse: {e}")
                return

    # --- Results ---
    if "result_b" in st.session_state:
        res = st.session_state["result_b"]

        st.markdown("---")
        st.markdown("### 📊 Vergleichsergebnisse")

        # KPI cards
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("MAPE", f"{res['report'].mape:.1f} %")
        c2.metric("Max. Abweichung", f"{res['report'].max_deviation_kw:.1f} kW")
        c3.metric("Unerklärte Grundlast", f"{res['report'].unexplained_base_load_kw:.1f} kW")
        c4.metric("Anomalie-Intervalle", f"{res['report'].anomaly_count:,}")

        # Summary stats side by side
        st.markdown("#### Kennzahlen im Vergleich")
        col_s, col_r = st.columns(2)
        with col_s:
            st.markdown("**Synthetisch (Typenschild)**")
            render_summary_cards(res["stats_synth"])
        with col_r:
            st.markdown("**Real (Lastgang)**")
            render_summary_cards(res["stats_real"])

        # Charts
        tab1, tab2 = st.tabs(["📈 Profilvergleich", "📊 Abweichungen"])
        with tab1:
            render_comparison_chart(res["synth"], res["real"])
        with tab2:
            render_deviation_chart(res["dev"])

        st.markdown("---")
        render_tariff_recommendation(res["rec"])

        # Export
        st.markdown("---")
        st.markdown("### 📥 Export")
        excel_buf = export_scenario_b_excel(
            res["synth"], res["real"], res["dev"],
            res["stats_synth"], res["stats_real"],
            res["report"], res["machine_set"], res["rec"],
        )
        st.download_button(
            label="📥 Vollständigen Bericht als Excel herunterladen",
            data=excel_buf,
            file_name=f"Vergleichsbericht_{res['machine_set'].plant_name}_{res['machine_set'].year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
