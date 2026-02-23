"""
modules/labor.py — Labor Market module for Macro Terminal
Sources: BLS API (payrolls, unemployment, wages) + FRED API (JOLTS)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import json
import os

# ── Style constants ────────────────────────────────────────────────────────────
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

SECTOR_COLORS = {
    "Total Private":            "#3b82f6",
    "Goods-producing":          "#10b981",
    "Mining & Logging":         "#065f46",
    "Construction":             "#34d399",
    "Manufacturing":            "#6ee7b7",
    "Service-providing":        "#60a5fa",
    "Trade, Transport & Util.": "#93c5fd",
    "Information":              "#a78bfa",
    "Financial Activities":     "#f59e0b",
    "Professional & Business":  "#fbbf24",
    "Education & Health":       "#4ade80",
    "Leisure & Hospitality":    "#fb7185",
    "Other Services":           "#94a3b8",
    "Government":               "#f97316",
}

# ── BLS Series IDs ─────────────────────────────────────────────────────────────
BLS_SERIES = {
    # Headline
    "payrolls_total":    "CES0000000001",   # Total Nonfarm, thousands
    "payrolls_private":  "CES0500000001",   # Total Private
    "payrolls_govt":     "CES9000000001",   # Government
    "unemployment":      "LNS14000000",     # U-3 Unemployment Rate
    "u6":                "LNS13327709",     # U-6 Broad Unemployment
    "participation":     "LNS11300000",     # Participation Rate
    "wages_ahe":         "CES0500000003",   # Avg Hourly Earnings, private, $/hr
    # Sector payrolls (thousands)
    "sec_goods":         "CES0600000001",
    "sec_mining":        "CES1000000001",
    "sec_construction":  "CES2000000001",
    "sec_manufacturing": "CES3000000001",
    "sec_services":      "CES0800000001",
    "sec_trade_trans":   "CES4000000001",
    "sec_information":   "CES5000000001",
    "sec_financial":     "CES5500000001",
    "sec_prof_biz":      "CES6000000001",
    "sec_edu_health":    "CES6500000001",
    "sec_leisure":       "CES7000000001",
    "sec_other":         "CES8000000001",
}

# JOLTS from FRED
FRED_SERIES = {
    "jolts_openings":   "JTSJOL",    # Job Openings, thousands
    "jolts_hires":      "JTSHIL",    # Hires
    "jolts_quits":      "JTSQUL",    # Quits
    "jolts_layoffs":    "JTSLAL",    # Layoffs & Discharges
    "jolts_separations":"JTSSEL",    # Total Separations
}


# ── Data fetching ──────────────────────────────────────────────────────────────
def _get_bls_key():
    try:
        return st.secrets["BLS_API_KEY"]
    except Exception:
        return os.getenv("BLS_API_KEY", "")

def _get_fred_key():
    try:
        return st.secrets["FRED_API_KEY"]
    except Exception:
        return os.getenv("FRED_API_KEY", "")


@st.cache_data(ttl=3600, show_spinner=False)
def load_bls_data(start_year: str = "2010") -> pd.DataFrame:
    """Fetch all BLS series, return tidy DataFrame: series_id, date, value."""
    api_key = _get_bls_key()
    end_year = str(pd.Timestamp.now().year)

    headers = {"Content-type": "application/json"}
    payload = {
        "seriesid": list(BLS_SERIES.values()),
        "startyear": start_year,
        "endyear": end_year,
        "registrationkey": api_key,
        "annualaverage": False,
    }

    resp = requests.post(
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        data=json.dumps(payload), headers=headers, timeout=45
    )
    resp.raise_for_status()
    data = resp.json()

    rows = []
    for series in data["Results"]["series"]:
        sid = series["seriesID"]
        for obs in series["data"]:
            period = obs["period"]
            year   = obs["year"]
            if not period.startswith("M") or period == "M13":
                continue
            month = int(period[1:])
            date  = pd.Timestamp(f"{year}-{month:02d}-01")
            try:
                val = float(obs["value"])
            except Exception:
                continue
            rows.append({"series_id": sid, "date": date, "value": val})

    return pd.DataFrame(rows).sort_values(["series_id", "date"]).reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_fred_data(start: str = "2010-01-01") -> pd.DataFrame:
    """Fetch JOLTS series from FRED."""
    api_key = _get_fred_key()
    rows = []
    for name, sid in FRED_SERIES.items():
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": sid,
            "observation_start": start,
            "api_key": api_key,
            "file_type": "json",
        }
        try:
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            for obs in resp.json()["observations"]:
                try:
                    rows.append({
                        "series_id": name,
                        "date": pd.Timestamp(obs["date"]),
                        "value": float(obs["value"]),
                    })
                except Exception:
                    continue
        except Exception:
            continue

    return pd.DataFrame(rows).sort_values(["series_id", "date"]).reset_index(drop=True)


def get_s(df: pd.DataFrame, series_id: str) -> pd.Series:
    """Extract one series by ID, indexed by date."""
    mask = df["series_id"] == series_id
    return df[mask].set_index("date")["value"].sort_index()


def mom_change(level_series: pd.Series) -> pd.Series:
    """Month-over-month change (for level series like payrolls in thousands)."""
    return level_series.diff()


def yoy_pct(series: pd.Series) -> pd.Series:
    return series.pct_change(12) * 100


# ── Layout helper ──────────────────────────────────────────────────────────────
def base_layout(height=360, title=""):
    return dict(
        paper_bgcolor=BG, plot_bgcolor=BG2,
        font=dict(color=TEXT, size=11),
        title=dict(text=title, font=dict(size=12, color=MUTED), x=0, xanchor="left") if title else None,
        xaxis=dict(gridcolor=GRID, linecolor=GRID, showgrid=False),
        yaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=True, zerolinecolor="#444466"),
        hovermode="x unified",
        height=height,
        margin=dict(l=55, r=20, t=44 if title else 24, b=36),
        legend=dict(
            bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT, size=10),
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
        ),
    )


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
                       index=1, horizontal=True, label_visibility="collapsed")

    cuts = {"2Y": -24, "5Y": -60, "10Y": -120, "All": 0}
    cut  = cuts[rng]

    with st.spinner("Loading BLS + FRED data..."):
        try:
            bls  = load_bls_data()
            fred = load_fred_data()
        except Exception as e:
            st.error(f"Data fetch error: {e}")
            return

    # ── Pull main series ───────────────────────────────────────────────────────
    pay_tot  = get_s(bls, BLS_SERIES["payrolls_total"])
    pay_priv = get_s(bls, BLS_SERIES["payrolls_private"])
    pay_govt = get_s(bls, BLS_SERIES["payrolls_govt"])
    unemp    = get_s(bls, BLS_SERIES["unemployment"])
    u6       = get_s(bls, BLS_SERIES["u6"])
    part     = get_s(bls, BLS_SERIES["participation"])
    wages    = get_s(bls, BLS_SERIES["wages_ahe"])

    pay_ch      = mom_change(pay_tot)
    pay_priv_ch = mom_change(pay_priv)
    pay_govt_ch = mom_change(pay_govt)
    wages_yoy   = yoy_pct(wages)

    # Apply cut
    def trim(s): return s.iloc[cut:] if cut != 0 else s

    pay_ch_t      = trim(pay_ch)
    pay_priv_ch_t = trim(pay_priv_ch)
    pay_govt_ch_t = trim(pay_govt_ch)
    unemp_t       = trim(unemp)
    u6_t          = trim(u6)
    part_t        = trim(part)
    wages_yoy_t   = trim(wages_yoy)

    # Latest values
    latest_pay    = pay_ch.dropna().iloc[-1] if len(pay_ch.dropna()) else 0
    latest_u      = unemp.dropna().iloc[-1]  if len(unemp.dropna()) else 0
    latest_part   = part.dropna().iloc[-1]   if len(part.dropna()) else 0
    latest_wages  = wages_yoy.dropna().iloc[-1] if len(wages_yoy.dropna()) else 0

    prev_pay   = pay_ch.dropna().iloc[-2]  if len(pay_ch.dropna()) >= 2 else latest_pay
    prev_u     = unemp.dropna().iloc[-2]   if len(unemp.dropna()) >= 2 else latest_u
    prev_wages = wages_yoy.dropna().iloc[-2] if len(wages_yoy.dropna()) >= 2 else latest_wages

    pay_date = pay_ch.dropna().index[-1] if len(pay_ch.dropna()) else pd.Timestamp.now()

    # ── KPI Cards ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    kpis = [
        (f"{latest_pay:+,.0f}K",   "Nonfarm Payrolls",   f"prev {prev_pay:+,.0f}K",
         GREEN if latest_pay > 0 else RED),
        (f"{latest_u:.1f}%",       "Unemployment U-3",   f"prev {prev_u:.1f}%",
         GREEN if latest_u < prev_u else RED),
        (f"{latest_part:.1f}%",    "Participation Rate", f"prime-age benchmark ~83%",
         CYAN),
        (f"{latest_wages:+.1f}%",  "Wages YoY",          f"Fed comfort ~3.0–3.5%",
         AMBER if latest_wages > 3.5 else GREEN),
    ]
    for col, (val, label, sub, color) in zip([c1,c2,c3,c4], kpis):
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-value" style="color:{color}">{val}</div>
                <div class="kpi-label">{label}</div>
                <div class="kpi-sub" style="color:{MUTED}">{sub}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown(
        f'<div style="color:{MUTED};font-size:0.7rem;margin-top:6px;font-family:monospace">'
        f'Latest: {pay_date.strftime("%b %Y")} · BEA NIPA + BLS CES/CPS + FRED JOLTS</div>',
        unsafe_allow_html=True)

    # ── Section 1: Payrolls ────────────────────────────────────────────────────
    st.markdown('<div class="sec">Nonfarm Payrolls — Monthly Change (000s)</div>', unsafe_allow_html=True)

    view_opt = st.radio("View", ["Total", "Private vs Government"],
                        horizontal=True, label_visibility="collapsed")

    ma3 = pay_ch_t.rolling(3).mean()

    fig = go.Figure()
    if view_opt == "Total":
        colors_bar = [GREEN if v >= 0 else RED for v in pay_ch_t.values]
        fig.add_trace(go.Bar(
            name="Payrolls MoM", x=pay_ch_t.index, y=pay_ch_t.values,
            marker_color=colors_bar,
            hovertemplate="<b>%{x|%b %Y}</b>: %{y:+,.0f}K<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            name="3M Avg", x=ma3.index, y=ma3.values,
            line=dict(color=CYAN, width=2, dash="dot"),
            hovertemplate="<b>3M Avg</b>: %{y:+,.0f}K<extra></extra>",
        ))
    else:
        fig.add_trace(go.Bar(
            name="Private", x=pay_priv_ch_t.index, y=pay_priv_ch_t.values,
            marker_color=BLUE, opacity=0.85,
            hovertemplate="<b>Private</b>: %{y:+,.0f}K<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            name="Government", x=pay_govt_ch_t.index, y=pay_govt_ch_t.values,
            marker_color=AMBER, opacity=0.85,
            hovertemplate="<b>Government</b>: %{y:+,.0f}K<extra></extra>",
        ))

    fig.add_hline(y=0, line_color="#444466", line_width=1)
    fig.update_layout(**base_layout(340), barmode="stack")
    st.plotly_chart(fig, use_container_width=True)

    # ── Section 2: Sector Breakdown ────────────────────────────────────────────
    st.markdown('<div class="sec">Sector Payrolls — Latest Month Change (000s)</div>', unsafe_allow_html=True)

    sector_map = {
        "Total Private":            BLS_SERIES["payrolls_private"],
        "Goods-producing":          BLS_SERIES["sec_goods"],
        "Mining & Logging":         BLS_SERIES["sec_mining"],
        "Construction":             BLS_SERIES["sec_construction"],
        "Manufacturing":            BLS_SERIES["sec_manufacturing"],
        "Service-providing":        BLS_SERIES["sec_services"],
        "Trade, Transport & Util.": BLS_SERIES["sec_trade_trans"],
        "Information":              BLS_SERIES["sec_information"],
        "Financial Activities":     BLS_SERIES["sec_financial"],
        "Professional & Business":  BLS_SERIES["sec_prof_biz"],
        "Education & Health":       BLS_SERIES["sec_edu_health"],
        "Leisure & Hospitality":    BLS_SERIES["sec_leisure"],
        "Other Services":           BLS_SERIES["sec_other"],
        "Government":               BLS_SERIES["payrolls_govt"],
    }

    sector_vals = {}
    for name, sid in sector_map.items():
        s = get_s(bls, sid)
        ch = mom_change(s)
        if len(ch.dropna()) > 0:
            sector_vals[name] = ch.dropna().iloc[-1]

    sec_df = pd.DataFrame.from_dict(sector_vals, orient="index", columns=["change"]).sort_values("change")
    bar_colors = [GREEN if v >= 0 else RED for v in sec_df["change"]]

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        name="MoM Change", x=sec_df["change"], y=sec_df.index,
        orientation="h", marker_color=bar_colors,
        hovertemplate="<b>%{y}</b>: %{x:+,.0f}K<extra></extra>",
    ))
    fig2.add_vline(x=0, line_color="#444466", line_width=1)
    layout2 = base_layout(420)
    layout2["xaxis"]["title"] = "Thousands"
    layout2["yaxis"]["gridcolor"] = "transparent"
    layout2["margin"]["l"] = 160
    fig2.update_layout(**layout2)
    st.plotly_chart(fig2, use_container_width=True)

    # ── Section 3: Unemployment + Participation ────────────────────────────────
    st.markdown('<div class="sec">Unemployment & Labor Force Participation</div>', unsafe_allow_html=True)

    fig3 = make_subplots(specs=[[{"secondary_y": True}]])
    fig3.add_trace(go.Scatter(
        name="Unemployment U-3", x=unemp_t.index, y=unemp_t.values,
        line=dict(color=RED, width=2),
        hovertemplate="<b>U-3</b>: %{y:.1f}%<extra></extra>",
    ), secondary_y=False)
    fig3.add_trace(go.Scatter(
        name="U-6 Broad", x=u6_t.index, y=u6_t.values,
        line=dict(color="#f97316", width=1.5, dash="dot"),
        hovertemplate="<b>U-6</b>: %{y:.1f}%<extra></extra>",
    ), secondary_y=False)
    fig3.add_trace(go.Scatter(
        name="Participation Rate", x=part_t.index, y=part_t.values,
        line=dict(color=CYAN, width=2),
        hovertemplate="<b>Participation</b>: %{y:.1f}%<extra></extra>",
    ), secondary_y=True)

    fig3.update_layout(**base_layout(340))
    fig3.update_layout(paper_bgcolor=BG, plot_bgcolor=BG2, hovermode="x unified")
    fig3.update_yaxes(title_text="Unemployment %", gridcolor=GRID, linecolor=GRID,
                      zeroline=False, secondary_y=False,
                      title_font=dict(color=RED, size=10))
    fig3.update_yaxes(title_text="Participation %", gridcolor="transparent",
                      zeroline=False, secondary_y=True,
                      title_font=dict(color=CYAN, size=10))
    fig3.update_xaxes(gridcolor=GRID, linecolor=GRID)
    st.plotly_chart(fig3, use_container_width=True)

    # ── Section 4: Wages ───────────────────────────────────────────────────────
    st.markdown('<div class="sec">Average Hourly Earnings — YoY %</div>', unsafe_allow_html=True)

    fig4 = go.Figure()
    fig4.add_hrect(y0=3.0, y1=3.5, fillcolor="#10b981", opacity=0.07,
                   line_width=0, annotation_text="Fed comfort zone",
                   annotation_position="top right",
                   annotation_font=dict(color=GREEN, size=9))
    fig4.add_trace(go.Scatter(
        name="AHE YoY%", x=wages_yoy_t.index, y=wages_yoy_t.values,
        line=dict(color=AMBER, width=2.5),
        fill="tozeroy", fillcolor="rgba(245,158,11,0.08)",
        hovertemplate="<b>Wages YoY</b>: %{y:.2f}%<extra></extra>",
    ))
    fig4.update_layout(**base_layout(300))
    st.plotly_chart(fig4, use_container_width=True)

    # ── Section 5: JOLTS Drill-downs ───────────────────────────────────────────
    st.markdown('<div class="sec">JOLTS Deep Dive</div>', unsafe_allow_html=True)

    if fred.empty:
        st.warning("FRED data unavailable — check FRED_API_KEY in secrets.")
        return

    openings   = get_s(fred, "jolts_openings")
    hires      = get_s(fred, "jolts_hires")
    quits      = get_s(fred, "jolts_quits")
    layoffs    = get_s(fred, "jolts_layoffs")
    separations= get_s(fred, "jolts_separations")

    op_t   = trim(openings)
    hi_t   = trim(hires)
    qu_t   = trim(quits)
    lay_t  = trim(layoffs)
    sep_t  = trim(separations)

    jolts_tabs = st.tabs(["Beveridge Curve", "Flows (Hires/Quits/Layoffs)", "Openings vs Unemployment"])

    # Tab 1 — Beveridge Curve
    with jolts_tabs[0]:
        common_idx = openings.index.intersection(unemp.index).sort_values()
        if len(common_idx) > 12:
            op_bev = openings.reindex(common_idx)
            un_bev = unemp.reindex(common_idx)

            # Color by time for trail effect
            n = len(common_idx)
            # Normalize to 0-1 for color scale
            color_vals = list(range(n))

            fig_bev = go.Figure()
            # Trail — older points smaller/dimmer
            fig_bev.add_trace(go.Scatter(
                name="Beveridge Curve",
                x=un_bev.values,
                y=op_bev.values / 1000,  # convert to millions
                mode="lines+markers",
                line=dict(color="#1e1e3a", width=1),
                marker=dict(
                    size=6,
                    color=color_vals,
                    colorscale=[[0, "#1e3a5f"], [0.5, "#3b82f6"], [1, CYAN]],
                    colorbar=dict(
                        title=dict(text="Time →", font=dict(color=MUTED, size=9)),
                        thickness=8, len=0.5,
                        tickfont=dict(color=MUTED, size=8),
                    ),
                    showscale=True,
                ),
                hovertemplate=(
                    "<b>%{customdata}</b><br>"
                    "Unemployment: %{x:.1f}%<br>"
                    "Job Openings: %{y:.2f}M<extra></extra>"
                ),
                customdata=[d.strftime("%b %Y") for d in common_idx],
            ))
            # Highlight latest point
            fig_bev.add_trace(go.Scatter(
                name="Latest",
                x=[un_bev.iloc[-1]], y=[op_bev.iloc[-1] / 1000],
                mode="markers",
                marker=dict(symbol="star", size=14, color=CYAN,
                            line=dict(color=TEXT, width=1)),
                hovertemplate=f"<b>Latest: {common_idx[-1].strftime('%b %Y')}</b><br>"
                              f"Unemployment: {un_bev.iloc[-1]:.1f}%<br>"
                              f"Openings: {op_bev.iloc[-1]/1000:.2f}M<extra></extra>",
            ))

            layout_bev = base_layout(400, "Job Openings (M) vs Unemployment Rate (%)")
            layout_bev["xaxis"]["title"] = "Unemployment Rate (%)"
            layout_bev["yaxis"]["title"] = "Job Openings (M)"
            layout_bev["hovermode"] = "closest"
            layout_bev["showlegend"] = False
            fig_bev.update_layout(**layout_bev)
            st.plotly_chart(fig_bev, use_container_width=True)

            latest_ratio = op_bev.iloc[-1] / 1000
            latest_un2   = un_bev.iloc[-1]
            st.markdown(
                f'<div class="insight">📍 Latest: <b style="color:{CYAN}">{latest_ratio:.2f}M</b> openings '
                f'at <b style="color:{RED}">{latest_un2:.1f}%</b> unemployment. '
                f'Pre-COVID normal: ~7M openings at ~3.5% unemployment. '
                f'Higher openings / lower unemployment = tighter labor market.</div>',
                unsafe_allow_html=True)
        else:
            st.info("Not enough overlapping data for Beveridge Curve.")

    # Tab 2 — Hires / Quits / Layoffs
    with jolts_tabs[1]:
        fig_fl = go.Figure()
        for name, s, color in [
            ("Hires",   hi_t,  GREEN),
            ("Quits",   qu_t,  AMBER),
            ("Layoffs", lay_t, RED),
        ]:
            fig_fl.add_trace(go.Scatter(
                name=name, x=s.index, y=s.values / 1000,
                line=dict(color=color, width=2),
                hovertemplate=f"<b>{name}</b>: %{{y:.2f}}M<extra></extra>",
            ))

        layout_fl = base_layout(340, "JOLTS Flows (Millions)")
        layout_fl["yaxis"]["title"] = "Millions"
        fig_fl.update_layout(**layout_fl)
        st.plotly_chart(fig_fl, use_container_width=True)

        if len(quits.dropna()) > 1 and len(layoffs.dropna()) > 1:
            latest_q = quits.dropna().iloc[-1] / 1000
            latest_l = layoffs.dropna().iloc[-1] / 1000
            ratio_ql = latest_q / latest_l if latest_l > 0 else 0
            st.markdown(
                f'<div class="insight">🔄 Quits/Layoffs ratio: <b style="color:{AMBER}">{ratio_ql:.2f}x</b>. '
                f'Above 1.5x = workers confident enough to quit (tight market). '
                f'Below 1.0x = defensive labor market.</div>',
                unsafe_allow_html=True)

    # Tab 3 — Openings vs Unemployment level
    with jolts_tabs[2]:
        common_idx2 = openings.index.intersection(unemp.index).sort_values()
        op2 = trim(openings.reindex(common_idx2))
        un2 = trim(unemp.reindex(common_idx2))

        fig_ov = make_subplots(specs=[[{"secondary_y": True}]])
        fig_ov.add_trace(go.Scatter(
            name="Job Openings (M)", x=op2.index, y=op2.values / 1000,
            line=dict(color=CYAN, width=2),
            hovertemplate="<b>Openings</b>: %{y:.2f}M<extra></extra>",
        ), secondary_y=False)
        fig_ov.add_trace(go.Scatter(
            name="Unemployment %", x=un2.index, y=un2.values,
            line=dict(color=RED, width=2, dash="dot"),
            hovertemplate="<b>Unemployment</b>: %{y:.1f}%<extra></extra>",
        ), secondary_y=True)

        fig_ov.update_layout(**base_layout(320))
        fig_ov.update_layout(paper_bgcolor=BG, plot_bgcolor=BG2, hovermode="x unified")
        fig_ov.update_yaxes(title_text="Job Openings (M)", gridcolor=GRID, linecolor=GRID,
                            zeroline=False, secondary_y=False,
                            title_font=dict(color=CYAN, size=10))
        fig_ov.update_yaxes(title_text="Unemployment %", gridcolor="transparent",
                            zeroline=False, secondary_y=True,
                            title_font=dict(color=RED, size=10))
        fig_ov.update_xaxes(gridcolor=GRID, linecolor=GRID)
        st.plotly_chart(fig_ov, use_container_width=True)

    # ── Sector Heatmap ─────────────────────────────────────────────────────────
    st.markdown('<div class="sec">Sector Heatmap — Last 6 Months MoM Change (000s)</div>', unsafe_allow_html=True)

    heat_data = {}
    for name, sid in sector_map.items():
        s  = get_s(bls, sid)
        ch = mom_change(s)
        if len(ch.dropna()) >= 6:
            heat_data[name] = ch.dropna().iloc[-6:]

    if heat_data:
        heat_df = pd.DataFrame(heat_data).T
        heat_df.columns = [d.strftime("%b %Y") for d in heat_df.columns]

        def color_cell(val):
            if pd.isna(val): return "background-color:#0d0d1a;color:#3d3d5c;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
            if val > 80:     return "background-color:#0d4f2b;color:#4ade80;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
            elif val > 30:   return "background-color:#0a3320;color:#34d399;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
            elif val > 0:    return "background-color:#0c2918;color:#6ee7b7;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
            elif val > -30:  return "background-color:#2d1515;color:#fca5a5;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
            elif val > -80:  return "background-color:#3d1010;color:#f87171;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"
            else:            return "background-color:#4d0a0a;color:#ef4444;text-align:center;font-family:monospace;font-size:0.8rem;padding:6px"

        styled = heat_df.style.format("{:+.0f}").applymap(color_cell)
        st.dataframe(styled, use_container_width=True)

    st.markdown(
        f'<div style="color:{MUTED};font-size:0.7rem;margin-top:12px;font-family:monospace">'
        f'Sources: BLS CES (payrolls, wages) · BLS CPS (unemployment, participation) · FRED JOLTS</div>',
        unsafe_allow_html=True)
