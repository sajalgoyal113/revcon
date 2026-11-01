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

st.set_page_config(page_title="Concall · Guidance Accuracy Predictor", page_icon="🎯", layout="wide",
                   initial_sidebar_state="expanded")

# ---- design tokens (dark premium system) ----
SURF, INK, INK2, MUTED, GRID, AXIS = "#06080d", "#f8fafc", "#cbd5e1", "#94a3b8", "rgba(255,255,255,0.08)", "#334155"
BLUE = "#818cf8"
TEAL = "#00d2ff"
EMERALD = "#00f5a0"
AMBER = "#ffb703"
ROSE = "#ff4d6d"
STATUS = {"DELIVERED": "#10b981", "PARTIAL": "#f59e0b", "LATE": "#f59e0b", "REVISED_DOWN": "#fb923c",
          "MISSED": "#f43f5e", "ABANDONED": "#f43f5e", "GHOSTED": "#f43f5e", "PENDING": "#475569", "UNDATED": "#475569"}
ICON = {"DELIVERED": "✅", "PARTIAL": "◐", "LATE": "⏱", "REVISED_DOWN": "↘", "MISSED": "✖",
        "ABANDONED": "✖", "GHOSTED": "👻", "PENDING": "…", "UNDATED": "∅"}
ORDER = ["DELIVERED", "PARTIAL", "LATE", "REVISED_DOWN", "MISSED", "ABANDONED", "GHOSTED"]
FONT = dict(family="'Plus Jakarta Sans', system-ui, sans-serif", color=INK2, size=13)

