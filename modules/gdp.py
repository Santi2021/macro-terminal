"""
modules/gdp.py — GDP & Components module for Macro Terminal

Renders:
  1. Headline KPIs
  2. Contributions to Real GDP Growth (stacked bar + diamond line)
  3. Five drill-down charts (Consumption, Investment, Government, Net Exports, Final Sales)
  4. Last-8Q heatmap table
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.bea import fetch_nipa

# ── Color palette ──────────────────────────────────────────────────────────────
BG       = "#0d0d1a"
BG2      = "#13132b"
GRID     = "#1e1e3a"
TEXT     = "#e8e8f0"
MUTED    = "#6b6b8a"
ACCENT   = "#00d4ff"

COLORS = {
    "consumption":  "#3b82f6",   # blue
    "investment":   "#10b981",   # emerald
    "government":   "#f59e0b",   # amber
    "net_exports":  "#ef4444",   # red
    "gdp_line":     "#ffffff",
    # Consumption sub
    "durables":     "#60a5fa",
    "nondurables":  "#93c5fd",
    "services":     "#1d4ed8",
    # Investment sub
    "residential":  "#34d399",
    "nonresidential":"#6ee7b7",
    "inventories":  "#065f46",
    # Government sub
    "federal":      "#fbbf24",
    "state_local":  "#78350f",
    # Trade sub
    "exports":      "#4ade80",
    "imports":      "#f87171",
    # Final Sales sub
    "final_sales":  "#a78bfa",
    "inventories2": "#7c3aed",
}

# ── Series codes in T10102 ─────────────────────────────────────────────────────
# (These are contribution-to-growth series, annualized)
SERIES = {
    "gdp":               "A191RX",   # Real GDP growth
    "consumption":       "DPCERC",   # PCE contribution
    "durables":          "DDURRC",
    "nondurables":       "DNDGRC",
    "services":          "DSERRC",
    "investment":        "A006RC",   # Gross private domestic investment contribution
    "residential":       "A011RC",
    "nonresidential":    "A008RC",
    "inventories":       "A014RC",
    "government":        "A822RC",
    "federal":           "A823RC",
    "state_local":       "A829RC",
    "net_exports":       "A019RC",
    "exports":           "B020RC",
    "imports":           "B021RC",
    "final_sales":       "A180RC",   # Final sales to domestic purchasers contribution
}

PLOT_LAYOUT = dict(
    paper_bgcolor=BG,
    plot_bgcolor=BG2,
    font=dict(family="'IBM Plex Mono', monospace", color=TEXT, size=11),
    xaxis=dict(gridcolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED)),
    yaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=True,
               zerolinecolor="#ffffff30", ticksuffix=" pp"),
    legend=dict(bgcolor="#00000000", font=dict(color=TEXT, size=10),
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    hovermode="x unified",
    margin=dict(l=50, r=20, t=60, b=40),
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_data() -> pd.DataFrame:
    """Fetch T10102 and return full DataFrame."""
    return fetch_nipa("T10102", frequency="Q", year="ALL")


def get_series_values(df: pd.DataFrame, code: str) -> pd.Series:
    mask = df["SeriesCode"] == code
    s = df[mask].set_index("Date")["DataValue"].sort_index()
    return s


def render():
    """Entry point called by app.py."""

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
        .kpi-card {
            background: #13132b;
            border: 1px solid #1e1e3a;
            border-radius: 8px;
            padding: 16px 20px;
            text-align: center;
        }
        .kpi-value { font-family: 'IBM Plex Mono', monospace; font-size: 2rem; font-weight: 600; }
        .kpi-label { font-family: 'IBM Plex Sans', sans-serif; font-size: 0.75rem;
                     color: #6b6b8a; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 4px; }
        .kpi-delta { font-family: 'IBM Plex Mono', monospace; font-size: 0.85rem; margin-top: 4px; }
        .section-title {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.7rem;
            color: #6b6b8a;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            margin: 28px 0 8px 0;
            border-bottom: 1px solid #1e1e3a;
            padding-bottom: 6px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Load data ──────────────────────────────────────────────────────────────
    with st.spinner("Fetching BEA data…"):
        df = load_data()

    if df.empty:
        st.error("Could not load BEA data. Check your API key.")
        return

    gdp = get_series_values(df, SERIES["gdp"])
    consumption = get_series_values(df, SERIES["consumption"])
    investment = get_series_values(df, SERIES["investment"])
    government = get_series_values(df, SERIES["government"])
    net_exports = get_series_values(df, SERIES["net_exports"])

    # Align on common dates
    common = gdp.index.intersection(consumption.index).intersection(investment.index)
    gdp = gdp.loc[common]
    consumption = consumption.loc[common]
    investment = investment.loc[common]
    government = government.loc[common]
    net_exports = net_exports.reindex(common).fillna(0)

    # ── KPI row ────────────────────────────────────────────────────────────────
    latest_date = common[-1]
    prev_date   = common[-2]
    latest_gdp  = gdp.iloc[-1]
    prev_gdp    = gdp.iloc[-2]
    delta       = latest_gdp - prev_gdp

    quarter_label = f"{latest_date.year} Q{(latest_date.month - 1) // 3 + 1}"
    delta_color   = "#10b981" if delta >= 0 else "#ef4444"
    gdp_color     = "#10b981" if latest_gdp >= 0 else "#ef4444"

    cols = st.columns(5)
    kpis = [
        (f"{latest_gdp:+.1f}%", "GDP Growth", f"{delta:+.1f} pp vs prior Q", gdp_color),
        (f"{consumption.iloc[-1]:+.1f}", "Consumption", "contribution pp", COLORS["consumption"]),
        (f"{investment.iloc[-1]:+.1f}", "Investment", "contribution pp", COLORS["investment"]),
        (f"{government.iloc[-1]:+.1f}", "Government", "contribution pp", COLORS["government"]),
        (f"{net_exports.iloc[-1]:+.1f}", "Net Exports", "contribution pp", COLORS["net_exports"]),
    ]
    for col, (val, label, sub, color) in zip(cols, kpis):
        with col:
            st.markdown(
                f"""<div class="kpi-card">
                    <div class="kpi-value" style="color:{color}">{val}</div>
                    <div class="kpi-label">{label}</div>
                    <div class="kpi-delta" style="color:{MUTED}">{sub}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown(f'<div style="color:{MUTED}; font-size:0.72rem; margin-top:6px; font-family: IBM Plex Mono, monospace;">Latest quarter: {quarter_label} · Source: BEA NIPA T10102 · Annualized contribution to real GDP growth (pp)</div>', unsafe_allow_html=True)

    # ── Main chart ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Contributions to Real GDP Growth</div>', unsafe_allow_html=True)

    quarters = [f"{d.year} Q{(d.month-1)//3+1}" for d in common]

    fig = go.Figure()
    bars = [
        ("Consumption", consumption, COLORS["consumption"]),
        ("Investment", investment, COLORS["investment"]),
        ("Government", government, COLORS["government"]),
        ("Net Exports", net_exports, COLORS["net_exports"]),
    ]
    for name, series, color in bars:
        fig.add_trace(go.Bar(
            name=name, x=quarters, y=series.values,
            marker_color=color, marker_line_width=0,
            hovertemplate=f"<b>{name}</b>: %{{y:+.2f}} pp<extra></extra>",
        ))

    fig.add_trace(go.Scatter(
        name="Total GDP", x=quarters, y=gdp.values,
        mode="markers", marker=dict(symbol="diamond", size=8,
                                     color=COLORS["gdp_line"],
                                     line=dict(color=BG2, width=1)),
        hovertemplate="<b>GDP</b>: %{y:+.2f}%<extra></extra>",
    ))

    fig.update_layout(
        **PLOT_LAYOUT,
        barmode="relative",
        title=dict(text="", x=0),
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Drill-down selector ────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Drill-Down</div>', unsafe_allow_html=True)

    drill_options = {
        "📊 Consumption": _drilldown_consumption,
        "🏗️ Investment": _drilldown_investment,
        "🏛️ Government": _drilldown_government,
        "🌐 Net Exports": _drilldown_trade,
        "📈 Final Sales vs Inventories": _drilldown_final_sales,
    }

    tabs = st.tabs(list(drill_options.keys()))
    for tab, func in zip(tabs, drill_options.values()):
        with tab:
            func(df, quarters, common)

    # ── Heatmap table ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Last 8 Quarters — Contribution Summary</div>', unsafe_allow_html=True)
    _render_heatmap_table(df, quarters, common)


# ── Drill-down helpers ─────────────────────────────────────────────────────────

def _stacked_bar(df_data, quarters, title, height=320):
    fig = go.Figure()
    for name, series, color in df_data:
        fig.add_trace(go.Bar(
            name=name, x=quarters, y=series.values,
            marker_color=color, marker_line_width=0,
            hovertemplate=f"<b>{name}</b>: %{{y:+.2f}} pp<extra></extra>",
        ))
    layout = dict(**PLOT_LAYOUT, barmode="relative", height=height,
                  title=dict(text=title, font=dict(color=MUTED, size=11)))
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)


