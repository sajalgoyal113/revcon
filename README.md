# 🎯 Concall — Management Guidance Accuracy & Delivery Predictor

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://revcon.streamlit.app/)
&nbsp;&nbsp;
[![Live Demo](https://img.shields.io/badge/Live%20App-revcon.streamlit.app-6366f1?style=flat&logo=streamlit)](https://revcon.streamlit.app/)

**Live Web Application:** [https://revcon.streamlit.app/](https://revcon.streamlit.app/)

**Predicting the future accuracy of holding management guidance using a company's past concall track record.**

Every earnings conference call is packed with management guidance: revenue growth targets, margin expansion projections, capex completion dates, and order pipeline estimates. Analysts routinely anchor on these numbers. Yet some managements guide 25% and consistently deliver 26%, while others guide 25% and deliver 12%, then quietly guide 25% again next quarter.

**Concall keeps score and predicts future guidance holding accuracy.**

It tracks every guidance commitment an Indian listed company has made across ~250 earnings calls, follows each commitment forward in time against actual reported quarterly/annual financial results and subsequent calls, and uses **Meta's frontier models (Muse Spark & Muse Wonder)** alongside an **Ensemble Stacking Machine Learning Engine (Bayesian MAP Logistic Regression + Pure-NumPy HistGBDT)** to predict:
1. **$P(\text{Guidance Held})$**: Probability that future management guidance will be delivered in full and on time.
2. **Credibility-Adjusted Guidance**: The realistic expectation calibrated for management's historical optimism bias or sandbagging ratio (e.g. Guided 30% $\rightarrow$ Credibility-Adjusted 27.4%).
3. **Guidance Risk Diagnostics**: Ambition gap penalties, ghosting risk, timeline slippage, and category-specific track record scores.

All headline numbers are in **[RESULTS.md](RESULTS.md)**, generated deterministically from pipeline outputs (`python -m saydo.report`).

*Stack: Meta-only — extraction and judging run on `muse-spark-1.3`, memo synthesis on `muse-wonder-1.0` (recorded in `data/out/stats.json`).*

---

## How It Works

```
 Concall Transcripts (~250 calls, 35 companies)        Screener Actuals (Quarterly + Annual P&L, Balance Sheets)
        │                                                              │
  ① SAY  Meta Muse (Spark) ──► Verbatim-Quote Verifier (hallucinations dropped)
        │   {category, value range, period, firmness, speaker, section, conditions, delta/bps basis}
        ▼
  ② DO   Financial Guidance ─────────────► Resolved against reported results (deterministic code, supporting
                                           level targets, YoY/QoQ/CAGR growth, and bps margin expansion deltas)
         Operational Guidance ───────────► Models read each LATER concall:
                                           DELIVERED / ON_TRACK / DELAYED / REVISED_DOWN / MISSED /
                                           ABANDONED / GHOSTED (+ verified management evidence quote)
        ▼
  ③ RESOLVE  Timeline → Outcome + Symmetric `knowable_at` Date   (Point-in-time: zero look-ahead bias)
        ▼
  ④ TRACK RECORD  Category-Aware Delivery & Slippage Rates:
                  - Revenue Guidance: delivery rate + median delivery ratio (e.g., 0.86×)
                  - EBITDA Margin Guidance: margin bias & variance
                  - Capex / Commissioning: delivery rate & timeline slippage
                  - Guidance Style: Conservative Sandbagger vs Disciplined Guide vs Habitual Over-Promiser
                  - Ghost Rate & Interim Slippage: promises quietly dropped or delayed mid-stream
        ▼
  ⑤ PREDICT  P(Guidance Held) for FUTURE guidance:
             Ensemble Stacking Model (Bayesian MAP Logistic Regression + Pure-NumPy HistGBDT)
             evaluated via Leave-One-Company-Out (LOCO) and Walk-Forward temporal splits.
        ▼
  ⑥ MEMO  Muse Wonder synthesizes an institutional credibility memo with verified citations.
```

## Frontier Models Used

| Model | Role | Provider |
|---|---|---|
| **`muse-spark-1.3`** | Guidance extraction (SAY), later-call evidence verification (DO), and zero-shot forecasting | Meta Model API |
| **`muse-wonder-1.0`** | Forensic credibility memo synthesis & deep contextual guidance reasoning | Meta Model API |
| **`muse-voice-transcribe-1.0`** | Earnings-call audio transcription | Meta Model API |
| **Ensemble Model (Bayesian MAP Logistic + Pure-NumPy HistGBDT)** | Portable, zero-sklearn-dependency probability estimation combining category track records, concall context & ambition gap | Pure NumPy |

---

## Empirical Predictive Performance

On 1,121 resolved management guidance promises across 35 companies (43.1% base full-delivery rate):

- **Leave-One-Company-Out (LOCO) ROC AUC**: **0.654** (90% CI [0.625, 0.682])
  - Category-Aware Company Score Alone: **0.533** (vs 0.486 before symmetric censoring fix)
  - Brier Score: **0.225** (vs 0.247 base rate)
  - Generalizes across management teams the model has never seen before.
- **Walk-Forward Temporal Split**: **0.648** (90% CI [0.612, 0.687])
  - Train strictly on outcomes knowable before 2025-07-18 ($n=189$); test on later guidance ($n=562$).
  - Category-Aware Company Score Alone: **0.550** (vs 0.437 before symmetric censoring fix)
  - Brier Score: **0.230** (vs 0.253 base rate).
- **Probability Calibration**:
  - Predicted 0–35% (mean 28.3%) $\rightarrow$ Actually kept: **33.3%** ($n=390$)
  - Predicted 35–45% (mean 39.9%) $\rightarrow$ Actually kept: **34.3%** ($n=286$)
  - Predicted 45–55% (mean 49.3%) $\rightarrow$ Actually kept: **46.3%** ($n=203$)
  - Predicted 55–65% (mean 59.5%) $\rightarrow$ Actually kept: **59.9%** ($n=142$)
  - Predicted 65–100% (mean 73.9%) $\rightarrow$ Actually kept: **76.0%** ($n=100$)

---

## Quickstart

```bash
# 1. Enter the Concall directory
cd concall_algorithm_package

# 2. Add your META_MODEL_API_KEY in .env (only needed for live LLM extraction)
cp .env.example .env

# 3. Run unit tests & standalone benchmark evaluation (deterministic, zero network overhead)
python3 run_evaluation.py
python3 tests/test_core.py
python3 tests/test_guidance_predict.py
```
