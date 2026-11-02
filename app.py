"""Concall: Management Guidance Accuracy & Credibility Prediction Engine.

Uses past management guidance of Indian listed companies to predict future accuracy
of holding future guidance of the same company.

Run: streamlit run app.py --server.address 127.0.0.1
"""
import json
import os
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from saydo import config, history, predict

st.set_page_config(
    page_title="Concall · Guidance Accuracy Predictor",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---- design tokens (dark premium system) ----
SURF, INK, INK2, MUTED, GRID, AXIS = "#06080d", "#f8fafc", "#cbd5e1", "#94a3b8", "rgba(255,255,255,0.08)", "#334155"
BLUE = "#818cf8"
TEAL = "#00d2ff"
EMERALD = "#00f5a0"
AMBER = "#ffb703"
ROSE = "#ff4d6d"
STATUS = {
    "DELIVERED": "#10b981", "PARTIAL": "#f59e0b", "LATE": "#f59e0b", "REVISED_DOWN": "#fb923c",
    "MISSED": "#f43f5e", "ABANDONED": "#f43f5e", "GHOSTED": "#f43f5e", "PENDING": "#475569", "UNDATED": "#475569"
}
ICON = {
    "DELIVERED": "✅", "PARTIAL": "◐", "LATE": "⏱", "REVISED_DOWN": "↘", "MISSED": "✖",
    "ABANDONED": "✖", "GHOSTED": "👻", "PENDING": "…", "UNDATED": "∅"
}
ORDER = ["DELIVERED", "PARTIAL", "LATE", "REVISED_DOWN", "MISSED", "ABANDONED", "GHOSTED"]
FONT = dict(family="'Inter', system-ui, sans-serif", color=INK2, size=13)

# ---- Clean, Aesthetic, Institutional Styling ----
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700;800&family=Outfit:wght@500;600;700;800;900&display=swap" rel="stylesheet">

<style>
:root {
  --bg-main: #070a12;
  --bg-card: #0d121f;
  --border-subtle: rgba(255, 255, 255, 0.08);
  --border-hover: rgba(99, 102, 241, 0.4);
  --accent-primary: #6366f1;
  --accent-cyan: #00d2ff;
  --accent-emerald: #10b981;
  --accent-amber: #f59e0b;
  --accent-rose: #f43f5e;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --text-tertiary: #64748b;
  --font-heading: 'Outfit', sans-serif;
  --font-body: 'Inter', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

/* Global App */
.stApp {
  background-color: var(--bg-main) !important;
  background-image: 
    radial-gradient(circle at 50% -10%, rgba(99, 102, 241, 0.14) 0%, transparent 60%),
    radial-gradient(circle at 90% 15%, rgba(0, 210, 255, 0.06) 0%, transparent 45%) !important;
  font-family: var(--font-body) !important;
  color: var(--text-primary) !important;
}

#MainMenu, footer { visibility: hidden !important; }
header[data-testid="stHeader"] { background: transparent !important; }

/* Page Headroom */
.block-container {
  padding-top: 1.8rem !important;
  padding-bottom: 3rem !important;
  max-width: 1340px !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
  background: rgba(10, 14, 24, 0.96) !important;
  border-right: 1px solid var(--border-subtle) !important;
}
section[data-testid="stSidebar"] * {
  font-family: var(--font-body) !important;
}

/* Unified Compact Header */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 22px;
  background: rgba(13, 18, 31, 0.85);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  margin-bottom: 22px;
  box-shadow: 0 4px 24px -2px rgba(0, 0, 0, 0.5);
  flex-wrap: wrap;
  gap: 14px;
}
.brand-group {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-logo {
  width: 44px;
  height: 44px;
  border-radius: 13px;
  background: linear-gradient(135deg, #6366f1 0%, #00d2ff 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 23px;
  box-shadow: 0 0 24px rgba(99, 102, 241, 0.45);
}
.brand-title {
  font-family: var(--font-heading);
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #fff;
  line-height: 1.1;
}
.brand-sub {
  font-size: 0.8rem;
  color: var(--text-secondary);
  font-weight: 500;
  margin-top: 2px;
}
.header-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.stat-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-subtle);
  font-family: var(--font-mono);
  font-size: 11.5px;
}
.stat-pill .k {
  color: var(--text-tertiary);
  text-transform: uppercase;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
}
.stat-pill .v {
  color: #f8fafc;
  font-weight: 700;
}
.live-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 13px;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.35);
  color: #818cf8 !important;
  font-family: var(--font-mono);
  font-size: 11.5px;
  font-weight: 700;
  text-decoration: none;
  transition: all 0.2s ease;
}
.live-link:hover {
  background: rgba(99, 102, 241, 0.25);
  border-color: rgba(99, 102, 241, 0.6);
  color: #a5b4fc !important;
}

/* Card Boxes */
.card-box {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 22px;
  box-shadow: 0 4px 24px -2px rgba(0, 0, 0, 0.45);
  margin-bottom: 16px;
  height: 100%;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.card-title {
  font-family: var(--font-heading);
  font-size: 1.15rem;
  font-weight: 700;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
}
.meta-tag {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 3px 9px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  border: 1px solid rgba(99, 102, 241, 0.3);
}

/* KPI Card */
.kpi {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 16px 18px;
  box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.4);
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  position: relative;
  overflow: hidden;
}
.kpi:hover {
  transform: translateY(-2px);
  border-color: var(--border-hover);
  box-shadow: 0 8px 25px -4px rgba(0, 0, 0, 0.6);
}
.kpi .l {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.kpi .v {
  font-family: var(--font-mono);
  font-size: 1.75rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #fff;
  margin: 0;
  line-height: 1.15;
}
.kpi .s {
  font-family: var(--font-body);
  font-size: 0.74rem;
  color: var(--text-tertiary);
  margin-top: 6px;
  font-weight: 500;
}

/* 2x2 Metric Grid */
.stat-grid-2x2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 14px;
}
.mini-stat {
  background: rgba(7, 10, 18, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 12px 14px;
}
.mini-stat .k {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-tertiary);
}
.mini-stat .v {
  font-family: var(--font-mono);
  font-size: 1.35rem;
  font-weight: 800;
  color: #fff;
  margin-top: 3px;
  line-height: 1.1;
}
.mini-stat .s {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 3px;
}