st.markdown("""<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
--bg-main:#06080d;--bg-surface:rgba(14,19,31,.72);--border-subtle:rgba(255,255,255,.08);
--accent-primary:#6366f1;--accent-cyan:#00d2ff;--accent-emerald:#00f5a0;--accent-amber:#ffb703;--accent-rose:#ff4d6d;
--text-primary:#f8fafc;--text-secondary:#94a3b8;--text-tertiary:#64748b;
--font-main:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,sans-serif;--font-mono:'JetBrains Mono',monospace}
.stApp{background-color:var(--bg-main)!important;
background-image:radial-gradient(circle at 50% 0%,rgba(99,102,241,.14) 0%,transparent 55%),radial-gradient(circle at 85% 20%,rgba(0,210,255,.07) 0%,transparent 45%),radial-gradient(circle at 15% 40%,rgba(0,245,160,.06) 0%,transparent 45%)!important;
font-family:var(--font-main)!important;color:var(--text-primary)!important}
#MainMenu{visibility:hidden}footer{visibility:hidden}header{visibility:hidden}
.block-container{padding-top:1.4rem;max-width:1320px}
section[data-testid="stSidebar"]{background:rgba(10,14,24,.9)!important;border-right:1px solid var(--border-subtle)}
section[data-testid="stSidebar"] *{font-family:var(--font-main)}
.hero{text-align:center;padding:40px 16px 18px;max-width:860px;margin:0 auto}
.hero-badge{display:inline-flex;align-items:center;justify-content:center;width:60px;height:60px;border-radius:18px;
background:linear-gradient(135deg,#6366f1 0%,#00d2ff 100%);box-shadow:0 0 32px rgba(99,102,241,.45);font-size:29px;margin-bottom:16px}
.hero-title{font-size:3rem;font-weight:800;letter-spacing:-.04em;line-height:1.1;margin:0;
background:linear-gradient(135deg,#fff 40%,#94a3b8 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero-sub{font-size:1.05rem;color:#94a3b8;font-weight:500;margin-top:10px;line-height:1.5}
.hero-meta{font-size:.82rem;color:#64748b;margin-top:10px;font-family:var(--font-mono)}
.kpi{background:rgba(255,255,255,.025);border:1px solid var(--border-subtle);border-radius:14px;padding:16px 18px;transition:all .2s ease}
.kpi:hover{background:rgba(255,255,255,.04);border-color:rgba(255,255,255,.14);transform:translateY(-2px)}
.kpi .v{font-family:var(--font-mono);font-size:1.7rem;font-weight:700;letter-spacing:-.03em;color:#fff;margin:0;line-height:1.15}
.kpi .l{font-size:.76rem;font-weight:600;color:var(--text-tertiary);letter-spacing:.06em;text-transform:uppercase;margin-top:6px}
.say{border-left:3px solid #6366f1;padding:10px 14px;background:rgba(99,102,241,.09);border-radius:6px;color:#e2e8f0;margin-bottom:6px}
.do{border-left:3px solid #475569;padding:10px 14px;background:rgba(255,255,255,.03);border-radius:6px;color:#cbd5e1}
.tag{display:inline-block;padding:2px 8px;border-radius:9999px;font-size:11.5px;font-weight:700;color:#fff}
.pred-card{background:var(--bg-surface);border:1px solid var(--border-subtle);border-radius:16px;padding:18px 20px;margin-bottom:12px}
.risk-box{background:rgba(255,77,109,.08);border-left:3px solid #ff4d6d;padding:10px 14px;border-radius:6px;margin-top:6px;font-size:13px;color:#fecdd3}
.stTextInput>div>div>input,.stNumberInput input,.stTextArea textarea{background:rgba(14,20,32,.8)!important;
border:1px solid rgba(255,255,255,.12)!important;border-radius:12px!important;color:#fff!important;font-family:var(--font-main)!important}
.stTextInput>div>div>input:focus,.stNumberInput input:focus,.stTextArea textarea:focus{border-color:var(--accent-primary)!important;
box-shadow:0 0 0 2px rgba(99,102,241,.25)!important}
.stButton>button{background:rgba(255,255,255,.04)!important;border:1px solid var(--border-subtle)!important;border-radius:10px!important;
color:var(--text-primary)!important;font-weight:600!important;transition:all .2s ease!important}
.stButton>button:hover{background:rgba(99,102,241,.25)!important;border-color:var(--accent-primary)!important;color:#fff!important}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#6366f1 0%,#00d2ff 100%)!important;border:none!important;color:#fff!important}
.stTabs [data-baseweb="tab-list"]{gap:8px;background:rgba(14,20,32,.5);padding:6px;border-radius:14px;border:1px solid var(--border-subtle)}
.stTabs [data-baseweb="tab"]{border-radius:10px;color:var(--text-secondary);font-weight:600;padding:9px 18px;border:none!important}
.stTabs [aria-selected="true"]{background:rgba(99,102,241,.22)!important;color:#fff!important;border:1px solid rgba(99,102,241,.4)!important}
div[data-baseweb="select"]>div{background:rgba(14,20,32,.85)!important;border:1px solid rgba(255,255,255,.12)!important;border-radius:12px!important;color:#fff!important}
div[data-baseweb="select"] *{color:#fff!important;font-family:var(--font-main)!important}
div[data-baseweb="popover"] ul{background:#0b0f19!important;border:1px solid rgba(255,255,255,.15)!important;border-radius:12px!important}
div[data-baseweb="popover"] li{color:#e2e8f0!important}
div[data-baseweb="popover"] li:hover{background:rgba(99,102,241,.25)!important;color:#fff!important}
details{border:1px solid var(--border-subtle)!important;border-radius:12px!important;background:rgba(255,255,255,.02)!important}
code{font-family:var(--font-mono)!important;color:#a5b4fc!important}
.stAlert{border-radius:12px!important}
</style>""", unsafe_allow_html=True)


def layout(fig, h=420, **kw):
    fig.update_layout(height=h, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font=FONT,
                      margin=dict(l=10, r=20, t=30, b=10), hoverlabel=dict(bgcolor="#0e1420", font_color="#f8fafc"),
                      **kw)
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=MUTED))
    return fig


