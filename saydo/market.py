"""Does the market price management credibility? Two point-in-time tests.

1. Cross-sectional: at each earnings call, the company's Say-Do score (outcomes knowable
   before that day only) vs its excess return over the next 90 days (vs the equal-weighted
   universe). Reported as mean rank IC per quarter + tercile spread, with a company-level
   bootstrap CI.
2. Event study: when a broken promise becomes public (knowable_at), the 60-day excess return
   that follows, versus when a kept promise becomes public.

Small universe (36 names, ~2 years) -> wide intervals. We report them; we do not hide them.
"""
from datetime import date, timedelta

import numpy as np

from . import financials, score

HOLD = 90
ENTRY_LAG = 2


def _ret(act, d0, days):
    p0, p1 = act.price_on(d0), act.price_on(d0 + timedelta(days=days))
    last = act.snap.get("prices", [])
    if not p0 or not p1 or not last or date.fromisoformat(last[-1][0]) < d0 + timedelta(days=days):
        return None
    return p1 / p0 - 1


def _universe_ret(acts, d0, days):
    rs = [r for r in (_ret(a, d0, days) for a in acts.values()) if r is not None]
    return float(np.mean(rs)) if rs else None


def _rankdata(a):
    """Tie-averaged ranks (1-indexed)."""
    arr = np.asarray(a, dtype=float)
    order = np.argsort(arr)
    ranks = np.empty(len(arr), dtype=float)
    i = 0
    while i < len(arr):
        j = i
        while j + 1 < len(arr) and arr[order[j + 1]] == arr[order[i]]:
            j += 1
        avg_rank = 0.5 * (i + j) + 1.0
        ranks[order[i:j + 1]] = avg_rank
        i = j + 1
    return ranks


def _spearman(a, b):
    ra, rb = _rankdata(a), _rankdata(b)
    if np.std(ra) == 0 or np.std(rb) == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def cross_section(resolved, calls_by_ticker, snaps, min_n=3):
    acts = {t: financials.Actuals(s) for t, s in snaps.items() if s and s.get("prices")}
    rows = []
    for t, calls in calls_by_ticker.items():
        if t not in acts:
            continue
        for c in calls:
            cs = score.company_score(resolved, t, c.date)
            if cs["n"] < min_n:
                continue
            d0 = c.date + timedelta(days=ENTRY_LAG)
            r, u = _ret(acts[t], d0, HOLD), _universe_ret(acts, d0, HOLD)
            if r is None or u is None:
                continue
            fy, q = c.fy, c.q
            rows.append({"ticker": t, "date": c.date.isoformat(), "bucket": f"{fy}Q{q}",
                         "score": cs["score"], "n": cs["n"], "excess": r - u})
    if len(rows) < 15:
        return {"events": len(rows), "note": "too few scored events yet"}
    ics = []
    for b in sorted({r["bucket"] for r in rows}):
        g = [r for r in rows if r["bucket"] == b]
        if len(g) >= 5:
            ic = _spearman([r["score"] for r in g], [r["excess"] for r in g])
            if ic is not None:
                ics.append({"bucket": b, "n": len(g), "ic": round(ic, 3)})
    s = np.array([r["score"] for r in rows])
    e = np.array([r["excess"] for r in rows])
    lo, hi = np.quantile(s, 1 / 3), np.quantile(s, 2 / 3)
    top, bot = e[s >= hi], e[s <= lo]
    # company-clustered bootstrap of the tercile spread
    tick = np.array([r["ticker"] for r in rows])
    names = np.unique(tick)
    rng = np.random.default_rng(7)
    spreads = []
    for _ in range(2000):
        pick = rng.choice(names, len(names))
        idx = np.concatenate([np.where(tick == n)[0] for n in pick])
        ss, ee = s[idx], e[idx]
        t_, b_ = ee[ss >= hi], ee[ss <= lo]
        if len(t_) and len(b_):
            spreads.append(t_.mean() - b_.mean())
    return {
        "events": len(rows), "companies": int(len(names)), "hold_days": HOLD,
        "mean_ic": round(float(np.mean([x["ic"] for x in ics])), 3) if ics else None,
        "ic_by_quarter": ics,
        "top_tercile_excess": round(float(top.mean()) * 100, 2),
        "bottom_tercile_excess": round(float(bot.mean()) * 100, 2),
        "spread_pct": round(float(top.mean() - bot.mean()) * 100, 2),
        "spread_ci90_pct": [round(float(np.quantile(spreads, 0.05)) * 100, 2),
                            round(float(np.quantile(spreads, 0.95)) * 100, 2)] if spreads else None,
        "rows": rows,
    }


def event_study(resolved, snaps, days=60):
    acts = {t: financials.Actuals(s) for t, s in snaps.items() if s and s.get("prices")}
    kept, broken = [], []
    seen = set()
    for p in resolved:
        r = p["resolution"]
        if r.get("y") is None or not r.get("knowable_at") or p["ticker"] not in acts:
            continue
        key = (p["ticker"], r["knowable_at"], r["y"] >= 0.75)
        if key in seen:      # one event per company/date/sign
            continue
        seen.add(key)
        d0 = date.fromisoformat(r["knowable_at"]) + timedelta(days=ENTRY_LAG)
        x, u = _ret(acts[p["ticker"]], d0, days), _universe_ret(acts, d0, days)
        if x is None or u is None:
            continue
        (kept if r["y"] >= 0.75 else broken).append(x - u)
    if not kept or not broken:
        return {"note": "insufficient events"}
    diff = np.mean(kept) - np.mean(broken)
    rng = np.random.default_rng(3)
    boot = [rng.choice(kept, len(kept)).mean() - rng.choice(broken, len(broken)).mean() for _ in range(2000)]
    return {"days": days, "kept_events": len(kept), "broken_events": len(broken),
            "kept_excess_pct": round(float(np.mean(kept)) * 100, 2),
            "broken_excess_pct": round(float(np.mean(broken)) * 100, 2),
            "diff_pct": round(float(diff) * 100, 2),
            "diff_ci90_pct": [round(float(np.quantile(boot, 0.05)) * 100, 2),
                              round(float(np.quantile(boot, 0.95)) * 100, 2)]}