/* Executive Verdict Banner */
.verdict-banner {
  border-radius: 16px;
  padding: 18px 22px;
  border: 1px solid;
  margin: 18px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

/* Glowing Border Utilities */
.glow-emerald {
  border-color: rgba(16, 185, 129, 0.35) !important;
  box-shadow: 0 0 25px -5px rgba(16, 185, 129, 0.25) !important;
}
.glow-indigo {
  border-color: rgba(99, 102, 241, 0.35) !important;
  box-shadow: 0 0 25px -5px rgba(99, 102, 241, 0.25) !important;
}
.glow-amber {
  border-color: rgba(245, 158, 11, 0.35) !important;
  box-shadow: 0 0 25px -5px rgba(245, 158, 11, 0.25) !important;
}
.glow-rose {
  border-color: rgba(244, 63, 94, 0.35) !important;
  box-shadow: 0 0 25px -5px rgba(244, 63, 94, 0.25) !important;
}

/* Pulsing Beacons */
@keyframes beacon {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.35; transform: scale(0.85); }
}
.pulse-emerald {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  animation: beacon 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
.pulse-cyan {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #00d2ff;
  animation: beacon 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
.pulse-amber {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f59e0b;
  animation: beacon 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
.pulse-rose {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f43f5e;
  animation: beacon 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

/* Verbatim Quote Blocks */
.say {
  border-left: 3px solid #6366f1;
  padding: 12px 16px;
  background: rgba(99, 102, 241, 0.08);
  border-radius: 0 10px 10px 0;
  color: #e2e8f0;
  font-size: 0.88rem;
  line-height: 1.6;
  margin-bottom: 8px;
}
.do {
  border-left: 3px solid #10b981;
  padding: 12px 16px;
  background: rgba(16, 185, 129, 0.06);
  border-radius: 0 10px 10px 0;
  color: #cbd5e1;
  font-size: 0.88rem;
  line-height: 1.6;
}
.tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 700;
  font-family: var(--font-mono);
}
.risk-box {
  background: rgba(244, 63, 94, 0.08);
  border-left: 3px solid #f43f5e;
  padding: 12px 16px;
  border-radius: 0 10px 10px 0;
  margin-top: 8px;
  font-size: 13px;
  color: #fecdd3;
  line-height: 1.55;
}

/* Streamlit Tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 6px;
  background: rgba(13, 18, 31, 0.95);
  padding: 6px;
  border-radius: 14px;
  border: 1px solid var(--border-subtle);
  margin-bottom: 20px;
}
.stTabs [data-baseweb="tab"] {
  border-radius: 10px;
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 0.9rem;
  font-family: var(--font-body);
  padding: 9px 18px;
  border: none !important;
  transition: all 0.2s ease;
}
.stTabs [aria-selected="true"] {
  background: rgba(99, 102, 241, 0.2) !important;
  color: #fff !important;
  border: 1px solid rgba(99, 102, 241, 0.5) !important;
  box-shadow: 0 2px 10px -2px rgba(99, 102, 241, 0.3) !important;
}

/* Streamlit Inputs */
.stTextInput > div > div > input, .stNumberInput input, .stTextArea textarea {
  background: #070a12 !important;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  border-radius: 10px !important;
  color: #fff !important;
  font-family: var(--font-body) !important;
}
.stTextInput > div > div > input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
  border-color: var(--accent-primary) !important;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.25) !important;
}
div[data-baseweb="select"] > div {
  background: #070a12 !important;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  border-radius: 10px !important;
  color: #fff !important;
}
div[data-baseweb="select"] * {
  color: #fff !important;
  font-family: var(--font-body) !important;
}
div[data-baseweb="popover"] ul {
  background: #0b0f19 !important;
  border: 1px solid rgba(255, 255, 255, 0.15) !important;
  border-radius: 12px !important;
}
div[data-baseweb="popover"] li {
  color: #e2e8f0 !important;
}
div[data-baseweb="popover"] li:hover {
  background: rgba(99, 102, 241, 0.25) !important;
  color: #fff !important;
}

/* Primary Button */
.stButton > button {
  background: #111827 !important;
  border: 1px solid rgba(255, 255, 255, 0.12) !important;
  border-radius: 12px !important;
  color: var(--text-primary) !important;
  font-weight: 600 !important;
  font-family: var(--font-body) !important;
  padding: 0.6rem 1.25rem !important;
  transition: all 0.2s ease !important;
}
.stButton > button:hover {
  background: #1e293b !important;
  border-color: rgba(99, 102, 241, 0.5) !important;
  color: #fff !important;
  box-shadow: 0 4px 14px -2px rgba(99, 102, 241, 0.25) !important;
  transform: translateY(-1px);
}
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #6366f1 0%, #4338ca 100%) !important;
  border: 1px solid rgba(255, 255, 255, 0.18) !important;
  color: #fff !important;
  border-radius: 12px !important;
  font-weight: 700 !important;
  box-shadow: 0 0 20px -2px rgba(99, 102, 241, 0.45) !important;
  width: 100% !important;
}
.stButton > button[kind="primary"]:hover {
  background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%) !important;
  box-shadow: 0 0 25px rgba(99, 102, 241, 0.65) !important;
}

