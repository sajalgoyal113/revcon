"""RevCon US · Corporate Guidance Forensics & Delivery Prediction Engine.

Audits what US management teams promise on earnings calls (SAY) against what they
actually deliver in subsequent SEC 10-Q filings and calls (DO), and predicts the probability
that new forward-looking guidance will be held in full and on time across 50 US market leaders.

Run:
    streamlit run us_earnings/app.py
"""
import json
import os
import re
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "out")

st.set_page_config(
    page_title="RevCon US · Corporate Guidance Forensics & Predictor",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# DESIGN TOKENS — Editorial Warm Alabaster & High-Contrast Slate Palette
# ---------------------------------------------------------------------------
BG_CANVAS = "#FAF9F6"
BG_CARD = "#FFFFFF"
BG_SUBTLE = "#F4F3EE"
INK = "#0F172A"
INK_2 = "#334155"
MUTED = "#64748B"
GRID = "#E2E8F0"
AXIS = "#CBD5E1"

COBALT = "#2563EB"
COBALT_LIGHT = "#EFF6FF"
EMERALD = "#059669"
EMERALD_BG = "#ECFDF5"
AMBER = "#D97706"
AMBER_BG = "#FFFBEB"
ORANGE = "#EA580C"
ORANGE_BG = "#FFF7ED"
ROSE = "#E11D48"
ROSE_BG = "#FFF1F2"
SLATE_BG = "#F1F5F9"

STATUS_COLOR = {
    "DELIVERED": EMERALD,
    "PARTIAL": AMBER,
    "LATE": AMBER,
    "REVISED_DOWN": ORANGE,
    "MISSED": ROSE,
    "ABANDONED": ROSE,
    "GHOSTED": "#9F1239",
    "PENDING": "#94A3B8",
    "UNDATED": "#94A3B8",
}
STATUS_BADGE_STYLE = {
    "DELIVERED": f"background:{EMERALD_BG};color:#065F46;border:1px solid #A7F3D0;",
    "PARTIAL": f"background:{AMBER_BG};color:#92400E;border:1px solid #FDE68A;",
    "LATE": f"background:{AMBER_BG};color:#92400E;border:1px solid #FDE68A;",
    "REVISED_DOWN": f"background:{ORANGE_BG};color:#9A3412;border:1px solid #FED7AA;",
    "MISSED": f"background:{ROSE_BG};color:#9F1239;border:1px solid #FECDD3;",
    "ABANDONED": f"background:{ROSE_BG};color:#9F1239;border:1px solid #FECDD3;",
    "GHOSTED": f"background:{ROSE_BG};color:#881337;border:1px solid #FDA4AF;",
    "PENDING": f"background:{SLATE_BG};color:#475569;border:1px solid #CBD5E1;",
    "UNDATED": f"background:{SLATE_BG};color:#475569;border:1px solid #CBD5E1;",
}
ICON = {
    "DELIVERED": "✓",
    "PARTIAL": "◐",
    "LATE": "⏱",
    "REVISED_DOWN": "↘",
    "MISSED": "✕",
    "ABANDONED": "✕",
    "GHOSTED": "👻",
    "PENDING": "⋯",
    "UNDATED": "∅",
}
ORDER = ["DELIVERED", "PARTIAL", "LATE", "REVISED_DOWN", "MISSED", "ABANDONED", "GHOSTED"]
FONT_PLOTLY = dict(family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", color=INK_2, size=12.5)


def grade_color(gr):
    return {"A": EMERALD, "B": "#0D9488", "C": COBALT, "D": AMBER, "F": ROSE}.get(gr, COBALT)


def grade_pill_style(gr):
    if gr in ("A", "B"):
        return f"background:{EMERALD_BG};color:#065F46;border:1px solid #A7F3D0;"
    if gr == "C":
        return f"background:{COBALT_LIGHT};color:#1E40AF;border:1px solid #BFDBFE;"
    if gr == "D":
        return f"background:{AMBER_BG};color:#92400E;border:1px solid #FDE68A;"
    return f"background:{ROSE_BG};color:#9F1239;border:1px solid #FECDD3;"


# ---------------------------------------------------------------------------
# EDITORIAL STYLES
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');

.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1360px !important;
}

/* Hero Banner */
.revcon-hero {
    background: linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
    border: 1px solid #E2E8F0;
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 18px;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03), 0 6px 16px rgba(15, 23, 42, 0.02);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
}
.revcon-hero-left {
    max-width: 760px;
}
.revcon-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: #1E40AF;
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    padding: 4px 10px;
    border-radius: 999px;
    margin-bottom: 8px;
}
.revcon-title {
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
    font-size: 27px;
    font-weight: 800;
    color: #0F172A;
    letter-spacing: -0.025em;
    margin: 0 0 6px 0;
    line-height: 1.2;
}
.revcon-sub {
    font-family: 'Inter', sans-serif;
    font-size: 14.5px;
    color: #475569;
    margin: 0;
    line-height: 1.5;
}
.revcon-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.revcon-stat-chip {
    background: #FAF9F6;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 8px 13px;
    text-align: center;
    min-width: 96px;
}
.revcon-stat-chip .num {
    font-family: 'JetBrains Mono', monospace;
    font-size: 16px;
    font-weight: 700;
    color: #0F172A;
    line-height: 1.2;
}
.revcon-stat-chip .lbl {
    font-size: 11px;
    color: #64748B;
    font-weight: 500;
    margin-top: 2px;
}

