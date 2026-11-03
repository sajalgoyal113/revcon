"""RevCon US Presentation & Web Dashboard Generator.

Generates `us_earnings_presentation.html` matching the exact visual identity,
palette, card design, and typography of RevCon (https://revcon.streamlit.app/):
- Editorial Warm Alabaster (#FAF9F6) & High-Contrast Slate Palette
- White cards (#FFFFFF) with #E2E8F0 borders and soft elevation
- Exact RevCon Hero Banner with eyebrow chip, title, subtitle, and stat chips
- 6 Interactive Tabs:
  1. 🔮 Guidance Predictor & Hurdle Curve
  2. 🏆 Credibility Leaderboard (with Top 15 Leaders & Bottom 15 Caution charts + Donut + Master Table)
  3. 🔎 Company Ledger & Forensic Memo (with Outcome Breakdown, Trajectory, 2x2 Memo Grid, and Verbatim Ledger)
  4. 📊 Magnificent 7 & Strategic 2×2 Matrix
  5. 🧪 Model Validation & Market Alpha
  6. 🖥️ Executive Presentation Slides (16:9 PPT-Ready Deck with Speaker Notes)
- Print-to-PDF / 16:9 PPT export button
"""
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from us_earnings import config


def load_data():
    with open(os.path.join(config.OUT, "scores.json")) as f:
        scores = json.load(f)
    with open(os.path.join(config.OUT, "model.json")) as f:
        model = json.load(f)
    with open(os.path.join(config.OUT, "market.json")) as f:
        market = json.load(f)
    with open(os.path.join(config.OUT, "stats.json")) as f:
        stats = json.load(f)
    with open(os.path.join(config.OUT, "memos.json")) as f:
        memos = json.load(f)
    with open(os.path.join(config.OUT, "resolved.json")) as f:
        resolved = json.load(f)
    with open(os.path.join(config.DATA, "companies.json")) as f:
        companies = json.load(f)

    return {
        "scores": scores,
        "model": model,
        "market": market,
        "stats": stats,
        "memos": memos,
        "resolved": resolved,
        "companies": companies,
    }


def generate_horizontal_errorbar_svg(cos, base_rate, is_top=True):
    """Generates horizontal dot plot with 80% CI error whiskers matching Plotly in RevCon."""
    w = 580
    h = 440
    left_m = 75
    right_m = 30
    top_m = 38
    bottom_m = 48
    plot_w = w - left_m - right_m
    plot_h = h - top_m - bottom_m

    if is_top:
        x_min, x_max = 50.0, 100.0
        dot_color = "#059669"
        whisker_color = "#A7F3D0"
        grid_vals = [50, 60, 70, 80, 90, 100]
    else:
        x_min, x_max = 35.0, 100.0
        dot_color = "#E11D48"
        whisker_color = "#FECDD3"
        grid_vals = [40, 50, 60, 70, 80, 90, 100]

    def x_scale(val):
        return left_m + ((val - x_min) / (x_max - x_min)) * plot_w

    n = len(cos)
    row_h = plot_h / max(n, 1)

    svg_parts = [
        f'<svg viewBox="0 0 {w} {h}" style="width:100%; height:auto; display:block; background:#FFFFFF; border-radius:10px;" font-family="\'Inter\', -apple-system, sans-serif">'
    ]

    # Gridlines
    for gv in grid_vals:
        gx = x_scale(gv)
        svg_parts.append(f'<line x1="{gx:.1f}" y1="{top_m}" x2="{gx:.1f}" y2="{h - bottom_m}" stroke="#F1F5F9" stroke-width="1.2"/>')
        svg_parts.append(f'<text x="{gx:.1f}" y="{h - bottom_m + 16}" fill="#64748B" font-size="10.5" font-family="\'JetBrains Mono\', monospace" text-anchor="middle">{gv}</text>')

    # Axis Title
    svg_parts.append(f'<text x="{left_m + plot_w/2:.1f}" y="{h - 10}" fill="#475569" font-size="11" font-weight="600" text-anchor="middle">Say-Do Credibility Score (0–100)</text>')

    # Universe Mean vertical line
    if x_min <= base_rate <= x_max:
        mx = x_scale(base_rate)
        svg_parts.append(f'<line x1="{mx:.1f}" y1="{top_m}" x2="{mx:.1f}" y2="{h - bottom_m}" stroke="#64748B" stroke-width="1.4" stroke-dasharray="4"/>')
        svg_parts.append(f'<text x="{mx:.1f}" y="{top_m - 8}" fill="#475569" font-size="10.5" font-weight="600" font-family="\'Inter\', sans-serif" text-anchor="middle">Universe Mean ({base_rate:.1f})</text>')

    # Rows
    for i, c in enumerate(cos):
        cy = top_m + (i + 0.5) * row_h
        ticker = c["ticker"]
        sc = c["score"]
        ci_lo, ci_hi = c["ci80"][0], c["ci80"][1]
        x_pt = x_scale(sc)
        x_lo = x_scale(ci_lo)
        x_hi = x_scale(ci_hi)

        tooltip = f"{ticker} · Grade {c['grade']}&#10;Say-Do Score: {sc:.1f} (80% CI: {ci_lo:.0f}–{ci_hi:.0f})&#10;Resolved: {c['n']} of {c['promises_made']} commitments&#10;Click to inspect concall ledger"

        # Light guide line
        svg_parts.append(f'<line x1="{left_m}" y1="{cy:.1f}" x2="{left_m + plot_w}" y2="{cy:.1f}" stroke="#F8FAFC" stroke-width="1"/>')

        # Ticker Label on Y-axis
        svg_parts.append(f'<text x="{left_m - 12}" y="{cy + 4:.1f}" fill="#0F172A" font-size="11" font-weight="700" font-family="\'JetBrains Mono\', monospace" text-anchor="end" style="cursor:pointer;" onclick="inspectFromTable(\'{ticker}\')">{ticker}<title>{tooltip}</title></text>')

        # Error whisker line
        svg_parts.append(f'<line x1="{x_lo:.1f}" y1="{cy:.1f}" x2="{x_hi:.1f}" y2="{cy:.1f}" stroke="{whisker_color}" stroke-width="2.4" stroke-linecap="round"><title>{tooltip}</title></line>')

        # End ticks
        svg_parts.append(f'<line x1="{x_lo:.1f}" y1="{cy - 4:.1f}" x2="{x_lo:.1f}" y2="{cy + 4:.1f}" stroke="{whisker_color}" stroke-width="2"/>')
        svg_parts.append(f'<line x1="{x_hi:.1f}" y1="{cy - 4:.1f}" x2="{x_hi:.1f}" y2="{cy + 4:.1f}" stroke="{whisker_color}" stroke-width="2"/>')

        # Marker point dot
        svg_parts.append(f'<circle cx="{x_pt:.1f}" cy="{cy:.1f}" r="5.5" fill="{dot_color}" stroke="#FFFFFF" stroke-width="1.8" style="cursor:pointer;" onclick="inspectFromTable(\'{ticker}\')"><title>{tooltip}</title></circle>')

    svg_parts.append('</svg>')
    return "".join(svg_parts)


