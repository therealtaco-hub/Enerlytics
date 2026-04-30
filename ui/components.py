"""
Reusable Streamlit UI components for charts, tables and KPI cards.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.models import TariffRecommendation, TariffType


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
COLORS = {
    "primary": "#00843D",
    "secondary": "#16a34a",
    "accent": "#22d3ee",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "bg_card": "rgba(255,255,255,0.05)",
    "grid": "rgba(255,255,255,0.08)",
    "text": "#e2e8f0",
    "text_muted": "#94a3b8",
}

MACHINE_COLORS = [
    "#00843D", "#22d3ee", "#f59e0b", "#ef4444",
    "#8b5cf6", "#ec4899", "#14b8a6", "#f97316",
]


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

def render_summary_cards(stats: dict) -> None:
    """Display key metrics as Streamlit metric cards."""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Spitzenlast", f"{stats['peak_kw']:.1f} kW")
    c2.metric("Grundlast", f"{stats['base_kw']:.1f} kW")
    c3.metric("Jahresverbrauch", f"{stats['annual_kwh']:,.0f} kWh")
    c4.metric("Last-Faktor", f"{stats['load_factor']:.1%}")


# ---------------------------------------------------------------------------
# Tariff recommendation
# ---------------------------------------------------------------------------

def render_tariff_recommendation(rec: TariffRecommendation) -> None:
    """Render the tariff recommendation as a styled info block."""
    icon = "⚡" if rec.recommended_tariff == TariffType.RLM else "📊"
    label = "RLM (Registrierende Leistungsmessung)" if rec.recommended_tariff == TariffType.RLM else "SLP (Standardlastprofil)"

    st.markdown(f"### {icon} Tarifempfehlung: **{label}**")

    if rec.load_shifting_recommended:
        st.warning("⚠️ Lastverschiebung wird empfohlen, um Leistungsspitzen zu reduzieren.")

    for r in rec.reasoning:
        st.markdown(f"- {r}")


# ---------------------------------------------------------------------------
# Weekly profile chart
# ---------------------------------------------------------------------------

def render_weekly_profile_chart(
    profile: pd.Series,
    per_machine: Optional[dict[str, pd.Series]] = None,
    title: str = "Synthetisches Wochenlastprofil",
) -> None:
    """
    Plotly line chart showing a representative week (Monday-Sunday).
    If per_machine is provided, shows stacked area per machine.
    """
    # Extract one representative week (second full week to avoid edge effects)
    week_start_idx = 7 * 96  # start of second week
    week_end_idx = week_start_idx + 7 * 96

    if len(profile) < week_end_idx:
        week_start_idx = 0
        week_end_idx = min(7 * 96, len(profile))

    week_data = profile.iloc[week_start_idx:week_end_idx]

    day_labels = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    hours = []
    for d in range(7):
        for q in range(96):
            h = q / 4
            hours.append(f"{day_labels[d]} {int(h):02d}:{int((h % 1) * 60):02d}")

    fig = go.Figure()

    if per_machine:
        for i, (name, series) in enumerate(per_machine.items()):
            week_m = series.iloc[week_start_idx:week_end_idx]
            fig.add_trace(go.Scatter(
                x=list(range(len(week_m))),
                y=week_m.values,
                name=name,
                stackgroup="one",
                line=dict(width=0.5),
                fillcolor=MACHINE_COLORS[i % len(MACHINE_COLORS)],
            ))
    else:
        fig.add_trace(go.Scatter(
            x=list(range(len(week_data))),
            y=week_data.values,
            name="Gesamtlast",
            fill="tozeroy",
            line=dict(color=COLORS["primary"], width=2),
        ))

    # Add day separators
    for d in range(1, 7):
        fig.add_vline(x=d * 96, line_dash="dot", line_color=COLORS["grid"], opacity=0.5)

    tick_positions = [d * 96 + 48 for d in range(7)]
    fig.update_layout(
        title=title,
        xaxis=dict(
            tickmode="array",
            tickvals=tick_positions,
            ticktext=day_labels,
            title="Wochentag",
        ),
        yaxis=dict(title="Leistung (kW)"),
        template="plotly_dark",
        height=450,
        legend=dict(orientation="h", y=-0.15),
        margin=dict(l=60, r=20, t=50, b=60),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------------------
# Annual heatmap
# ---------------------------------------------------------------------------

def render_annual_heatmap(
    profile: pd.Series,
    title: str = "Jahreslastgang (Heatmap)",
) -> None:
    """
    Plotly heatmap: rows = days of year, columns = 15-min intervals (96),
    color = kW.
    """
    n_days = len(profile) // 96
    matrix = profile.values[:n_days * 96].reshape(n_days, 96)

    hour_labels = [f"{h:02d}:00" for h in range(24)]
    tick_positions = list(range(0, 96, 4))

    # Month labels for y-axis
    month_starts = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    month_names = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]

    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        colorscale=[
            [0, "#0f172a"],
            [0.2, "#1e3a5f"],
            [0.4, "#00843D"],
            [0.6, "#16a34a"],
            [0.8, "#f59e0b"],
            [1.0, "#ef4444"],
        ],
        colorbar=dict(title="kW"),
    ))

    fig.update_layout(
        title=title,
        xaxis=dict(
            tickmode="array",
            tickvals=tick_positions,
            ticktext=hour_labels,
            title="Uhrzeit",
        ),
        yaxis=dict(
            tickmode="array",
            tickvals=month_starts,
            ticktext=month_names,
            title="Monat",
            autorange="reversed",
        ),
        template="plotly_dark",
        height=500,
        margin=dict(l=60, r=20, t=50, b=60),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------------------
# Comparison chart (Scenario B)
# ---------------------------------------------------------------------------

def render_comparison_chart(
    synthetic: pd.Series,
    real: pd.Series,
    title: str = "Synthetisch vs. Real (Wochenansicht)",
) -> None:
    """Side-by-side overlay of synthetic and real load profiles (one week)."""
    week_start = 7 * 96
    week_end = week_start + 7 * 96

    if len(synthetic) < week_end or len(real) < week_end:
        week_start = 0
        week_end = min(7 * 96, len(synthetic), len(real))

    day_labels = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=list(range(week_end - week_start)),
        y=synthetic.iloc[week_start:week_end].values,
        name="Synthetisch (Typenschild)",
        line=dict(color=COLORS["primary"], width=2),
    ))

    fig.add_trace(go.Scatter(
        x=list(range(week_end - week_start)),
        y=real.iloc[week_start:week_end].values,
        name="Real (Lastgang)",
        line=dict(color=COLORS["accent"], width=2),
    ))

    for d in range(1, 7):
        fig.add_vline(x=d * 96, line_dash="dot", line_color=COLORS["grid"], opacity=0.5)

    tick_positions = [d * 96 + 48 for d in range(7)]
    fig.update_layout(
        title=title,
        xaxis=dict(tickmode="array", tickvals=tick_positions, ticktext=day_labels, title="Wochentag"),
        yaxis=dict(title="Leistung (kW)"),
        template="plotly_dark",
        height=450,
        legend=dict(orientation="h", y=-0.15),
        margin=dict(l=60, r=20, t=50, b=60),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------------------
# Deviation bar chart
# ---------------------------------------------------------------------------

def render_deviation_chart(
    deviation: pd.Series,
    title: str = "Stündliche Durchschnittsabweichung",
) -> None:
    """Bar chart of hourly average absolute deviations."""
    hourly = deviation.abs().groupby(deviation.index.hour).mean()

    colors = [COLORS["primary"] if v < hourly.mean() else COLORS["warning"] for v in hourly.values]

    fig = go.Figure(go.Bar(
        x=[f"{h:02d}:00" for h in hourly.index],
        y=hourly.values,
        marker_color=colors,
    ))

    fig.update_layout(
        title=title,
        xaxis=dict(title="Stunde"),
        yaxis=dict(title="Ø Abweichung (kW)"),
        template="plotly_dark",
        height=350,
        margin=dict(l=60, r=20, t=50, b=60),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, width="stretch")
