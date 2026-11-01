"""SAY: extract every forward-looking management commitment from a call, with Meta Muse / Gemini.

Anti-hallucination: every promise must carry a verbatim quote that is verified against the
transcript text; unverifiable promises are dropped and counted (reported in the README).
"""
import concurrent.futures as cf
import re

from . import config, llm, periods, transcripts

CATEGORIES = {
    # checkable from reported P&L ("financials")
    "revenue_growth", "revenue_target", "ebitda_margin", "pat_margin", "pat_growth", "ebitda_growth",
    # need later disclosure ("disclosure")
    "order_book", "order_inflow", "capex", "capacity", "commissioning", "product_launch",
    "customer_win", "debt", "market_share", "expansion", "cost_saving", "other",
}
FINANCIAL = {"revenue_growth", "revenue_target", "ebitda_margin", "pat_margin", "pat_growth", "ebitda_growth"}
STRENGTH_W = {"firm": 1.0, "target": 0.85, "aspirational": 0.6, "hedged": 0.6}

_BPS_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?)\s*)?(?:bps|basis\s+points?)\b", re.I)
_DELTA_MARGIN_RE = re.compile(r"\b(bps|basis\s+points?|expansion|improve\s+by|improvement\s+of|add(?:ition)?\s+to\s+ebitda)\b", re.I)

SYSTEM = """You are a forensic equity analyst auditing whether company management keeps its word.
From an Indian listed company's earnings-call transcript, extract EVERY forward-looking commitment
made by MANAGEMENT (company executives only; never analysts, moderators or investors).

INCLUDE anything a later call or the reported financials could prove kept or broken:
- numeric guidance: revenue/topline growth, revenue target, EBITDA/operating margin, PAT margin,
  PAT/EBITDA growth, order inflow, order book, capex amount, debt reduction, cost savings
- operational milestones with any timeframe: plant/line commissioning, capacity additions,
  product launches, regulatory approvals, store/branch/hospital openings, customer ramp-ups, exits
- strategic commitments: "net-debt free by FY27", "double revenue in 3 years", market-share targets

EXCLUDE: past or current-quarter results, analyst statements, vague optimism with nothing
verifiable ("we are excited about the opportunity"), safe-harbour boilerplate, industry/market
forecasts not about this company's own numbers, and pure repetition of the same promise
(extract it once, using the clearest quote).
Also EXCLUDE casual conversational commentary/estimates in Q&A (e.g. rough customer concentration
estimates like "top 5 roughly 80%", conversational cost mix remarks like "material mix should be similar",
rhetorical remarks like "that will sort of correct within a quarter, right", and routine accounting line-item
clarifications like "ECL provision is a one-off and will correct next quarter"). Guidance must be a concrete,
deliberate business commitment, forward target, or capital project timeline announced by management.

Return a JSON object {"promises": [ ... ]}; each element:
{
 "quote": "EXACT verbatim copy from the transcript, 1-3 sentences, character for character",
 "speaker": "name as printed", "role": "CEO|CFO|MD|Chairman|Founder|BusinessHead|IR|Other",
 "category": one of [revenue_growth, revenue_target, ebitda_margin, pat_margin, pat_growth,
   ebitda_growth, order_book, order_inflow, capex, capacity, commissioning, product_launch,
   customer_win, debt, market_share, expansion, cost_saving, other],
 "summary": "one plain-English line: what exactly was promised, by when",
 "value_low": number or null, "value_high": number or null,
 "unit": "%|crore|bn_usd|mn_usd|x|units|null",
 "direction": "at_least|at_most|approx|range|null",
 "growth_basis": "yoy|qoq|cagr|delta_pp|null",
 "segment": "company|<segment name if the promise is about one segment only>",
 "period": "FY27 | Q3FY26 | H2FY26 | FY25-FY28 | 2026-03 | null (no timeframe)",
 "strength": "firm|target|aspirational|hedged",
 "conditions": "explicit conditions/caveats or null",
 "reiteration": true if management says it is maintaining/reiterating earlier guidance, else false,
 "verifiable_by": "financials|disclosure"
}
Rules:
- Percent values as numbers (25 not 0.25). Ranges "15-16%" -> low 15, high 16, direction range.
  "25%+" -> low 25, direction at_least. Single point "~20%" -> low=high=20, direction approx.
- For margin expansion in basis points (e.g. "100 bps margin expansion"), convert to percentage points
  (value_low: 1.0, unit: "%", growth_basis: "delta_pp").
- Rupee amounts in crore (1,000 crore -> 1000). Do not convert currencies; keep USD as bn_usd/mn_usd.
- strength: firm = "we will/guidance is/confident of"; target = "targeting/aim/plan";
  aspirational = "aspire/hope/endeavour/should be able to"; hedged = explicitly conditional.
- verifiable_by "financials" ONLY for company-level revenue, margin, PAT or EBITDA numbers.
- Resolve relative periods with the calendar given in the user message. Use the MOST SPECIFIC
  timeframe stated: "by December 2025" -> "2025-12" (not H2FY26); "in Q3" -> that quarter.
- If there are no commitments, return {"promises": []}."""


def _calendar(call):
    cur_fy = periods.fy_of(call.date)
    fy, q = periods.quarter_of(call.date)
    nfy, nq = (fy, q + 1) if q < 4 else (fy + 1, 1)
    return (f"Call date: {call.date:%d %B %Y}. Results discussed: Q{call.q}FY{call.fy % 100:02d}. "
            f"Indian fiscal year ends 31 March. 'This year'/'current year' = FY{cur_fy % 100:02d}; "
            f"'next year' = FY{(cur_fy + 1) % 100:02d}; 'this quarter' = Q{q}FY{fy % 100:02d}; "
            f"'next quarter' = Q{nq}FY{nfy % 100:02d}; 'second half' = H2FY{cur_fy % 100:02d}.")


