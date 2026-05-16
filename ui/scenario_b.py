"""
Streamlit UI for Scenario B — Comparison with real RLM data (Bestandskunde).

Allows uploading a real RLM load profile CSV, defining machines,
and comparing synthetic vs. measured load profiles.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.calculator import calculate_summary_stats, generate_synthetic_load_profile
from core.comparator import align_profiles, calculate_deviations, parse_rlm_csv
from core.config import DEVIATION_THRESHOLD_PCT, SAMPLE_MACHINES_WP
from core.models import Machine, MachineSet
from core.recommender import recommend_tariff
from ui.components import (
    render_annual_comparison_chart,
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
        st.session_state["machines_b"] = [dict(m) for m in SAMPLE_MACHINES_WP]
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

    if st.button("➕ Maschine hinzufügen", key="add_machine_b", width="stretch"):
        machines.append({
            "name": f"Neue Maschine {len(machines) + 1}",
            "rated_power_kw": 10.0,
            "operating_hours_per_day": 8.0,
            "days_per_week": 5,
            "simultaneity_factor": 1.0,
            "load_factor": 1.0,
            "start_hour": 6.0,
            "category": "production",
        })
        st.session_state["machines_b"] = machines
        st.rerun()

    updated: list[dict] = []
    categories = {"production": "Produktion", "auxiliary": "Hilfsbetrieb", "building_services": "Gebäudetechnik"}
    cat_keys = list(categories.keys())
    cat_labels = list(categories.values())

    for i, m in enumerate(machines):
        with st.expander(f"🔧 {m.get('name', f'Maschine {i+1}')}", expanded=False):
            btn1, btn2, _ = st.columns([1, 1, 4])
            with btn1:
                if st.button("🗑️ Löschen", key=f"del_b_{i}", use_container_width=True):
                    machines.pop(i)
                    st.session_state["machines_b"] = machines
                    st.rerun()
            with btn2:
                if st.button("📋 Kopieren", key=f"copy_b_{i}", use_container_width=True):
                    copy = dict(m)
                    copy["name"] = f"Kopie: {m.get('name', f'Maschine {i+1}')}"
                    machines.insert(i + 1, copy)
                    st.session_state["machines_b"] = machines
                    st.rerun()

            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Name", value=m.get("name", ""), key=f"bname_{i}")
                rated = st.number_input("Nennleistung (kW)", value=m.get("rated_power_kw", 10.0), min_value=0.1, max_value=10000.0, step=0.5, key=f"brated_{i}")
                hours = st.number_input("Betriebsstunden / Tag", value=m.get("operating_hours_per_day", 8.0), min_value=0.25, max_value=24.0, step=0.5, key=f"bhours_{i}")
                days = st.number_input("Betriebstage / Woche", value=m.get("days_per_week", 5), min_value=1, max_value=7, step=1, key=f"bdays_{i}")
            with c2:
                start = st.number_input("Startzeit (Uhr)", value=m.get("start_hour", 6.0), min_value=0.0, max_value=23.75, step=0.25, key=f"bstart_{i}")
                cat_idx = cat_keys.index(m.get("category", "production")) if m.get("category") in cat_keys else 0
                cat = st.selectbox("Kategorie", cat_labels, index=cat_idx, key=f"bcat_{i}")

            with st.expander("Erweiterte Einstellungen"):
                ec1, ec2 = st.columns(2)
                with ec1:
                    sim = st.slider("Gleichzeitigkeitsfaktor", 0.0, 1.0, m.get("simultaneity_factor", 1.0), 0.05, key=f"bsim_{i}",
                                    help="Anteil der Zeit, in der die Maschine während ihres Betriebsfensters tatsächlich läuft.")
                with ec2:
                    lf = st.slider("Lastfaktor", 0.0, 1.0, m.get("load_factor", 1.0), 0.05, key=f"blf_{i}",
                                   help="Durchschnittlicher Anteil der Nennleistung, der im Betrieb abgerufen wird.")

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
            help=(
                "Intervalle, bei denen die Abweichung zwischen synthetischem und realem Lastgang "
                "diesen Schwellenwert überschreitet, werden als Anomalien gezählt.\n\n"
                "Relevant erst bei MAPE < 30 % — bei großen strukturellen Modellabweichungen "
                "(z. B. Wärmepumpen ohne Saisonalität) sind fast alle Intervalle Anomalien."
            ),
        )

    # --- File upload ---
    st.markdown("#### 📂 RLM-Lastgang hochladen")
    uploaded_file = st.file_uploader(
        "CSV-Datei auswählen (15-min Intervalle)",
        type=["csv", "txt"],
        key="rlm_upload",
    )

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
                # Parse uploaded CSV (first pass without year filter to detect year)
                from io import BytesIO
                raw_bytes = BytesIO(uploaded_file.getvalue())
                real_series_full, fmt = parse_rlm_csv(raw_bytes, year=None)

                # Auto-detect year from CSV and update session state
                detected_year = int(pd.Series(real_series_full.index.year).mode()[0])
                if detected_year != st.session_state["year_b"]:
                    st.session_state["year_b"] = detected_year
                    st.info(f"📅 Jahr automatisch erkannt und auf **{detected_year}** gesetzt.")

                # Filter to detected year
                real_series = real_series_full[real_series_full.index.year == detected_year]
                st.info(f"📄 Format erkannt: {fmt} — {len(real_series):,} Datenpunkte geladen.")

                # Build machine set & synthetic profile (use detected year)
                machines = [Machine(**md) for md in machine_dicts]
                machine_set = MachineSet(
                    machines=machines,
                    plant_name=st.session_state["plant_name_b"],
                    industry_type=st.session_state["industry_b"],
                    year=detected_year,
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

        # KPI cards (2×2, mobile-first)
        c1, c2 = st.columns(2)
        c1.metric(
            "MAPE",
            f"{res['report'].mape:.1f} %",
            help=(
                "Mean Absolute Percentage Error — mittlere prozentuale Abweichung des synthetischen "
                "Profils vom realen Lastgang.\n\n"
                "Faustregeln: < 10 % sehr gut · 10–30 % akzeptabel · > 100 % strukturelle Modelllücke "
                "(z. B. fehlende Saisonalität bei Wärmepumpen)."
            ),
        )
        c2.metric("Max. Abweichung", f"{res['report'].max_deviation_kw:.1f} kW")
        c3, c4 = st.columns(2)
        c3.metric("Grundlast (unerklärte)", f"{res['report'].unexplained_base_load_kw:.1f} kW")
        c4.metric("Anomalie-Intervalle", f"{res['report'].anomaly_count:,}")

        # Summary stats — stacked for mobile, side-by-side on wider screens
        st.markdown("#### Kennzahlen im Vergleich")
        st.markdown("**Real (Lastgang)**")
        render_summary_cards(res["stats_real"])
        with st.expander("Synthetisch (Typenschild) — Kennzahlen anzeigen"):
            render_summary_cards(res["stats_synth"])

        # Charts
        tab1, tab2 = st.tabs(["📈 Profilvergleich", "📊 Abweichungen"])
        with tab1:
            render_annual_comparison_chart(res["synth"], res["real"])
            with st.expander("🔍 Wochendetail (repräsentative Woche)"):
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
