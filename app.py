"""
app.py — Macro Terminal · Top nav bar
"""

import streamlit as st

st.set_page_config(
    page_title="Macro Terminal",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0d0d1a;
    color: #e8e8f0;
}

#MainMenu, footer, header { visibility: hidden; }

.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 2rem;
    max-width: 100%;
}

[data-testid="collapsedControl"] { display: none !important; }

.stTabs [data-baseweb="tab-list"] {
    background-color: #08080f;
    border-bottom: 1px solid #1e1e3a;
    gap: 0;
    padding: 0 16px;
}
.stTabs [data-baseweb="tab"] {
    color: #6b6b8a !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.78rem !important;
    font-weight: 400;
    padding: 14px 20px !important;
    border-radius: 0 !important;
    background: transparent !important;
    border: none !important;
    letter-spacing: 0.05em;
}
.stTabs [aria-selected="true"] {
    color: #00d4ff !important;
    border-bottom: 2px solid #00d4ff !important;
    background: transparent !important;
    font-weight: 600 !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #e8e8f0 !important;
    background: #13132b !important;
}
.stTabs [data-baseweb="tab-panel"] {
    padding: 0 !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab-border"] { display: none !important; }

.stSpinner > div { border-top-color: #00d4ff !important; }

[data-testid="stDataFrame"] {
    border: 1px solid #1e1e3a;
    border-radius: 6px;
    overflow: hidden;
}

hr { border-color: #1e1e3a; }
</style>
""", unsafe_allow_html=True)

# ── Top bar ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="
    display: flex;
    align-items: center;
    gap: 32px;
    padding: 12px 24px;
    background: #08080f;
    border-bottom: 1px solid #1e1e3a;
    margin-bottom: 0;
">
    <div>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:1rem; font-weight:600; color:#00d4ff; letter-spacing:0.08em;">MACRO</span>
        <span style="font-family:'IBM Plex Mono',monospace; font-size:1rem; font-weight:300; color:#e8e8f0; letter-spacing:0.08em; margin-left:4px;">TERMINAL</span>
    </div>
    <div style="font-family:'IBM Plex Mono',monospace; font-size:0.6rem; color:#3d3d5c; letter-spacing:0.15em;">
        BEA · BLS · FRED
    </div>
</div>
""", unsafe_allow_html=True)

# ── Navigation ─────────────────────────────────────────────────────────────────
MODULES = [
    ("📊  GDP & Components",   "gdp",       True),
    ("👷  Labor Market",       "labor",     True),
    ("📈  Inflation",          "inflation", True),
    ("🏢  Corporate Health",   "corporate", False),
    ("📡  Leading Indicators", "leading",   False),
]

tabs = st.tabs([m[0] for m in MODULES])

for tab, (label, module_name, is_live) in zip(tabs, MODULES):
    with tab:
        if not is_live:
            icon = label.strip().split()[0]
            name = label.strip().split("  ", 1)[-1]
            st.markdown(f"""
            <div style="display:flex; flex-direction:column; align-items:center;
                        justify-content:center; height:400px;
                        font-family:'IBM Plex Mono',monospace;">
                <div style="font-size:2.5rem; margin-bottom:16px;">{icon}</div>
                <div style="font-size:1rem; color:#e8e8f0;">{name}</div>
                <div style="font-size:0.78rem; margin-top:8px; color:#3d3d5c;">Coming soon</div>
            </div>
            """, unsafe_allow_html=True)
            continue

        if module_name == "gdp":
            from modules.gdp import render as render_gdp
            render_gdp()
        elif module_name == "labor":
            from modules.labor import render as render_labor
            render_labor()
        elif module_name == "inflation":
            from modules.inflation import render as render_inflation
            render_inflation()
