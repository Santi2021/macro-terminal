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

html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
.stApp { background-color: #0d0d1a; color: #e8e8f0; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }

[data-testid="stSidebar"] {
    background-color: #0a0a18 !important;
    border-right: 1px solid #1e1e3a;
}
[data-testid="stSidebar"] * { color: #e8e8f0 !important; }

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
.stSpinner > div { border-top-color: #00d4ff !important; }
[data-testid="stDataFrame"] { border: 1px solid #1e1e3a; border-radius: 6px; overflow: hidden; }

/* Force sidebar radio buttons to look like nav */
[data-testid="stSidebar"] .stRadio label {
    display: block;
    width: 100%;
    padding: 9px 16px;
    margin: 2px 0;
    background: transparent;
    border-radius: 6px;
    color: #9999bb !important;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.82rem;
    cursor: pointer;
    transition: all 0.15s ease;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: #1e1e3a;
    color: #e8e8f0 !important;
}
[data-testid="stSidebar"] .stRadio [aria-checked="true"] + label,
[data-testid="stSidebar"] .stRadio input:checked ~ label {
    background: #1a1a3a;
    color: #00d4ff !important;
    border-left: 2px solid #00d4ff;
}
[data-testid="stSidebar"] .stRadio > div { gap: 0; }
[data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] { display: none; }
hr { border-color: #1e1e3a; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
section[data-testid="stSidebar"] { transform: none !important; min-width: 250px !important; }
</style>
""", unsafe_allow_html=True)

MODULES = {
    "📊  GDP & Components":   {"module": "gdp",       "status": "live"},
    "📈  Inflation":          {"module": "inflation",  "status": "soon"},
    "👷  Labor Market":       {"module": "labor",      "status": "soon"},
    "🏢  Corporate Health":   {"module": "corporate",  "status": "soon"},
    "📡  Leading Indicators": {"module": "leading",    "status": "soon"},
}

with st.sidebar:
    st.markdown("""
    <div style="padding:12px 4px 20px 4px;">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:1.15rem;font-weight:600;color:#00d4ff;letter-spacing:0.05em;">MACRO</div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:1.15rem;font-weight:300;color:#e8e8f0;letter-spacing:0.05em;margin-top:-4px;">TERMINAL</div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;color:#6b6b8a;margin-top:6px;letter-spacing:0.1em;">US MACRO DASHBOARD</div>
    </div>
    <hr style="margin:0 0 12px 0">
    <div style="font-family:IBM Plex Mono,monospace;font-size:0.62rem;color:#6b6b8a;text-transform:uppercase;letter-spacing:0.15em;margin-bottom:8px;padding-left:4px;">Modules</div>
    """, unsafe_allow_html=True)

    module_names = list(MODULES.keys())
    selected = st.radio(
        "nav",
        options=module_names,
        index=0,
        label_visibility="collapsed",
    )

    st.markdown("""
    <hr style="margin:20px 0 12px 0">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.62rem;color:#3d3d5c;line-height:1.8;padding-left:4px;">
        Sources<br>
        <span style="color:#6b6b8a">BEA</span> · NIPA Tables<br>
        <span style="color:#6b6b8a">FRED</span> · St. Louis Fed<br>
        <span style="color:#6b6b8a">BLS</span> · Bureau of Labor Stats<br>
        <br>Cache TTL: 1 hour
    </div>
    """, unsafe_allow_html=True)

# ── Main area ──────────────────────────────────────────────────────────────────
info   = MODULES[selected]
status = info["status"]

name_clean = selected.split("  ", 1)[-1]  # remove emoji prefix

st.markdown(f"""
<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:4px;">
    <span style="font-family:'IBM Plex Mono',monospace;font-size:1.4rem;font-weight:600;color:#e8e8f0;">{name_clean}</span>
    {"<span style='font-family:IBM Plex Mono,monospace;font-size:0.65rem;color:#10b981;background:#0a2a1a;padding:3px 8px;border-radius:20px;border:1px solid #10b98140;'>LIVE</span>"
     if status == "live" else
     "<span style='font-family:IBM Plex Mono,monospace;font-size:0.65rem;color:#6b6b8a;background:#13132b;padding:3px 8px;border-radius:20px;border:1px solid #2a2a4a;'>COMING SOON</span>"}
</div>
<div style="height:1px;background:linear-gradient(90deg,#1e1e3a 0%,transparent 100%);margin-bottom:20px;"></div>
""", unsafe_allow_html=True)

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