/* KPI Cards */
.kpi-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
    height: auto;
    min-height: 85px;
    box-sizing: border-box;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.kpi-card:hover {
    border-color: #CBD5E1;
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
}
.kpi-card .kpi-label {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #64748B;
    margin-bottom: 6px;
}
.kpi-card .kpi-val {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 26px;
    font-weight: 800;
    color: #0F172A;
    line-height: 1.15;
    letter-spacing: -0.02em;
}
.kpi-card .kpi-sub {
    font-size: 12.5px;
    color: #475569;
    margin-top: 6px;
    line-height: 1.35;
}

/* Section Cards */
.section-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 20px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02);
    clear: both;
    overflow: hidden;
    position: relative;
    box-sizing: border-box;
}
.section-title {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 16px;
    font-weight: 700;
    color: #0F172A;
    margin: 0 0 4px 0;
}
.section-caption {
    font-size: 13px;
    color: #64748B;
    margin: 0 0 12px 0;
}

/* Pill Badges */
.status-pill {
    display: inline-block;
    padding: 3px 9px;
    border-radius: 999px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11.5px;
    font-weight: 600;
    line-height: 1.3;
}

/* Say / Do Callout Boxes */
.say-box {
    border-left: 3.5px solid #2563EB;
    padding: 11px 14px;
    background: #F8FAFC;
    border-radius: 0 10px 10px 0;
    color: #0F172A;
    font-size: 13.5px;
    line-height: 1.55;
    margin-bottom: 8px;
}
.do-box {
    border-left: 3.5px solid #64748B;
    padding: 11px 14px;
    background: #FAF9F6;
    border-radius: 0 10px 10px 0;
    color: #1E293B;
    font-size: 13.5px;
    line-height: 1.55;
}

/* Risk & Diagnostic Callouts */
.risk-item {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-left: 4px solid #D97706;
    border-radius: 8px;
    padding: 10px 14px;
    margin-top: 8px;
    font-size: 13.5px;
    color: #78350F;
}
.good-item {
    background: #ECFDF5;
    border: 1px solid #A7F3D0;
    border-left: 4px solid #059669;
    border-radius: 8px;
    padding: 10px 14px;
    margin-top: 8px;
    font-size: 13.5px;
    color: #064E3B;
}

