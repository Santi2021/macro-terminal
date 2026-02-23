"""
modules/inflation.py — Inflation module for Macro Terminal
Sources: BLS API (CPI components) + FRED API (PCE, expectations, breakevens)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
import os

# ── Style ──────────────────────────────────────────────────────────────────────
BG    = "#0d0d1a"
BG2   = "#13132b"
GRID  = "#1e1e3a"
TEXT  = "#e8e8f0"
MUTED = "#6b6b8a"
CYAN  = "#00d4ff"
GREEN = "#10b981"
RED   = "#ef4444"
AMBER = "#f59e0b"
BLUE  = "#3b82f6"
VIOLET= "#a78bfa"
FED_TARGET = 2.0

# ── Series IDs ─────────────────────────────────────────────────────────────────
BLS_CPI = {
    "cpi_all":       "CUUR0000SA0",
    "cpi_core":      "CUUR0000SA0L1E",
    "cpi_shelter":   "CUUR0000SAH1",
    "cpi_food_home": "CUUR0000SAF1",
    "cpi_food_out":  "CUUR0000SEFV",
    "cpi_energy":    "CUUR0000SA0E",
    "cpi_gasoline":  "CUUR0000SETB01",
    "cpi_medical":   "CUUR0000SAM",
    "cpi_apparel":   "CUUR0000SAA",
    "cpi_new_cars":  "CUUR0000SAT1",
    "cpi_used_cars": "CUUR0000SETA02",
}

FRED_INFL = {
    "pce":           "PCEPI",
    "pce_core":      "PCEPILFE",
    "breakeven_5y":  "T5YIE",
    "breakeven_10y": "T10YIE",
    "mich_1y":       "MICH",
    "mich_5y":       "EXPINF5YR",
}

COMPONENT_LABELS = {
    "cpi_shelter":   "Shelter",
    "cpi_food_home": "Food at Home",
    "cpi_food_out":  "Food Away from Home",
    "cpi_medical":   "Medical Care",
    "cpi_energy":    "Energy",
    "cpi_gasoline":  "Gasoline",
    "cpi_new_cars":  "New Vehicles",
    "cpi_used_cars": "Used Vehicles",
    "cpi_apparel":   "Apparel",
}

COMPONENT_COLORS = {
    "Shelter":              "#3b82f6",
    "Food at Home":         "#10b981",
    "Food Away from Home":  "#34d399",
    "Medical Care":         "#a78bfa",
    "Energy":               "#f59e0b",
    "Gasoline":             "#fbbf24",
    "New Vehicles":         "#94a3b8",
    "Used Vehicles":        "#64748b",
    "Apparel":              "#f97316",
}

# ── API helpers ────────────────────────────────────────────────────────────────
def _bls_key():
    try:    return st.secrets["BLS_API_KEY"]
    except: return os.getenv("BLS_API_KEY", "")

def _fred_key():
    try:    return st.secrets["FRED_API_KEY"]
    except: return os.getenv("FRED_API_KEY", "")


@st.cache_data(ttl=3600, show_spinner=False)
def load_cpi_data(start_year="2015") -> pd.DataFrame:
    api_key  = _bls_key()
    end_year = str(pd.Timestamp.now().year)
    payload  = {
        "seriesid": list(BLS_CPI.values()),
        "startyear": start_year,
        "endyear": end_year,
        "registrationkey": api_key,
        "annualaverage": False,
    }
    resp = requests.post(
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        data=json.dumps(payload),
        headers={"Content-type": "application/json"}, timeout=45
    )
    resp.raise_for_status()
    rows = []
    for series in resp.json()["Results"]["series"]:
        sid = series["seriesID"]
        for obs in series["data"]:
            p = obs["period"]
            if not p.startswith("M") or p == "M13": continue
            try:
                rows.append({
                    "series_id": sid,
                    "date": pd.Timestamp(f"{obs['year']}-{int(p[1:]):02d}-01"),
                    "value": float(obs["value"])
                })
            except: continue
    return pd.DataFrame(rows).sort_values(["series_id","date"]).reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_fred_data(start="2015-01-01") -> pd.DataFrame:
    api_key = _fred_key()
    rows = []
    for name, sid in FRED_INFL.items():
        params = {
            "series_id": sid,
            "observation_start": start,
            "api_key": api_key,
            "file_type": "json",
        }
        try:
            resp = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params=params, timeout=20
            )
            for obs in resp.json()["observations"]:
                try:
                    rows.append({
                        "series_id": name,
                        "date": pd.Timestamp(obs["date"]),
                        "value": float(obs["value"])
                    })
                except: continue
        except: continue
    return pd.DataFrame(rows).sort_values(["series_id","date"]).reset_index(drop=True)


def get_s(df, sid):
    return df[df["series_id"] == sid].set_index("date")["value"].sort_index()

def yoy(s): return s.pct_change(12) * 100

def base_layout(height=360, title=""):
    layout = dict(
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color=TEXT, size=11),
        xaxis=dict(gridcolor=GRID, linecolor=GRID, showgrid=False),
        yaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=False),
        hovermode="x unified",
        height=height,
        margin=dict(l=55, r=20, t=44 if title else 24, b=36),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT, size=10),
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
        ),
    )
    if title:
        layout["title"] = dict(text=title, font=dict(size=12, color=MUTED), x=0, xanchor="left")
    return layout


# ── Main render ────────────────────────────────────────────────────────────────
def render():
    st.markdown("""
    <style>
    .kpi-card { background:#13132b; border:1px solid #1e1e3a; border-radius:8px;
                padding:16px 20px; text-align:center; }
    .kpi-value { font-family:monospace; font-size:1.85rem; font-weight:600; }
    .kpi-label { font-size:0.72rem; color:#6b6b8a; text-transform:uppercase;
                 letter-spacing:0.1em; margin-top:4px; }
    .kpi-sub   { font-family:monospace; font-size:0.78rem; margin-top:4px; }
    .sec { font-family:monospace; font-size:0.68rem; color:#6b6b8a; text-transform:uppercase;
           letter-spacing:0.15em; margin:24px 0 8px 0;
           border-bottom:1px solid #1e1e3a; padding-bottom:6px; }
    .insight { background:#0a0a18; border-left:3px solid #00d4ff; border-radius:0 6px 6px 0;
               padding:10px 14px; font-family:monospace; font-size:0.78rem;
               color:#9999bb; margin:8px 0 16px 0; }
    </style>
    """, unsafe_allow_html=True)

    # Range selector
    col_r, _ = st.columns([3, 7])
    with col_r:
        rng = st.radio("Range", ["2Y", "5Y", "10Y", "All"],
                       index=1, horizontal=True, label_visibility="collapsed", key="inflation_range")
    cuts = {"2Y": -24, "5Y": -60, "10Y": -120, "All": 0}
    cut  = cuts[rng]

    with st.spinner("Loading BLS + FRED inflation data..."):
        try:
            cpi  = load_cpi_data()
            fred = load_fred_data()
        except Exception as e:
            st.error(f"Data fetch error: {e}")
            return

    # ── Pull & compute YoY ────────────────────────────────────────────────────
    cpi_all  = yoy(get_s(cpi, BLS_CPI["cpi_all"]))
    cpi_core = yoy(get_s(cpi, BLS_CPI["cpi_core"]))
    pce      = yoy(get_s(fred, "pce"))
    pce_core = yoy(get_s(fred, "pce_core"))

    def trim(s): return s.iloc[cut:] if cut != 0 else s

    # Latest values
    def latest(s): return s.dropna().iloc[-1] if len(s.dropna()) else 0
    def prev(s):   return s.dropna().iloc[-2] if len(s.dropna()) >= 2 else 0

    l_cpi      = latest(cpi_all)
    l_cpi_core = latest(cpi_core)
    l_pce      = latest(pce)
    l_pce_core = latest(pce_core)
    l_be5      = latest(get_s(fred, "breakeven_5y"))

    latest_date = cpi_all.dropna().index[-1].strftime("%b %Y") if len(cpi_all.dropna()) else ""

    def kpi_color(val):
        if val > 3.5:  return RED
        elif val > 2.5: return AMBER
        else:           return GREEN

    # ── KPI Cards ─────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        (f"{l_cpi:.1f}%",      "CPI Headline",  f"prev {prev(cpi_all):.1f}%",      kpi_color(l_cpi)),
        (f"{l_cpi_core:.1f}%", "Core CPI",      f"ex Food & Energy",               kpi_color(l_cpi_core)),
        (f"{l_pce:.1f}%",      "PCE Headline",  f"prev {prev(pce):.1f}%",           kpi_color(l_pce)),
        (f"{l_pce_core:.1f}%", "Core PCE",      f"Fed target: 2.0%",               kpi_color(l_pce_core)),
        (f"{l_be5:.2f}%",      "5Y Breakeven",  f"mkt inflation expectations",     CYAN),
    ]
    for col, (val, label, sub, color) in zip([c1,c2,c3,c4,c5], kpis):
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-value" style="color:{color}">{val}</div>
                <div class="kpi-label">{label}</div>
                <div class="kpi-sub" style="color:{MUTED}">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(
        f'<div style="color:{MUTED};font-size:0.7rem;margin-top:6px;font-family:monospace">'
        f'Latest: {latest_date} · BLS CPI + BEA PCE + FRED TIPS</div>',
        unsafe_allow_html=True)

    # ── Section 1: CPI vs PCE ─────────────────────────────────────────────────
    st.markdown('<div class="sec">CPI vs PCE — YoY %</div>', unsafe_allow_html=True)

    fig = go.Figure()
    fig.add_hrect(y0=0, y1=FED_TARGET, fillcolor=GREEN, opacity=0.04, line_width=0)
    fig.add_hline(y=FED_TARGET, line_color=GREEN, line_width=1, line_dash="dot",
                  annotation_text="Fed 2% target", annotation_position="bottom right",
                  annotation_font=dict(color=GREEN, size=9))

    for name, s, color, dash in [
        ("CPI Headline",  trim(cpi_all),   RED,    "solid"),
        ("Core CPI",      trim(cpi_core),  AMBER,  "dot"),
        ("PCE Headline",  trim(pce),       BLUE,   "solid"),
        ("Core PCE",      trim(pce_core),  VIOLET, "dot"),
    ]:
        fig.add_trace(go.Scatter(
            name=name, x=s.index, y=s.values,
            line=dict(color=color, width=2, dash=dash),
            hovertemplate=f"<b>{name}</b>: %{{y:.2f}}%<extra></extra>",
        ))

    fig.update_layout(**base_layout(360))
    st.plotly_chart(fig, use_container_width=True)

    # ── Section 2: CPI Component Breakdown ────────────────────────────────────
    st.markdown('<div class="sec">CPI Components — Latest Month YoY % Contribution</div>', unsafe_allow_html=True)

    comp_vals = {}
    for key, label in COMPONENT_LABELS.items():
        s = yoy(get_s(cpi, BLS_CPI[key]))
        if len(s.dropna()) > 0:
            comp_vals[label] = s.dropna().iloc[-1]

    comp_df = pd.DataFrame.from_dict(comp_vals, orient="index", columns=["yoy"]).sort_values("yoy")
    bar_colors = [COMPONENT_COLORS.get(k, CYAN) for k in comp_df.index]

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=comp_df["yoy"], y=comp_df.index,
        orientation="h",
        marker_color=bar_colors,
        hovertemplate="<b>%{y}</b>: %{x:+.2f}% YoY<extra></extra>",
    ))
    fig2.add_vline(x=0, line_color="#444466", line_width=1)
    fig2.add_vline(x=FED_TARGET, line_color=GREEN, line_width=1, line_dash="dot")

    layout2 = base_layout(360)
    layout2["xaxis"]["title"] = dict(text="YoY %")
    layout2["yaxis"]["gridcolor"] = "rgba(0,0,0,0)"
    layout2["margin"]["l"] = 170
    fig2.update_layout(**layout2)
    st.plotly_chart(fig2, use_container_width=True)

    # Insight
    shelter_val = comp_vals.get("Shelter", 0)
    energy_val  = comp_vals.get("Energy", 0)
    st.markdown(
        f'<div class="insight">🏠 Shelter YoY: <b style="color:{BLUE}">{shelter_val:.1f}%</b> — '
        f'tiene lag de 12-18 meses respecto al mercado inmobiliario real. '
        f'Core ex-Shelter es la métrica más limpia de inflación subyacente. '
        f'⛽ Energy: <b style="color:{AMBER}">{energy_val:.1f}%</b></div>',
        unsafe_allow_html=True)

    # ── Section 3: Shelter vs Core ex-Shelter ─────────────────────────────────
    st.markdown('<div class="sec">Shelter vs Core ex-Shelter — YoY %</div>', unsafe_allow_html=True)

    shelter     = yoy(get_s(cpi, BLS_CPI["cpi_shelter"]))
    core        = yoy(get_s(cpi, BLS_CPI["cpi_core"]))

    # Core ex-Shelter: approximate via weighted difference
    # Shelter weight ~36% in core CPI
    shelter_w   = 0.36
    core_ex_shelter = (core - shelter_w * shelter) / (1 - shelter_w)

    fig3 = go.Figure()
    fig3.add_hline(y=FED_TARGET, line_color=GREEN, line_width=1, line_dash="dot",
                   annotation_text="2%", annotation_position="bottom right",
                   annotation_font=dict(color=GREEN, size=9))
    for name, s, color, dash in [
        ("Shelter",          trim(shelter),          BLUE,  "solid"),
        ("Core CPI",         trim(core),             AMBER, "dot"),
        ("Core ex-Shelter*", trim(core_ex_shelter),  CYAN,  "solid"),
    ]:
        fig3.add_trace(go.Scatter(
            name=name, x=s.index, y=s.values,
            line=dict(color=color, width=2, dash=dash),
            hovertemplate=f"<b>{name}</b>: %{{y:.2f}}%<extra></extra>",
        ))

    layout3 = base_layout(320)
    fig3.update_layout(**layout3)
    st.plotly_chart(fig3, use_container_width=True)
    st.markdown(
        f'<div style="color:{MUTED};font-size:0.68rem;font-family:monospace;margin-top:-8px;">'
        f'* Core ex-Shelter aproximado con weight 36% de Shelter en Core CPI</div>',
        unsafe_allow_html=True)

    # ── Section 4: Inflation Expectations ─────────────────────────────────────
    st.markdown('<div class="sec">Inflation Expectations — Market & Consumer</div>', unsafe_allow_html=True)

    be5  = trim(get_s(fred, "breakeven_5y"))
    be10 = trim(get_s(fred, "breakeven_10y"))
    m1y  = trim(get_s(fred, "mich_1y"))
    m5y  = trim(get_s(fred, "mich_5y"))

    exp_tabs = st.tabs(["TIPS Breakevens", "Michigan Consumer"])

    with exp_tabs[0]:
        fig4 = go.Figure()
        fig4.add_hrect(y0=1.8, y1=2.2, fillcolor=GREEN, opacity=0.06, line_width=0,
                       annotation_text="Fed comfort zone", annotation_position="top right",
                       annotation_font=dict(color=GREEN, size=9))
        for name, s, color in [
            ("5Y Breakeven",  be5,  CYAN),
            ("10Y Breakeven", be10, VIOLET),
        ]:
            fig4.add_trace(go.Scatter(
                name=name, x=s.index, y=s.values,
                line=dict(color=color, width=2),
                hovertemplate=f"<b>{name}</b>: %{{y:.2f}}%<extra></extra>",
            ))
        fig4.update_layout(**base_layout(300))
        st.plotly_chart(fig4, use_container_width=True)

        l_be10 = latest(get_s(fred, "breakeven_10y"))
        st.markdown(
            f'<div class="insight">📊 5Y breakeven: <b style="color:{CYAN}">{l_be5:.2f}%</b> · '
            f'10Y: <b style="color:{VIOLET}">{l_be10:.2f}%</b>. '
            f'Por encima de 2.5% el mercado está descontando inflación persistente — señal hawkish para el Fed.</div>',
            unsafe_allow_html=True)

    with exp_tabs[1]:
        fig5 = make_subplots(specs=[[{"secondary_y": True}]])
        fig5.add_trace(go.Scatter(
            name="Michigan 1Y", x=m1y.index, y=m1y.values,
            line=dict(color=RED, width=2),
            hovertemplate="<b>Michigan 1Y</b>: %{y:.1f}%<extra></extra>",
        ), secondary_y=False)
        fig5.add_trace(go.Scatter(
            name="Michigan 5Y", x=m5y.index, y=m5y.values,
            line=dict(color=AMBER, width=2),
            hovertemplate="<b>Michigan 5Y</b>: %{y:.2f}%<extra></extra>",
        ), secondary_y=True)

        fig5.update_layout(**base_layout(300))
        fig5.update_layout(paper_bgcolor=BG, plot_bgcolor=BG2, hovermode="x unified")
        fig5.update_yaxes(title_text="1Y Expectations %", gridcolor=GRID,
                          zeroline=False, secondary_y=False,
                          title_font=dict(color=RED, size=10))
        fig5.update_yaxes(title_text="5Y Expectations %", gridcolor="rgba(0,0,0,0)",
                          zeroline=False, secondary_y=True,
                          title_font=dict(color=AMBER, size=10))
        fig5.update_xaxes(gridcolor=GRID, linecolor=GRID)
        st.plotly_chart(fig5, use_container_width=True)

        l_m1y = latest(get_s(fred, "mich_1y"))
        l_m5y = latest(get_s(fred, "mich_5y"))
        anchor_status = "✅ ancladas" if l_m5y < 3.0 else "⚠️ desancladas"
        st.markdown(
            f'<div class="insight">🧠 Michigan 1Y: <b style="color:{RED}">{l_m1y:.1f}%</b> · '
            f'5Y: <b style="color:{AMBER}">{l_m5y:.2f}%</b>. '
            f'Expectations de largo plazo {anchor_status} — el Fed considera ancladas por debajo de 3.0%.</div>',
            unsafe_allow_html=True)

    # ── Heatmap CPI Components ─────────────────────────────────────────────────
    st.markdown('<div class="sec">CPI Components Heatmap — Last 6 Months YoY %</div>', unsafe_allow_html=True)

    heat = {}
    for key, label in COMPONENT_LABELS.items():
        s = yoy(get_s(cpi, BLS_CPI[key]))
        if len(s.dropna()) >= 6:
            heat[label] = s.dropna().iloc[-6:]

    if heat:
        heat_df = pd.DataFrame(heat).T
        heat_df.columns = [d.strftime("%b %Y") for d in heat_df.columns]

        def color_cell(val):
            if pd.isna(val):  return "background:#0d0d1a;color:#3d3d5c;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
            if val > 6:       return "background:#4d0a0a;color:#ef4444;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
            elif val > 4:     return "background:#3d1010;color:#f87171;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
            elif val > 2:     return "background:#2d1515;color:#fca5a5;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
            elif val > 0:     return "background:#0c2918;color:#6ee7b7;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
            else:             return "background:#0d4f2b;color:#4ade80;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"

        styled = heat_df.style.format("{:.1f}%").applymap(color_cell)
        st.dataframe(styled, use_container_width=True)

    st.markdown(
        f'<div style="color:{MUTED};font-size:0.7rem;margin-top:12px;font-family:monospace">'
        f'Sources: BLS CPI · BEA PCE · FRED TIPS Breakevens · U. Michigan Surveys</div>',
        unsafe_allow_html=True)
