"""
app.py — Macro Terminal
"""

import streamlit as st

st.set_page_config(
    page_title="Macro Terminal",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

/* Base */
html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0d0d1a;
    color: #e8e8f0;
}

/* Hide streamlit chrome */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header    { visibility: hidden; }

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100%;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background-color: #08080f !important;
    border-right: 1px solid #1e1e3a !important;
    min-width: 220px !important;
    max-width: 220px !important;
}

[data-testid="stSidebar"] > div:first-child {
    padding: 0;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background-color: transparent;
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

/* ── Misc ── */
.stSpinner > div { border-top-color: #00d4ff !important; }
hr { border-color: #1e1e3a; }
[data-testid="stDataFrame"] {
    border: 1px solid #1e1e3a;
    border-radius: 6px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# ── Module registry ────────────────────────────────────────────────────────────
MODULES = {
    "GDP & Components":   {"module": "gdp",       "status": "live",  "icon": "📊"},
    "Labor Market":       {"module": "labor",      "status": "live",  "icon": "👷"},
    "Inflation":          {"module": "inflation",  "status": "soon",  "icon": "📈"},
    "Corporate Health":   {"module": "corporate",  "status": "soon",  "icon": "🏢"},
    "Leading Indicators": {"module": "leading",    "status": "soon",  "icon": "📡"},
}

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo
    st.markdown("""
    <div style="padding:24px 20px 20px 20px; border-bottom:1px solid #1e1e3a;">
        <div style="font-family:'IBM Plex Mono',monospace; font-size:1.1rem; font-weight:600; color:#00d4ff; letter-spacing:0.06em;">MACRO</div>
        <div style="font-family:'IBM Plex Mono',monospace; font-size:1.1rem; font-weight:300; color:#e8e8f0; letter-spacing:0.06em; margin-top:-2px;">TERMINAL</div>
    </div>
    <div style="padding:16px 20px 8px 20px;">
        <div style="font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:#3d3d5c; text-transform:uppercase; letter-spacing:0.18em;">Modules</div>
    </div>
    """, unsafe_allow_html=True)

    # Nav buttons — one per module
    if "selected_module" not in st.session_state:
        st.session_state.selected_module = "GDP & Components"

    for name, info in MODULES.items():
        is_active = st.session_state.selected_module == name
        is_live   = info["status"] == "live"

        active_style = "background:#12122a; color:#00d4ff; border-left:2px solid #00d4ff;" if is_active else "background:transparent; color:#9999bb; border-left:2px solid transparent;"
        muted_style  = "" if is_live else "opacity:0.45;"

        clicked = st.button(
            f"{info['icon']}  {name}",
            key=f"nav_{name}",
            use_container_width=True,
            disabled=not is_live,
        )
        if clicked:
            st.session_state.selected_module = name
            st.rerun()

    # Footer
    st.markdown("""
    <div style="position:absolute; bottom:0; left:0; right:0; padding:16px 20px; border-top:1px solid #1e1e3a;">
        <div style="font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:#3d3d5c; line-height:2;">
            BEA · BLS · FRED<br>
            <span style="color:#2a2a4a">Cache TTL: 1h</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Main area ──────────────────────────────────────────────────────────────────
selected = st.session_state.selected_module
info     = MODULES[selected]

# Page header
status_badge = (
    "<span style='font-size:0.65rem;color:#10b981;background:#0a2a1a;padding:3px 10px;border-radius:20px;border:1px solid #10b98140;font-family:monospace;'>LIVE</span>"
    if info["status"] == "live" else
    "<span style='font-size:0.65rem;color:#3d3d5c;background:#0d0d1a;padding:3px 10px;border-radius:20px;border:1px solid #1e1e3a;font-family:monospace;'>SOON</span>"
)

st.markdown(f"""
<div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
    <span style="font-family:'IBM Plex Mono',monospace; font-size:1.2rem; font-weight:600; color:#e8e8f0;">
        {info['icon']}  {selected}
    </span>
    {status_badge}
</div>
<div style="height:1px; background:linear-gradient(90deg,#1e1e3a 0%,transparent 80%); margin-bottom:20px;"></div>
""", unsafe_allow_html=True)

# ── Route to module ────────────────────────────────────────────────────────────
module_name = info["module"]

if module_name == "gdp":
    from modules.gdp import render
elif module_name == "labor":
    from modules.labor import render
elif module_name == "inflation":
    from modules.inflation import render
elif module_name == "corporate":
    from modules.corporate import render
elif module_name == "leading":
    from modules.leading import render
else:
    def render():
        st.info("Module not found.")

render()
