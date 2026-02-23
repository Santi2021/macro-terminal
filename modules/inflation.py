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
    "cpi_recreation":"CUUR0000SAR",
    "cpi_education": "CUUR0000SAE1",
    "cpi_comm":      "CUUR0000SACE",
    "cpi_alcohol":   "CUUR0000SAG1",
    "cpi_furnish":   "CUUR0000SEHF",
    "cpi_hhops":     "CUUR0000SAH2",
    "cpi_transp":    "CUUR0000SAT",
}

FRED_INFL = {
    "pce":           "PCEPI",
    "pce_core":      "PCEPILFE",
    "breakeven_5y":  "T5YIE",
    "breakeven_10y": "T10YIE",
    "mich_1y":       "MICH",
    "mich_5y":       "EXPINF5YR",
}

# Component metadata: label, weight (BLS Relative Importance 2024), color
COMPONENTS = {
    "cpi_shelter":   ("Shelter",             0.3620, "#3b82f6"),
    "cpi_food_home": ("Food at Home",        0.0850, "#10b981"),
    "cpi_food_out":  ("Food Away from Home", 0.0540, "#34d399"),
    "cpi_medical":   ("Medical Care",        0.0640, "#a78bfa"),
    "cpi_energy":    ("Energy",              0.0640, "#f59e0b"),
    "cpi_new_cars":  ("New Vehicles",        0.0340, "#94a3b8"),
    "cpi_used_cars": ("Used Vehicles",       0.0230, "#64748b"),
    "cpi_apparel":   ("Apparel",             0.0240, "#f97316"),
    "cpi_recreation":("Recreation",          0.0570, "#06b6d4"),
    "cpi_education": ("Education",           0.0330, "#8b5cf6"),
    "cpi_comm":      ("Communication",       0.0360, "#ec4899"),
    "cpi_alcohol":   ("Alcoholic Beverages", 0.0090, "#84cc16"),
    "cpi_furnish":   ("Household Furnishings",0.0440,"#0891b2"),
    "cpi_hhops":     ("Household Operations",0.0310,"#0e7490"),
    "cpi_transp":    ("Transport Services",  0.0590, "#7c3aed"),
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

    # ── Section 2: CPI Contributions Stacked Bar (Bloomberg/Truflation style) ──
    st.markdown('<div class="sec">CPI Contributions to Inflation — pp (Bloomberg style)</div>', unsafe_allow_html=True)

    # Toggle MoM vs YoY
    col_t, _ = st.columns([3, 7])
    with col_t:
        mode = st.radio("Mode", ["YoY %", "MoM %"],
                        horizontal=True, label_visibility="collapsed", key="infl_contrib_mode")

    # Build contributions DataFrame for all periods
    contrib_data = {}
    raw_index = {}
    for key, (label, weight, color) in COMPONENTS.items():
        s = get_s(cpi, BLS_CPI[key])
        if len(s.dropna()) < 13:
            continue
        if mode == "YoY %":
            # Contribution = weight * (index_t / index_t-12 - 1) * 100
            contrib = s.pct_change(12) * 100 * weight
        else:
            # MoM contribution
            contrib = s.pct_change(1) * 100 * weight
        contrib_data[label] = contrib
        raw_index[label] = (s, weight, color)

    contrib_df = pd.DataFrame(contrib_data).dropna()
    contrib_df = trim(contrib_df)

    # Total line
    if mode == "YoY %":
        total = trim(yoy(get_s(cpi, BLS_CPI["cpi_all"])))
    else:
        total = trim(get_s(cpi, BLS_CPI["cpi_all"]).pct_change(1) * 100)

    # Align
    common_idx = contrib_df.index.intersection(total.index)
    contrib_df  = contrib_df.reindex(common_idx)
    total       = total.reindex(common_idx)

    # Build stacked bar using Scatter with fill — 100% compatible with Streamlit
    fig2 = go.Figure()
    labels   = [k for k, (lbl,_,__) in COMPONENTS.items() if lbl in contrib_df.columns]
    cols     = [lbl for k,(lbl,_,__)  in COMPONENTS.items() if lbl in contrib_df.columns]
    colors   = [c   for k,(_,__,c)   in COMPONENTS.items() if _ in contrib_df.columns]

    # Compute cumulative positive and negative stacks separately
    pos_stack = pd.Series(0.0, index=common_idx)
    neg_stack = pd.Series(0.0, index=common_idx)

    for label, color in zip(cols, colors):
        vals = contrib_df[label]
        pos_vals = vals.clip(lower=0)
        neg_vals = vals.clip(upper=0)

        if pos_vals.abs().sum() > 0:
            fig2.add_trace(go.Bar(
                name=label,
                x=common_idx,
                y=pos_vals.values,
                base=pos_stack.values,
                marker=dict(color=color, line=dict(width=0)),
                showlegend=True,
                hovertemplate=f"<b>{label}</b>: %{{y:+.3f}}pp<extra></extra>",
            ))
            pos_stack += pos_vals

        if neg_vals.abs().sum() > 0:
            fig2.add_trace(go.Bar(
                name=label,
                x=common_idx,
                y=neg_vals.values,
                base=neg_stack.values,
                marker=dict(color=color, line=dict(width=0)),
                showlegend=False,
                hovertemplate=f"<b>{label}</b>: %{{y:+.3f}}pp<extra></extra>",
            ))
            neg_stack += neg_vals

    # Total line on top
    fig2.add_trace(go.Scatter(
        name="CPI Total",
        x=common_idx,
        y=total.values,
        mode="lines",
        line=dict(color="#ffffff", width=2),
        hovertemplate="<b>CPI Total</b>: %{y:.2f}%<extra></extra>",
    ))

    fig2.add_hline(y=0, line_color="#2a2a4a", line_width=1)
    fig2.add_hline(y=FED_TARGET, line_color=GREEN, line_width=1, line_dash="dot",
                   annotation_text="2% target", annotation_position="top right",
                   annotation_font=dict(color=GREEN, size=9))

    # Shutdown annotation
    fig2.add_vline(x="2025-10-01", line_color=RED, line_width=1, line_dash="dot")
    fig2.add_annotation(
        x="2025-10-01", y=1.0, yref="paper",
        text="Oct '25<br>Shutdown",
        showarrow=False,
        font=dict(color=RED, size=9, family="monospace"),
        xanchor="left",
        bgcolor="rgba(13,13,26,0.8)",
        bordercolor=RED, borderwidth=1, borderpad=3,
    )

    fig2.update_layout(
        barmode="overlay",
        bargap=0.15,
        height=480,
        paper_bgcolor=BG,
        plot_bgcolor=BG2,
        font=dict(color=TEXT, family="monospace", size=11),
        hovermode="x unified",
        margin=dict(l=55, r=20, t=100, b=40),
        legend=dict(
            orientation="h", y=1.18, x=0, xanchor="left",
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10, color=MUTED),
            itemsizing="constant",
        ),
        xaxis=dict(showgrid=False, linecolor=GRID, tickcolor=GRID, tickfont=dict(color=MUTED)),
        yaxis=dict(
            showgrid=True, gridcolor="#1a1a2e", gridwidth=0.5,
            zeroline=True, zerolinecolor="#2a2a4a", zerolinewidth=1,
            tickfont=dict(color=MUTED), ticksuffix="pp",
            title=dict(text="pp contribution"),
        ),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Insight dinámico basado en mayor contribuidor
    if len(contrib_df) > 0:
        latest_contribs = contrib_df.iloc[-1].sort_values(ascending=False)
        top = latest_contribs.index[0]
        top_val = latest_contribs.iloc[0]
        shelter_contrib = contrib_df["Shelter"].iloc[-1] if "Shelter" in contrib_df else 0
        energy_contrib  = contrib_df["Energy"].iloc[-1]  if "Energy"  in contrib_df else 0
        st.markdown(
            f'<div class="insight">📊 Mayor contribuidor: <b style="color:#e8e8f0">{top}</b> ' 
            f'(<b style="color:{CYAN}">{top_val:+.3f}pp</b>). '
            f'🏠 Shelter: <b style="color:{BLUE}">{shelter_contrib:+.3f}pp</b> — ' 
            f'lag 12-18 meses del mercado inmobiliario. '
            f'⛽ Energy: <b style="color:{AMBER}">{energy_contrib:+.3f}pp</b></div>',
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
    for key, (label, weight, color) in COMPONENTS.items():
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
