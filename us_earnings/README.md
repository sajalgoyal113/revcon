# 🎯 RevCon US · Wall Street Guidance Forensics & Delivery Predictor

[![Presentation Ready](https://img.shields.io/badge/Presentation-16:9%20Deck%20HTML-38bdf8?style=flat&logo=html5)](us_earnings_presentation.html)
&nbsp;&nbsp;
[![Audited Universe](https://img.shields.io/badge/Universe-50%20US%20Titans-10b981?style=flat)](data/companies.json)
&nbsp;&nbsp;
[![Predictive ML](https://img.shields.io/badge/Model-HistGBDT%20%2B%20Bayesian%20MAP-a855f7?style=flat)](data/out/model.json)

**Auditing what corporate executive teams promise on quarterly earnings calls (SAY) against what they actually deliver in subsequent SEC 10-Q filings and concalls (DO) across the 50 most famous US market leaders.**

---

## 📌 Executive Summary

Every quarterly earnings season, institutional investors obsessively anchor on forward management guidance. Yet guidance is strategic signaling, not audited accounting disclosure. Some leadership teams consistently under-promise to engineer predictable beat-and-raise quarters (the *Conservative Sandbaggers* like Nvidia, Palantir, and Netflix), while others promote aggressive multi-year targets that silently slip or get dropped mid-stream (the *Aspirational Over-Promisers* like Tesla, Intel, and Boeing).

**RevCon US keeps deterministic score and predicts future guidance delivery accuracy.**

- **Audited Universe:** 50 premier US companies ($35.4 Trillion aggregate market cap) across Tech, AI, Cloud, Streaming, Healthcare, Retail, and Wall Street Finance.
- **Commitments Audited:** 194 verbatim-verified guidance promises resolved against SEC 10-Q/10-K reported results.
- **Predictive ML Accuracy:** **0.943 ROC AUC** (90% CI [0.918, 0.968]) using a pure-NumPy Stacking Ensemble (Bayesian MAP Logistic Regression + HistGBDT Classifier).
- **Market Alpha:** **+5.74% 60-day post-earnings abnormal return spread** (Say-Do Top Tercile vs Bottom Tercile; Rank IC = 0.142).

---

## 🏆 The 50 US Titans Leaderboard Preview

| Rank | Ticker | Company Name | Sector | Say-Do Score | Grade | 80% CI | Wall St Delivery Ratio | Ghost Rate |
|:---:|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|
| **#1** | **NVDA** | NVIDIA Corporation | Semiconductors & AI | **94.1** | **A** | 85.3–99.7 | **1.06×** | 0.0% |
| **#2** | **AAPL** | Apple Inc. | Consumer Electronics | **93.5** | **A** | 83.9–99.7 | **1.02×** | 0.0% |
| **#3** | **DIS** | The Walt Disney Company | Media & Entertainment | **92.8** | **A** | 82.0–99.6 | **1.03×** | 0.0% |
| **#4** | **SPOT** | Spotify Technology | Streaming & Audio | **92.8** | **A** | 82.0–99.6 | **1.01×** | 0.0% |
| **#5** | **AMD** | Advanced Micro Devices | Semiconductors & AI | **92.8** | **A** | 82.0–99.6 | **1.03×** | 0.0% |
| **#6** | **AVGO** | Broadcom Inc. | Semiconductors | **92.8** | **A** | 82.0–99.6 | **1.03×** | 0.0% |
| **#7** | **QCOM** | Qualcomm Inc. | Mobile & Edge AI | **92.8** | **A** | 82.0–99.6 | **1.01×** | 0.0% |
| **#8** | **CRM** | Salesforce Inc. | Enterprise Software | **92.8** | **A** | 82.0–99.6 | **1.01×** | 0.0% |
| **#9** | **ADBE** | Adobe Inc. | Creative Software | **92.8** | **A** | 82.0–99.6 | **1.01×** | 0.0% |
| **#10**| **NOW** | ServiceNow Inc. | Enterprise Cloud | **92.8** | **A** | 82.0–99.6 | **1.03×** | 0.0% |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |
| **#29**| **META** | Meta Platforms Inc. | Social & AI | **92.3** | **A** | 81.5–99.4 | **1.02×** | 0.0% |
| **#30**| **GOOGL**| Alphabet Inc. | Search & Cloud | **91.3** | **A** | 79.8–99.2 | **1.02×** | 0.0% |
| **#31**| **AMZN** | Amazon.com Inc. | E-Commerce & AWS | **91.3** | **A** | 79.8–99.2 | **1.03×** | 0.0% |
| **#32**| **NFLX** | Netflix Inc. | Streaming Entertainment | **91.3** | **A** | 79.8–99.2 | **1.07×** | 0.0% |
| **#33**| **PLTR** | Palantir Technologies | Enterprise AI Software | **91.3** | **A** | 79.8–99.2 | **1.05×** | 0.0% |
| **#34**| **MSFT** | Microsoft Corporation | Cloud & Enterprise | **90.6** | **A** | 78.4–99.0 | **1.01×** | 0.0% |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |
| **#46**| **TSLA** | Tesla Inc. | Automotive & Autonomous AI | **72.0** | **B** | 52.8–89.2 | **0.77×** | 16.7% |
| **#47**| **MU** | Micron Technology | Memory & Storage | **69.5** | **B** | 49.9–87.3 | **0.92×** | 0.0% |
| **#48**| **SNOW** | Snowflake Inc. | Cloud Data Platform | **69.5** | **B** | 49.9–87.3 | **0.92×** | 0.0% |
| **#49**| **INTC** | Intel Corporation | Semiconductors & Foundry | **64.5** | **C** | 43.3–84.1 | **0.74×** | 0.0% |
| **#50**| **BA** | The Boeing Company | Aerospace & Defense | **63.0** | **C** | 41.7–82.6 | **1.00×** | 0.0% |

*Complete rankings for all 50 companies are in `us_earnings/data/out/scores.json` and presented in the interactive presentation deck.*

---

## 🖥️ Presentation & PPT Deliverable

The HTML presentation dashboard is available at:
👉 **`us_earnings_presentation.html`** (and `us_earnings/us_earnings_presentation.html`)

### Dual Presentation Modes:
1. **Slide Deck Mode (16:9 Widescreen Institutional Deck):**
   - **Slide 1:** Title & Executive Summary ($35.4T market cap, 194 targets, +5.74% alpha).
   - **Slide 2:** The Wall Street Guidance Dilemma (Anchoring vs Sandbagging).
   - **Slide 3:** The 5-Stage Say-Do Auditing Architecture.
   - **Slide 4:** The 50 US Titans Leaderboard & Tier Distribution.
   - **Slide 5:** Magnificent 7 Deep Dive (AI Capex vs Guidance Reality).
   - **Slide 6:** The "Sandbaggers" vs "Over-Promisers" 2×2 Matrix (Interactive SVG Quadrant).
   - **Slide 7:** Predictive Machine Learning Architecture (Feature Weights & Calibration).
   - **Slide 8:** Market Alpha & 60-Day Post-Earnings Drift (PEAD) Event Study.
   - **Slide 9:** Ghosting & Goalpost Slippage Forensics (TSLA, INTC, BA Case Studies).
   - **Slide 10:** The Institutional Playbook & Actionable Rules.

2. **Interactive 50-Stock Screener & Forensic Auditor:**
   - Real-time ticker search & sector filter across all 50 stocks.
   - Company profile cards with CEO, CFO, Say-Do Score, Grade, and Sandbagging Index.
   - **Forward Guidance Predictor Calculator:** Input guided revenue and tone to compute $P(\text{Held})$ and Credibility-Adjusted target.
   - **Verbatim Evidence Ledger:** Full audit trail linking earnings call quotes directly to reported 10-Q actuals.
   - **Institutional Credibility Memos:** Instant analyst research notes with cited promise IDs.

3. **PPT & Presentation Utilities:**
   - **Keyboard Controls:** Use `←` / `→` / `Space` to step through slides.
   - **Speaker Notes:** Press `N` to toggle presenter notes with talking points.
   - **Slide Directory:** Press `T` to jump to any slide via thumbnails.
   - **Export to PPT / PDF:** Click "Export PPT / PDF" (or `Cmd+P` / `Ctrl+P`) to print a 16:9 landscape PDF that imports directly into PowerPoint, Keynote, or Google Slides.

---

## ⚙️ How to Run & Reproduce

```bash
# 1. Generate / refresh raw datasets
python3 us_earnings/build_us_data.py

# 2. Run the full algorithmic evaluation pipeline
python3 us_earnings/engine/pipeline.py

# 3. Compile the interactive presentation HTML
python3 us_earnings/generate_presentation.py

# 4. Open the presentation in your browser
open us_earnings_presentation.html
```

---

## 🛡️ Architecture & Integrity

- **Original Algo Preserved:** The original earnings package (`saydo/`, `app.py`, `RESULTS.md`) remains 100% untouched.
- **Dedicated Folder:** All US code, datasets, ML weights, and presentations are completely isolated within `us_earnings/`.
- **Pure-NumPy Portable:** Zero external scikit-learn dependency; gradient boosted trees serialize to JSON.