def kpi(col, value, label):
    col.markdown(f'<div class="kpi"><div class="v">{value}</div><div class="l">{label}</div></div>',
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

# Sidebar: Model and Key Selection
with st.sidebar:
    st.markdown("### ⚙️ Engine Configuration")
    st.markdown("**Frontier AI Provider:** Meta Muse (Active)")

    user_meta_key = st.text_input(
        "Meta Model API Key",
        value=config.META_API_KEY,
        type="password",
        placeholder="metamodel_...",
        help="Key from the Meta Model API for live concall parsing"
    )
    if user_meta_key:
        os.environ["META_MODEL_API_KEY"] = user_meta_key
        st.success("🟢 Muse Active")
    elif config.META_API_KEY:
        st.success("🟢 Muse Active (.env)")
    else:
        st.warning("⚠️ Enter Meta Model API Key to enable live concall parsing")

    st.markdown("---")
    st.markdown("**Predictive Architecture:**")
    st.markdown("- **Ensemble Stacking**: HistGradientBoosting + Calibrated Logistic Regression")
    st.markdown("- **Signals**: Category delivery history, ambition gap, ghosting propensity, goalpost tracking, speaker credibility")
    st.markdown(f"- **LOCO AUC**: `{model['evaluation']['loco']['auc_model']:.3f}`")
    st.markdown(f"- **Walk-Forward AUC**: `{model['evaluation']['walk_forward']['auc_model']:.3f}`")


# Header
st.markdown(f"""<div class="hero">
<div class="hero-badge">🎯</div>
<div class="hero-title">Concall</div>
<div class="hero-sub">Management Guidance Accuracy &amp; Delivery Predictor.<br>
Keeping score on every promise — and predicting which future guidance will hold.</div>
<div class="hero-meta">{stats['companies']} COMPANIES · {stats['calls']} EARNINGS CALLS · ENSEMBLE HISTGB + LOGISTIC · MUSE SPARK &amp; WONDER · {stats['today']}</div>
</div>""", unsafe_allow_html=True)

tab_pred, tab_board, tab_co, tab_live, tab_val = st.tabs([
    "🔮 Guidance Predictor", "🏆 Leaderboard", "🔎 Company Ledger", "🎙️ Live Call", "🧪 Model Validation"
])

# =============================================================== Guidance Predictor Tab
with tab_pred:
    st.markdown("### 🔮 Predict Future Accuracy of Holding Management Guidance")
    st.markdown("Select a company and specify a management guidance statement. The model analyzes the company's "
                "**entire historical track record of guidance delivery** to forecast the probability of management holding "
                "to this future guidance, alongside a **credibility-adjusted target**.")

    tickers_list = sorted([c["ticker"] for c in scores["companies"]])
    p_c1, p_c2 = st.columns([1, 2])
    
    with p_c1:
        chosen_ticker = st.selectbox("Select Listed Company", tickers_list, index=tickers_list.index("KAYNES") if "KAYNES" in tickers_list else 0)
        co_record = history.guidance_track_record(resolved, chosen_ticker)
        
        st.markdown(f"**Historical Delivery Profile: {chosen_ticker}**")
        st.markdown(f"- Overall Delivery Rate: **{co_record.get('delivery_rate', '–')}%**")
        st.markdown(f"- Guidance Style: *{co_record.get('style', '–')}*")
        
        rev_info = co_record.get("revenue_guidance", {})
        if rev_info.get("count", 0) > 0:
            st.markdown(f"- Top-Line Accuracy: **{rev_info.get('median_accuracy_ratio', 1.0):.2f}×** of guided revenue delivered")
        
        beh = co_record.get("behavior", {})
        st.markdown(f"- 👻 Ghost Rate: **{beh.get('ghost_rate_pct', 0)}%** ({beh.get('ghosted_count', 0)} promises quietly dropped)")
        st.markdown(f"- ⏱ Goalpost Moving: **{beh.get('revision_rate_pct', 0)}%** targets revised or delayed")

    with p_c2:
        st.markdown("**Enter Future Guidance Statement to Evaluate:**")
        f1, f2, f3 = st.columns(3)
        cat_map = {
            "Top-line Revenue Growth (%)": "revenue_growth",
            "EBITDA Margin (%)": "ebitda_margin",
            "PAT Growth (%)": "pat_growth",
            "Capex / Capacity Expansion (₹ Cr)": "capex",
            "Commercial / Order Inflow (₹ Cr)": "order_inflow",
            "Product Launch / Commissioning": "commissioning",
        }
        g_cat_label = f1.selectbox("Guidance Type", list(cat_map.keys()), index=0)
        g_cat = cat_map[g_cat_label]
        
        default_val = 30.0 if "Growth" in g_cat_label else (15.0 if "Margin" in g_cat_label else 250.0)
        g_val = f2.number_input("Guided Value / Target", value=float(default_val), step=1.0)
        
        g_horizon = f3.selectbox("Guidance Horizon", ["Quarterly (3 months)", "Semi-Annual (6 months)", "Full Year (12 months)", "Multi-Year (24 months)"], index=2)
        h_months = 3 if "3" in g_horizon else (6 if "6" in g_horizon else (24 if "24" in g_horizon else 12))
        
        f4, f5 = st.columns(2)
        g_strength = f4.selectbox("Management Tone", ["Firm Commitment ('We will achieve / Committed to')", "Aspirational / Hedged ('Aiming for / Subject to')"], index=0)
        str_val = "firm" if "Firm" in g_strength else "aspirational"
        
        g_speaker = f5.selectbox("Executive Speaker", ["MD / Promoter CEO", "CFO / Finance Head", "Director / COO"], index=0)
        spk_val = "MD" if "MD" in g_speaker else ("CFO" if "CFO" in g_speaker else "COO")
        
        g_quote = st.text_area(
            "Verbatim Concall Quote (Optional)",
            value=f"We are guiding for {g_val:g}% in the coming year, backed by strong operational visibility and execution capabilities.",
            height=70
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
        
        st.markdown("---")
        st.markdown(f"### 📊 Prediction Results for `{chosen_ticker}` Future Guidance")
        
        res_cols = st.columns(4)
        p_val = pred_res["p_kept"]
        kpi(res_cols[0], f"{p_val:.0%}", f"P(Guidance Kept in Full) · Grade {pred_res['grade']}")
        
        if pred_res.get("guided_value") is not None and pred_res.get("adjusted_value") is not None:
            unit_str = "%" if "Growth" in g_cat_label or "Margin" in g_cat_label else " Cr"
            kpi(res_cols[1], f"{pred_res['guided_value']:g}{unit_str} → {pred_res['adjusted_value']:g}{unit_str}", "Credibility-Adjusted Expectation")
            kpi(res_cols[2], f"{pred_res['adjustment_factor']:.2f}×", "Historical Delivery Factor")
        else:
            kpi(res_cols[1], "N/A", "Credibility-Adjusted Target")
            kpi(res_cols[2], "N/A", "Adjustment Factor")
            
        diag = pred_res.get("diagnostics", {})
        kpi(res_cols[3], f"{diag.get('consecutive_streak', 0)} consecutive", "Current Delivery Streak")
        
        if pred_res.get("risks"):
            st.markdown("**Management Guidance Diagnostics & Risks:**")
            for rk in pred_res["risks"]:
                st.markdown(f'<div class="risk-box">{rk}</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"#### 📈 Guidance Hurdle Curve & Sensitivity Simulator for `{chosen_ticker}`")
        st.caption("How does P(Delivery) evolve as management raises guidance targets? Reveals the operational tipping point where ambition outstrips capacity.")

        sim_data = predict.simulate_guidance_hurdle_curve(
            model=model, resolved=resolved, ticker=chosen_ticker,
            category=g_cat, steps=11, horizon_months=h_months,
            strength=str_val, role=spk_val
        )

        sim_col1, sim_col2 = st.columns([3, 2])
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
                marker=dict(size=14, color="#e37400", symbol="star", line=dict(color="#fff", width=2)),
                hovertemplate=f"Current: {g_val:g}{unit_lbl} -> {p_val:.1%}<extra></extra>"
            ))

            layout(fig_h, h=330, xaxis_title=f"Guided Target ({unit_lbl})", yaxis_title="P(Delivery) %", yaxis_range=[0, 100])
            st.plotly_chart(fig_h, width='stretch')

        with sim_col2:
            st.markdown("**Hurdle Analysis & Tipping Points:**")
            st.markdown(f"- **Trailing Historical Run Rate:** `{sim_data['benchmark_trailing']:g}{unit_lbl}`")
            if sim_data.get("high_confidence_ceiling") is not None:
                st.markdown(f"- **🟢 High Confidence Ceiling (P ≥ 65%):** up to `{sim_data['high_confidence_ceiling']:g}{unit_lbl}`")
            else:
                st.markdown(f"- **🟢 High Confidence Ceiling:** N/A (Track record requires conservative guidance)")

            if sim_data.get("hurdle_50_ceiling") is not None:
                st.markdown(f"- **🟡 Max Viable Guidance (P ≥ 50%):** `{sim_data['hurdle_50_ceiling']:g}{unit_lbl}`")
            else:
                st.markdown(f"- **🟡 Max Viable Guidance (P ≥ 50%):** `< {x_vals[0]:g}{unit_lbl}`")

            if sim_data.get("breakdown_risk_point") is not None:
                st.markdown(f"- **🔴 Breakdown Point (P < 45%):** beyond `{sim_data['breakdown_risk_point']:g}{unit_lbl}` (Elevated miss risk)")
            else:
                st.markdown(f"- **🔴 Breakdown Point:** Not reached within tested range.")

            st.info("💡 **Takeaway:** When guidance exceeds management's trailing run-rate by >15%, delivery probability drops non-linearly. Anchor analyst expectations to the **Credibility-Adjusted Guidance**.")

        st.write("")
        # Show recent similar promises by this company
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
    k = st.columns(5)
    kpi(k[0], f"{stats['promises']:,}", "promises extracted (quote-verified)")
    kpi(k[1], f"{stats['scored']:,}", "promises resolved so far")
    kept = sum(v for o, v in stats["outcomes"].items() if o == "DELIVERED")
    kpi(k[2], f"{100 * kept / max(1, stats['scored']):.0f}%", "delivered in full and on time")
    kpi(k[3], f"{stats['outcomes'].get('GHOSTED', 0):,}", "quietly dropped (never mentioned again)")
    kpi(k[4], f"{stats['unverifiable_dropped']:,}", "LLM quotes rejected by verifier")
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
    c1, c2 = st.columns([3, 2])
    c1.markdown("**Management Credibility Ranking** · companies with ≥3 resolved promises")
    c1.plotly_chart(fig, width='stretch')
    with c2:
        st.markdown("**Methodology & Guardrails**")
        st.markdown(
            "- **Say**: Models read every concall and extract each forward-looking commitment with a verbatim quote.\n"
            "- **Do**: Financial guidance is verified against reported numbers; operational commitments against later calls.\n"
            "- **Predict**: Ensemble machine learning combines past category hit rates, ambition gaps, and ghosting trends.\n"
            "- **👻 Ghosted**: Target missed and never mentioned again — the red flag markets overlook.")
        tbl = pd.DataFrame([{"Ticker": c["ticker"], "Score": c["score"], "Grade": c["grade"],
                             "Resolved": c["n"], "Ghost %": (c["ghost_rate"] or 0) * 100,
                             "Delayed/cut": c["goalpost_moves"],
                             "Rev. delivered/guided": c["revenue_delivery_ratio"]}
                            for c in scores["companies"]])
        st.dataframe(tbl, hide_index=True, width='stretch', height=360,
                     column_config={"Ghost %": st.column_config.NumberColumn(format="%.0f%%"),
                                    "Rev. delivered/guided": st.column_config.NumberColumn(format="%.2f×")})

# =============================================================== Company Ledger Tab
with tab_co:
    tickers = [c["ticker"] for c in sorted(scores["companies"], key=lambda c: -c["n"])]
    t = st.selectbox("Company", tickers, index=tickers.index("KAYNES") if "KAYNES" in tickers else 0, key="co_select")
    c = by_t[t]
    mine = [p for p in resolved if p["ticker"] == t]
    k = st.columns(5)
    kpi(k[0], f"{c['score']:.0f} · {c['grade']}", f"Say-Do (80% CI {c['ci80'][0]:.0f}–{c['ci80'][1]:.0f})")
    kpi(k[1], f"{c['financial']['score']:.0f}" if c.get("financial") else "–", "financial guidance score")
    kpi(k[2], f"{c['operational']['score']:.0f}" if c.get("operational") else "–", "operational guidance score")
    kpi(k[3], f"{c['revenue_delivery_ratio']:.2f}×" if c.get("revenue_delivery_ratio") else "–",
        "revenue delivered ÷ guided (median)")
    kpi(k[4], f"{c['goalpost_moves']}", "promises later delayed or cut")
    st.write("")

    g1, g2 = st.columns([3, 2])
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
    st.markdown("**Drop in a brand-new earnings call.** Frontier models extract every guidance promise; "
                "the ensemble predictor estimates which ones management will actually deliver, using historical track records.")
    l1, l2 = st.columns([1, 2])
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
        kpi(k[0], f"{lo.get('auc_model', 0):.3f}", f"LOCO AUC (90% CI {lo.get('auc_ci90')})")
        kpi(k[1], f"{wf.get('auc_model', 0):.3f}" if wf else "–", f"Walk-Forward AUC (Train < {wf.get('cutoff', '?')})")
        kpi(k[2], f"{lo.get('brier_model', 0):.3f}", f"Brier Score (Base Rate {lo.get('brier_base_rate', 0):.3f})")
        kpi(k[3], f"{ev['n']}", f"Resolved Promises · {ev['kept_rate']:.0%} Kept")
        st.write("")
        
        v1, v2 = st.columns(2)
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
    m1, m2 = st.columns(2)
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