details {
  border: 1px solid var(--border-subtle) !important;
  border-radius: 12px !important;
  background: var(--bg-card) !important;
  margin-bottom: 8px !important;
}
details:hover {
  border-color: rgba(99, 102, 241, 0.3) !important;
}
details summary {
  padding: 12px 16px !important;
  font-weight: 600 !important;
  color: #f8fafc !important;
}
code {
  font-family: var(--font-mono) !important;
  color: #a5b4fc !important;
}
</style>
""", unsafe_allow_html=True)


def layout(fig, h=420, **kw):
    fig.update_layout(
        height=h,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=FONT,
        margin=dict(l=10, r=20, t=30, b=10),
        hoverlabel=dict(bgcolor="#0e1420", font_color="#f8fafc", font_family="'JetBrains Mono', monospace"),
        **kw
    )
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED, family="'JetBrains Mono', monospace", size=11))
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED, family="'JetBrains Mono', monospace", size=11))
    return fig


def kpi(col, value, label, sub=None, glow=""):
    glow_class = f" glow-{glow}" if glow else ""
    sub_html = f'<div class="s">{sub}</div>' if sub else ""
    col.markdown(f'<div class="kpi{glow_class}"><div class="l">{label}</div><div class="v">{value}</div>{sub_html}</div>',
                 unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load(name):
    p = os.path.join(config.OUT, name)
    return json.load(open(p)) if os.path.exists(p) else None


scores, resolved, model, market, stats = (load(n) for n in
                                           ("scores.json", "resolved.json", "model.json", "market.json", "stats.json"))
if not scores or not resolved:
    st.error("No pipeline output found. Run `python -m saydo.pipeline all` to build artifacts.")
    st.stop()

by_t = {c["ticker"]: c for c in scores["companies"]}
preds = (model or {}).get("predictions", {})

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Engine Settings")
    st.markdown("**Frontier AI Provider:** Meta Muse (Active)")

    user_meta_key = st.text_input(
        "Meta Model API Key",
        value=config.META_API_KEY,
        type="password",
        placeholder="metamodel_...",
        help="Key from Meta Model API for live concall parsing"
    )
    if user_meta_key:
        os.environ["META_MODEL_API_KEY"] = user_meta_key
        st.success("🟢 Muse Active")
    elif config.META_API_KEY:
        st.success("🟢 Muse Active (.env)")
    else:
        st.warning("⚠️ Enter Meta Model API Key for live concall parsing")

    st.markdown("---")
    st.markdown("**Predictive Architecture:**")
    st.markdown("- **Ensemble Stacking**: HistGBDT + Bayesian MAP Logistic Regression")
    st.markdown(f"- **LOCO ROC AUC**: `{model['evaluation']['loco']['auc_model']:.3f}`")
    st.markdown(f"- **Walk-Forward AUC**: `{model['evaluation']['walk_forward']['auc_model']:.3f}`")
    st.markdown("---")
    st.markdown(f"**Live Web App:** [revcon.streamlit.app](https://revcon.streamlit.app/)")


# Unified Compact Top Bar
st.markdown(f"""
<div class="app-header">
  <div class="brand-group">
    <div class="brand-logo">🎯</div>
    <div>
      <div class="brand-title">Concall</div>
      <div class="brand-sub">Management Guidance Accuracy &amp; Delivery Predictor</div>
    </div>
  </div>
  <div class="header-stats">
    <div class="stat-pill"><span class="k">Companies</span><span class="v">{stats['companies']}</span></div>
    <div class="stat-pill"><span class="k">Calls</span><span class="v">{stats['calls']}</span></div>
    <div class="stat-pill"><span class="k">Resolved</span><span class="v">{stats['scored']:,}</span></div>
    <div class="stat-pill"><span class="k">LOCO AUC</span><span class="v">{model['evaluation']['loco']['auc_model']:.3f}</span></div>
    <a href="https://revcon.streamlit.app/" target="_blank" class="live-link">
      <span class="pulse-cyan"></span>revcon.streamlit.app ↗
    </a>
  </div>