def _clean(p, call, chunk_idx):
    if not isinstance(p, dict) or not p.get("quote"):
        return None
    cat = str(p.get("category", "other")).strip().lower()
    p["category"] = cat if cat in CATEGORIES else "other"
    p["strength"] = p.get("strength") if p.get("strength") in STRENGTH_W else "target"
    for k in ("value_low", "value_high"):
        try:
            p[k] = float(p[k]) if p.get(k) is not None else None
        except (TypeError, ValueError):
            p[k] = None
    if p["value_low"] is None and p["value_high"] is not None:
        p["value_low"] = p["value_high"]
    if p["value_high"] is None and p["value_low"] is not None:
        p["value_high"] = p["value_low"]

    # Normalize basis-point (bps) margin expansion deltas into percentage points
    txt_combined = f"{p.get('summary') or ''} {p.get('quote') or ''}"
    if p["category"] in ("ebitda_margin", "pat_margin") and p["value_low"] is not None:
        if _DELTA_MARGIN_RE.search(txt_combined):
            if p["value_low"] >= 15.0 and _BPS_RE.search(txt_combined):
                p["value_low"] = round(p["value_low"] / 100.0, 2)
                p["value_high"] = round((p["value_high"] or p["value_low"]) / 100.0, 2)
                p["unit"] = "%"
                p["growth_basis"] = "delta_pp"
            elif p["value_low"] <= 4.0:
                p["growth_basis"] = "delta_pp"

    seg = str(p.get("segment") or "company").strip()
    p["segment"] = "company" if seg.lower() in ("", "company", "overall", "consolidated", "null") else seg
    if (p.get("verifiable_by") != "financials"
            or p["category"] not in FINANCIAL
            or p["segment"] != "company"
            or (p["category"] == "revenue_growth" and str(p.get("unit") or "").lower() == "x")):
        p["verifiable_by"] = "disclosure"

    per = periods.parse_period(p.get("period"), call.date)
    if not per:
        inferred = periods.infer_period_from_text(txt_combined, call.date)
        if inferred:
            per = periods.parse_period(inferred, call.date)
            if per and not p.get("period"):
                p["period"] = inferred

    p["deadline"] = per["end"].isoformat() if per else None
    p["report_by"] = per["report_by"].isoformat() if per else None
    p["period_kind"] = per["kind"] if per else None
    p["horizon_months"] = round(periods.months_between(call.date, per["end"]), 1) if per else None
    if per and per["end"] < call.date:
        return None  # backward-looking: not a promise
    p["ticker"], p["call_id"], p["call_date"] = call.ticker, call.id, call.date.isoformat()
    p["call_label"], p["chunk"] = call.label, chunk_idx
    p["section"] = call.section_of(p["quote"])
    return p


def extract_call(call, model=None):
    """All verified promises from one call (+ stats on dropped hallucinations)."""
    found, dropped = [], 0
    chunks = call.chunks()
    for i, ch in enumerate(chunks):
        if model == config.STUDENT_MODEL:   # fine-tuned Llama: same prompt format it was trained on
            from .finetune_data import STUDENT_SYSTEM
            system, user = STUDENT_SYSTEM, f"Company: {call.ticker}. {_calendar(call)}\n<<<\n{ch}\n>>>"
        else:
            system = SYSTEM
            user = (f"Company: {call.ticker}. {_calendar(call)}\n"
                    f"Transcript part {i + 1} of {len(chunks)}:\n<<<\n{ch}\n>>>")
        out = llm.chat_json(system, user, model=model or config.EXTRACT_MODEL, max_tokens=12000)
        items = (out or {}).get("promises", []) if isinstance(out, dict) else (out or [])
        for p in items:
            if not isinstance(p, dict):
                continue
            v = transcripts.verify_quote(p.get("quote", ""), call.text_norm)
            if not v:
                dropped += 1
                continue
            p["quote_check"] = v
            c = _clean(p, call, i)
            if c:
                found.append(c)
    # De-duplicate promises repeated across overlapping chunks
    uniq, seen = [], set()
    for p in found:
        k1 = transcripts.norm(p["quote"])[:60]
        k2 = (p["category"], p.get("period"), p.get("value_low"), p.get("segment"))
        if k1 in seen or (p.get("value_low") is not None and k2 in seen):
            continue
        seen.update({k1, k2} if p.get("value_low") is not None else {k1})
        uniq.append(p)
    for j, p in enumerate(uniq):
        p["id"] = f"{call.id}#{j}"
    return {"call_id": call.id, "promises": uniq, "dropped_unverified": dropped}


def extract_all(calls_by_ticker, workers=None):
    calls = [c for cs in calls_by_ticker.values() for c in cs]
    results = {}
    with cf.ThreadPoolExecutor(workers or config.CONCURRENCY) as ex:
        futs = {ex.submit(extract_call, c): c for c in calls}
        for n, f in enumerate(cf.as_completed(futs), 1):
            c = futs[f]
            try:
                results[c.id] = f.result()
            except Exception as e:
                print(f"   [extract] {c.id} failed: {e}")
                continue
            r = results[c.id]
            print(f"   [{n}/{len(calls)}] {c.id}: {len(r['promises'])} promises "
                  f"({r['dropped_unverified']} unverifiable dropped)", flush=True)
    return results