def _drilldown_consumption(df, quarters, common):
    data = [
        ("Durables",     get_series_values(df, SERIES["durables"]).reindex(common).fillna(0),     COLORS["durables"]),
        ("Nondurables",  get_series_values(df, SERIES["nondurables"]).reindex(common).fillna(0),  COLORS["nondurables"]),
        ("Services",     get_series_values(df, SERIES["services"]).reindex(common).fillna(0),     COLORS["services"]),
    ]
    _stacked_bar(data, quarters, "Consumption Components")


def _drilldown_investment(df, quarters, common):
    data = [
        ("Residential",    get_series_values(df, SERIES["residential"]).reindex(common).fillna(0),    COLORS["residential"]),
        ("Nonresidential", get_series_values(df, SERIES["nonresidential"]).reindex(common).fillna(0), COLORS["nonresidential"]),
        ("Inventories",    get_series_values(df, SERIES["inventories"]).reindex(common).fillna(0),    COLORS["inventories"]),
    ]
    _stacked_bar(data, quarters, "Investment Components")


def _drilldown_government(df, quarters, common):
    data = [
        ("Federal",     get_series_values(df, SERIES["federal"]).reindex(common).fillna(0),     COLORS["federal"]),
        ("State & Local", get_series_values(df, SERIES["state_local"]).reindex(common).fillna(0), COLORS["state_local"]),
    ]
    _stacked_bar(data, quarters, "Government Components")


