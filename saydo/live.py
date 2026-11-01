"""Live mode: a NEW call (text, or audio via muse-voice-transcribe / Gemini) -> scored promises.

For each new promise: P(kept) from the predictor, plus a credibility-adjusted number for
revenue guidance (guided x the company's historical delivery ratio, shrunk to the universe).
"""
import hashlib
import json
import os
from datetime import date, timedelta

from . import config, extract, financials, forecast, history, llm, predict, score, transcripts


def _load(name):
    p = os.path.join(config.OUT, name)
    return json.load(open(p)) if os.path.exists(p) else None


def analyze(ticker, text, call_date=None, audio_path=None, use_student=False):
    ticker = ticker.upper().strip()
    call_date = call_date or date.today()
    if audio_path and not text:
        text = llm.transcribe(audio_path)
    if not text or len(text) < 500:
        raise ValueError("Need a transcript (>500 chars) or an audio file.")
    fy, q = transcripts.periods.last_reported_quarter(call_date)
    call = transcripts.Call(ticker, f"live:{hashlib.md5(text.encode()).hexdigest()[:8]}", text, call_date, (fy, q))
    ex = extract.extract_call(call, model=config.STUDENT_MODEL if use_student else None)

    resolved = _load("resolved.json") or []
    model = _load("model.json")
    snap = financials.fetch(ticker)
    act = financials.Actuals(snap) if snap else None
    prior = score.base_rate(resolved)
    company = score.company_score(resolved, ticker, None, prior)
    universe_ratio = _universe_ratio(resolved)
    fc = forecast.forecast_all(ex["promises"], {ticker: snap} if snap else {}) if ex["promises"] else {}

    cut = call_date - timedelta(days=1)
    rows = []
    for p in ex["promises"]:
        hist = history.history_features(resolved, ticker, cut, category=p.get("category"))
        ctx = {"hist": hist, "promises_in_call": len(ex["promises"]), "actuals": act, "muse_p": fc.get(p["id"])}
        prob = predict.score_new(model, p, ctx) if model else None
        adj = None
        unit_ok = (p["category"] == "revenue_growth" and p.get("unit") == "%") or \
                  (p["category"] == "revenue_target" and (p.get("unit") or "").lower() in ("crore", "cr"))
        if unit_ok and p.get("value_low") is not None:
            v, f = score.credibility_adjusted(p["value_low"], company, universe_ratio)
            adj = {"guided": p["value_low"], "adjusted": v, "factor": f, "unit": p.get("unit")}
        rows.append({**p, "p_kept": round(prob, 3) if prob is not None else None,
                     "muse_p": fc.get(p["id"]), "credibility_adjusted": adj})
    rows.sort(key=lambda r: (r["p_kept"] is None, r["p_kept"] or 0))
    return {"ticker": ticker, "call": call.label, "company": company, "promises": rows,
            "dropped_unverified": ex["dropped_unverified"],
            "open_from_before": [p for p in resolved if p["ticker"] == ticker and p["resolution"]["outcome"] == "PENDING"]}


def _universe_ratio(resolved):
    import numpy as np
    r = [p["resolution"]["ratio"] for p in resolved
         if p["category"] in ("revenue_growth", "revenue_target")
         and str(p.get("unit") or "").lower() != "x"
         and p["resolution"].get("ratio") is not None
         and 0.35 <= p["resolution"]["ratio"] <= 1.8]
    return float(np.clip(np.median(r), 0.5, 1.1)) if r else 0.95
