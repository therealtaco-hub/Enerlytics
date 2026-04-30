"""
Lastgang vs. Typenschild — Streamlit Entry Point.

VR Energieservice GmbH — Energieberatungs-Tool
"""

import streamlit as st

# ---------------------------------------------------------------------------
# Page config (MUST be the first Streamlit command)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Lastgang vs. Typenschild — VR Energieservice",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS for premium look
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* -- Global font -- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* -- Header bar -- */
    .main-header {
        background: linear-gradient(135deg, #00843D 0%, #16a34a 50%, #22d3ee 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 132, 61, 0.3);
    }

    .main-header h1 {
        color: white;
        font-weight: 700;
        font-size: 1.8rem;
        margin: 0;
        letter-spacing: -0.02em;
    }

    .main-header p {
        color: rgba(255, 255, 255, 0.85);
        font-size: 0.95rem;
        margin: 0.3rem 0 0 0;
    }

    /* -- Metric cards -- */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(0,132,61,0.1), rgba(22,163,74,0.05));
        border: 1px solid rgba(0,132,61,0.2);
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    [data-testid="stMetricValue"] {
        font-weight: 600;
        color: #00843D;
    }

    /* -- Buttons -- */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #00843D, #16a34a);
        border: none;
        font-weight: 600;
        letter-spacing: 0.02em;
        transition: all 0.3s ease;
        box-shadow: 0 2px 10px rgba(0,132,61,0.3);
    }

    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 4px 20px rgba(0,132,61,0.5);
        transform: translateY(-1px);
    }

    /* -- Download button -- */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #1e3a5f, #2563eb);
        border: none;
        color: white;
        font-weight: 500;
        border-radius: 8px;
    }

    /* -- Expanders -- */
    .streamlit-expanderHeader {
        font-weight: 600;
        font-size: 0.95rem;
    }

    /* -- Tabs -- */
    .stTabs [data-baseweb="tab"] {
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        border-bottom-color: #00843D;
    }

    /* -- Sidebar -- */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }

    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #22d3ee;
    }

    /* -- Dividers -- */
    hr {
        border-color: rgba(0,132,61,0.2);
    }

    /* -- Hide Streamlit branding -- */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="main-header">
    <h1>⚡ Lastgang vs. Typenschild</h1>
    <p>VR Energieservice GmbH — Energieberatung & Tarifoptimierung</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Scenario selector
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔀 Szenario wählen")
    scenario = st.radio(
        "Analyse-Typ",
        options=["Szenario A — Neukunde", "Szenario B — Bestandskunde"],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("---")

# ---------------------------------------------------------------------------
# Route to the selected scenario
# ---------------------------------------------------------------------------
if scenario == "Szenario A — Neukunde":
    from ui.scenario_a import render_scenario_a
    render_scenario_a()
else:
    from ui.scenario_b import render_scenario_b
    render_scenario_b()