</div>
""", unsafe_allow_html=True)

tab_pred, tab_board, tab_co, tab_live, tab_val = st.tabs([
    "🔮 Guidance Predictor", "🏆 Leaderboard", "🔎 Company Ledger", "🎙️ Live Call", "🧪 Model Validation"
])

# =============================================================== Guidance Predictor Tab
with tab_pred:
    tickers_list = sorted([c["ticker"] for c in scores["companies"]])
    p_c1, p_c2 = st.columns([1, 2], gap="medium")

    with p_c1:
        st.markdown("""
        <div class="card-header" style="margin-bottom:10px;padding-bottom:8px;">
          <span class="card-title">🏢 Company Dossier</span>
          <span class="meta-tag">TRACK RECORD</span>
        </div>
        """, unsafe_allow_html=True)

        chosen_ticker = st.selectbox(
            "Select Listed Company",
            tickers_list,
            index=tickers_list.index("KAYNES") if "KAYNES" in tickers_list else 0,
            label_visibility="collapsed"
        )
        co_record = history.guidance_track_record(resolved, chosen_ticker)
        co_score = by_t.get(chosen_ticker, {})
        grade = co_score.get("grade", "–")
        grade_color = "#10b981" if grade in ("A", "B") else ("#f59e0b" if grade == "C" else "#f43f5e")

        beh = co_record.get("behavior", {})
        rev_info = co_record.get("revenue_guidance", {})
        rev_factor = rev_info.get("median_accuracy_ratio", 1.0)

        st.markdown(f"""
        <div class="card-box" style="margin-top:4px;">
          <div style="display:flex;align-items:center;justify-content:space-between;">
            <div>
              <span style="font-family:'JetBrains Mono',monospace;font-size:1.1rem;font-weight:800;color:#fff;">{chosen_ticker}</span>
              <span style="font-size:12px;color:#94a3b8;margin-left:6px;">Historical Audit</span>
            </div>
            <div style="display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:8px;background:{grade_color}15;border:1px solid {grade_color}40;">
              <span style="font-family:'JetBrains Mono',monospace;font-size:10.5px;color:#cbd5e1;font-weight:700;">GRADE</span>
              <span style="font-family:'Outfit',sans-serif;font-size:15px;font-weight:900;color:{grade_color};">{grade}</span>
            </div>
          </div>
          
          <div class="stat-grid-2x2">
            <div class="mini-stat">
              <div class="k">Overall Kept</div>
              <div class="v">{co_record.get('delivery_rate', '–')}%</div>
              <div class="s">{co_score.get('n', 0)} resolved</div>
            </div>
            <div class="mini-stat">
              <div class="k">Top-Line Factor</div>
              <div class="v">{rev_factor:.2f}×</div>
              <div class="s">Actual ÷ Guided</div>
            </div>
            <div class="mini-stat">
              <div class="k">Ghost Rate</div>
              <div class="v" style="color:{'#f43f5e' if beh.get('ghost_rate_pct', 0) > 5 else '#cbd5e1'};">{beh.get('ghost_rate_pct', 0)}%</div>
              <div class="s">{beh.get('ghosted_count', 0)} dropped</div>
            </div>
            <div class="mini-stat">
              <div class="k">Goalpost Moves</div>
              <div class="v" style="color:{'#f59e0b' if beh.get('revision_rate_pct', 0) > 20 else '#cbd5e1'};">{beh.get('revision_rate_pct', 0)}%</div>
              <div class="s">Delayed or cut</div>
            </div>
          </div>
          
          <div style="margin-top:14px;padding:9px 12px;border-radius:8px;background:rgba(8,12,20,0.6);border:1px solid rgba(255,255,255,0.06);font-size:11.5px;color:#94a3b8;">
            Guidance Style: <strong style="color:#f1f5f9;">{co_record.get('style', '–')}</strong>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with p_c2:
        st.markdown("""
        <div class="card-header" style="margin-bottom:10px;padding-bottom:8px;">
          <span class="card-title">🔮 Evaluate Future Guidance</span>
          <span class="meta-tag">PREDICTION ENGINE</span>
        </div>
        """, unsafe_allow_html=True)

        cat_map = {
            "Top-line Revenue Growth (%)": "revenue_growth",
            "EBITDA Margin (%)": "ebitda_margin",
            "PAT Growth (%)": "pat_growth",
            "Capex / Capacity Expansion (₹ Cr)": "capex",
            "Commercial / Order Inflow (₹ Cr)": "order_inflow",
            "Product Launch / Commissioning": "commissioning",
        }
        f1, f2 = st.columns([3, 2])
        g_cat_label = f1.selectbox("Guidance Type", list(cat_map.keys()), index=0)
        g_cat = cat_map[g_cat_label]

        default_val = 30.0 if "Growth" in g_cat_label else (15.0 if "Margin" in g_cat_label else 250.0)
        unit_lbl = "%" if "Growth" in g_cat_label or "Margin" in g_cat_label else " Cr"
        g_val = f2.number_input(f"Target Value ({unit_lbl})", value=float(default_val), step=1.0)

        f3, f4 = st.columns([1, 1])
        g_horizon = f3.selectbox("Guidance Horizon", [
            "Full Year (12 months)", "Quarterly (3 months)", "Semi-Annual (6 months)", "Multi-Year (24 months)"
        ], index=0)
        h_months = 3 if "3" in g_horizon else (6 if "6" in g_horizon else (24 if "24" in g_horizon else 12))

        g_speaker = f4.selectbox("Executive Speaker", [
            "MD / Promoter CEO", "CFO / Finance Head", "Director / COO"
        ], index=0)
        spk_val = "MD" if "MD" in g_speaker else ("CFO" if "CFO" in g_speaker else "COO")

        g_strength = st.selectbox("Management Tone Commitment", [
            "Firm Commitment ('We will achieve / Committed to')",
            "Aspirational / Hedged ('Aiming for / Subject to')"
        ], index=0)
        str_val = "firm" if "Firm" in g_strength else "aspirational"

        g_quote = st.text_area(
            "Verbatim Concall Quote (Optional)",
            value=f"We are guiding for {g_val:g}% in the coming year, backed by strong operational visibility and execution capabilities.",
            height=60
        )

        calc_btn = st.button("🚀 Predict Guidance Holding Accuracy", type="primary")

    if calc_btn or chosen_ticker:
        pred_res = predict.predict_guidance_accuracy(
            model=model,
            resolved=resolved,
            ticker=chosen_ticker,
            category=g_cat,
            value=g_val,
            horizon_months=h_months,
            strength=str_val,
            role=spk_val,
            quote=g_quote,
            asof=date.today()
        )

        p_val = pred_res["p_kept"]
        grade_pred = pred_res.get("grade", "–")

        if p_val >= 0.65:
            verdict_text = "HIGH CONVICTION DELIVERY (P ≥ 65%)"
            verdict_dot = "pulse-emerald"
            verdict_style = "background:rgba(16,185,129,0.1);border-color:rgba(16,185,129,0.35);color:#34d399;"
            verdict_glow = "glow-emerald"
            commentary = f"Management has an established track record in {g_cat.replace('_', ' ')}. Guidance is statistically well-supported by past execution."
        elif p_val >= 0.50:
            verdict_text = "MODERATE / HURDLE CONSTRAINED (50% ≤ P < 65%)"
            verdict_dot = "pulse-amber"
            verdict_style = "background:rgba(245,158,11,0.1);border-color:rgba(245,158,11,0.35);color:#fbbf24;"
            verdict_glow = "glow-amber"
            commentary = f"Target is achievable but susceptible to execution friction. Recommend anchoring analyst expectations to the Credibility-Adjusted target."
        else:
            verdict_text = "ELEVATED MISS / OVER-PROMISE RISK (P < 50%)"
            verdict_dot = "pulse-rose"
            verdict_style = "background:rgba(244,63,94,0.1);border-color:rgba(244,63,94,0.35);color:#fb7185;"
            verdict_glow = "glow-rose"
            commentary = f"Target ambition significantly exceeds historical run-rate or company category factor. Elevated probability of downward revision."

        st.markdown(f"""
        <div class="verdict-banner {verdict_glow}" style="{verdict_style}">
          <div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:4px;opacity:0.85;">
              Institutional Conviction Verdict · {chosen_ticker}
            </div>
            <div style="font-family:'Outfit',sans-serif;font-size:1.35rem;font-weight:900;display:flex;align-items:center;gap:10px;">
              <span class="{verdict_dot}"></span>{verdict_text}
            </div>
            <div style="font-size:12.5px;margin-top:6px;color:#e2e8f0;font-weight:500;">
              {commentary}
            </div>
          </div>
          <div style="text-align:right;">
            <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#94a3b8;">CALIBRATED GRADE</div>
            <div style="font-family:'Outfit',sans-serif;font-size:2rem;font-weight:900;line-height:1.1;">{grade_pred}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        res_cols = st.columns(4)
        kpi(res_cols[0], f"{p_val:.0%}", "P(Guidance Held)", sub=f"Grade {grade_pred} · Out-of-Sample", glow="indigo" if p_val >= 0.5 else "rose")

        if pred_res.get("guided_value") is not None and pred_res.get("adjusted_value") is not None:
            unit_str = "%" if "Growth" in g_cat_label or "Margin" in g_cat_label else " Cr"
            kpi(res_cols[1], f"{pred_res['guided_value']:g}{unit_str} → {pred_res['adjusted_value']:g}{unit_str}",
                "Credibility-Adjusted Target", sub="Bias-corrected expectation", glow="emerald" if pred_res['adjustment_factor'] >= 1.0 else "amber")
            kpi(res_cols[2], f"{pred_res['adjustment_factor']:.2f}×", "Historical Factor", sub="Historical ratio delivered", glow="brand")
        else:
            kpi(res_cols[1], "N/A", "Credibility-Adjusted Target", sub="Non-numeric category")
            kpi(res_cols[2], "N/A", "Adjustment Factor", sub="Baseline rate applied")

        diag = pred_res.get("diagnostics", {})
        kpi(res_cols[3], f"{diag.get('consecutive_streak', 0)} consecutive", "Current Streak", sub=f"Category: {g_cat.replace('_', ' ')}")

        if pred_res.get("risks"):
            st.markdown("<div style='margin-top:14px;font-weight:600;font-size:13px;color:#cbd5e1;'>Guidance Diagnostics & Risks:</div>", unsafe_allow_html=True)
            for rk in pred_res["risks"]:
                st.markdown(f'<div class="risk-box">⚠️ {rk}</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"#### 📈 Hurdle Sensitivity & Tipping Points for `{chosen_ticker}`")
        st.caption("How does P(Delivery) evolve as management raises guidance targets? Reveals operational thresholds where ambition outstrips capacity.")

        sim_data = predict.simulate_guidance_hurdle_curve(
            model=model, resolved=resolved, ticker=chosen_ticker,
            category=g_cat, steps=11, horizon_months=h_months,
            strength=str_val, role=spk_val
        )

        sim_col1, sim_col2 = st.columns([3, 2], gap="medium")
        unit_lbl = "%" if "growth" in g_cat or "margin" in g_cat else " Cr"
        with sim_col1:
            x_vals = [pt["guided_value"] for pt in sim_data["points"]]
            y_vals = [pt["p_kept"] * 100 for pt in sim_data["points"]]

            fig_h = go.Figure()
            fig_h.add_hline(y=50, line=dict(color=ROSE, dash="dot", width=1.5),
                            annotation_text="50% Hurdle Threshold", annotation_font_color=ROSE)
            fig_h.add_hline(y=65, line=dict(color=EMERALD, dash="dot", width=1.5),
                            annotation_text="65% High Confidence", annotation_font_color=EMERALD)

            fig_h.add_trace(go.Scatter(
                x=x_vals, y=y_vals, mode="lines+markers",
                name="P(Delivery)",
                line=dict(color=TEAL, width=3),
                marker=dict(size=8, color=TEAL),
                hovertemplate="Guided: %{x:g}" + unit_lbl + "<br>P(Delivery): %{y:.1f}%<extra></extra>"
            ))

            fig_h.add_trace(go.Scatter(
                x=[g_val], y=[p_val * 100], mode="markers",
                name="Current Input",
                marker=dict(size=14, color="#ffb703", symbol="star", line=dict(color="#fff", width=2)),
                hovertemplate=f"Current: {g_val:g}{unit_lbl} -> {p_val:.1%}<extra></extra>"
            ))

            layout(fig_h, h=330, xaxis_title=f"Guided Target ({unit_lbl})", yaxis_title="P(Delivery) %", yaxis_range=[0, 100])
            st.plotly_chart(fig_h, width='stretch')

        with sim_col2:
            st.markdown('<div class="card-title" style="font-size:1.05rem;margin-bottom:12px;">Tipping Points Breakdown</div>', unsafe_allow_html=True)
            
            c_trail = f"{sim_data['benchmark_trailing']:g}{unit_lbl}"
            c_high = f"{sim_data['high_confidence_ceiling']:g}{unit_lbl}" if sim_data.get("high_confidence_ceiling") is not None else "N/A"
            c_viable = f"{sim_data['hurdle_50_ceiling']:g}{unit_lbl}" if sim_data.get("hurdle_50_ceiling") is not None else f"< {x_vals[0]:g}{unit_lbl}"
            c_break = f"> {sim_data['breakdown_risk_point']:g}{unit_lbl}" if sim_data.get("breakdown_risk_point") is not None else "Not reached"

            st.markdown(f"""
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
              <div class="mini-stat">
                <div class="k">Trailing Run-Rate</div>
                <div class="v">{c_trail}</div>
                <div class="s">Historical benchmark</div>
              </div>
              <div class="mini-stat glow-emerald">
                <div class="k" style="color:#10b981;">P ≥ 65% Ceiling</div>
                <div class="v" style="color:#34d399;">{c_high}</div>
                <div class="s">High confidence upper bound</div>
              </div>
              <div class="mini-stat glow-amber">
                <div class="k" style="color:#f59e0b;">P ≥ 50% Max Viable</div>
                <div class="v" style="color:#fbbf24;">{c_viable}</div>
                <div class="s">Hurdle threshold ceiling</div>
              </div>
              <div class="mini-stat glow-rose">
                <div class="k" style="color:#f43f5e;">P < 45% Breakdown</div>
                <div class="v" style="color:#fb7185;">{c_break}</div>
                <div class="s">Elevated miss cliff</div>
              </div>
            </div>
            
            <div style="margin-top:12px;padding:12px;border-radius:10px;background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);font-size:12px;line-height:1.5;color:#cbd5e1;">
              💡 <strong>Takeaway:</strong> When guidance exceeds trailing run-rate by >15%, delivery probability drops non-linearly. Anchor estimates to the <strong>Credibility-Adjusted Guidance</strong>.
            </div>
            """, unsafe_allow_html=True)

        st.write("")
        st.markdown(f"**Historical Concall Precedents from `{chosen_ticker}` in this category:**")
        matches = [p for p in resolved if p["ticker"] == chosen_ticker and p["category"] == g_cat and p["resolution"].get("y") is not None]
        if matches:
            m_rows = []
            for m in matches[:6]:
                res = m["resolution"]
                m_rows.append({
                    "Date": m["call_date"],
                    "Quote": m["quote"][:120] + "...",
                    "Outcome": f"{ICON.get(res['outcome'], '')} {res['outcome']}",
                    "Actual vs Guided": res.get("why", "–"),
                })
            st.dataframe(pd.DataFrame(m_rows), hide_index=True, width='stretch')
        else:
            st.info(f"No previous recorded guidance in exact category `{g_cat}` for {chosen_ticker}. Evaluated using company track record and category baseline.")


# =============================================================== Leaderboard Tab
with tab_board:
    st.markdown("### 🏆 Management Credibility Leaderboard & Say-Do Rankings")
    k = st.columns(5)
    kpi(k[0], f"{stats['promises']:,}", "Promises Extracted", sub="Quote-verified by verifier")
    kpi(k[1], f"{stats['scored']:,}", "Promises Resolved", sub="Against reported financials")
    kept = sum(v for o, v in stats["outcomes"].items() if o == "DELIVERED")
    kpi(k[2], f"{100 * kept / max(1, stats['scored']):.0f}%", "Universe Delivery Rate", sub="Delivered in full & on time", glow="emerald")
    kpi(k[3], f"{stats['outcomes'].get('GHOSTED', 0):,}", "Ghosted Targets", sub="Quietly dropped mid-stream", glow="rose")
    kpi(k[4], f"{stats['unverifiable_dropped']:,}", "Hallucinations Blocked", sub="Dropped by quote verifier", glow="indigo")
    st.write("")

    rows = [c for c in scores["companies"] if c["n"] >= 3]
    rows.sort(key=lambda c: c["score"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[c["score"] for c in rows], y=[c["ticker"] for c in rows], mode="markers",
        marker=dict(size=11, color=BLUE, line=dict(color=SURF, width=2)),
        error_x=dict(type="data", symmetric=False, color="#86b6ef", thickness=2, width=0,
                     array=[c["ci80"][1] - c["score"] for c in rows],
                     arrayminus=[c["score"] - c["ci80"][0] for c in rows]),
        customdata=[[c["grade"], c["n"], c["ci80"][0], c["ci80"][1], c["promises_made"]] for c in rows],
        hovertemplate="<b>%{y}</b>  grade %{customdata[0]}<br>Say-Do %{x:.0f} "
                      "(80%% CI %{customdata[2]:.0f}–%{customdata[3]:.0f})<br>"
                      "%{customdata[1]} resolved of %{customdata[4]} promises<extra></extra>"))
    fig.add_vline(x=scores["base_rate"], line=dict(color=MUTED, dash="dot", width=1.5),
                  annotation_text=f"universe {scores['base_rate']:.0f}", annotation_font_color=MUTED)
    layout(fig, h=max(420, 22 * len(rows)), showlegend=False,
           xaxis_title="Say-Do score (dot) with 80% credible interval", xaxis_range=[0, 100])
    c1, c2 = st.columns([3, 2], gap="medium")
    c1.markdown("**Management Credibility Ranking** · companies with ≥3 resolved promises")
    c1.plotly_chart(fig, width='stretch')
    with c2:
        st.markdown('<div class="card-title" style="font-size:1.05rem;margin-bottom:10px;">Methodology & Guardrails</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="background:#0d121f;border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:16px;font-size:12.5px;line-height:1.6;color:#cbd5e1;">
          <div style="margin-bottom:8px;"><strong>1 · SAY (Extraction)</strong>: Frontier models parse earnings transcripts to extract exact forward commitments with verbatim quote citations.</div>
          <div style="margin-bottom:8px;"><strong>2 · DO (Resolution)</strong>: Financial guidance is resolved against audited reported numbers; operational goals against later calls.</div>
          <div style="margin-bottom:8px;"><strong>3 · PREDICT (Machine Learning)</strong>: Pure-NumPy HistGBDT + Bayesian MAP Logistic Regression stack forecasts forward holding accuracy.</div>
          <div><strong>4 · 👻 GHOSTED (Red Flag)</strong>: Targets missed and never mentioned again — the quiet warning markets overlook.</div>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        tbl = pd.DataFrame([{"Ticker": c["ticker"], "Score": c["score"], "Grade": c["grade"],
                             "Resolved": c["n"], "Ghost %": (c["ghost_rate"] or 0) * 100,
                             "Delayed/cut": c["goalpost_moves"],
                             "Rev. delivered/guided": c["revenue_delivery_ratio"]}
                            for c in scores["companies"]])
        st.dataframe(tbl, hide_index=True, width='stretch', height=340,
                     column_config={"Ghost %": st.column_config.NumberColumn(format="%.0f%%"),
                                    "Rev. delivered/guided": st.column_config.NumberColumn(format="%.2f×")})


# =============================================================== Company Ledger Tab
with tab_co:
    tickers = [c["ticker"] for c in sorted(scores["companies"], key=lambda c: -c["n"])]
    t = st.selectbox("Company", tickers, index=tickers.index("KAYNES") if "KAYNES" in tickers else 0, key="co_select")
    c = by_t[t]
    mine = [p for p in resolved if p["ticker"] == t]
    k = st.columns(5)
    kpi(k[0], f"{c['score']:.0f} · {c['grade']}", "Say-Do Credibility", sub=f"80% CI: {c['ci80'][0]:.0f}–{c['ci80'][1]:.0f}", glow="brand")
    kpi(k[1], f"{c['financial']['score']:.0f}" if c.get("financial") else "–", "Financial Guidance", sub="Audited reported deltas")
    kpi(k[2], f"{c['operational']['score']:.0f}" if c.get("operational") else "–", "Operational Guidance", sub="Capex & commercial goals")
    kpi(k[3], f"{c['revenue_delivery_ratio']:.2f}×" if c.get("revenue_delivery_ratio") else "–",
        "Revenue Ratio", sub="Median delivered ÷ guided", glow="emerald" if (c.get('revenue_delivery_ratio') or 0) >= 1.0 else "amber")
    kpi(k[4], f"{c['goalpost_moves']}", "Delayed / Cut", sub="Goalposts revised mid-stream", glow="rose" if c['goalpost_moves'] > 10 else "")
    st.write("")

    g1, g2 = st.columns([3, 2], gap="medium")
    with g1:
        oc = c["outcomes"]
        fig = go.Figure()
        for o in ORDER:
            if oc.get(o):
                fig.add_trace(go.Bar(x=[oc[o]], y=[""], orientation="h", name=f"{ICON[o]} {o.title().replace('_', ' ')}",
                                     marker=dict(color=STATUS[o], line=dict(color=SURF, width=2)),
                                     text=[oc[o]], textposition="inside", insidetextfont=dict(color="#0b0b0b" if o in ("PARTIAL", "LATE") else "#fff"),
                                     hovertemplate=f"{o.title()}: %{{x}}<extra></extra>"))
        layout(fig, h=150, barmode="stack", legend=dict(orientation="h", y=-0.5, font=dict(color=INK2)),
               xaxis=dict(showgrid=False, showticklabels=False), yaxis=dict(showticklabels=False))
        st.markdown(f"**Outcomes of {c['n']} resolved guidance promises** · {c['pending']} open or undated")
        st.plotly_chart(fig, width='stretch')
    with g2:
        h = [x for x in scores["history"].get(t, []) if x["n"] > 0]
        if len(h) >= 2:
            fig = go.Figure(go.Scatter(x=[x["date"] for x in h], y=[x["score"] for x in h], mode="lines+markers",
                                       line=dict(color=BLUE, width=2), marker=dict(size=8, color=BLUE),
                                       customdata=[x["n"] for x in h],
                                       hovertemplate="%{x}: %{y:.0f} (%{customdata} resolved)<extra></extra>"))
            layout(fig, h=190, yaxis_range=[0, 100], showlegend=False)
            st.markdown("**Point-in-Time Score Trajectory** (strictly knowable on call day)")
            st.plotly_chart(fig, width='stretch')

    st.markdown("#### The Ledger: What They Said → What Happened")
    f1, f2 = st.columns([2, 3])
    show = f1.multiselect("Filter Outcomes", ORDER + ["PENDING", "UNDATED"], default=["MISSED", "GHOSTED", "REVISED_DOWN", "ABANDONED", "DELIVERED", "LATE", "PARTIAL"])
    reps_only = f2.toggle("Hide repeated restatements", value=True)
    rows = [p for p in mine if p["resolution"]["outcome"] in show and (not reps_only or p.get("repeat_index", 0) == 0)]
    rows.sort(key=lambda p: p["call_date"])
    for p in rows[:150]:
        r = p["resolution"]
        o = r["outcome"]
        pk = preds.get(p["id"])
        head = (f'<span class="tag" style="background:{STATUS[o]};color:{"#0b0b0b" if o in ("PARTIAL", "LATE") else "#fff"}">'
                f'{ICON[o]} {o.replace("_", " ")}</span>  **{p["summary"]}**  ·  '
                f'{p["category"].replace("_", " ")} · by {p.get("period") or "no date"} · {p.get("strength")}'
                + (f" · model P(kept) at time: **{pk:.0%}**" if pk is not None else ""))
        with st.expander(f'{ICON[o]} {p["call_label"]} — {p["summary"][:110]}'):
            st.markdown(head, unsafe_allow_html=True)
            st.markdown(f'<div class="say">🗣️ <b>SAID</b> ({p.get("speaker") or "management"}, {p["call_label"]}): '
                        f'“{p["quote"]}”</div>', unsafe_allow_html=True)
            st.write("")
            do = f"<b>DID</b>: {r.get('why', '')}"
            for e in r.get("evidence", [])[-2:]:
                if e.get("evidence_quote"):
                    do += f'<br>📄 {e["call_label"]} — <i>{e["status"].replace("_", " ").lower()}</i>: “{e["evidence_quote"]}”'
            st.markdown(f'<div class="do">{do}</div>', unsafe_allow_html=True)


# =============================================================== Live Call Tab
with tab_live:
    st.markdown("### 🎙️ Live Concall Parser & Guidance Predictor")
    st.markdown("Drop in a brand-new earnings call transcript or audio recording. Frontier models extract each "
                "forward-looking commitment; the ensemble predictor estimates which ones management will actually deliver.")
    l1, l2 = st.columns([1, 2], gap="medium")
    lt = l1.text_input("Company Ticker", value="KAYNES").upper()
    ld = l1.date_input("Call Date", value=date.today())
    up = l1.file_uploader("Upload Transcript (.txt) or Audio (.mp3/.wav/.m4a)", type=["txt", "mp3", "wav", "m4a"])
    txt = l2.text_area("…or paste transcript text here", height=220)

    if st.button("Analyze Call & Predict Guidance Holding", type="primary"):
        from saydo import live
        audio = None
        if up is not None and up.name.endswith(".txt"):
            txt = up.read().decode(errors="ignore")
        elif up is not None:
            audio = os.path.join(config.CACHE, "upload_" + up.name)
            open(audio, "wb").write(up.read())
        with st.spinner("Analyzing concall and calculating delivery predictions…"):
            try:
                res = live.analyze(lt, txt, ld, audio_path=audio)
            except Exception as e:
                st.error(f"{type(e).__name__}: {e}")
                res = None
        if res:
            cs = res["company"]
            st.success(f"{len(res['promises'])} promises extracted ({res['dropped_unverified']} unverified rejected). "
                       f"{lt} Say-Do score: {cs['score']:.0f} ({cs['grade']}) with {cs['n']} historical promises on record.")
            df = pd.DataFrame([{
                "P(kept)": r["p_kept"], "Promise": r["summary"], "By": r.get("period"),
                "Type": r["category"].replace("_", " "), "Firmness": r.get("strength"),
                "Credibility-adjusted": (f'{r["credibility_adjusted"]["guided"]:g} → {r["credibility_adjusted"]["adjusted"]:g} '
                                         f'{r["credibility_adjusted"]["unit"] or ""} (×{r["credibility_adjusted"]["factor"]})')
                if r.get("credibility_adjusted") else "",
                "Quote": r["quote"]} for r in res["promises"]])
            st.dataframe(df, hide_index=True, width='stretch',
                         column_config={"P(kept)": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=1)})


# =============================================================== Model Validation Tab
with tab_val:
    st.markdown("### 🧪 Statistical Validation: Does Past Guidance Predict Future Holding Accuracy?")
    if model:
        ev = model["evaluation"]
        lo, wf = ev.get("loco", {}), ev.get("walk_forward", {})
        k = st.columns(4)
        kpi(k[0], f"{lo.get('auc_model', 0):.3f}", "LOCO ROC AUC", sub=f"90% CI {lo.get('auc_ci90')}", glow="brand")
        kpi(k[1], f"{wf.get('auc_model', 0):.3f}" if wf else "–", "Walk-Forward AUC", sub=f"Train < {wf.get('cutoff', '?')}", glow="emerald")
        kpi(k[2], f"{lo.get('brier_model', 0):.3f}", "Brier Score", sub=f"Base Rate {lo.get('brier_base_rate', 0):.3f}")
        kpi(k[3], f"{ev['n']}", "Resolved Promises", sub=f"{ev['kept_rate']:.0%} Kept Rate")
        st.write("")

        v1, v2 = st.columns(2, gap="medium")
        cal = ev.get("calibration", [])
        if cal:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=AXIS, dash="dot", width=1.5),
                                     hoverinfo="skip", name="Perfect Calibration"))
            fig.add_trace(go.Scatter(x=[b["predicted"] for b in cal], y=[b["kept"] for b in cal], mode="markers+lines",
                                     marker=dict(size=[8 + min(18, b["n"] / 8) for b in cal], color=BLUE,
                                                 line=dict(color=SURF, width=2)),
                                     line=dict(color=BLUE, width=2), name="Concall Ensemble Predictor",
                                     customdata=[b["n"] for b in cal],
                                     hovertemplate="Predicted %{x:.0%} → Actually Kept %{y:.0%} (n=%{customdata})<extra></extra>"))
            layout(fig, h=340, xaxis_title="Predicted P(Kept), Out-of-Sample", yaxis_title="Observed Delivery Rate",
                   xaxis_range=[0, 1], yaxis_range=[0, 1], legend=dict(orientation="h", y=1.12))
            v1.markdown("**1 · Probability Calibration on Unseen Companies**")
            v1.plotly_chart(fig, width='stretch')

        coefs = model["coefficients"]
        coefs = [kv for kv in coefs if kv[0] != "bias"][:10][::-1]
        fig = go.Figure(go.Bar(x=[v for _, v in coefs], y=[n.replace("_", " ") for n, _ in coefs], orientation="h",
                               marker=dict(color=[TEAL if v > 0 else ROSE for _, v in coefs],
                                           line=dict(color=SURF, width=2)),
                               hovertemplate="%{y}: %{x:+.2f}<extra></extra>"))
        layout(fig, h=340, xaxis_title="← Lowers P(Kept)   ·   Raises P(Kept) →", showlegend=False)
        v2.markdown("**2 · Top Predictors of Guidance Delivery** (Standardized Weights)")
        v2.plotly_chart(fig, width='stretch')

    mk = market or {}
    cs, es = mk.get("cross_section", {}), mk.get("event_study", {})
    st.markdown("**3 · Market Reaction: Does Track Record Generate Alpha?** (Point-in-Time Excess Return)")
    m1, m2 = st.columns(2, gap="medium")
    if cs.get("spread_pct") is not None:
        fig = go.Figure(go.Bar(x=["Bottom Third Credibility", "Top Third Credibility"],
                               y=[cs["bottom_tercile_excess"], cs["top_tercile_excess"]],
                               marker=dict(color=[MUTED, EMERALD], line=dict(color=SURF, width=2)),
                               text=[f'{cs["bottom_tercile_excess"]:+.1f}%', f'{cs["top_tercile_excess"]:+.1f}%'],
                               textposition="outside", hovertemplate="%{x}: %{y:+.1f}%<extra></extra>"))
        layout(fig, h=300, yaxis_title=f"{cs['hold_days']}-Day Excess Return After Call", showlegend=False)
        m1.markdown(f"Credibility Tercile → Next-{cs['hold_days']}-Day Excess Return · Spread: **{cs['spread_pct']:+.1f}%**")
        m1.plotly_chart(fig, width='stretch')
    else:
        m1.info(cs.get("note", "Not enough scored events yet."))

    if es.get("diff_pct") is not None:
        m2.markdown(f"**When Guidance Outcomes Surface Publicly** ({es['days']}-Day Excess Return)")
        m2.markdown(f"- Kept guidance revealed: **{es['kept_excess_pct']:+.1f}%** (n={es['kept_events']})\n"
                    f"- Broken guidance revealed: **{es['broken_excess_pct']:+.1f}%** (n={es['broken_events']})\n"
                    f"- Spread: **{es['diff_pct']:+.1f}%** (90% CI {es['diff_ci90_pct']})")
