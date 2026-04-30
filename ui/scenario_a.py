"""
Streamlit UI for Scenario A — Synthetic Load Profile (Neukunde).

Allows the user to define machines via nameplate data and generates
a bottom-up synthetic load profile with charts, KPIs and export.
"""

from __future__ import annotations

import streamlit as st

from core.calculator import calculate_summary_stats, generate_synthetic_load_profile
from core.config import SAMPLE_MACHINES
from core.models import Machine, MachineCategory, MachineSet
from core.recommender import recommend_tariff
from ui.components import (
    render_annual_heatmap,
    render_summary_cards,
    render_tariff_recommendation,
    render_weekly_profile_chart,
)
from utils.export import export_scenario_a_excel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_session_state() -> None:
    """Ensure session-state keys exist."""
    if "machines_a" not in st.session_state:
        st.session_state["machines_a"] = [dict(m) for m in SAMPLE_MACHINES]
    if "plant_name_a" not in st.session_state:
        st.session_state["plant_name_a"] = "Musterbetrieb Metallverarbeitung"
    if "industry_a" not in st.session_state:
        st.session_state["industry_a"] = "Metallverarbeitung"
    if "year_a" not in st.session_state:
        st.session_state["year_a"] = 2025


def _machine_editor() -> list[dict]:
    """Render the machine input form and return updated machine dicts."""
    machines = st.session_state["machines_a"]

    st.markdown("#### ⚙️ Verbraucher (Maschinen)")
    st.caption("Fügen Sie alle elektrischen Verbraucher mit ihren Typenschilddaten hinzu.")

    # Add / remove buttons
    col_add, col_remove, _ = st.columns([1, 1, 3])
    with col_add:
        if st.button("➕ Maschine hinzufügen", key="add_machine_a", width="stretch"):
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
            st.session_state["machines_a"] = machines
            st.rerun()
    with col_remove:
        if len(machines) > 1:
            if st.button("➖ Letzte entfernen", key="remove_machine_a", width="stretch"):
                machines.pop()
                st.session_state["machines_a"] = machines
                st.rerun()

    updated: list[dict] = []
    categories = {"production": "Produktion", "auxiliary": "Hilfsbetrieb", "building_services": "Gebäudetechnik"}
    cat_keys = list(categories.keys())
    cat_labels = list(categories.values())

    for i, m in enumerate(machines):
        with st.expander(f"🔧 {m.get('name', f'Maschine {i+1}')}", expanded=(i < 2)):
            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("Name", value=m.get("name", ""), key=f"name_{i}")
                rated = st.number_input("Nennleistung (kW)", value=m.get("rated_power_kw", 10.0), min_value=0.1, max_value=10000.0, step=0.5, key=f"rated_{i}")
                hours = st.number_input("Betriebsstunden / Tag", value=m.get("operating_hours_per_day", 8.0), min_value=0.25, max_value=24.0, step=0.5, key=f"hours_{i}")
                days = st.number_input("Betriebstage / Woche", value=m.get("days_per_week", 5), min_value=1, max_value=7, step=1, key=f"days_{i}")
            with c2:
                sim = st.slider("Gleichzeitigkeitsfaktor", 0.0, 1.0, m.get("simultaneity_factor", 0.8), 0.05, key=f"sim_{i}")
                lf = st.slider("Lastfaktor", 0.0, 1.0, m.get("load_factor", 0.7), 0.05, key=f"lf_{i}")
                start = st.number_input("Startzeit (Uhr)", value=m.get("start_hour", 6.0), min_value=0.0, max_value=23.75, step=0.25, key=f"start_{i}")
                cat_idx = cat_keys.index(m.get("category", "production")) if m.get("category") in cat_keys else 0
                cat = st.selectbox("Kategorie", cat_labels, index=cat_idx, key=f"cat_{i}")

            eff = rated * sim * lf
            st.caption(f"Effektive Leistung: **{eff:.1f} kW** | Geschätzter Jahresverbrauch: **{eff * hours * days * 52:,.0f} kWh**")

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

    st.session_state["machines_a"] = updated
    return updated


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_scenario_a() -> None:
    """Render the full Scenario A page."""
    _init_session_state()

    st.markdown(
        """
        ## 📋 Szenario A — Synthetisches Lastprofil (Neukunde)
        Erstellen Sie ein synthetisches Lastprofil auf Basis der Typenschilddaten
        Ihrer Verbraucher. Das Tool berechnet den geschätzten Jahresverbrauch
        und empfiehlt den passenden Tarif.
        """
    )

    # --- Sidebar: Plant info ---
    with st.sidebar:
        st.markdown("### 🏭 Betriebsdaten")
        st.session_state["plant_name_a"] = st.text_input(
            "Betriebsname",
            value=st.session_state["plant_name_a"],
            key="plant_input_a",
        )
        st.session_state["industry_a"] = st.text_input(
            "Branche",
            value=st.session_state["industry_a"],
            key="industry_input_a",
        )
        st.session_state["year_a"] = st.number_input(
            "Referenzjahr",
            value=st.session_state["year_a"],
            min_value=2000,
            max_value=2100,
            key="year_input_a",
        )

    # --- Machine editor ---
    machine_dicts = _machine_editor()

    st.divider()

    # --- Calculate ---
    if st.button("🔄 Lastprofil berechnen", type="primary", width="stretch", key="calc_a"):
        with st.spinner("Berechnung läuft..."):
            try:
                machines = [Machine(**md) for md in machine_dicts]
                machine_set = MachineSet(
                    machines=machines,
                    plant_name=st.session_state["plant_name_a"],
                    industry_type=st.session_state["industry_a"],
                    year=st.session_state["year_a"],
                )

                total, per_machine = generate_synthetic_load_profile(machine_set)
                stats = calculate_summary_stats(total)
                rec = recommend_tariff(stats["annual_kwh"], stats["load_factor"], stats["peak_kw"])

                # Store in session state for persistence
                st.session_state["result_a"] = {
                    "total": total,
                    "per_machine": per_machine,
                    "stats": stats,
                    "rec": rec,
                    "machine_set": machine_set,
                }
            except Exception as e:
                st.error(f"Fehler bei der Berechnung: {e}")
                return

    # --- Display results ---
    if "result_a" in st.session_state:
        res = st.session_state["result_a"]

        st.markdown("---")
        st.markdown("### 📊 Ergebnisse")

        render_summary_cards(res["stats"])

        tab1, tab2 = st.tabs(["📈 Wochenprofil", "🗺️ Jahres-Heatmap"])
        with tab1:
            render_weekly_profile_chart(res["total"], res["per_machine"])
        with tab2:
            render_annual_heatmap(res["total"])

        st.markdown("---")
        render_tariff_recommendation(res["rec"])

        # --- Export ---
        st.markdown("---")
        st.markdown("### 📥 Export")
        excel_buf = export_scenario_a_excel(
            res["total"],
            res["per_machine"],
            res["stats"],
            res["machine_set"],
            res["rec"],
        )
        st.download_button(
            label="📥 Als Excel herunterladen",
            data=excel_buf,
            file_name=f"Lastprofil_{res['machine_set'].plant_name}_{res['machine_set'].year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