def _drilldown_trade(df, quarters, common):
    exports = get_series_values(df, SERIES["exports"]).reindex(common).fillna(0)
    imports = get_series_values(df, SERIES["imports"]).reindex(common).fillna(0)

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Exports", x=quarters, y=exports.values,
                         marker_color=COLORS["exports"], marker_line_width=0,
                         hovertemplate="<b>Exports</b>: %{y:+.2f} pp<extra></extra>"))
    fig.add_trace(go.Bar(name="Imports", x=quarters, y=imports.values,
                         marker_color=COLORS["imports"], marker_line_width=0,
                         hovertemplate="<b>Imports</b>: %{y:+.2f} pp<extra></extra>"))
    layout = dict(**PLOT_LAYOUT, barmode="relative", height=320,
                  title=dict(text="Net Exports Decomposition", font=dict(color=MUTED, size=11)))
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)


def _drilldown_final_sales(df, quarters, common):
    gdp = get_series_values(df, SERIES["gdp"]).loc[common]
    final_sales = get_series_values(df, SERIES["final_sales"]).reindex(common).fillna(0)
    inventories = gdp - final_sales  # residual

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Final Sales", x=quarters, y=final_sales.values,
                         marker_color=COLORS["final_sales"], marker_line_width=0,
                         hovertemplate="<b>Final Sales</b>: %{y:+.2f} pp<extra></extra>"))
    fig.add_trace(go.Bar(name="Inventory Change", x=quarters, y=inventories.values,
                         marker_color=COLORS["inventories2"], marker_line_width=0,
                         hovertemplate="<b>Inventories</b>: %{y:+.2f} pp<extra></extra>"))
    layout = dict(**PLOT_LAYOUT, barmode="relative", height=320,
                  title=dict(text="Final Sales vs. Inventory Investment", font=dict(color=MUTED, size=11)))
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True)


def _render_heatmap_table(df, quarters, common):
    last8 = common[-8:]
    q_labels = [f"{d.year} Q{(d.month-1)//3+1}" for d in last8]

    series_map = {
        "GDP":          SERIES["gdp"],
        "Consumption":  SERIES["consumption"],
        "Investment":   SERIES["investment"],
        "Government":   SERIES["government"],
        "Net Exports":  SERIES["net_exports"],
        "Durables":     SERIES["durables"],
        "Nondurables":  SERIES["nondurables"],
        "Services":     SERIES["services"],
        "Residential":  SERIES["residential"],
        "Nonresidential": SERIES["nonresidential"],
        "Inventories":  SERIES["inventories"],
    }

    rows = {}
    for label, code in series_map.items():
        s = get_series_values(df, code).reindex(last8).fillna(0)
        rows[label] = s.values

    table_df = pd.DataFrame(rows, index=q_labels).T

    # Build color scale per cell
    def color_cell(val):
        if val > 1.5:   bg = "#0d4f2b"; color = "#4ade80"
        elif val > 0.5: bg = "#0a3320"; color = "#34d399"
        elif val > 0:   bg = "#0c2918"; color = "#6ee7b7"
        elif val > -0.5: bg = "#2d1515"; color = "#fca5a5"
        elif val > -1.5: bg = "#3d1010"; color = "#f87171"
        else:           bg = "#4d0a0a"; color = "#ef4444"
        return f"background-color:{bg}; color:{color}; text-align:center; font-family:'IBM Plex Mono',monospace; font-size:0.8rem; padding:6px 8px;"

    styled = table_df.style.format("{:+.2f}").applymap(color_cell)

    st.markdown(
        "<style>.dataframe th { background:#13132b; color:#6b6b8a; font-family:'IBM Plex Mono',monospace; font-size:0.72rem; text-transform:uppercase; } .dataframe { border-collapse: collapse; } </style>",
        unsafe_allow_html=True
    )
    st.dataframe(styled, use_container_width=True)