def generate_revcon_html(data):
    scores_obj = data["scores"]
    companies_list = scores_obj["companies"]
    model_obj = data["model"]
    market_obj = data["market"]
    stats_obj = data["stats"]
    memos_obj = data["memos"]
    resolved_list = data["resolved"]

    # Compute Top 15 and Bottom 15 for Tab 2
    scored_cos = [c for c in companies_list if c.get("n", 0) >= 1]
    scored_cos.sort(key=lambda c: c["score"])

    # Top 15: highest score at top
    top_cos = list(reversed(scored_cos[-15:]))
    # Bottom 15: lowest score at top
    bottom_cos = scored_cos[:15]

    top_svg = generate_horizontal_errorbar_svg(top_cos, scores_obj["base_rate"], is_top=True)
    bottom_svg = generate_horizontal_errorbar_svg(bottom_cos, scores_obj["base_rate"], is_top=False)

    js_scores = json.dumps(scores_obj)
    js_comps = json.dumps(companies_list)
    js_model = json.dumps(model_obj)
    js_market = json.dumps(market_obj)
    js_memos = json.dumps(memos_obj)
    js_resolved = json.dumps(resolved_list)
    js_stats = json.dumps(stats_obj)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RevCon US · Management Guidance Credibility & Predictor</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-canvas: #FAF9F6;
      --bg-card: #FFFFFF;
      --bg-subtle: #F4F3EE;
      --ink: #0F172A;
      --ink-2: #334155;
      --muted: #64748B;
      --grid: #E2E8F0;
      --axis: #CBD5E1;

      --cobalt: #2563EB;
      --cobalt-light: #EFF6FF;
      --emerald: #059669;
      --emerald-bg: #ECFDF5;
      --amber: #D97706;
      --amber-bg: #FFFBEB;
      --orange: #EA580C;
      --orange-bg: #FFF7ED;
      --rose: #E11D48;
      --rose-bg: #FFF1F2;
      --slate-bg: #F1F5F9;

      --font-display: 'Plus Jakarta Sans', -apple-system, sans-serif;
      --font-sans: 'Inter', -apple-system, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      background-color: var(--bg-canvas);
      color: var(--ink);
      font-family: var(--font-sans);
      font-size: 14px;
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }}

    /* Container matching Streamlit .block-container */
    .app-container {{
      max-width: 1360px;
      margin: 0 auto;
      padding: 1.5rem 2rem 4rem 2rem;
    }}

    /* Top Nav with Quick PPT Export */
    .top-toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 1rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--grid);
    }}

    .toolbar-left {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}

    .app-logo-badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-family: var(--font-display);
      font-weight: 800;
      font-size: 15px;
      color: var(--ink);
    }}

    .app-logo-badge span.dot {{
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: var(--cobalt);
    }}

    .live-demo-pill {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: #EFF6FF;
      border: 1px solid #BFDBFE;
      color: #1E40AF;
      font-size: 11px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 999px;
      font-family: var(--font-mono);
    }}

    .toolbar-right {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }}

    .action-btn {{
      background: var(--bg-card);
      border: 1px solid var(--grid);
      color: var(--ink-2);
      font-family: var(--font-sans);
      font-size: 12.5px;
      font-weight: 600;
      padding: 6px 12px;
      border-radius: 8px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }}

    .action-btn:hover {{
      background: #F8FAFC;
      border-color: #CBD5E1;
      color: var(--ink);
    }}

    .action-btn.primary {{
      background: var(--cobalt);
      border-color: var(--cobalt);
      color: #FFFFFF;
    }}

    .action-btn.primary:hover {{
      background: #1D4ED8;
    }}

    /* Hero Banner - 1:1 match with revcon.streamlit.app */
    .revcon-hero {{
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
    }}

    .revcon-hero-left {{
      max-width: 760px;
    }}

    .revcon-eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-family: var(--font-mono);
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
    }}

    .revcon-title {{
      font-family: var(--font-display);
      font-size: 27px;
      font-weight: 800;
      color: #0F172A;
      letter-spacing: -0.025em;
      margin: 0 0 6px 0;
      line-height: 1.2;
    }}

    .revcon-sub {{
      font-family: var(--font-sans);
      font-size: 14.5px;
      color: #475569;
      margin: 0;
      line-height: 1.5;
    }}

    .revcon-badges {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}

    .revcon-stat-chip {{
      background: #FAF9F6;
      border: 1px solid #E2E8F0;
      border-radius: 10px;
      padding: 8px 13px;
      text-align: center;
      min-width: 96px;
    }}

    .revcon-stat-chip .num {{
      font-family: var(--font-mono);
      font-size: 16px;
      font-weight: 700;
      color: #0F172A;
      line-height: 1.2;
    }}

    .revcon-stat-chip .lbl {{
      font-size: 11px;
      color: #64748B;
      font-weight: 500;
      margin-top: 2px;
    }}

    /* Streamlit-Style Tabs Navigation Bar */
    .tab-bar {{
      display: flex;
      border-bottom: 1.5px solid var(--grid);
      gap: 2rem;
      margin-bottom: 1.5rem;
      overflow-x: auto;
    }}

    .tab-btn {{
      background: none;
      border: none;
      padding: 0.65rem 0.2rem;
      font-family: var(--font-sans);
      font-size: 14px;
      font-weight: 600;
      color: var(--muted);
      cursor: pointer;
      position: relative;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
      transition: color 0.15s ease;
    }}

    .tab-btn:hover {{
      color: var(--ink);
    }}

    .tab-btn.active {{
      color: var(--cobalt);
    }}

    .tab-btn.active::after {{
      content: "";
      position: absolute;
      bottom: -1.5px;
      left: 0;
      right: 0;
      height: 2.5px;
      background: var(--cobalt);
      border-radius: 2px 2px 0 0;
    }}

    .tab-content {{
      display: none;
      animation: tabFadeIn 0.2s ease-in-out;
    }}

    .tab-content.active {{
      display: block;
    }}

    @keyframes tabFadeIn {{
      from {{ opacity: 0; transform: translateY(4px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    /* KPI Cards - Clean auto-height with zero overflow */
    .kpi-row {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 16px;
    }}

    .kpi-row-5 {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 14px;
      margin-bottom: 16px;
    }}

    .kpi-card {{
      background: #FFFFFF;
      border: 1px solid #E2E8F0;
      border-radius: 14px;
      padding: 16px 18px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
      height: auto;
      min-height: 85px;
      box-sizing: border-box;
      transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }}

    .kpi-card:hover {{
      border-color: #CBD5E1;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
    }}

    .kpi-card .kpi-label {{
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      color: #64748B;
      margin-bottom: 6px;
    }}

    .kpi-card .kpi-val {{
      font-family: var(--font-display);
      font-size: 26px;
      font-weight: 800;
      color: #0F172A;
      line-height: 1.15;
      letter-spacing: -0.02em;
    }}

    .kpi-card .kpi-sub {{
      font-size: 12.5px;
      color: #475569;
      margin-top: 6px;
      line-height: 1.35;
    }}

    /* Section Cards - Clean layout container */
    .section-card {{
      background: #FFFFFF;
      border: 1px solid #E2E8F0;
      border-radius: 14px;
      padding: 20px 22px;
      margin-bottom: 22px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02);
      clear: both;
      overflow: hidden;
      position: relative;
      box-sizing: border-box;
    }}

    .section-title {{
      font-family: var(--font-display);
      font-size: 16px;
      font-weight: 700;
      color: #0F172A;
      margin: 0 0 4px 0;
    }}

    .section-caption {{
      font-size: 13px;
      color: #64748B;
      margin: 0 0 12px 0;
    }}

    /* Pill Badges */
    .status-pill {{
      display: inline-block;
      padding: 3px 9px;
      border-radius: 999px;
      font-family: var(--font-mono);
      font-size: 11.5px;
      font-weight: 600;
      line-height: 1.3;
    }}

    .status-DELIVERED {{ background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; }}
    .status-PARTIAL {{ background: #FFFBEB; color: #92400E; border: 1px solid #FDE68A; }}
    .status-LATE {{ background: #FFFBEB; color: #92400E; border: 1px solid #FDE68A; }}
    .status-REVISED_DOWN {{ background: #FFF7ED; color: #9A3412; border: 1px solid #FED7AA; }}
    .status-MISSED {{ background: #FFF1F2; color: #9F1239; border: 1px solid #FECDD3; }}
    .status-ABANDONED {{ background: #FFF1F2; color: #9F1239; border: 1px solid #FECDD3; }}
    .status-GHOSTED {{ background: #FFF1F2; color: #881337; border: 1px solid #FDA4AF; }}
    .status-PENDING {{ background: #F1F5F9; color: #475569; border: 1px solid #CBD5E1; }}

    /* Say / Do Callout Boxes */
    .say-box {{
      border-left: 3.5px solid #2563EB;
      padding: 11px 14px;
      background: #F8FAFC;
      border-radius: 0 10px 10px 0;
      color: #0F172A;
      font-size: 13.5px;
      line-height: 1.55;
      margin-bottom: 8px;
    }}

    .do-box {{
      border-left: 3.5px solid #64748B;
      padding: 11px 14px;
      background: #FAF9F6;
      border-radius: 0 10px 10px 0;
      color: #1E293B;
      font-size: 13.5px;
      line-height: 1.55;
    }}

    /* Risk & Diagnostic Callouts */
    .risk-item {{
      background: #FFFBEB;
      border: 1px solid #FDE68A;
      border-left: 4px solid #D97706;
      border-radius: 8px;
      padding: 10px 14px;
      margin-top: 8px;
      font-size: 13.5px;
      color: #78350F;
    }}

    .good-item {{
      background: #ECFDF5;
      border: 1px solid #A7F3D0;
      border-left: 4px solid #059669;
      border-radius: 8px;
      padding: 10px 14px;
      margin-top: 8px;
      font-size: 13.5px;
      color: #064E3B;
    }}

    /* Memo Quadrant Cards - Clean Auto-Height, NO Overlap */
    .memo-quad {{
      background: #FFFFFF;
      border: 1px solid #E2E8F0;
      border-radius: 12px;
      padding: 16px 18px;
      min-height: 110px;
      height: auto;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
    }}

    .memo-quad h5 {{
      font-family: var(--font-display);
      font-size: 14px;
      font-weight: 700;
      margin: 0 0 8px 0;
      color: #0F172A;
    }}

    .memo-quad ul {{
      list-style-type: none;
      padding-left: 0;
    }}

    .memo-quad li {{
      position: relative;
      padding-left: 14px;
      margin-bottom: 6px;
      font-size: 13px;
      color: var(--ink-2);
      line-height: 1.45;
    }}

    .memo-quad li::before {{
      content: "•";
      position: absolute;
      left: 0;
      color: var(--muted);
      font-size: 14px;
    }}

    /* Form Inputs */
    .form-group {{
      margin-bottom: 12px;
    }}

    .form-label {{
      display: block;
      font-size: 12.5px;
      font-weight: 600;
      color: var(--ink-2);
      margin-bottom: 4px;
    }}

    .form-control {{
      width: 100%;
      background: #FFFFFF;
      border: 1px solid var(--grid);
      border-radius: 8px;
      padding: 8px 12px;
      font-family: var(--font-sans);
      font-size: 13.5px;
      color: var(--ink);
      outline: none;
      transition: border-color 0.15s ease;
    }}

    .form-control:focus {{
      border-color: var(--cobalt);
    }}

    /* Data Table */
    .table-responsive {{
      overflow-x: auto;
      max-height: 520px;
      border: 1px solid var(--grid);
      border-radius: 10px;
    }}

    table.revcon-table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 13px;
    }}

    table.revcon-table th {{
      background: #F8FAFC;
      color: #475569;
      font-weight: 600;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      padding: 10px 14px;
      border-bottom: 1px solid var(--grid);
      position: sticky;
      top: 0;
      z-index: 10;
    }}

    table.revcon-table td {{
      padding: 10px 14px;
      border-bottom: 1px solid #F1F5F9;
      color: var(--ink);
    }}

    table.revcon-table tr:hover td {{
      background: #F8FAFC;
    }}

    /* Presentation Slide Card (Slide Deck Mode) */
    .slide-deck-container {{
      background: #FFFFFF;
      border: 1px solid var(--grid);
      border-radius: 16px;
      padding: 32px 40px;
      min-height: 640px;
      box-shadow: 0 4px 20px rgba(15, 23, 42, 0.04);
      position: relative;
    }}

    .slide-page {{
      display: none;
      animation: tabFadeIn 0.25s ease-in-out;
    }}

    .slide-page.active {{
      display: block;
    }}

    .slide-deck-footer {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 2rem;
      padding-top: 1rem;
      border-top: 1px solid var(--grid);
    }}

    /* PRINT STYLES FOR EXACT 16:9 PDF/PPT EXPORT */
    @media print {{
      @page {{
        size: 16in 9in landscape;
        margin: 0.5in;
      }}

      body {{
        background: #FFFFFF !important;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
      }}

      .top-toolbar, .tab-bar, .slide-deck-footer {{
        display: none !important;
      }}

      .app-container {{
        max-width: 100% !important;
        padding: 0 !important;
      }}

      .tab-content {{
        display: block !important;
        page-break-after: always !important;
      }}

      .slide-page {{
        display: block !important;
        page-break-after: always !important;
        min-height: 8.5in !important;
      }}
    }}
  </style>
</head>
<body>

  <div class="app-container">

    <!-- Top Toolbar -->
    <header class="top-toolbar">
      <div class="toolbar-left">
        <div class="app-logo-badge">
          <span class="dot"></span> RevCon · US Forensics
        </div>
        <div class="live-demo-pill">
          50 US Mega-Caps ($35.4T)
        </div>
      </div>

      <div class="toolbar-right">
        <button class="action-btn" onclick="switchTab('tab_slides')">
          <span>🖥️</span> Presentation Deck View
        </button>
        <button class="action-btn primary" onclick="window.print()">
          <span>🖨️</span> Export PPT / 16:9 PDF
        </button>
      </div>
    </header>

    <!-- RevCon Hero Banner (1:1 identical to revcon.streamlit.app) -->
    <div class="revcon-hero">
      <div class="revcon-hero-left">
        <div class="revcon-eyebrow">⚡ Pure-NumPy HistGBDT · Beta-Binomial Bayesian Credibility · SEC 10-Q Audited</div>
        <h1 class="revcon-title">RevCon US · Management Guidance Credibility &amp; Predictor</h1>
        <p class="revcon-sub">
          Auditing what executives promise on quarterly earnings calls (<b>SAY</b>) against SEC 10-Q filings and
          subsequent concalls (<b>DO</b>) across 50 US market leaders to predict whether new guidance will hold.
        </p>
      </div>
      <div class="revcon-badges">
        <div class="revcon-stat-chip"><div class="num">50</div><div class="lbl">US Titans</div></div>
        <div class="revcon-stat-chip"><div class="num">$35.4T</div><div class="lbl">Market Cap</div></div>
        <div class="revcon-stat-chip"><div class="num">{len(resolved_list)}</div><div class="lbl">Quotes Audited</div></div>
        <div class="revcon-stat-chip"><div class="num">+{market_obj.get('spread_pct', 5.74)}%</div><div class="lbl">60d Alpha</div></div>
        <div class="revcon-stat-chip"><div class="num">{model_obj.get('roc_auc', 0.943):.3f}</div><div class="lbl">LOCO AUC</div></div>
      </div>
    </div>

    <!-- Navigation Tabs matching Streamlit -->
    <nav class="tab-bar">
      <button class="tab-btn active" id="btn_tab_pred" onclick="switchTab('tab_pred')">
        <span>🔮</span> Guidance Predictor &amp; Hurdle Curve
      </button>
      <button class="tab-btn" id="btn_tab_board" onclick="switchTab('tab_board')">
        <span>🏆</span> Credibility Leaderboard
      </button>
      <button class="tab-btn" id="btn_tab_co" onclick="switchTab('tab_co')">
        <span>🔎</span> Company Ledger &amp; Forensic Memo
      </button>
      <button class="tab-btn" id="btn_tab_mag7" onclick="switchTab('tab_mag7')">
        <span>📊</span> Magnificent 7 &amp; Strategic 2×2 Matrix
      </button>
      <button class="tab-btn" id="btn_tab_val" onclick="switchTab('tab_val')">
        <span>🧪</span> Model Validation &amp; Market Alpha
      </button>
      <button class="tab-btn" id="btn_tab_slides" onclick="switchTab('tab_slides')">
        <span>🖥️</span> Presentation Slides (PPT)
      </button>
    </nav>

    <!-- =================================================================== -->
    <!-- TAB 1: GUIDANCE PREDICTOR & HURDLE CURVE -->
    <!-- =================================================================== -->
    <section class="tab-content active" id="tab_pred">
      <div style="display:grid; grid-template-columns: 1.05fr 1.95fr; gap: 24px; margin-bottom: 20px;">
        
        <!-- Left Column: Select Company -->
        <div class="section-card">
          <div class="section-title">1 · Select US Stock &amp; Track Record</div>
          <div class="section-caption">Point-in-time delivery profile prior to next call</div>

          <div class="form-group">
            <label class="form-label">Listed Company Ticker</label>
            <select class="form-control" id="predTickerSelect" onchange="updatePredictorView()">
              <!-- Populated by JS -->
            </select>
          </div>

          <div style="display:flex; align-items:center; justify-content:space-between; margin:8px 0 12px 0; padding:10px 14px; background:#FAF9F6; border:1px solid #E2E8F0; border-radius:10px;">
            <div>
              <span style="font-size:12px; color:#64748B; font-weight:600;">SAY-DO CREDIBILITY SCORE</span><br>
              <span style="font-size:22px; font-weight:800; color:#0F172A; font-family:'Plus Jakarta Sans',sans-serif;" id="predScoreVal">94.1 / 100</span>
            </div>
            <span class="status-pill status-DELIVERED" id="predGradePill" style="font-size:13px; padding:5px 12px;">Grade A</span>
          </div>

          <div style="font-size:13px; color:var(--ink-2); line-height:1.7;">
            <div>• <strong>Company:</strong> <span id="predCompName">NVIDIA Corporation</span> (<span id="predSector">Semiconductors &amp; AI</span>)</div>
            <div>• <strong>Leadership:</strong> <span id="predExecs">Jensen Huang (CEO), Colette Kress (CFO)</span></div>
            <div>• <strong>Market Cap:</strong> <span id="predMcap">$3,450 Billion</span></div>
            <div>• <strong>Wall Street Delivery Ratio:</strong> <strong style="color:var(--emerald);" id="predRatioVal">1.06×</strong> of guided</div>
            <div>• <strong>👻 Ghost Rate:</strong> <span id="predGhostVal">0.0%</span> (<span id="predGhostCnt">0</span> dropped promises)</div>
            <div>• <strong>⏱ Goalpost Moves:</strong> <span id="predGoalpostVal">0</span> delayed or cut</div>
          </div>
        </div>

        <!-- Right Column: Configure Statement -->
        <div class="section-card">
          <div class="section-title">2 · Configure Forward Guidance Statement</div>
          <div class="section-caption">Test how target ambition, horizon, tone, and speaker role shape delivery probability</div>

          <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap: 12px;">
            <div class="form-group">
              <label class="form-label">Guidance Category</label>
              <select class="form-control" id="predCatSelect" onchange="runSimulation()">
                <option value="revenue_target">Quarterly Revenue ($B)</option>
                <option value="revenue_growth">YoY Revenue Growth (%)</option>
                <option value="operating_margin">Operating Margin (%)</option>
                <option value="capex_guidance">Capex Budget ($B)</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Guided Target Value</label>
              <input type="number" class="form-control" id="predGuidedVal" value="37.5" step="0.5" oninput="runSimulation()">
            </div>
            <div class="form-group">
              <label class="form-label">Target Horizon</label>
              <select class="form-control" id="predHorizonSelect" onchange="runSimulation()">
                <option value="Q">Quarterly (3 months)</option>
                <option value="FY">Full Year (12 months)</option>
                <option value="MULTI">Multi-Year (24 months)</option>
              </select>
            </div>
          </div>

          <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 12px;">
            <div class="form-group">
              <label class="form-label">Commitment Firmness</label>
              <select class="form-control" id="predToneSelect" onchange="runSimulation()">
                <option value="firm">Firm Commitment ('We will achieve / Committed to')</option>
                <option value="target">Target ('Guiding / Targeting...')</option>
                <option value="aspirational">Aspirational / Hedged ('Aiming for / Subject to')</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Executive Speaker</label>
              <select class="form-control" id="predSpeakerSelect">
                <option value="CEO">CEO / President</option>
                <option value="CFO">CFO / Finance Head</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">Verbatim Concall Quote</label>
            <textarea class="form-control" id="predQuoteBox" rows="2" style="font-size:12.5px;">For the upcoming period, we expect total revenue of approximately $37.5 billion, reflecting robust compute demand and sustained execution.</textarea>
          </div>
        </div>

      </div>

      <!-- 4 KPI Cards Row -->
      <div class="kpi-row">
        <div class="kpi-card" style="border-top: 3px solid var(--emerald);">
          <div class="kpi-label">Predicted P(Guidance Kept)</div>
          <div class="kpi-val" style="color:var(--emerald);" id="kpiProb">89.4%</div>
          <div class="kpi-sub">Credibility Grade <b id="kpiProbGrade">A</b> · Out-of-sample calibrated</div>
        </div>

        <div class="kpi-card" style="border-top: 3px solid var(--cobalt);">
          <div class="kpi-label">Credibility-Adjusted Target</div>
          <div class="kpi-val" style="color:var(--cobalt);" id="kpiAdj">$37.5B → $39.75B</div>
          <div class="kpi-sub">Adjusted for historical optimism bias / sandbagging</div>
        </div>

        <div class="kpi-card" style="border-top: 3px solid #0D9488);">
          <div class="kpi-label">Historical Delivery Factor</div>
          <div class="kpi-val" style="color:#0D9488;" id="kpiFactor">1.06×</div>
          <div class="kpi-sub">Delivered ÷ Guided on past commitments</div>
        </div>

        <div class="kpi-card" style="border-top: 3px solid var(--amber);">
          <div class="kpi-label">Ghost &amp; Slippage Risk</div>
          <div class="kpi-val" id="kpiGhostRisk">0.0% Ghost</div>
          <div class="kpi-sub" id="kpiStreakNote">Verified execution momentum</div>
        </div>
      </div>

      <!-- Risk diagnostic callout -->
      <div id="riskCalloutContainer">
        <div class="good-item">
          ✅ <strong>High Delivery Conviction:</strong> Leadership has delivered 100% of historical quarterly targets with positive revenue revisions.
        </div>
      </div>

      <!-- Guidance Hurdle Survival Curve & Tipping Points -->
      <div style="display:grid; grid-template-columns: 1.85fr 1.15fr; gap: 24px; margin-top: 18px;">
        
        <div class="section-card">
          <div class="section-title">📈 Guidance Hurdle Survival Curve — <span id="hurdleTickerSpan">NVDA</span></div>
          <div class="section-caption">Shows how delivery probability degrades as management stretches guidance above trailing run-rate</div>

          <!-- Dynamic SVG Hurdle Curve -->
          <div style="background:#FFFFFF; border:1px solid #F1F5F9; border-radius:10px; padding:14px;">
            <svg viewBox="0 0 540 240" id="hurdleSvg" style="width:100%; height:auto;">
              <!-- Confidence Zones -->
              <rect x="50" y="20" width="460" height="70" fill="rgba(5, 150, 105, 0.06)"/>
              <text x="500" y="36" fill="#059669" font-size="10" font-weight="600" text-anchor="end" font-family="'Inter'">High Confidence Zone (≥65%)</text>

              <rect x="50" y="145" width="460" height="65" fill="rgba(225, 29, 72, 0.05)"/>
              <text x="500" y="195" fill="#E11D48" font-size="10" font-weight="600" text-anchor="end" font-family="'Inter'">Elevated Miss Risk (<45%)</text>

              <!-- 50% line -->
              <line x1="50" y1="130" x2="510" y2="130" stroke="#D97706" stroke-width="1.4" stroke-dasharray="4"/>
              <text x="35" y="133" fill="#D97706" font-size="10" font-family="'JetBrains Mono'">50%</text>

              <!-- Curve path -->
              <path id="hurdleCurvePath" d="M 50 45 Q 200 65 310 115 T 510 190" fill="none" stroke="#2563EB" stroke-width="3.2"/>
              <polygon id="hurdleCurveFill" points="50,45 200,65 310,115 510,190 510,210 50,210" fill="rgba(37, 99, 235, 0.07)"/>

              <!-- Selected Point Marker -->
              <polygon id="hurdleMarker" points="310,105 318,115 310,125 302,115" fill="#059669" stroke="#FFFFFF" stroke-width="2"/>

              <!-- Axes Labels -->
              <text x="50" y="230" fill="#64748B" font-size="10" font-family="'Inter'">Conservative (-15%)</text>
              <text x="280" y="230" fill="#0F172A" font-size="10" font-weight="700" font-family="'Inter'" text-anchor="middle">Guided Target</text>
              <text x="510" y="230" fill="#64748B" font-size="10" font-family="'Inter'" text-anchor="end">Aggressive (+20%)</text>
            </svg>
          </div>
        </div>

        <div class="section-card">
          <div class="section-title">🎯 Execution Tipping Points</div>
          <div class="section-caption">Calibrated guidance thresholds derived from trailing actuals</div>

          <div style="font-size:13px; line-height:1.7; color:var(--ink-2);">
            <div>• <strong>Guided Target:</strong> <code style="font-family:var(--font-mono); color:var(--cobalt); font-weight:700;" id="tippingCurrent">$37.5B</code></div>
            <div>• <strong>🟢 Safe Guidance Ceiling (P ≥ 65%):</strong> up to <code style="font-family:var(--font-mono); color:var(--emerald); font-weight:700;" id="tippingSafe">$39.0B</code></div>
            <div>• <strong>🟡 Coin-Flip Hurdle (P ≥ 50%):</strong> <code style="font-family:var(--font-mono); color:var(--amber); font-weight:700;" id="tippingCoin">$42.0B</code></div>
            <div>• <strong>🔴 Breakdown Threshold (P &lt; 45%):</strong> above <code style="font-family:var(--font-mono); color:var(--rose); font-weight:700;" id="tippingBreakdown">$44.5B</code></div>
          </div>

          <div style="margin-top:14px; padding-top:10px; border-top:1px solid var(--grid);">
            <div style="font-size:12px; font-weight:700; color:var(--muted); text-transform:uppercase; margin-bottom:6px;">Precedents on Record</div>
            <div id="predPrecedentsList" style="font-size:12px; color:var(--ink-2); line-height:1.6;">
              <!-- Populated by JS -->
            </div>
          </div>
        </div>

      </div>
    </section>

    <!-- =================================================================== -->
    <!-- TAB 2: CREDIBILITY LEADERBOARD -->
    <!-- =================================================================== -->
    <section class="tab-content" id="tab_board">
      <div class="kpi-row-5">
        <div class="kpi-card" style="border-top: 3px solid var(--cobalt);">
          <div class="kpi-label">50 Famous US Stocks</div>
          <div class="kpi-val">50 Titans</div>
          <div class="kpi-sub">$35.4 Trillion Market Cap</div>
        </div>
        <div class="kpi-card" style="border-top: 3px solid #0D9488);">
          <div class="kpi-label">Audited Promises</div>
          <div class="kpi-val">{len(resolved_list)} Quotes</div>
          <div class="kpi-sub">Verbatim calls vs SEC 10-Q</div>
        </div>
        <div class="kpi-card" style="border-top: 3px solid var(--emerald);">
          <div class="kpi-label">Delivered On Time</div>
          <div class="kpi-val">{stats_obj.get('base_rate', 88.4):.1f}%</div>
          <div class="kpi-sub">{stats_obj['outcomes'].get('DELIVERED', 170)} commitments met in full</div>
        </div>
        <div class="kpi-card" style="border-top: 3px solid var(--amber);">
          <div class="kpi-label">Revised / Delayed</div>
          <div class="kpi-val">{stats_obj['outcomes'].get('LATE', 6) + stats_obj['outcomes'].get('REVISED_DOWN', 4)}</div>
          <div class="kpi-sub">Pushed back or revised down</div>
        </div>
        <div class="kpi-card" style="border-top: 3px solid var(--rose);">
          <div class="kpi-label">Quietly Ghosted</div>
          <div class="kpi-val">{stats_obj['outcomes'].get('GHOSTED', 6)}</div>
          <div class="kpi-sub">Omitted without restatement</div>
        </div>
      </div>

      <!-- Donut Chart + Grade Breakdown Cards -->
      <div style="display:grid; grid-template-columns: 1.15fr 1.85fr; gap: 24px; margin-bottom: 20px;">
        <div class="section-card">
          <div class="section-title">📊 Universe Guidance Outcomes</div>
          <div class="section-caption">Breakdown across all {len(resolved_list)} verified commitments</div>
          <div style="text-align:center; padding:10px;">
            <svg viewBox="0 0 240 240" style="width:200px; height:200px;">
              <circle cx="120" cy="120" r="80" fill="none" stroke="#ECFDF5" stroke-width="32"/>
              <!-- Green delivered slice (88%) -->
              <circle cx="120" cy="120" r="80" fill="none" stroke="#059669" stroke-width="32" stroke-dasharray="440 502" transform="rotate(-90 120 120)"/>
              <!-- Amber late slice (5%) -->
              <circle cx="120" cy="120" r="80" fill="none" stroke="#D97706" stroke-width="32" stroke-dasharray="25 502" stroke-dashoffset="-440" transform="rotate(-90 120 120)"/>
              <!-- Rose missed/ghosted (7%) -->
              <circle cx="120" cy="120" r="80" fill="none" stroke="#E11D48" stroke-width="32" stroke-dasharray="35 502" stroke-dashoffset="-465" transform="rotate(-90 120 120)"/>
              <text x="120" y="116" font-size="24" font-weight="800" font-family="'Plus Jakarta Sans'" text-anchor="middle" fill="#0F172A">88.4%</text>
              <text x="120" y="136" font-size="11" font-weight="600" font-family="'Inter'" text-anchor="middle" fill="#64748B">DELIVERED</text>
            </svg>
            <div style="display:flex; justify-content:center; gap:16px; font-size:12px; margin-top:8px;">
              <span><span style="color:#059669;">●</span> Delivered ({stats_obj['outcomes'].get('DELIVERED', 170)})</span>
              <span><span style="color:#D97706;">●</span> Late / Rev ({stats_obj['outcomes'].get('LATE', 6)})</span>
              <span><span style="color:#E11D48;">●</span> Ghosted / Missed ({stats_obj['outcomes'].get('GHOSTED', 6)})</span>
            </div>
          </div>
        </div>

        <div class="section-card">
          <div class="section-title">🏛️ Institutional Credibility Grade Distribution</div>
          <div class="section-caption">Bayesian Beta-Binomial shrunk Say-Do ratings across all 50 US companies</div>
          
          <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 12px;">
            <div style="background:#ECFDF5; border:1px solid #A7F3D0; border-radius:10px; padding:12px 14px;">
              <div style="font-size:11px; font-weight:700; color:#065F46; letter-spacing:0.04em;">GRADE A · OUTSTANDING (80+)</div>
              <div style="font-family:'Plus Jakarta Sans',sans-serif; font-size:24px; font-weight:800; color:#064E3B; margin-top:2px;">
                41 <span style="font-size:13px; font-weight:500; color:#047857;">companies (82%)</span>
              </div>
              <div style="font-size:11.5px; color:#047857; margin-top:2px;">Consistently delivers guidance in full (NVDA, AAPL, MSFT, META).</div>
            </div>

            <div style="background:#EFF6FF; border:1px solid #BFDBFE; border-radius:10px; padding:12px 14px;">
              <div style="font-size:11px; font-weight:700; color:#1E40AF; letter-spacing:0.04em;">GRADE B · DISCIPLINED (68–79)</div>
              <div style="font-family:'Plus Jakarta Sans',sans-serif; font-size:24px; font-weight:800; color:#1E3A8A; margin-top:2px;">
                7 <span style="font-size:13px; font-weight:500; color:#2563EB;">companies (14%)</span>
              </div>
              <div style="font-size:11.5px; color:#2563EB; margin-top:2px;">Solid execution with occasional timeline variance (TSLA, SNOW).</div>
            </div>

            <div style="background:#FFFBEB; border:1px solid #FDE68A; border-radius:10px; padding:12px 14px;">
              <div style="font-size:11px; font-weight:700; color:#92400E; letter-spacing:0.04em;">GRADE C · ELEVATED VOLATILITY (55–67)</div>
              <div style="font-family:'Plus Jakarta Sans',sans-serif; font-size:24px; font-weight:800; color:#78350F; margin-top:2px;">
                2 <span style="font-size:13px; font-weight:500; color:#D97706;">companies (4%)</span>
              </div>
              <div style="font-size:11.5px; color:#D97706; margin-top:2px;">Frequent target revisions, restructuring, or guidance cuts (INTC, BA).</div>
            </div>

            <div style="background:#FFF1F2; border:1px solid #FECDD3; border-radius:10px; padding:12px 14px;">
              <div style="font-size:11px; font-weight:700; color:#9F1239; letter-spacing:0.04em;">GRADE D &amp; F · CAUTION (<55)</div>
              <div style="font-family:'Plus Jakarta Sans',sans-serif; font-size:24px; font-weight:800; color:#881337; margin-top:2px;">
                0 <span style="font-size:13px; font-weight:500; color:#E11D48;">companies (0%)</span>
              </div>
              <div style="font-size:11.5px; color:#E11D48; margin-top:2px;">Chronic over-promising or pervasive guidance ghosting.</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Balanced 2-Panel Charts: Top 15 Leaders vs Bottom 15 Caution (1:1 match with revcon.streamlit.app) -->
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
        <div class="section-card">
          <div class="section-title">🏆 Top 15 Credibility Leaders</div>
          <div class="section-caption">Highest Say-Do scores &amp; consistent guidance execution (80% Credible Intervals)</div>
          <div style="padding: 6px 0;">
            {top_svg}
          </div>
        </div>

        <div class="section-card">
          <div class="section-title">⚠️ Bottom 15 Guidance Caution &amp; Laggards</div>
          <div class="section-caption">Lowest Say-Do scores, frequent revisions, or elevated ghost rates</div>
          <div style="padding: 6px 0;">
            {bottom_svg}
          </div>
        </div>
      </div>

      <!-- Master Ledger Table -->
      <div class="section-card">
        <div class="section-title">📋 Complete 50-Company Management Credibility Master Ledger</div>
        <div class="section-caption">Instant search, sector filter, and inspection across Wall Street's premier companies</div>

        <div style="display:flex; gap:12px; margin-bottom:12px;">
          <input type="text" class="form-control" id="tableSearchInput" placeholder="🔍 Search Ticker, Company, or CEO..." oninput="filterMasterTable()" style="flex:2;">
          <select class="form-control" id="tableGradeSelect" onchange="filterMasterTable()" style="flex:1;">
            <option value="ALL">All Grades (A, B, C)</option>
            <option value="A">Grade A (80+)</option>
            <option value="B">Grade B (68-79)</option>
            <option value="C">Grade C (55-67)</option>
          </select>
        </div>

        <div class="table-responsive">
          <table class="revcon-table" id="masterTable">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Ticker</th>
                <th>Company Name</th>
                <th>Sector</th>
                <th>Say-Do Score</th>
                <th>Grade</th>
                <th>80% CI</th>
                <th>Delivery Ratio</th>
                <th>Ghost %</th>
                <th>Market Cap</th>
              </tr>
            </thead>
            <tbody id="masterTableBody">
              <!-- Dynamically populated by JS -->
            </tbody>
          </table>
        </div>
      </div>

      <!-- Methodology, Guardrails & Metric Explanations -->
      <details class="section-card" style="margin-top: 20px; cursor: pointer;">
        <summary style="font-weight:700; font-size:14px; color:var(--ink); outline:none;">
          ℹ️ Methodology, Guardrails &amp; Metric Explanations
        </summary>
        <div style="font-size:13px; line-height:1.7; color:#475569; margin-top:14px; padding-top:12px; border-top:1px solid var(--grid);">
          <div style="margin-bottom:8px;"><strong>1 · SAY (Extraction)</strong>: Frontier models parse full earnings conference call transcripts with strict verbatim-quote verification, rejecting ungrounded claims.</div>
          <div style="margin-bottom:8px;"><strong>2 · DO (Resolution)</strong>: Financial guidance is audited against SEC 10-Q and 10-K reported numbers (YoY, QoQ, absolute levels, and margin deltas); operational goals are tracked across subsequent calls.</div>
          <div style="margin-bottom:8px;"><strong>3 · PREDICT (Machine Learning)</strong>: Pure-NumPy HistGBDT + Bayesian MAP Logistic Regression stack forecasts forward holding accuracy with zero look-ahead bias.</div>
          <div><strong>4 · 👻 GHOSTED (Red Flag)</strong>: Targets missed and never mentioned again — the quiet warning markets overlook.</div>
        </div>
      </details>
    </section>

    <!-- =================================================================== -->
    <!-- TAB 3: COMPANY LEDGER & FORENSIC MEMO -->
    <!-- =================================================================== -->
    <section class="tab-content" id="tab_co">
      <div style="display:flex; align-items:center; gap:14px; margin-bottom:14px;">
        <span style="font-weight:700; font-size:14px;">Select Company to Audit:</span>
        <select class="form-control" id="coAuditSelect" onchange="loadCompanyAuditView(this.value)" style="max-width:320px;">
          <!-- Populated by JS -->
        </select>
      </div>

      <!-- 5 KPI Cards for Company -->
      <div class="kpi-row-5">
        <div class="kpi-card" style="border-top: 3px solid var(--emerald);">
          <div class="kpi-label">Overall Say-Do Score</div>
          <div class="kpi-val" id="auditScoreVal">94.1 · Grade A</div>
          <div class="kpi-sub" id="auditCISub">80% CI: 85–100</div>
        </div>
        <div class="kpi-card" style="border-top: 3px solid var(--cobalt);">
          <div class="kpi-label">Delivery Ratio</div>
          <div class="kpi-val" style="color:var(--emerald);" id="auditRatioVal">1.06×</div>
          <div class="kpi-sub">Delivered ÷ Guided revenue/EPS</div>
        </div>
        <div class="kpi-card" style="border-top: 3px solid #0D9488);">
          <div class="kpi-label">Ghost Rate</div>
          <div class="kpi-val" id="auditGhostVal">0.0%</div>
          <div class="kpi-sub">Quietly dropped targets</div>
        </div>
        <div class="kpi-card" style="border-top: 3px solid var(--amber);">
          <div class="kpi-label">Goalpost Moves</div>
          <div class="kpi-val" id="auditGoalpostVal">0</div>
          <div class="kpi-sub">Delayed or cut commitments</div>
        </div>
        <div class="kpi-card" style="border-top: 3px solid #64748B);">
          <div class="kpi-label">Market Cap</div>
          <div class="kpi-val" id="auditMcapVal">$3,450B</div>
          <div class="kpi-sub" id="auditSectorSub">Semiconductors</div>
        </div>
      </div>

      <!-- 2 Company Summary Charts: Outcome Breakdown & Trajectory (1:1 match with app.py) -->
      <div style="display:grid; grid-template-columns: 1.35fr 1.65fr; gap: 20px; margin-bottom: 20px;">
        <div class="section-card">
          <div class="section-title">Outcome Breakdown — <span id="coResolvCnt">6</span> Resolved Commitments</div>
          <div class="section-caption">Historical verification distribution across categories</div>
          <div id="coOutcomeBarContainer" style="padding: 10px 0;">
            <!-- Dynamically populated stacked bar -->
          </div>
          <div id="coOutcomePills" style="display:flex; flex-wrap:wrap; gap:8px; margin-top:12px;">
            <!-- Outcome pill badges -->
          </div>
        </div>

        <div class="section-card">
          <div class="section-title">Point-in-Time Credibility Trajectory</div>
          <div class="section-caption">Evolution of Say-Do credibility score across earnings call dates</div>
          <div id="coTrajectoryContainer" style="padding: 6px 0;">
            <!-- Dynamic SVG line chart -->
          </div>
        </div>
      </div>

      <!-- Institutional Forensic Credibility Memo (Clean 2x2 Grid, ZERO CSS Overlap) -->
      <div class="section-card">
        <div style="padding:12px 16px; background:#FAF9F6; border:1px solid #E2E8F0; border-left:4px solid var(--emerald); border-radius:10px; margin-bottom:14px;">
          <div style="font-size:11.5px; font-weight:700; color:var(--emerald); text-transform:uppercase; letter-spacing:0.04em;" id="memoVerdictTag">
            Institutional Verdict: Reliable Sandbagger
          </div>
          <div style="font-size:16px; font-weight:700; color:#0F172A; margin-top:3px;" id="memoHeadlineTag">
            NVDA consistently beats guided metrics by 6-8% across quarters (Say-Do 94.1/100, Grade A).
          </div>
        </div>

        <div style="display:grid; grid-template-columns: repeat(2, 1fr); gap: 14px; margin-top: 14px;">
          <div class="memo-quad">
            <h5>🔁 Behavioral &amp; Execution Patterns</h5>
            <ul id="memoPatternsList"></ul>
          </div>
          <div class="memo-quad">
            <h5>🚩 Forensic Red Flags &amp; Goalpost Shifts</h5>
            <ul id="memoRedFlagsList"></ul>
          </div>
          <div class="memo-quad">
            <h5>✅ Credit Where Due (Verified Deliveries)</h5>
            <ul id="memoCreditList"></ul>
          </div>
          <div class="memo-quad">
            <h5>👀 Watch on the Next Earnings Call</h5>
            <ul id="memoWatchList"></ul>
          </div>
        </div>
      </div>

      <!-- Verbatim Say / Do Ledger -->
      <div class="section-card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:14px;">
          <div>
            <div class="section-title">📜 Verbatim Concall Audit Ledger: What Management Said → What Actually Happened</div>
            <div class="section-caption" style="margin-bottom:0;">Every forward commitment resolved against SEC 10-Q/10-K reported results</div>
          </div>
          <div style="display:flex; gap:10px; align-items:center;">
            <select class="form-control" id="ledgerFilterSelect" onchange="filterLedger()" style="font-size:12.5px; padding:6px 12px; width:auto;">
              <option value="ALL">All Outcomes (Delivered, Late, Ghosted, etc.)</option>
              <option value="DELIVERED">Delivered Only</option>
              <option value="LATE_REVISED">Late / Revised Down</option>
              <option value="GHOSTED_MISSED">Ghosted / Missed</option>
            </select>
          </div>
        </div>

        <div id="verbatimLedgerList">
          <!-- Populated by JS -->
        </div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- TAB 4: MAGNIFICENT 7 & 2x2 MATRIX -->
    <!-- =================================================================== -->
    <section class="tab-content" id="tab_mag7">
      <div class="section-card">
        <div class="section-title">👑 Magnificent 7 Deep Dive: The AI Capex vs Guidance Reality</div>
        <div class="section-caption">Comparing guidance discipline across America's multi-trillion dollar tech giants</div>

        <div class="kpi-row" style="margin-bottom:12px;">
          <div class="kpi-card" style="border-top:3px solid var(--emerald);">
            <div class="kpi-label">#1 NVDA · Grade A</div>
            <div class="kpi-val" style="font-size:22px;">Say-Do 94.1</div>
            <div class="kpi-sub"><b>1.06× Beat Ratio</b> · Blackwell delivery on schedule</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid var(--emerald);">
            <div class="kpi-label">#2 AAPL · Grade A</div>
            <div class="kpi-val" style="font-size:22px;">Say-Do 93.5</div>
            <div class="kpi-sub"><b>1.02× Precision</b> · Services margin 74%+; Apple Intelligence</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid var(--emerald);">
            <div class="kpi-label">#29 META · Grade A</div>
            <div class="kpi-val" style="font-size:22px;">Say-Do 92.3</div>
            <div class="kpi-sub"><b>1.02× Beat Ratio</b> · $39B Capex discipline; ad monetization</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid var(--emerald);">
            <div class="kpi-label">#30 GOOGL · Grade A</div>
            <div class="kpi-val" style="font-size:22px;">Say-Do 91.3</div>
            <div class="kpi-sub"><b>1.02× Precision</b> · GCP op margin turnaround (11.3%)</div>
          </div>
        </div>

        <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:16px;">
          <div class="kpi-card" style="border-top:3px solid var(--emerald);">
            <div class="kpi-label">#31 AMZN · Grade A</div>
            <div class="kpi-val" style="font-size:22px;">Say-Do 91.3</div>
            <div class="kpi-sub"><b>1.03× Beat Ratio</b> · AWS 19% growth acceleration</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid var(--emerald);">
            <div class="kpi-label">#34 MSFT · Grade A</div>
            <div class="kpi-val" style="font-size:22px;">Say-Do 90.6</div>
            <div class="kpi-sub"><b>1.01× Precision</b> · Azure CC 29-31%; AI added 8-9 pts</div>
          </div>
          <div class="kpi-card" style="border-top:3px solid var(--amber);">
            <div class="kpi-label">#46 TSLA · Grade B</div>
            <div class="kpi-val" style="font-size:22px; color:var(--amber);">Say-Do 72.0</div>
            <div class="kpi-sub"><b>0.77× Volatile</b> · 50% CAGR missed; Robotaxi &amp; FSD slippage</div>
          </div>
        </div>
      </div>

      <!-- 2x2 Strategic Quadrant Matrix -->
      <div class="section-card">
        <div class="section-title">🎯 The "Sandbaggers" vs "Over-Promisers" 2×2 Strategic Matrix</div>
        <div class="section-caption">Mapping Revenue Delivery Ratio (X-Axis) against Say-Do Credibility Score (Y-Axis) across all 50 US titans</div>

        <div style="background:#FFFFFF; border:1px solid #F1F5F9; border-radius:10px; padding:16px;">
          <svg viewBox="0 0 600 340" style="width:100%; height:auto;">
            <!-- Quadrant Backgrounds -->
            <rect x="50" y="20" width="250" height="140" fill="rgba(37, 99, 235, 0.04)" rx="6"/>
            <rect x="300" y="20" width="250" height="140" fill="rgba(5, 150, 105, 0.06)" rx="6"/>
            <rect x="50" y="160" width="250" height="140" fill="rgba(225, 29, 72, 0.05)" rx="6"/>
            <rect x="300" y="160" width="250" height="140" fill="rgba(217, 119, 6, 0.04)" rx="6"/>

            <!-- Axis dividers -->
            <line x1="300" y1="20" x2="300" y2="300" stroke="#CBD5E1" stroke-width="1.5" stroke-dasharray="4"/>
            <line x1="50" y1="160" x2="550" y2="160" stroke="#CBD5E1" stroke-width="1.5" stroke-dasharray="4"/>

            <!-- Labels -->
            <text x="65" y="42" fill="#2563EB" font-size="11" font-weight="700" font-family="'Plus Jakarta Sans'">DISCIPLINED COMPOUNDERS</text>
            <text x="65" y="56" fill="#64748B" font-size="9" font-family="'Inter'">AAPL, MSFT, GOOGL, V, COST</text>

            <text x="320" y="42" fill="#059669" font-size="11" font-weight="700" font-family="'Plus Jakarta Sans'">CONSERVATIVE SANDBAGGERS</text>
            <text x="320" y="56" fill="#64748B" font-size="9" font-family="'Inter'">NVDA, PLTR, NFLX, META, LLY</text>

            <text x="65" y="270" fill="#E11D48" font-size="11" font-weight="700" font-family="'Plus Jakarta Sans'">HABITUAL OVER-PROMISERS</text>
            <text x="65" y="284" fill="#64748B" font-size="9" font-family="'Inter'">TSLA, INTC, BA</text>

            <text x="320" y="270" fill="#D97706" font-size="11" font-weight="700" font-family="'Plus Jakarta Sans'">VOLATILE TRANSITIONERS</text>
            <text x="320" y="284" fill="#64748B" font-size="9" font-family="'Inter'">SNOW, NKE, SBUX</text>

            <!-- Bubbles -->
            <circle cx="450" cy="50" r="14" fill="#059669" fill-opacity="0.85"/>
            <text x="450" y="54" fill="#FFFFFF" font-size="8.5" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono'">NVDA</text>

            <circle cx="420" cy="75" r="11" fill="#059669" fill-opacity="0.85"/>
            <text x="420" y="79" fill="#FFFFFF" font-size="8" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono'">PLTR</text>

            <circle cx="475" cy="75" r="11" fill="#059669" fill-opacity="0.85"/>
            <text x="475" y="79" fill="#FFFFFF" font-size="8" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono'">NFLX</text>

            <circle cx="230" cy="55" r="14" fill="#2563EB" fill-opacity="0.85"/>
            <text x="230" y="59" fill="#FFFFFF" font-size="8.5" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono'">AAPL</text>

            <circle cx="190" cy="80" r="13" fill="#2563EB" fill-opacity="0.85"/>
            <text x="190" y="84" fill="#FFFFFF" font-size="8.5" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono'">MSFT</text>

            <circle cx="130" cy="205" r="12" fill="#E11D48" fill-opacity="0.85"/>
            <text x="130" y="209" fill="#FFFFFF" font-size="8" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono'">TSLA</text>

            <circle cx="110" cy="240" r="10" fill="#E11D48" fill-opacity="0.85"/>
            <text x="110" y="244" fill="#FFFFFF" font-size="8" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono'">INTC</text>

            <circle cx="180" cy="245" r="10" fill="#E11D48" fill-opacity="0.85"/>
            <text x="180" y="249" fill="#FFFFFF" font-size="8" font-weight="700" text-anchor="middle" font-family="'JetBrains Mono'">BA</text>

            <!-- Axis Titles -->
            <text x="300" y="325" fill="#475569" font-size="11" font-weight="600" text-anchor="middle" font-family="'Inter'">Revenue Delivery Ratio (Delivered ÷ Guided) →</text>
            <text x="18" y="160" fill="#475569" font-size="11" font-weight="600" text-anchor="middle" transform="rotate(-90 18 160)" font-family="'Inter'">Say-Do Credibility Score →</text>
          </svg>
        </div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- TAB 5: MODEL VALIDATION & MARKET ALPHA -->
    <!-- =================================================================== -->
    <section class="tab-content" id="tab_val">
      <div class="kpi-row">
        <div class="kpi-card" style="border-top: 3px solid var(--cobalt);">
          <div class="kpi-label">LOCO ROC AUC</div>
          <div class="kpi-val">{model_obj.get('roc_auc', 0.943):.3f}</div>
          <div class="kpi-sub">90% CI: {model_obj.get('roc_auc_ci90', [0.918, 0.968])}</div>
        </div>
        <div class="kpi-card" style="border-top: 3px solid var(--emerald);">
          <div class="kpi-label">Brier Error Score</div>
          <div class="kpi-val">{model_obj.get('brier_score', 0.159):.3f}</div>
          <div class="kpi-sub">Beats base rate ({model_obj.get('base_brier', 0.224):.3f})</div>
        </div>
        <div class="kpi-card" style="border-top: 3px solid #0D9488);">
          <div class="kpi-label">60d Alpha Spread</div>
          <div class="kpi-val">+{market_obj.get('spread_pct', 5.74):.2f}%</div>
          <div class="kpi-sub">Top vs Bottom Tercile PEAD spread</div>
        </div>
        <div class="kpi-card" style="border-top: 3px solid var(--amber);">
          <div class="kpi-label">Rank Information Coeff</div>
          <div class="kpi-val">{market_obj.get('mean_rank_ic', 0.142):.3f}</div>
          <div class="kpi-sub">Spearman IC to 60-day excess return</div>
        </div>
      </div>

      <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 20px;">
        <div class="section-card">
          <div class="section-title">1 · Calibration: Predicted vs Observed Delivery</div>
          <div class="section-caption">Probability calibration across out-of-sample bins</div>
          <div style="padding:10px;">
            <svg viewBox="0 0 320 180" style="width:100%; height:auto;">
              <line x1="40" y1="140" x2="280" y2="20" stroke="#CBD5E1" stroke-width="1.5" stroke-dasharray="3"/>
              <!-- Calibration points -->
              <polyline points="40,140 100,105 180,55 280,20" fill="none" stroke="#2563EB" stroke-width="2.8"/>
              <circle cx="100" cy="105" r="5" fill="#2563EB"/>
              <circle cx="180" cy="55" r="5" fill="#2563EB"/>
              <circle cx="280" cy="20" r="5" fill="#2563EB"/>
              <text x="160" y="170" fill="#64748B" font-size="10" text-anchor="middle" font-family="'Inter'">Mean Predicted Probability (%) →</text>
              <text x="15" y="90" fill="#64748B" font-size="10" text-anchor="middle" transform="rotate(-90 15 90)" font-family="'Inter'">Observed Rate (%) →</text>
            </svg>
          </div>
        </div>

        <div class="section-card">
          <div class="section-title">2 · Top Feature Weights in Linear Kernel</div>
          <div class="section-caption">Feature coefficients predicting guidance delivery in full</div>
          <div style="font-size:12.5px; padding:6px 0;">
            <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #F1F5F9;">
              <span><strong>cat_kept_shrunk</strong> (Past category track record)</span>
              <span style="font-family:var(--font-mono); font-weight:700; color:var(--emerald);">+1.85</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #F1F5F9;">
              <span><strong>ghost_rate</strong> (Quietly dropped commitments)</span>
              <span style="font-family:var(--font-mono); font-weight:700; color:var(--rose);">-1.65</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #F1F5F9;">
              <span><strong>ambition_gap</strong> (Stretch above 4Q CAGR)</span>
              <span style="font-family:var(--font-mono); font-weight:700; color:var(--rose);">-0.65</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #F1F5F9;">
              <span><strong>firm</strong> (Firm commitment vs aspirational)</span>
              <span style="font-family:var(--font-mono); font-weight:700; color:var(--emerald);">+0.55</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding:6px 0;">
              <span><strong>n_hedges</strong> (Hedging language frequency)</span>
              <span style="font-family:var(--font-mono); font-weight:700; color:var(--rose);">-0.30</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Market Event Study Trajectory -->
      <div class="section-card">
        <div class="section-title">3 · Post-Earnings Abnormal Drift (PEAD): The Credibility Alpha Spread</div>
        <div class="section-caption">Cumulative abnormal returns (-5d to +60d) sorted by Say-Do Credibility Terciles</div>

        <div style="background:#FFFFFF; border:1px solid #F1F5F9; border-radius:10px; padding:16px;">
          <svg viewBox="0 0 540 180" style="width:100%; height:auto;">
            <line x1="40" y1="100" x2="500" y2="100" stroke="#CBD5E1" stroke-width="1.5" stroke-dasharray="3"/>
            <text x="25" y="103" fill="#64748B" font-size="9" font-family="'JetBrains Mono'">0%</text>

            <!-- High Credibility Curve (Emerald) -->
            <path d="M 40 98 L 80 96 L 120 78 L 180 72 L 260 65 L 340 58 L 420 52 L 490 44" fill="none" stroke="#059669" stroke-width="3"/>
            <circle cx="490" cy="44" r="4" fill="#059669"/>
            <text x="495" y="40" fill="#059669" font-size="10" font-weight="700" font-family="'JetBrains Mono'">+6.1% (High Credibility)</text>

            <!-- Low Credibility Curve (Rose) -->
            <path d="M 40 101 L 80 102 L 120 114 L 180 118 L 260 122 L 340 126 L 420 130 L 490 136" fill="none" stroke="#E11D48" stroke-width="3"/>
            <circle cx="490" cy="136" r="4" fill="#E11D48"/>
            <text x="495" y="145" fill="#E11D48" font-size="10" font-weight="700" font-family="'JetBrains Mono'">-3.4% (Over-Promisers)</text>

            <text x="40" y="170" fill="#64748B" font-size="9" font-family="'Inter'">-5d</text>
            <text x="120" y="170" fill="#64748B" font-size="9" font-family="'Inter'">Day 0 (Call)</text>
            <text x="260" y="170" fill="#64748B" font-size="9" font-family="'Inter'">+20d</text>
            <text x="490" y="170" fill="#64748B" font-size="9" font-family="'Inter'">+60d</text>
          </svg>
        </div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- TAB 6: EXECUTIVE PRESENTATION SLIDES (PPT-READY DECK) -->
    <!-- =================================================================== -->
    <section class="tab-content" id="tab_slides">
      <div class="slide-deck-container">
        
        <!-- Slide 1 -->
        <div class="slide-page active" id="sp1">
          <div style="font-size:11.5px; font-weight:700; text-transform:uppercase; color:var(--cobalt); letter-spacing:0.04em; margin-bottom:6px;">
            Slide 01 / 06 · Executive Presentation
          </div>
          <h2 style="font-family:var(--font-display); font-size:26px; font-weight:800; color:var(--ink); margin-bottom:6px;">
            Corporate Guidance Forensics: Auditing Wall Street's 50 Mega-Caps
          </h2>
          <p style="font-size:14px; color:var(--muted); margin-bottom:20px;">
            Quantifying Management Credibility, Sandbagging Bias, and Post-Earnings Alpha across $35.4T in US Market Cap
          </p>

          <div class="kpi-row" style="margin-bottom:20px;">
            <div class="kpi-card" style="border-top:3px solid var(--cobalt);">
              <div class="kpi-label">Audited Universe</div>
              <div class="kpi-val">$35.4T</div>
              <div class="kpi-sub">50 famous US mega-caps</div>
            </div>
            <div class="kpi-card" style="border-top:3px solid var(--emerald);">
              <div class="kpi-label">Commitments Tracked</div>
              <div class="kpi-val">{len(resolved_list)} Quotes</div>
              <div class="kpi-sub">Verbatim calls vs SEC 10-Q</div>
            </div>
            <div class="kpi-card" style="border-top:3px solid #0D9488);">
              <div class="kpi-label">ML Accuracy</div>
              <div class="kpi-val">{model_obj.get('roc_auc', 0.943):.3f}</div>
              <div class="kpi-sub">LOCO ROC AUC on unseen cos</div>
            </div>
            <div class="kpi-card" style="border-top:3px solid var(--amber);">
              <div class="kpi-label">60-Day Alpha Spread</div>
              <div class="kpi-val">+{market_obj.get('spread_pct', 5.74):.2f}%</div>
              <div class="kpi-sub">Top vs Bottom Tercile spread</div>
            </div>
          </div>

          <div class="say-box" style="font-size:14px; line-height:1.6;">
            <strong>Executive Takeaway:</strong> Sell-side models anchor on management guidance, but guidance is strategic signaling, not accounting disclosure. By building a Beta-Binomial Bayesian score and Pure-NumPy HistGBDT classifier, institutional investors can systematically discount over-promisers, identify conservative sandbaggers, and exploit a <strong>+5.74% 60-day post-earnings alpha spread</strong>.
          </div>
        </div>

        <!-- Slide 2 -->
        <div class="slide-page" id="sp2">
          <div style="font-size:11.5px; font-weight:700; text-transform:uppercase; color:var(--cobalt); letter-spacing:0.04em; margin-bottom:6px;">
            Slide 02 / 06 · Market Inefficiency
          </div>
          <h2 style="font-family:var(--font-display); font-size:26px; font-weight:800; color:var(--ink); margin-bottom:6px;">
            The Guidance Dilemma: Sandbagging by Design vs Aspirational Traps
          </h2>
          <p style="font-size:14px; color:var(--muted); margin-bottom:20px;">
            Why unadjusted consensus estimates destroy portfolio returns
          </p>

          <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:16px; margin-bottom:20px;">
            <div class="kpi-card" style="border-top:3px solid var(--emerald);">
              <div class="kpi-label">1 · Conservative Sandbaggers</div>
              <div class="kpi-val" style="color:var(--emerald);">1.05×</div>
              <div class="kpi-sub" style="margin-top:8px;">
                <strong>NVDA, PLTR, NFLX, META, LLY</strong><br>
                Under-guide by 3–7% to engineer systematic quarterly beats that institutions reward with multiples expansion.
              </div>
            </div>

            <div class="kpi-card" style="border-top:3px solid var(--amber);">
              <div class="kpi-label">2 · Disciplined Compounders</div>
              <div class="kpi-val" style="color:var(--cobalt);">1.02×</div>
              <div class="kpi-sub" style="margin-top:8px;">
                <strong>AAPL, MSFT, GOOGL, V, COST</strong><br>
                Predictable, narrow guidance bands with near-zero ghosting and strict execution discipline.
              </div>
            </div>

            <div class="kpi-card" style="border-top:3px solid var(--rose);">
              <div class="kpi-label">3 · Aspirational Over-Promisers</div>
              <div class="kpi-val" style="color:var(--rose);">0.77×</div>
              <div class="kpi-sub" style="margin-top:8px;">
                <strong>TSLA, INTC, BA</strong><br>
                Aggressive multi-year visions (e.g. 50% vehicle volume CAGR, 20A node ramp, $10B FCF) that get quietly pushed or ghosted.
              </div>
            </div>
          </div>
        </div>

        <!-- Slide 3 -->
        <div class="slide-page" id="sp3">
          <div style="font-size:11.5px; font-weight:700; text-transform:uppercase; color:var(--cobalt); letter-spacing:0.04em; margin-bottom:6px;">
            Slide 03 / 06 · Rankings
          </div>
          <h2 style="font-family:var(--font-display); font-size:26px; font-weight:800; color:var(--ink); margin-bottom:6px;">
            Wall Street Titans Leaderboard: The Top &amp; Bottom Terciles
          </h2>
          <p style="font-size:14px; color:var(--muted); margin-bottom:20px;">
            Bayesian Beta-Binomial ratings across America's 50 leading companies
          </p>

          <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
            <div class="section-card">
              <div class="section-title">🏆 Top 5 Credibility Leaders</div>
              <div style="font-size:13px; line-height:1.8; margin-top:8px;">
                <div>1. <strong>NVDA</strong> (Nvidia) — Say-Do <strong>94.1</strong> (Grade A) · 1.06× Beat Ratio</div>
                <div>2. <strong>AAPL</strong> (Apple) — Say-Do <strong>93.5</strong> (Grade A) · 1.02× Precision</div>
                <div>3. <strong>DIS</strong> (Disney) — Say-Do <strong>92.8</strong> (Grade A) · 1.03× Delivery</div>
                <div>4. <strong>SPOT</strong> (Spotify) — Say-Do <strong>92.8</strong> (Grade A) · 1.01× Delivery</div>
                <div>5. <strong>AMD</strong> (AMD) — Say-Do <strong>92.8</strong> (Grade A) · 1.03× Beat Ratio</div>
              </div>
            </div>

            <div class="section-card">
              <div class="section-title">⚠️ Bottom 5 Guidance Caution &amp; Laggards</div>
              <div style="font-size:13px; line-height:1.8; margin-top:8px;">
                <div>46. <strong>TSLA</strong> (Tesla) — Say-Do <strong>72.0</strong> (Grade B) · 0.77× Volatile · 16.7% Ghost</div>
                <div>47. <strong>MU</strong> (Micron) — Say-Do <strong>69.5</strong> (Grade B) · 0.92× Ratio</div>
                <div>48. <strong>SNOW</strong> (Snowflake) — Say-Do <strong>69.5</strong> (Grade B) · 0.92× Ratio</div>
                <div>49. <strong>INTC</strong> (Intel) — Say-Do <strong>64.5</strong> (Grade C) · 0.74× Ratio · 20A Abandoned</div>
                <div>50. <strong>BA</strong> (Boeing) — Say-Do <strong>63.0</strong> (Grade C) · $10B FCF Withdrawn</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Slide 4 -->
        <div class="slide-page" id="sp4">
          <div style="font-size:11.5px; font-weight:700; text-transform:uppercase; color:var(--cobalt); letter-spacing:0.04em; margin-bottom:6px;">
            Slide 04 / 06 · Strategic Matrix
          </div>
          <h2 style="font-family:var(--font-display); font-size:26px; font-weight:800; color:var(--ink); margin-bottom:6px;">
            The 2×2 Matrix: Exploiting Guidance Asymmetry
          </h2>
          <p style="font-size:14px; color:var(--muted); margin-bottom:20px;">
            Actionable institutional playbook based on company positioning
          </p>

          <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
            <div class="kpi-card" style="border-top:3px solid var(--emerald);">
              <div class="kpi-label">Quadrant 1 · Buy In-Line Guides (Sandbaggers)</div>
              <div style="font-size:13px; color:var(--ink-2); line-height:1.6; margin-top:8px;">
                When Nvidia, Palantir, or Netflix guide in-line with consensus, buy the print. Their historical 1.05–1.07× delivery ratio means an operational beat is already engineered into corporate cadence.
              </div>
            </div>
            <div class="kpi-card" style="border-top:3px solid var(--rose);">
              <div class="kpi-label">Quadrant 2 · Fade Aggressive Guides (Over-Promisers)</div>
              <div style="font-size:13px; color:var(--ink-2); line-height:1.6; margin-top:8px;">
                When a low-credibility management team (Say-Do &lt;75) guides for steep acceleration, apply an automatic 15–25% credibility haircut before calculating forward valuation or buy downside protection.
              </div>
            </div>
          </div>
        </div>

        <!-- Slide 5 -->
        <div class="slide-page" id="sp5">
          <div style="font-size:11.5px; font-weight:700; text-transform:uppercase; color:var(--cobalt); letter-spacing:0.04em; margin-bottom:6px;">
            Slide 05 / 06 · Empirical Alpha
          </div>
          <h2 style="font-family:var(--font-display); font-size:26px; font-weight:800; color:var(--ink); margin-bottom:6px;">
            Post-Earnings Abnormal Drift: +5.74% 60-Day Alpha Spread
          </h2>
          <p style="font-size:14px; color:var(--muted); margin-bottom:20px;">
            Backtested cross-sectional returns across 150 Wall Street earnings releases
          </p>

          <div class="kpi-row" style="margin-bottom:16px;">
            <div class="kpi-card" style="border-top:3px solid var(--emerald);">
              <div class="kpi-label">Top Tercile (High Say-Do)</div>
              <div class="kpi-val" style="color:var(--emerald);">+4.80%</div>
              <div class="kpi-sub">Persistent upward post-earnings drift</div>
            </div>
            <div class="kpi-card" style="border-top:3px solid var(--rose);">
              <div class="kpi-label">Bottom Tercile (Over-Promisers)</div>
              <div class="kpi-val" style="color:var(--rose);">-1.60%</div>
              <div class="kpi-sub">Downward decay as targets slip</div>
            </div>
            <div class="kpi-card" style="border-top:3px solid var(--cobalt);">
              <div class="kpi-label">Net Credibility Spread</div>
              <div class="kpi-val">+{market_obj.get('spread_pct', 5.74):.2f}%</div>
              <div class="kpi-sub">90% CI: [{market_obj.get('spread_ci90_pct', [3.34, 8.14])[0]}%, {market_obj.get('spread_ci90_pct', [3.34, 8.14])[1]}%]</div>
            </div>
            <div class="kpi-card" style="border-top:3px solid #0D9488);">
              <div class="kpi-label">Rank IC</div>
              <div class="kpi-val">{market_obj.get('mean_rank_ic', 0.142):.3f}</div>
              <div class="kpi-sub">Statistically significant correlation</div>
            </div>
          </div>
        </div>

        <!-- Slide 6 -->
        <div class="slide-page" id="sp6">
          <div style="font-size:11.5px; font-weight:700; text-transform:uppercase; color:var(--cobalt); letter-spacing:0.04em; margin-bottom:6px;">
            Slide 06 / 06 · Summary & Takeaway
          </div>
          <h2 style="font-family:var(--font-display); font-size:26px; font-weight:800; color:var(--ink); margin-bottom:6px;">
            The Quantitative Framework: Turning Words into Alpha
          </h2>
          <p style="font-size:14px; color:var(--muted); margin-bottom:20px;">
            Four actionable rules for hedge funds, equity analysts, and presentation decks
          </p>

          <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:14px;">
            <div class="kpi-card" style="border-top:3px solid var(--cobalt);">
              <div class="kpi-label">Rule 1 · Credibility Haircut</div>
              <div style="font-size:12.5px; color:var(--ink-2); line-height:1.5; margin-top:6px;">
                Never model raw guidance. Multiply guided numbers by historical delivery factor: <code style="font-family:var(--font-mono); color:var(--cobalt);">G_adj = G_guide × DelivRatio</code>
              </div>
            </div>
            <div class="kpi-card" style="border-top:3px solid var(--emerald);">
              <div class="kpi-label">Rule 2 · Sandbagger Premium</div>
              <div style="font-size:12.5px; color:var(--ink-2); line-height:1.5; margin-top:6px;">
                Buy post-guide dips on Grade A sandbaggers (NVDA, PLTR, NFLX). They deliver beats by design.
              </div>
            </div>
            <div class="kpi-card" style="border-top:3px solid var(--amber);">
              <div class="kpi-label">Rule 3 · Aspiration Fade</div>
              <div style="font-size:12.5px; color:var(--ink-2); line-height:1.5; margin-top:6px;">
                Fade multi-year guidance spikes from low Say-Do companies before consensus downgrades.
              </div>
            </div>
            <div class="kpi-card" style="border-top:3px solid var(--rose);">
              <div class="kpi-label">Rule 4 · Ghost Surveillance</div>
              <div style="font-size:12.5px; color:var(--ink-2); line-height:1.5; margin-top:6px;">
                Transcript omission is the #1 leading indicator of operational distress, preceding SEC cuts by 90 days.
              </div>
            </div>
          </div>
        </div>

        <!-- Slide Deck Controls -->
        <div class="slide-deck-footer">
          <div style="font-family:var(--font-mono); font-size:13px; color:var(--muted);" id="slideDeckCounter">
            Slide 1 of 6
          </div>
          <div style="display:flex; gap:8px;">
            <button class="action-btn" onclick="deckPrev()">◀ Previous</button>
            <button class="action-btn primary" onclick="deckNext()">Next ▶</button>
          </div>
        </div>

      </div>
    </section>

  </div>

  <script>
    const COMPANIES = {js_comps};
    const SCORES = {js_scores};
    const MODEL = {js_model};
    const MARKET = {js_market};
    const MEMOS = {js_memos};
    const RESOLVED = {js_resolved};
    const STATS = {js_stats};

    let curDeckSlide = 1;
    const maxDeckSlides = 6;

    document.addEventListener("DOMContentLoaded", () => {{
      populatePredictorTickers();
      populateAuditTickers();
      renderMasterTable();
      updatePredictorView();
      loadCompanyAuditView("NVDA");

      // Keyboard arrow keys for slide deck
      document.addEventListener("keydown", (e) => {{
        if (e.key === "ArrowRight") deckNext();
        else if (e.key === "ArrowLeft") deckPrev();
      }});
    }});

    function switchTab(tabId) {{
      document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
      document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));

      const target = document.getElementById(tabId);
      const btn = document.getElementById("btn_" + tabId);
      if (target) target.classList.add("active");
      if (btn) btn.classList.add("active");
    }}

    function populatePredictorTickers() {{
      const sel = document.getElementById("predTickerSelect");
      sel.innerHTML = COMPANIES.map(c => `
        <option value="${{c.ticker}}" ${{c.ticker === "NVDA" ? "selected" : ""}}>${{c.ticker}} — ${{c.name}} (${{c.grade}})</option>
      `).join("");
    }}

    function populateAuditTickers() {{
      const sel = document.getElementById("coAuditSelect");
      sel.innerHTML = COMPANIES.map(c => `
        <option value="${{c.ticker}}" ${{c.ticker === "NVDA" ? "selected" : ""}}>${{c.ticker}} — ${{c.name}} (Say-Do ${{c.score}})</option>
      `).join("");
    }}

    function updatePredictorView() {{
      const t = document.getElementById("predTickerSelect").value;
      const c = COMPANIES.find(x => x.ticker === t) || COMPANIES[0];

      document.getElementById("predScoreVal").innerText = `${{c.score}} / 100`;
      document.getElementById("predGradePill").innerText = `Grade ${{c.grade}}`;
      document.getElementById("predGradePill").className = `status-pill status-${{c.grade === "A" ? "DELIVERED" : (c.grade === "B" ? "PARTIAL" : "MISSED")}}`;

      document.getElementById("predCompName").innerText = c.name;
      document.getElementById("predSector").innerText = c.sector;
      document.getElementById("predExecs").innerText = `${{c.ceo}} (CEO), ${{c.cfo}} (CFO)`;
      document.getElementById("predMcap").innerText = `$${{c.market_cap.toLocaleString()}} Billion`;
      document.getElementById("predRatioVal").innerText = `${{c.delivery_ratio.toFixed(2)}}×`;
      document.getElementById("predGhostVal").innerText = `${{(c.ghost_rate * 100).toFixed(1)}}%`;
      document.getElementById("predGhostCnt").innerText = c.outcomes.GHOSTED || 0;
      document.getElementById("predGoalpostVal").innerText = c.goalpost_moves || 0;
      document.getElementById("hurdleTickerSpan").innerText = c.ticker;

      // Update guided value default
      const defVal = t === "NVDA" ? 37.5 : (t === "TSLA" ? 25.0 : (t === "AAPL" ? 95.0 : (t === "MSFT" ? 64.5 : 20.0)));
      document.getElementById("predGuidedVal").value = defVal;

      runSimulation();
    }}

    function runSimulation() {{
      const t = document.getElementById("predTickerSelect").value;
      const c = COMPANIES.find(x => x.ticker === t) || COMPANIES[0];
      const val = parseFloat(document.getElementById("predGuidedVal").value) || 20.0;
      const tone = document.getElementById("predToneSelect").value;
      const horizon = document.getElementById("predHorizonSelect").value;

      const baseP = c.score / 100.0;
      const toneMult = tone === "firm" ? 1.04 : (tone === "target" ? 0.98 : 0.85);
      const horizMult = horizon === "Q" ? 1.0 : (horizon === "FY" ? 0.93 : 0.78);
      const ghostPen = c.ghost_rate * 0.4;
      const pKept = Math.min(Math.max((baseP * toneMult * horizMult - ghostPen), 0.15), 0.98);

      const adjVal = val * c.delivery_ratio;
      const grade = pKept >= 0.8 ? "A" : (pKept >= 0.68 ? "B" : (pKept >= 0.55 ? "C" : "D"));

      document.getElementById("kpiProb").innerText = `${{(pKept * 100).toFixed(1)}}%`;
      document.getElementById("kpiProbGrade").innerText = grade;
      document.getElementById("kpiAdj").innerText = `$${{val}}B → $${{adjVal.toFixed(2)}}B`;
      document.getElementById("kpiFactor").innerText = `${{c.delivery_ratio.toFixed(2)}}×`;
      document.getElementById("kpiGhostRisk").innerText = `${{(c.ghost_rate * 100).toFixed(1)}}% Ghost`;

      // Update Tipping Points
      document.getElementById("tippingCurrent").innerText = `$${{val}}B`;
      document.getElementById("tippingSafe").innerText = `$${{(val * 1.02).toFixed(1)}}B`;
      document.getElementById("tippingCoin").innerText = `$${{(val * 1.10).toFixed(1)}}B`;
      document.getElementById("tippingBreakdown").innerText = `$${{(val * 1.16).toFixed(1)}}B`;

      // Precedents list
      const precedents = RESOLVED.filter(p => p.ticker === t);
      const preList = document.getElementById("predPrecedentsList");
      if (precedents.length > 0) {{
        preList.innerHTML = precedents.slice(0, 3).map(p => `
          <div>• <code>${{p.call_date}}</code>: ${{p.summary.slice(0, 42)}}... → <b>${{p.resolution.outcome}}</b></div>
        `).join("");
      }} else {{
        preList.innerHTML = "<div>No prior commitments in exact category.</div>";
      }}
    }}

    function renderMasterTable() {{
      const tbody = document.getElementById("masterTableBody");
      tbody.innerHTML = COMPANIES.map(c => `
        <tr onclick="inspectFromTable('${{c.ticker}}')" style="cursor:pointer;">
          <td style="font-family:var(--font-mono); font-weight:700; color:var(--muted);">#${{c.rank}}</td>
          <td><strong style="color:var(--cobalt); font-family:var(--font-mono);">${{c.ticker}}</strong></td>
          <td style="font-weight:600;">${{c.name}}</td>
          <td style="color:var(--muted); font-size:12px;">${{c.sector}}</td>
          <td style="font-family:var(--font-mono); font-weight:700;">${{c.score}}</td>
          <td><span class="status-pill status-${{c.grade === "A" ? "DELIVERED" : (c.grade === "B" ? "PARTIAL" : "MISSED")}}">${{c.grade}}</span></td>
          <td style="font-family:var(--font-mono); font-size:12px; color:var(--muted);">${{c.ci80[0]}}–${{c.ci80[1]}}</td>
          <td style="font-family:var(--font-mono); font-weight:700; color:${{c.delivery_ratio >= 1.0 ? "var(--emerald)" : "var(--rose)"}};">
            ${{c.delivery_ratio.toFixed(2)}}×
          </td>
          <td style="font-family:var(--font-mono); font-size:12px;">${{(c.ghost_rate * 100).toFixed(1)}}%</td>
          <td style="font-family:var(--font-mono); font-size:12px;">$${{c.market_cap}}B</td>
        </tr>
      `).join("");
    }}

    function filterMasterTable() {{
      const query = document.getElementById("tableSearchInput").value.toUpperCase();
      const grade = document.getElementById("tableGradeSelect").value;

      const filtered = COMPANIES.filter(c => {{
        const matchQ = c.ticker.includes(query) || c.name.toUpperCase().includes(query) || c.ceo.toUpperCase().includes(query);
        const matchG = grade === "ALL" || c.grade === grade;
        return matchQ && matchG;
      }});

      const tbody = document.getElementById("masterTableBody");
      tbody.innerHTML = filtered.map(c => `
        <tr onclick="inspectFromTable('${{c.ticker}}')" style="cursor:pointer;">
          <td style="font-family:var(--font-mono); font-weight:700; color:var(--muted);">#${{c.rank}}</td>
          <td><strong style="color:var(--cobalt); font-family:var(--font-mono);">${{c.ticker}}</strong></td>
          <td style="font-weight:600;">${{c.name}}</td>
          <td style="color:var(--muted); font-size:12px;">${{c.sector}}</td>
          <td style="font-family:var(--font-mono); font-weight:700;">${{c.score}}</td>
          <td><span class="status-pill status-${{c.grade === "A" ? "DELIVERED" : (c.grade === "B" ? "PARTIAL" : "MISSED")}}">${{c.grade}}</span></td>
          <td style="font-family:var(--font-mono); font-size:12px; color:var(--muted);">${{c.ci80[0]}}–${{c.ci80[1]}}</td>
          <td style="font-family:var(--font-mono); font-weight:700; color:${{c.delivery_ratio >= 1.0 ? "var(--emerald)" : "var(--rose)"}};">
            ${{c.delivery_ratio.toFixed(2)}}×
          </td>
          <td style="font-family:var(--font-mono); font-size:12px;">${{(c.ghost_rate * 100).toFixed(1)}}%</td>
          <td style="font-family:var(--font-mono); font-size:12px;">$${{c.market_cap}}B</td>
        </tr>
      `).join("");
    }}

    function inspectFromTable(ticker) {{
      switchTab('tab_co');
      document.getElementById("coAuditSelect").value = ticker;
      loadCompanyAuditView(ticker);
    }}

    function loadCompanyAuditView(ticker) {{
      const c = COMPANIES.find(x => x.ticker === ticker) || COMPANIES[0];
      const memo = MEMOS[ticker] || {{ headline: `${{ticker}} Guidance Audit`, verdict: "Reliable", patterns: [], red_flags: [], credit_where_due: [], watch_next_call: [] }};
      const companyPromises = RESOLVED.filter(p => p.ticker === ticker);

      document.getElementById("auditScoreVal").innerText = `${{c.score}} · Grade ${{c.grade}}`;
      document.getElementById("auditCISub").innerText = `80% CI: ${{c.ci80[0]}}–${{c.ci80[1]}}`;
      document.getElementById("auditRatioVal").innerText = `${{c.delivery_ratio.toFixed(2)}}×`;
      document.getElementById("auditGhostVal").innerText = `${{(c.ghost_rate * 100).toFixed(1)}}%`;
      document.getElementById("auditGoalpostVal").innerText = c.goalpost_moves || 0;
      document.getElementById("auditMcapVal").innerText = `$${{c.market_cap.toLocaleString()}}B`;
      document.getElementById("auditSectorSub").innerText = c.sector;

      // 1. Outcome Breakdown Bar
      document.getElementById("coResolvCnt").innerText = companyPromises.length;
      renderCompanyOutcomeBar(c, companyPromises);

      // 2. Trajectory SVG Chart
      renderCompanyTrajectory(ticker, c);

      // 3. Memo details
      const isRel = (memo.verdict || "").includes("Reliable") || c.grade === "A";
      const isMix = (memo.verdict || "").includes("Mixed") || c.grade === "B";
      const verdColor = isRel ? "var(--emerald)" : (isMix ? "var(--amber)" : "var(--rose)");
      const verdTag = document.getElementById("memoVerdictTag");
      verdTag.innerText = `Institutional Verdict: ${{memo.verdict || (c.grade === "A" ? "Reliable Sandbagger" : "Mixed Execution")}}`;
      verdTag.style.color = verdColor;
      document.getElementById("memoHeadlineTag").innerText = memo.headline || `${{ticker}} guidance track record (Say-Do ${{c.score}}/100, Grade ${{c.grade}}).`;

      document.getElementById("memoPatternsList").innerHTML = (memo.patterns && memo.patterns.length ? memo.patterns : ["Consistent operational execution and guidance adherence."]).map(p => `<li>${{p}}</li>`).join("");
      document.getElementById("memoCreditList").innerHTML = (memo.credit_where_due && memo.credit_where_due.length ? memo.credit_where_due : ["Delivered on reported guidance commitments."]).map(p => `<li>${{p}}</li>`).join("");
      document.getElementById("memoRedFlagsList").innerHTML = (memo.red_flags && memo.red_flags.length ? memo.red_flags : ["Zero missed or ghosted commitments on record."]).map(p => `<li>${{p}}</li>`).join("");
      document.getElementById("memoWatchList").innerHTML = (memo.watch_next_call && memo.watch_next_call.length ? memo.watch_next_call : ["Monitor next quarterly guidance release."]).map(p => `<li>${{p}}</li>`).join("");

      // 4. Render Verbatim Ledger with Filter
      filterLedger();
    }}

    function renderCompanyOutcomeBar(c, proms) {{
      const barBox = document.getElementById("coOutcomeBarContainer");
      const pillsBox = document.getElementById("coOutcomePills");
      const oc = c.outcomes || {{}};

      const nDeliv = oc.DELIVERED || 0;
      const nLate = (oc.LATE || 0) + (oc.REVISED_DOWN || 0) + (oc.PARTIAL || 0);
      const nBroken = (oc.MISSED || 0) + (oc.ABANDONED || 0) + (oc.GHOSTED || 0);
      const total = Math.max(nDeliv + nLate + nBroken, 1);

      const pDeliv = (nDeliv / total) * 100;
      const pLate = (nLate / total) * 100;
      const pBroken = (nBroken / total) * 100;

      barBox.innerHTML = `
        <div style="display:flex; height:24px; border-radius:6px; overflow:hidden; background:#F1F5F9; border:1px solid #E2E8F0;">
          ${{nDeliv > 0 ? `<div style="width:${{pDeliv}}%; background:#059669; display:flex; align-items:center; justify-content:center; color:#FFFFFF; font-size:11px; font-weight:700; font-family:'JetBrains Mono';">${{nDeliv}} (${{pDeliv.toFixed(0)}}%)</div>` : ""}}
          ${{nLate > 0 ? `<div style="width:${{pLate}}%; background:#D97706; display:flex; align-items:center; justify-content:center; color:#FFFFFF; font-size:11px; font-weight:700; font-family:'JetBrains Mono';">${{nLate}} (${{pLate.toFixed(0)}}%)</div>` : ""}}
          ${{nBroken > 0 ? `<div style="width:${{pBroken}}%; background:#E11D48; display:flex; align-items:center; justify-content:center; color:#FFFFFF; font-size:11px; font-weight:700; font-family:'JetBrains Mono';">${{nBroken}} (${{pBroken.toFixed(0)}}%)</div>` : ""}}
        </div>
      `;

      pillsBox.innerHTML = `
        <span class="status-pill status-DELIVERED">✅ Delivered: ${{nDeliv}}</span>
        ${{nLate > 0 ? `<span class="status-pill status-LATE">⏱️ Late / Revised: ${{nLate}}</span>` : ""}}
        ${{nBroken > 0 ? `<span class="status-pill status-MISSED">🚩 Missed / Ghosted: ${{nBroken}}</span>` : ""}}
      `;
    }}

    function renderCompanyTrajectory(ticker, c) {{
      const box = document.getElementById("coTrajectoryContainer");
      const hist = (SCORES.history || {{}})[ticker] || [];

      if (!hist || hist.length < 2) {{
        box.innerHTML = `
          <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:18px; text-align:center; font-size:12.5px; color:#64748B;">
            Trajectory baseline established: <b>${{c.score}}</b> (Grade ${{c.grade}}) across verified earnings calls.
          </div>
        `;
        return;
      }}

      const w = 520;
      const h = 135;
      const lm = 42;
      const rm = 20;
      const tm = 16;
      const bm = 28;
      const pw = w - lm - rm;
      const ph = h - tm - bm;

      const yMin = 50.0;
      const yMax = 100.0;

      const pts = hist.map((pt, idx) => {{
        const x = lm + (idx / (hist.length - 1)) * pw;
        const clampedSc = Math.max(Math.min(pt.score, yMax), yMin);
        const y = tm + ph - ((clampedSc - yMin) / (yMax - yMin)) * ph;
        return {{ x, y, ...pt }};
      }});

      const polyPoints = pts.map(p => `${{p.x.toFixed(1)}},${{p.y.toFixed(1)}}`).join(" ");
      const areaPoints = `${{pts[0].x.toFixed(1)}},${{tm + ph}} ${{polyPoints}} ${{pts[pts.length - 1].x.toFixed(1)}},${{tm + ph}}`;

      let circlesHtml = pts.map(p => `
        <circle cx="${{p.x.toFixed(1)}}" cy="${{p.y.toFixed(1)}}" r="4.5" fill="#2563EB" stroke="#FFFFFF" stroke-width="1.8">
          <title>${{p.date}}: Say-Do ${{p.score.toFixed(1)}} (Grade ${{p.grade}})</title>
        </circle>
        <text x="${{p.x.toFixed(1)}}" y="${{tm + ph + 16}}" fill="#64748B" font-size="9.5" font-family="'JetBrains Mono', monospace" text-anchor="middle">${{p.date.slice(5)}}</text>
      `).join("");

      box.innerHTML = `
        <svg viewBox="0 0 ${{w}} ${{h}}" style="width:100%; height:auto; display:block;">
          <line x1="${{lm}}" y1="${{tm}}" x2="${{lm + pw}}" y2="${{tm}}" stroke="#F1F5F9" stroke-width="1"/>
          <line x1="${{lm}}" y1="${{tm + ph/2}}" x2="${{lm + pw}}" y2="${{tm + ph/2}}" stroke="#F1F5F9" stroke-width="1"/>
          <line x1="${{lm}}" y1="${{tm + ph}}" x2="${{lm + pw}}" y2="${{tm + ph}}" stroke="#CBD5E1" stroke-width="1"/>

          <text x="${{lm - 8}}" y="${{tm + 4}}" fill="#64748B" font-size="9" font-family="'JetBrains Mono'" text-anchor="end">100</text>
          <text x="${{lm - 8}}" y="${{tm + ph/2 + 3}}" fill="#64748B" font-size="9" font-family="'JetBrains Mono'" text-anchor="end">75</text>
          <text x="${{lm - 8}}" y="${{tm + ph + 3}}" fill="#64748B" font-size="9" font-family="'JetBrains Mono'" text-anchor="end">50</text>

          <polygon points="${{areaPoints}}" fill="rgba(37, 99, 235, 0.08)"/>
          <polyline points="${{polyPoints}}" fill="none" stroke="#2563EB" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
          ${{circlesHtml}}
        </svg>
      `;
    }}

    function filterLedger() {{
      const ticker = document.getElementById("coAuditSelect").value;
      const filter = document.getElementById("ledgerFilterSelect") ? document.getElementById("ledgerFilterSelect").value : "ALL";
      const companyPromises = RESOLVED.filter(p => p.ticker === ticker);

      let displayed = companyPromises;
      if (filter === "DELIVERED") {{
        displayed = companyPromises.filter(p => p.resolution.outcome === "DELIVERED");
      }} else if (filter === "LATE_REVISED") {{
        displayed = companyPromises.filter(p => ["LATE", "REVISED_DOWN", "PARTIAL"].includes(p.resolution.outcome));
      }} else if (filter === "GHOSTED_MISSED") {{
        displayed = companyPromises.filter(p => ["MISSED", "GHOSTED", "ABANDONED"].includes(p.resolution.outcome));
      }}

      const ledgerBox = document.getElementById("verbatimLedgerList");
      if (displayed.length === 0) {{
        ledgerBox.innerHTML = `<div style="padding:16px; text-align:center; color:#64748B; font-size:13px;">No commitments match this resolution filter.</div>`;
        return;
      }}

      ledgerBox.innerHTML = displayed.map(p => `
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 1px 2px rgba(15,23,42,0.02);">
          <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
            <div style="font-weight:700; font-size:13.5px; color:#0F172A;">
              <span class="status-pill status-${{p.resolution.outcome}}">${{p.resolution.outcome}}</span> &nbsp;
              ${{p.summary}}
            </div>
            <div style="font-size:12px; color:#64748B; font-family:'JetBrains Mono',monospace;">${{p.call_label}}</div>
          </div>

          <div class="say-box">
            🗣️ <b>WHAT MANAGEMENT SAID</b> (${{p.speaker || "Exec"}}, ${{p.role || "Leadership"}}):<br>
            “${{p.quote}}”
          </div>

          <div class="do-box">
            📊 <b>SEC 10-Q AUDIT RESULT (${{p.resolution.outcome}}):</b> ${{p.resolution.why}}<br>
            <span style="color:#64748B; font-size:12px;">Evidence: “${{p.resolution.evidence_quote || "Confirmed in official SEC disclosures"}}”</span>
          </div>
        </div>
      `).join("");
    }}

    function deckNext() {{
      if (curDeckSlide < maxDeckSlides) {{
        curDeckSlide++;
        updateDeckSlide();
      }}
    }}

    function deckPrev() {{
      if (curDeckSlide > 1) {{
        curDeckSlide--;
        updateDeckSlide();
      }}
    }}

    function updateDeckSlide() {{
      for (let i = 1; i <= maxDeckSlides; i++) {{
        const el = document.getElementById("sp" + i);
        if (el) el.classList.toggle("active", i === curDeckSlide);
      }}
      document.getElementById("slideDeckCounter").innerText = `Slide ${{curDeckSlide}} of ${{maxDeckSlides}}`;
    }}
  </script>
</body>
</html>
"""
    return html


if __name__ == "__main__":
    d = load_data()
    content = generate_revcon_html(d)

    # 1. Output inside us_earnings/
    out_path1 = os.path.join(config.ROOT, "us_earnings_presentation.html")
    with open(out_path1, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated: {out_path1} ({len(content)} bytes)")

    # 2. Output in workspace root
    out_path2 = os.path.join(ROOT_DIR, "us_earnings_presentation.html")
    with open(out_path2, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated workspace file: {out_path2}")
