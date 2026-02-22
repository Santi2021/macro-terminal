"""
app.py — Macro Terminal
Personal Bloomberg-style macro dashboard · Streamlit Cloud

Run locally:
    streamlit run app.py
"""

import streamlit as st
import os

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Macro Terminal",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global styles ──────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

    /* ── Base ── */
    html, body, [class*="css"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .stApp {
        background-color: #0d0d1a;
        color: #e8e8f0;
    }

    /* ── Hide Streamlit chrome ── */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: #0a0a18 !important;
        border-right: 1px solid #1e1e3a;
    }
    [data-testid="stSidebar"] * { color: #e8e8f0 !important; }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #0d0d1a;
        border-bottom: 1px solid #1e1e3a;
        gap: 0;
    }
    .stTabs [data-baseweb="tab"] {
        color: #6b6b8a !important;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem;
        padding: 8px 16px;
        border-radius: 0;
        background: transparent;
    }
    .stTabs [aria-selected="true"] {
        color: #00d4ff !important;
        border-bottom: 2px solid #00d4ff !important;
        background: transparent !important;
    }

    /* ── Spinner ── */
    .stSpinner > div { border-top-color: #00d4ff !important; }

    /* ── DataFrames ── */
    .dataframe { background-color: #13132b !important; }
    [data-testid="stDataFrame"] { border: 1px solid #1e1e3a; border-radius: 6px; overflow: hidden; }

    /* ── Sidebar nav button ── */
    .nav-btn {
        display: block;
        width: 100%;
        padding: 10px 16px;
        margin: 2px 0;
        background: transparent;
        border: none;
        border-radius: 6px;
        color: #9999bb;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.8rem;
        text-align: left;
        cursor: pointer;
        transition: all 0.15s ease;
    }
    .nav-btn:hover   { background: #1e1e3a; color: #e8e8f0; }
    .nav-btn.active  { background: #1a1a3a; color: #00d4ff; border-left: 2px solid #00d4ff; }

    /* ── Divider ── */
    hr { border-color: #1e1e3a; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Module registry ────────────────────────────────────────────────────────────
MODULES = {
    "GDP & Components":      {"icon": "📊", "module": "gdp",       "status": "live"},
    "Inflation":             {"icon": "📈", "module": "inflation",  "status": "soon"},
    "Labor Market":          {"icon": "👷", "module": "labor",      "status": "soon"},
    "Corporate Health":      {"icon": "🏢", "module": "corporate",  "status": "soon"},
    "Leading Indicators":    {"icon": "📡", "module": "leading",    "status": "soon"},
}

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo / Header
    st.markdown(
        """
        <div style="padding: 12px 4px 20px 4px;">
            <div style="font-family:'IBM Plex Mono',monospace; font-size:1.15rem; font-weight:600;
                        color:#00d4ff; letter-spacing:0.05em;">MACRO</div>
            <div style="font-family:'IBM Plex Mono',monospace; font-size:1.15rem; font-weight:300;
                        color:#e8e8f0; letter-spacing:0.05em; margin-top:-4px;">TERMINAL</div>
            <div style="font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:#6b6b8a;
                        margin-top:6px; letter-spacing:0.1em;">US MACRO DASHBOARD</div>
        </div>
        <hr style="margin:0 0 12px 0">
        """,
        unsafe_allow_html=True,
    )

    # Navigation
    st.markdown(
        '<div style="font-family:IBM Plex Mono,monospace; font-size:0.62rem; color:#6b6b8a; '
        'text-transform:uppercase; letter-spacing:0.15em; margin-bottom:8px;">Modules</div>',
        unsafe_allow_html=True,
    )

    if "active_module" not in st.session_state:
        st.session_state.active_module = "GDP & Components"

    for name, info in MODULES.items():
        is_active = st.session_state.active_module == name
        status_tag = (
            '<span style="font-size:0.6rem; color:#10b981; margin-left:6px;">●</span>'
            if info["status"] == "live"
            else '<span style="font-size:0.6rem; color:#3d3d5c; margin-left:6px;">○</span>'
        )
        label = f'{info["icon"]} {name}{status_tag}'
        btn_style = (
            "background:#1a1a3a; color:#00d4ff; border-left:2px solid #00d4ff;"
            if is_active
            else ""
        )

        if st.button(
            f'{info["icon"]}  {name}',
            key=f"nav_{name}",
            use_container_width=True,
        ):
            st.session_state.active_module = name
            st.rerun()

    # Footer info
    st.markdown(
        """
        <hr style="margin:20px 0 12px 0">
        <div style="font-family:'IBM Plex Mono',monospace; font-size:0.62rem; color:#3d3d5c; line-height:1.8;">
            Sources<br>
            <span style="color:#6b6b8a">BEA</span> · NIPA Tables<br>
            <span style="color:#6b6b8a">FRED</span> · St. Louis Fed<br>
            <span style="color:#6b6b8a">BLS</span> · Bureau of Labor Stats<br>
            <br>
            Cache TTL: 1 hour
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Main area ──────────────────────────────────────────────────────────────────
active = st.session_state.active_module
info   = MODULES[active]

# Module header
st.markdown(
    f"""
    <div style="display:flex; align-items:baseline; gap:12px; margin-bottom:4px;">
        <span style="font-family:'IBM Plex Mono',monospace; font-size:1.4rem; font-weight:600;
                     color:#e8e8f0;">{info['icon']} {active}</span>
        {"<span style='font-family:IBM Plex Mono,monospace; font-size:0.65rem; color:#10b981; "
         "background:#0a2a1a; padding:3px 8px; border-radius:20px; border:1px solid #10b98140;'>LIVE</span>"
         if info['status'] == 'live' else
         "<span style='font-family:IBM Plex Mono,monospace; font-size:0.65rem; color:#6b6b8a; "
         "background:#13132b; padding:3px 8px; border-radius:20px; border:1px solid #2a2a4a;'>COMING SOON</span>"}
    </div>
    <div style="height:1px; background:linear-gradient(90deg, #1e1e3a 0%, transparent 100%);
                margin-bottom:20px;"></div>
    """,
    unsafe_allow_html=True,
)

# Lazy load the active module
module_name = info["module"]
if module_name == "gdp":
    from modules.gdp import render
elif module_name == "inflation":
    from modules.inflation import render
elif module_name == "labor":
    from modules.labor import render
elif module_name == "corporate":
    from modules.corporate import render
elif module_name == "leading":
    from modules.leading import render
else:
    def render():
        st.info("Module not found.")

render()