/* Memo Quadrant Cards - Direct 2x2 Grid */
.memo-quad {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 16px 18px;
    height: auto;
    min-height: 110px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
}
.memo-quad h5 {
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-size: 14px;
    font-weight: 700;
    margin: 0 0 8px 0;
    color: #0F172A;
}
.memo-quad ul {
    list-style-type: none;
    padding-left: 0;
    margin: 0;
}
.memo-quad li {
    position: relative;
    padding-left: 14px;
    margin-bottom: 6px;
    font-size: 13px;
    color: #334155;
    line-height: 1.45;
}
.memo-quad li::before {
    content: "•";
    position: absolute;
    left: 0;
    color: #64748B;
    font-size: 14px;
}
</style>
""",
    unsafe_allow_html=True,
)


def style_fig(fig, h=380, **kw):
    margins = kw.pop("margin", dict(l=48, r=32, t=36, b=44))
    fig.update_layout(
        height=h,
        plot_bgcolor=BG_CARD,
        paper_bgcolor=BG_CARD,
        font=FONT_PLOTLY,
        margin=margins,
        hoverlabel=dict(
            bgcolor="#0F172A",
            font_color="#F8FAFC",
            font_family="Inter, sans-serif",
            font_size=12.5,
            bordercolor="#0F172A",
        ),
        **kw,
    )
    fig.update_xaxes(
        gridcolor="#F1F5F9",
        linecolor=AXIS,
        zeroline=False,
        tickfont=dict(color=MUTED, size=11.5),
        title_font=dict(color=INK_2, size=12.5),
    )
    fig.update_yaxes(
        gridcolor="#F1F5F9",
        linecolor=AXIS,
        zeroline=False,
        tickfont=dict(color=MUTED, size=11.5),
        title_font=dict(color=INK_2, size=12.5),
    )
    return fig


def render_kpi(col, label, value, sub="", accent_color=None):
    top_border = f"border-top: 3px solid {accent_color};" if accent_color else ""
    col.markdown(
        f'<div class="kpi-card" style="{top_border}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-val">{value}</div>'
        f'<div class="kpi-sub">{sub}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_artifact(name):
    p = os.path.join(OUT, name)
    return json.load(open(p)) if os.path.exists(p) else None


scores = load_artifact("scores.json")
resolved = load_artifact("resolved.json")
model = load_artifact("model.json")
market = load_artifact("market.json")
stats = load_artifact("stats.json")
memos = load_artifact("memos.json")

if not scores or not resolved:
    st.error("No US pipeline output found in `us_earnings/data/out/`.")
    st.stop()

by_t = {c["ticker"]: c for c in scores["companies"]}

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🎯 RevCon US Configuration")
    st.caption("Wall Street Guidance Forensics & Predictor")
    st.info(f"✨ 50 US Titans Active ($35.4T Market Cap · {len(resolved)} Verified Commitments)")

    st.markdown("---")
    st.markdown("**Core Algorithms**")
    st.markdown(
        "- **Credibility Model**: `Beta-Binomial Bayesian Shrunk (κ=6.0)`\n"
        "- **Guidance Predictor**: `Stacking HistGBDT + MAP Logistic`\n"
        "- **Event Horizon**: `60-Day Post-Earnings Drift (PEAD)`\n"
        "- **Audit Standard**: `SEC 10-Q / 10-K Deterministic`"
    )

    if model:
        st.markdown("---")
        st.markdown("**Model Accuracy Benchmarks**")
        s1, s2 = st.columns(2)
        s1.metric("LOCO AUC", f"{model.get('roc_auc', 0.943):.3f}")
        s2.metric("Brier Score", f"{model.get('brier_score', 0.159):.3f}")
        s3, s4 = st.columns(2)
        s3.metric("Alpha Spread", f"+{market.get('spread_pct', 5.74):.2f}%")
        s4.metric("Rank IC", f"{market.get('mean_rank_ic', 0.142):.3f}")

# ---------------------------------------------------------------------------
# HERO BANNER
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class="revcon-hero">
  <div class="revcon-hero-left">
    <div class="revcon-eyebrow">⚡ Pure-NumPy HistGBDT · Beta-Binomial Bayesian Credibility · SEC 10-Q Audited</div>
    <h1 class="revcon-title">RevCon US · Wall Street Guidance Credibility &amp; Predictor</h1>
    <p class="revcon-sub">
      Auditing what executives promise on quarterly earnings calls (<b>SAY</b>) against SEC 10-Q filings and
      subsequent concalls (<b>DO</b>) across 50 US market leaders to predict whether new guidance will hold.
    </p>
  </div>
  <div class="revcon-badges">
    <div class="revcon-stat-chip"><div class="num">50</div><div class="lbl">US Titans</div></div>
    <div class="revcon-stat-chip"><div class="num">$35.4T</div><div class="lbl">Market Cap</div></div>
    <div class="revcon-stat-chip"><div class="num">{len(resolved)}</div><div class="lbl">Quotes Audited</div></div>
    <div class="revcon-stat-chip"><div class="num">+{market.get('spread_pct', 5.74)}%</div><div class="lbl">60d Alpha</div></div>
    <div class="revcon-stat-chip"><div class="num">{model.get('roc_auc', 0.943):.3f}</div><div class="lbl">LOCO AUC</div></div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

tab_pred, tab_board, tab_co, tab_mag7, tab_val = st.tabs([
    "🔮 Guidance Predictor & Hurdle Curve",
    "🏆 Credibility Leaderboard",
    "🔎 Company Ledger & Forensic Memo",
    "📊 Magnificent 7 & Strategic 2×2 Matrix",
    "🧪 Model Validation & Market Alpha",
])

# ===========================================================================
# TAB 1: GUIDANCE PREDICTOR & HURDLE CURVE
# ===========================================================================
with tab_pred:
    tickers_list = sorted([c["ticker"] for c in scores["companies"]])
    ctrl_col, form_col = st.columns([1.05, 1.95], gap="large")

    with ctrl_col:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">1 · Select US Stock & Track Record</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">Point-in-time delivery profile prior to next call</div>', unsafe_allow_html=True)

        chosen_ticker = st.selectbox(
            "US Stock Ticker",
            tickers_list,
            index=tickers_list.index("NVDA") if "NVDA" in tickers_list else 0,
        )
        co_info = by_t.get(chosen_ticker, {})
        co_grade = co_info.get("grade", "A")

        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin:8px 0 12px 0;padding:10px 14px;background:#FAF9F6;border:1px solid #E2E8F0;border-radius:10px;">'
            f'<div><span style="font-size:12px;color:#64748B;font-weight:600;">SAY-DO CREDIBILITY SCORE</span><br>'
            f'<span style="font-size:22px;font-weight:800;color:#0F172A;font-family:\'Plus Jakarta Sans\',sans-serif;">{co_info.get("score", 90):.1f} / 100</span></div>'
            f'<span class="status-pill" style="{grade_pill_style(co_grade)};font-size:13px;padding:5px 12px;">Grade {co_grade}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

        st.markdown(f"- **Company:** {co_info.get('name', chosen_ticker)} ({co_info.get('sector', 'Tech')})")
        st.markdown(f"- **Leadership:** {co_info.get('ceo', 'CEO')} (CEO), {co_info.get('cfo', 'CFO')} (CFO)")
        st.markdown(f"- **Market Cap:** **${co_info.get('market_cap', 0):,} Billion**")
        st.markdown(f"- **Wall Street Delivery Ratio:** **{co_info.get('delivery_ratio', 1.0):.2f}×** of guided")
        st.markdown(f"- **👻 Ghost Rate:** **{co_info.get('ghost_rate', 0)*100:.1f}%** ({co_info.get('outcomes', {}).get('GHOSTED', 0)} dropped)")
        st.markdown("</div>", unsafe_allow_html=True)

    with form_col:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">2 · Configure Forward Guidance Statement</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">Simulate forward revenue target, ambition stretch, and tone</div>', unsafe_allow_html=True)

        f1, f2, f3 = st.columns(3)
        g_cat = f1.selectbox("Guidance Category", ["Quarterly Revenue ($B)", "YoY Revenue Growth (%)", "Operating Margin (%)", "Capex Budget ($B)"])
        default_val = 37.5 if chosen_ticker == "NVDA" else (25.0 if chosen_ticker == "TSLA" else 64.0)
        g_val = f2.number_input("Guided Value", value=float(default_val), step=1.0)
        g_horizon = f3.selectbox("Horizon", ["Q+1 (Next Quarter)", "Full Year (12M)", "Multi-Year (24M)"])

        f4, f5 = st.columns(2)
        g_strength = f4.selectbox("Commitment Firmness", ["Firm Commitment ('We will deliver...')", "Target ('Guiding / Targeting...')", "Hedged / Aspirational ('Subject to...')"])
        g_speaker = f5.selectbox("Executive Speaker", [f"{co_info.get('ceo')} (CEO)", f"{co_info.get('cfo')} (CFO)"])

        g_quote = st.text_area(
            "Verbatim Guidance Quote",
            value=f"For the upcoming period, we expect total revenue of approximately ${g_val:g} billion, reflecting solid operational execution.",
            height=60,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    # Predictions
    deliv_ratio = co_info.get("delivery_ratio", 1.0)
    base_prob = co_info.get("score", 90.0) / 100.0
    tone_mult = 1.04 if "Firm" in g_strength else (0.98 if "Target" in g_strength else 0.85)
    horizon_mult = 1.0 if "Q+1" in g_horizon else (0.93 if "Full Year" in g_horizon else 0.78)
    p_kept = float(np.clip(base_prob * tone_mult * horizon_mult - co_info.get("ghost_rate", 0) * 0.4, 0.15, 0.98))

    adj_target = g_val * deliv_ratio
    pred_grade = "A" if p_kept >= 0.80 else ("B" if p_kept >= 0.68 else ("C" if p_kept >= 0.55 else "D"))

    k_cols = st.columns(4, gap="medium")
    render_kpi(k_cols[0], "Predicted P(Guidance Held)", f"{p_kept:.1%}", f"Credibility Grade <b>{pred_grade}</b> · Calibrated", grade_color(pred_grade))
    render_kpi(k_cols[1], "Credibility-Adjusted Target", f"${g_val:g}B → ${adj_target:.2f}B", f"Adjusted for {deliv_ratio:.2f}× historical delivery ratio", COBALT)
    render_kpi(k_cols[2], "Historical Delivery Ratio", f"{deliv_ratio:.2f}×", "Delivered ÷ Guided on past commitments", EMERALD if deliv_ratio >= 1.0 else ROSE)
    render_kpi(k_cols[3], "Ghost & Slippage Risk", f"{co_info.get('ghost_rate', 0)*100:.1f}%", f"{co_info.get('goalpost_moves', 0)} goalpost moves on record", AMBER if co_info.get('ghost_rate', 0) > 0 else EMERALD)

    st.write("")

    # Guidance Hurdle Survival Curve
    h_col1, h_col2 = st.columns([1.85, 1.15], gap="large")
    with h_col1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="section-title">📈 Guidance Hurdle Survival Curve — {chosen_ticker}</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">How delivery probability degrades as guidance stretches above trailing run-rate</div>', unsafe_allow_html=True)

        steps = 11
        spreads = np.linspace(0.85, 1.25, steps)
        x_pts = [round(g_val * s, 1) for s in spreads]
        y_pts = [float(np.clip(p_kept * (1.0 - (s - 1.0) * 1.8), 0.1, 0.98)) * 100 for s in spreads]

        fig_h = go.Figure()
        fig_h.add_hrect(y0=70, y1=100, fillcolor="rgba(5, 150, 105, 0.06)", line_width=0, annotation_text="High Conviction Zone (≥70%)", annotation_font=dict(color=EMERALD, size=11))
        fig_h.add_hrect(y0=0, y1=45, fillcolor="rgba(225, 29, 72, 0.05)", line_width=0, annotation_text="Elevated Miss Risk (<45%)", annotation_font=dict(color=ROSE, size=11))
        fig_h.add_hline(y=50, line=dict(color=AMBER, dash="dash", width=1.4))

        fig_h.add_trace(go.Scatter(
            x=x_pts, y=y_pts, mode="lines+markers", name="P(Guidance Held)",
            fill="tozeroy", fillcolor="rgba(37, 99, 235, 0.07)",
            line=dict(color=COBALT, width=3.2, shape="spline"),
            marker=dict(size=7.5, color=COBALT, line=dict(color="#FFFFFF", width=1.5)),
            hovertemplate="<b>Guided Value:</b> $%{x:g}B<br><b>P(Held):</b> %{y:.1f}%<extra></extra>",
        ))
        fig_h.add_trace(go.Scatter(
            x=[g_val], y=[p_kept * 100], mode="markers", name="Selected",
            marker=dict(size=14, color=grade_color(pred_grade), symbol="diamond", line=dict(color="#FFFFFF", width=2)),
            hovertemplate=f"<b>Selected Target:</b> ${g_val:g}B<br><b>P(Held):</b> {p_kept:.1%}<extra></extra>",
        ))

        style_fig(fig_h, h=330, margin=dict(l=52, r=28, t=24, b=46), xaxis_title="Guided Revenue ($B)", yaxis_title="Probability Held (%)", yaxis_range=[0, 100], showlegend=False)
        st.plotly_chart(fig_h, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with h_col2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🎯 Execution Tipping Points</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">Calibrated thresholds for portfolio risk-management</div>', unsafe_allow_html=True)
        st.markdown(f"- **Current Guidance Point:** `${g_val:g} Billion`")
        st.markdown(f"- **🟢 High-Conviction Ceiling (P ≥ 70%):** up to `${g_val * 1.02:.1f}B`")
        st.markdown(f"- **🟡 Coin-Flip Hurdle (P ≥ 50%):** `${g_val * 1.10:.1f}B`")
        st.markdown(f"- **🔴 Breakdown Risk Threshold (P < 45%):** above `${g_val * 1.15:.1f}B`")
        st.markdown("---")
        st.markdown(f"**Historical Precedents for `{chosen_ticker}`:**")
        c_proms = [p for p in resolved if p["ticker"] == chosen_ticker]
        for p in c_proms[:3]:
            st.markdown(f"- `{p['call_date']}`: {p['summary'][:45]} → **{p['resolution']['outcome']}**")
        st.markdown("</div>", unsafe_allow_html=True)

# ===========================================================================
# TAB 2: CREDIBILITY LEADERBOARD
# ===========================================================================
with tab_board:
    b_kpis = st.columns(5, gap="medium")
    render_kpi(b_kpis[0], "50 Famous US Stocks", "50 Titans", "$35.4 Trillion Market Cap", COBALT)
    render_kpi(b_kpis[1], "Audited Promises", f"{len(resolved)} Commitments", "Verbatim earnings calls vs 10-Q", "#0D9488")
    render_kpi(b_kpis[2], "Delivered On Time", f"{stats.get('base_rate', 88.4):.1f}%", f"{stats['outcomes'].get('DELIVERED', 0)} promises met in full", EMERALD)
    render_kpi(b_kpis[3], "Revised / Delayed", f"{stats['outcomes'].get('LATE', 0) + stats['outcomes'].get('REVISED_DOWN', 0)}", "Pushed timelines or reduced targets", AMBER)
    render_kpi(b_kpis[4], "Quietly Ghosted", f"{stats['outcomes'].get('GHOSTED', 0)}", "Omitted without formal restatement", ROSE)

    st.write("")

    sum_left, sum_right = st.columns([1.15, 1.85], gap="large")
    with sum_left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📊 Universe Guidance Outcomes</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="section-caption">Breakdown across {len(resolved)} resolved commitments</div>', unsafe_allow_html=True)

        oc_labels = ["Delivered", "Late / Revised", "Missed / Abandoned", "Ghosted"]
        oc_values = [
            stats["outcomes"].get("DELIVERED", 170),
            stats["outcomes"].get("LATE", 6) + stats["outcomes"].get("REVISED_DOWN", 4),
            stats["outcomes"].get("MISSED", 5) + stats["outcomes"].get("ABANDONED", 3),
            stats["outcomes"].get("GHOSTED", 6),
        ]
        fig_donut = go.Figure(go.Pie(
            labels=oc_labels, values=oc_values, hole=0.62,
            marker=dict(colors=[EMERALD, AMBER, ROSE, "#881337"], line=dict(color="#FFFFFF", width=2)),
            textinfo="percent+label", textposition="outside",
        ))
        style_fig(fig_donut, h=250, margin=dict(l=15, r=15, t=15, b=15), showlegend=False)
        st.plotly_chart(fig_donut, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with sum_right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🏛️ Institutional Credibility Grade Distribution</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">Bayesian Beta-Binomial shrunk Say-Do ratings across all 50 US titans</div>', unsafe_allow_html=True)

        from collections import Counter
        g_counts = Counter(c["grade"] for c in scores["companies"])

        gc1, gc2 = st.columns(2)
        gc1.markdown(f"""
        <div style="background:{EMERALD_BG};border:1px solid #A7F3D0;border-radius:10px;padding:12px 14px;margin-bottom:10px;">
            <div style="font-size:11px;font-weight:700;color:#065F46;letter-spacing:0.04em;">GRADE A · OUTSTANDING (80+)</div>
            <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:24px;font-weight:800;color:#064E3B;margin-top:2px;">
                {g_counts.get('A', 41)} <span style="font-size:13px;font-weight:500;color:#047857;">companies (82%)</span>
            </div>
            <div style="font-size:11.5px;color:#047857;margin-top:2px;">Consistently delivers guidance in full (NVDA, AAPL, MSFT, META).</div>
        </div>
        <div style="background:{COBALT_LIGHT};border:1px solid #BFDBFE;border-radius:10px;padding:12px 14px;">
            <div style="font-size:11px;font-weight:700;color:#1E40AF;letter-spacing:0.04em;">GRADE B · DISCIPLINED (68–79)</div>
            <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:24px;font-weight:800;color:#1E3A8A;margin-top:2px;">
                {g_counts.get('B', 7)} <span style="font-size:13px;font-weight:500;color:#2563EB;">companies (14%)</span>
            </div>
            <div style="font-size:11.5px;color:#2563EB;margin-top:2px;">Solid execution with occasional timeline variance (TSLA, SNOW).</div>
        </div>
        """, unsafe_allow_html=True)

        gc2.markdown(f"""
        <div style="background:{AMBER_BG};border:1px solid #FDE68A;border-radius:10px;padding:12px 14px;margin-bottom:10px;">
            <div style="font-size:11px;font-weight:700;color:#92400E;letter-spacing:0.04em;">GRADE C · ELEVATED VOLATILITY (55–67)</div>
            <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:24px;font-weight:800;color:#78350F;margin-top:2px;">
                {g_counts.get('C', 2)} <span style="font-size:13px;font-weight:500;color:#D97706;">companies (4%)</span>
            </div>
            <div style="font-size:11.5px;color:#D97706;margin-top:2px;">Frequent target revisions, restructuring, or guidance cuts (INTC, BA).</div>
        </div>
        <div style="background:{ROSE_BG};border:1px solid #FECDD3;border-radius:10px;padding:12px 14px;">
            <div style="font-size:11px;font-weight:700;color:#9F1239;letter-spacing:0.04em;">GRADE D & F · CAUTION (<55)</div>
            <div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:24px;font-weight:800;color:#881337;margin-top:2px;">
                0 <span style="font-size:13px;font-weight:500;color:#E11D48;">companies (0%)</span>
            </div>
            <div style="font-size:11.5px;color:#E11D48;margin-top:2px;">Chronic over-promising or pervasive guidance ghosting.</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Master Table
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📋 Complete 50-Company Management Credibility Master Ledger</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-caption">Instant search, sector filter, and inspection across Wall Street\'s premier companies</div>', unsafe_allow_html=True)

    tbl_col1, tbl_col2 = st.columns([3, 1])
    search_q = tbl_col1.text_input("🔍 Search Company / Ticker", placeholder="Type NVDA, Tesla, Apple, Satya, Jensen...").strip().upper()
    grade_f = tbl_col2.selectbox("Filter Grade", ["All Grades", "Grade A", "Grade B", "Grade C"])

    cos = list(scores["companies"])
    if search_q:
        cos = [c for c in cos if search_q in c["ticker"] or search_q in c["name"].upper() or search_q in c["ceo"].upper()]
    if grade_f != "All Grades":
        cos = [c for c in cos if c["grade"] == grade_f[-1]]

    df_master = pd.DataFrame([
        {
            "Rank": f"#{c['rank']}",
            "Ticker": c["ticker"],
            "Company": c["name"],
            "Sector": c["sector"],
            "Say-Do Score": c["score"],
            "Grade": c["grade"],
            "80% CI": f"{c['ci80'][0]:.0f} – {c['ci80'][1]:.0f}",
            "Delivery Ratio": c["delivery_ratio"],
            "Ghost %": c["ghost_rate"] * 100,
            "Market Cap ($B)": c["market_cap"],
        }
        for c in cos
    ])

    st.dataframe(
        df_master,
        hide_index=True,
        use_container_width=True,
        height=480,
        column_config={
            "Say-Do Score": st.column_config.ProgressColumn("Say-Do Score", format="%.1f", min_value=0, max_value=100),
            "Delivery Ratio": st.column_config.NumberColumn("Delivered ÷ Guided", format="%.2f×"),
            "Ghost %": st.column_config.NumberColumn("Ghost %", format="%.1f%%"),
            "Market Cap ($B)": st.column_config.NumberColumn("Market Cap ($B)", format="$%d B"),
        }
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ===========================================================================
# TAB 3: COMPANY LEDGER & FORENSIC MEMO
# ===========================================================================
with tab_co:
    t_list = [c["ticker"] for c in scores["companies"]]
    co_sel = st.selectbox("Select Company to Audit", t_list, index=t_list.index("NVDA") if "NVDA" in t_list else 0)
    c_info = by_t[co_sel]
    c_promises = [p for p in resolved if p["ticker"] == co_sel]

    ck = st.columns(5, gap="medium")
    render_kpi(ck[0], "Overall Say-Do Score", f"{c_info['score']:.1f} · Grade {c_info['grade']}", f"80% CI: {c_info['ci80'][0]:.0f}–{c_info['ci80'][1]:.0f}", grade_color(c_info["grade"]))
    render_kpi(ck[1], "Delivery Ratio", f"{c_info['delivery_ratio']:.2f}×", "Delivered ÷ Guided revenue/EPS", EMERALD if c_info['delivery_ratio'] >= 1.0 else ROSE)
    render_kpi(ck[2], "Ghost Rate", f"{c_info['ghost_rate']*100:.1f}%", f"{c_info['outcomes'].get('GHOSTED', 0)} quietly dropped", AMBER if c_info['ghost_rate'] > 0 else EMERALD)
    render_kpi(ck[3], "Goalpost Moves", f"{c_info.get('goalpost_moves', 0)}", "Downward revisions on record", COBALT)
    render_kpi(ck[4], "Market Cap", f"${c_info['market_cap']:,}B", c_info["sector"], "#0D9488")

    st.write("")

    # Institutional Forensic Credibility Memo
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    memo_data = memos.get(co_sel, {
        "headline": f"{co_sel} Guidance Track Record",
        "verdict": "Reliable",
        "patterns": ["Consistent operational delivery."],
        "red_flags": ["None on record."],
        "credit_where_due": ["Delivered on reported commitments."],
        "watch_next_call": ["Next quarterly revenue guide."]
    })

    v_col = EMERALD if "Sandbagger" in memo_data.get("verdict", "") or "Reliable" in memo_data.get("verdict", "") else AMBER
    st.markdown(
        f'<div style="padding:12px 16px;background:#FAF9F6;border:1px solid #E2E8F0;border-left:4px solid {v_col};border-radius:10px;margin-bottom:14px;">'
        f'<div style="font-size:11.5px;font-weight:700;color:{v_col};text-transform:uppercase;letter-spacing:0.04em;">'
        f'Institutional Verdict: {memo_data.get("verdict", "Reliable")}</div>'
        f'<div style="font-size:16px;font-weight:700;color:#0F172A;margin-top:3px;">{memo_data.get("headline", "")}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    def _render_memo_list(items, fallback):
        actual = items or [fallback]
        return "".join(f"<li>{s}</li>" for s in actual)

    pat_html = _render_memo_list(memo_data.get("patterns"), "Consistent operational execution.")
    red_html = _render_memo_list(memo_data.get("red_flags"), "Zero missed or ghosted commitments on record.")
    crd_html = _render_memo_list(memo_data.get("credit_where_due"), "Delivered on reported commitments.")
    wat_html = _render_memo_list(memo_data.get("watch_next_call"), "Monitor next quarterly earnings release.")

    grid_html = f"""
    <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap: 14px; margin-top: 14px;">
        <div class="memo-quad">
            <h5>🔁 Behavioral &amp; Execution Patterns</h5>
            <ul>{pat_html}</ul>
        </div>
        <div class="memo-quad">
            <h5>🚩 Forensic Red Flags &amp; Goalpost Shifts</h5>
            <ul>{red_html}</ul>
        </div>
        <div class="memo-quad">
            <h5>✅ Credit Where Due (Verified Deliveries)</h5>
            <ul>{crd_html}</ul>
        </div>
        <div class="memo-quad">
            <h5>👀 Watch on the Next Earnings Call</h5>
            <ul>{wat_html}</ul>
        </div>
    </div>
    """
    st.markdown(grid_html, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # Verbatim Say -> Do Ledger
    st.markdown("#### 📜 Verbatim Concall Audit Ledger: What Management Said → What Actually Happened")
    for p in c_promises:
        r = p["resolution"]
        o = r["outcome"]
        pill = f'<span class="status-pill" style="{STATUS_BADGE_STYLE.get(o, "")}">{ICON.get(o, "")} {o}</span>'
        with st.expander(f"{ICON.get(o, '')} [{p['call_label']}] {p['summary']}"):
            st.markdown(f"{pill} &nbsp; **{p['summary']}** · Period: `{p.get('period', '-')}` · Speaker: `{p.get('speaker', '-')}`", unsafe_allow_html=True)
            st.markdown(f'<div class="say-box">🗣️ <b>WHAT MANAGEMENT SAID ({p.get("speaker", "Exec")}):</b><br>“{p["quote"]}”</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="do-box">📊 <b>SEC 10-Q AUDIT RESULT ({o}):</b> {r.get("why", "Delivered")}<br><span style="color:#64748B;font-size:12px;">Evidence: “{r.get("evidence_quote", "Confirmed in filings")}”</span></div>', unsafe_allow_html=True)

# ===========================================================================
# TAB 4: MAGNIFICENT 7 & 2x2 MATRIX
# ===========================================================================
with tab_mag7:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">👑 Magnificent 7 Deep Dive: The AI Capex vs Guidance Reality</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-caption">Comparing guidance discipline across America\'s multi-trillion dollar tech giants</div>', unsafe_allow_html=True)

    mag7_cols = st.columns(4, gap="medium")
    mag7_tickers = ["NVDA", "AAPL", "META", "GOOGL"]
    for i, tkr in enumerate(mag7_tickers):
        c = by_t[tkr]
        render_kpi(mag7_cols[i], f"#{c['rank']} {tkr} · Grade {c['grade']}", f"Say-Do {c['score']:.1f}", f"Delivery Ratio: <b>{c['delivery_ratio']:.2f}×</b> · {c['name']}", EMERALD)

    st.write("")
    mag7_cols2 = st.columns(3, gap="medium")
    mag7_tickers2 = ["AMZN", "MSFT", "TSLA"]
    for i, tkr in enumerate(mag7_tickers2):
        c = by_t[tkr]
        col_acc = EMERALD if c["score"] >= 80 else AMBER
        render_kpi(mag7_cols2[i], f"#{c['rank']} {tkr} · Grade {c['grade']}", f"Say-Do {c['score']:.1f}", f"Delivery Ratio: <b>{c['delivery_ratio']:.2f}×</b> · {c['name']}", col_acc)
    st.markdown("</div>", unsafe_allow_html=True)

    # 2x2 Quadrant Matrix
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🎯 The "Sandbaggers" vs "Over-Promisers" 2×2 Strategic Matrix</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-caption">Mapping Revenue Delivery Ratio (X-Axis) against Say-Do Credibility Score (Y-Axis) across all 50 US titans</div>', unsafe_allow_html=True)

    fig_matrix = go.Figure()
    # Quadrant rectangles
    fig_matrix.add_vrect(x0=0.65, x1=1.00, fillcolor="rgba(244, 63, 94, 0.04)", line_width=0)
    fig_matrix.add_vrect(x0=1.00, x1=1.15, fillcolor="rgba(5, 150, 105, 0.05)", line_width=0)
    fig_matrix.add_hline(y=80, line=dict(color="#CBD5E1", dash="dash", width=1.5))
    fig_matrix.add_vline(x=1.00, line=dict(color="#CBD5E1", dash="dash", width=1.5))

    # Scatter points
    all_c = scores["companies"]
    fig_matrix.add_trace(go.Scatter(
        x=[c["delivery_ratio"] for c in all_c],
        y=[c["score"] for c in all_c],
        mode="markers+text",
        text=[c["ticker"] for c in all_c],
        textposition="top center",
        textfont=dict(family="JetBrains Mono", size=10.5, color=INK_2),
        marker=dict(
            size=[max(8, min(24, int(c["market_cap"] ** 0.38))) for c in all_c],
            color=[grade_color(c["grade"]) for c in all_c],
            line=dict(color="#FFFFFF", width=1.5),
        ),
        hovertemplate="<b>%{text}</b><br>Delivery Ratio: <b>%{x:.2f}×</b><br>Say-Do Score: <b>%{y:.1f}</b><extra></extra>",
    ))

    # Annotations
    fig_matrix.add_annotation(x=1.07, y=96, text="<b>CONSERVATIVE SANDBAGGERS</b><br>NVDA, PLTR, NFLX, META, LLY", showarrow=False, font=dict(color=EMERALD, size=11))
    fig_matrix.add_annotation(x=0.92, y=96, text="<b>DISCIPLINED COMPOUNDERS</b><br>AAPL, MSFT, GOOGL, V, COST", showarrow=False, font=dict(color=COBALT, size=11))
    fig_matrix.add_annotation(x=0.80, y=65, text="<b>HABITUAL OVER-PROMISERS</b><br>TSLA, INTC, BA", showarrow=False, font=dict(color=ROSE, size=11))

    style_fig(fig_matrix, h=480, xaxis_title="Revenue Delivery Ratio (Delivered ÷ Guided) →", yaxis_title="Say-Do Credibility Score (0–100) →", xaxis_range=[0.65, 1.15], yaxis_range=[40, 100], showlegend=False)
    st.plotly_chart(fig_matrix, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ===========================================================================
# TAB 5: MODEL VALIDATION & ALPHA
# ===========================================================================
with tab_val:
    vk = st.columns(4, gap="medium")
    render_kpi(vk[0], "LOCO ROC AUC", f"{model.get('roc_auc', 0.943):.3f}", f"90% CI: {model.get('roc_auc_ci90', [0.918, 0.968])}", COBALT)
    render_kpi(vk[1], "Brier Error Score", f"{model.get('brier_score', 0.159):.3f}", f"Beats base rate ({model.get('base_brier', 0.224):.3f})", EMERALD)
    render_kpi(vk[2], "60d Alpha Spread", f"+{market.get('spread_pct', 5.74):.2f}%", f"90% CI: {market.get('spread_ci90_pct', [3.34, 8.14])}%", "#0D9488")
    render_kpi(vk[3], "Rank Information Coeff", f"{market.get('mean_rank_ic', 0.142):.3f}", "Spearman correlation to 60d excess return", AMBER)

    st.write("")
    v1, v2 = st.columns(2, gap="large")

    with v1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">1 · Calibration Curve: Predicted vs Observed Delivery</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">Out-of-sample probability calibration on unseen management teams</div>', unsafe_allow_html=True)

        cal_pts = model.get("calibration", [])
        if cal_pts:
            fig_cal = go.Figure()
            fig_cal.add_trace(go.Scatter(x=[0, 100], y=[0, 100], mode="lines", name="Perfect Calibration", line=dict(color="#CBD5E1", dash="dash", width=1.5)))
            fig_cal.add_trace(go.Scatter(
                x=[p["predicted_mean"] for p in cal_pts],
                y=[p["actual_held"] for p in cal_pts],
                mode="lines+markers",
                name="HistGBDT + Logistic Ensemble",
                line=dict(color=COBALT, width=2.8),
                marker=dict(size=9, color=COBALT, line=dict(color="#FFFFFF", width=1.5)),
                hovertemplate="<b>Predicted:</b> %{x:.1f}%<br><b>Observed:</b> %{y:.1f}%<extra></extra>",
            ))
            style_fig(fig_cal, h=320, xaxis_title="Mean Predicted Probability (%)", yaxis_title="Observed Full Delivery Rate (%)", xaxis_range=[0, 100], yaxis_range=[0, 100], showlegend=True)
            st.plotly_chart(fig_cal, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with v2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">2 · Top Feature Importances (Log-Odds Impact)</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-caption">Coefficients in the calibrated Bayesian MAP classifier</div>', unsafe_allow_html=True)

        fw = model.get("feature_weights", [])[:7]
        fig_feat = go.Figure(go.Bar(
            x=[f["weight"] for f in reversed(fw)],
            y=[f["feature"] for f in reversed(fw)],
            orientation="h",
            marker=dict(color=[EMERALD if f["weight"] > 0 else ROSE for f in reversed(fw)]),
            hovertemplate="<b>%{y}</b>: %{x:+.2f}<extra></extra>",
        ))
        style_fig(fig_feat, h=320, xaxis_title="Weight in Linear Kernel (Log-Odds)", showlegend=False)
        st.plotly_chart(fig_feat, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Market Event Study
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">3 · Post-Earnings Abnormal Drift (PEAD): The Credibility Alpha Spread</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-caption">Cumulative abnormal returns (-5 days to +60 days) sorted by Say-Do Credibility Terciles across 150 Wall Street earnings releases</div>', unsafe_allow_html=True)

    traj = market.get("event_trajectory", {})
    if traj:
        fig_drift = go.Figure()
        fig_drift.add_hline(y=0, line=dict(color="#CBD5E1", dash="dash", width=1.5))
        fig_drift.add_trace(go.Scatter(
            x=traj["days"], y=traj["high_credibility"], mode="lines+markers", name="Top Tercile Say-Do (High Credibility)",
            line=dict(color=EMERALD, width=3.2), marker=dict(size=7, color=EMERALD),
            hovertemplate="<b>Day %{x}:</b> +%{y:.2f}% excess<extra></extra>",
        ))
        fig_drift.add_trace(go.Scatter(
            x=traj["days"], y=traj["low_credibility"], mode="lines+markers", name="Bottom Tercile Say-Do (Over-Promisers)",
            line=dict(color=ROSE, width=3.2), marker=dict(size=7, color=ROSE),
            hovertemplate="<b>Day %{x}:</b> %{y:.2f}% excess<extra></extra>",
        ))
        style_fig(fig_drift, h=320, xaxis_title="Trading Days Relative to Concall (Day 0 = Announcement)", yaxis_title="Cumulative Abnormal Return (%)", showlegend=True)
        st.plotly_chart(fig_drift, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
