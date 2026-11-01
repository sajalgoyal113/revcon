"""The Say-Do Score: a point-in-time, uncertainty-aware management credibility score.

score = 100 x posterior mean of a Beta-Binomial delivery rate, where each resolved promise
contributes its delivery credit y in [0,1] weighted by how firm and specific it was.
Prior = universe base rate with KAPPA pseudo-promises, so a company with two kept promises
cannot look as credible as one with thirty. The 80% credible interval is reported alongside.
"""
from datetime import date

import numpy as np

from .extract import FINANCIAL, STRENGTH_W

KAPPA = 6.0
GRADES = [(80, "A"), (68, "B"), (55, "C"), (42, "D"), (0, "F")]


def weight(p):
    w = STRENGTH_W.get(p.get("strength"), 0.8)
    specific = p.get("value_low") is not None or p.get("deadline") is not None
    return w * (1.0 if specific else 0.7) / (max(1, p.get("cluster_size", 1)) ** 0.5)


def scored(resolved, asof=None, ticker=None):
    """Resolved promises whose outcome was knowable on `asof` (point-in-time filter)."""
    out = []
    for p in resolved:
        r = p["resolution"]
        if r.get("y") is None or (ticker and p["ticker"] != ticker):
            continue
        if asof is not None and (not r.get("knowable_at") or date.fromisoformat(r["knowable_at"]) > asof):
            continue
        out.append(p)
    return out


def base_rate(resolved, asof=None):
    s = scored(resolved, asof)
    if not s:
        return 0.6
    w = np.array([weight(p) for p in s])
    y = np.array([p["resolution"]["y"] for p in s])
    raw = float((w * y).sum() / w.sum())
    return float(np.clip(raw, 0.05, 0.95))


def beta_score(items, prior):
    prior = float(np.clip(prior, 0.05, 0.95))
    a0, b0 = prior * KAPPA, (1 - prior) * KAPPA
    w = np.array([weight(p) for p in items]) if items else np.zeros(0)
    y = np.array([p["resolution"]["y"] for p in items]) if items else np.zeros(0)
    a, b = max(0.01, a0 + (w * y).sum()), max(0.01, b0 + (w * (1 - y)).sum())
    rng = np.random.default_rng(0)
    draws = rng.beta(a, b, 20000)
    return {"score": round(100 * a / (a + b), 1), "ci80": [round(100 * float(np.quantile(draws, 0.1)), 1),
                                                            round(100 * float(np.quantile(draws, 0.9)), 1)],
            "n": len(items), "effective_n": round(float(w.sum()), 1)}


def grade(s):
    return next(g for cut, g in GRADES if s >= cut)


def company_score(resolved, ticker, asof=None, prior=None):
    prior = base_rate(resolved, asof) if prior is None else prior
    mine = scored(resolved, asof, ticker)
    allp = [p for p in resolved if p["ticker"] == ticker and
            (asof is None or date.fromisoformat(p["call_date"]) <= asof)]
    res = beta_score(mine, prior)
    fin = [p for p in mine if p["category"] in FINANCIAL and p["verifiable_by"] == "financials"]
    ops = [p for p in mine if p not in fin]
    outcomes = {}
    for p in mine:
        outcomes[p["resolution"]["outcome"]] = outcomes.get(p["resolution"]["outcome"], 0) + 1
    ratios = [p["resolution"]["ratio"] for p in fin
              if p["category"] in ("revenue_growth", "revenue_target")
              and str(p.get("unit") or "").lower() != "x"
              and p["resolution"].get("ratio") is not None
              and 0.35 <= p["resolution"]["ratio"] <= 1.8]
    reps = [p for p in allp if p.get("repeat_index", 0) == 0]
    revisions = sum(1 for p in reps if p["resolution"].get("revisions", 0) > 0)
    hedged = sum(1 for p in allp if p.get("strength") in ("hedged", "aspirational"))
    res.update({
        "ticker": ticker, "grade": grade(res["score"]),
        "financial": beta_score(fin, prior) if fin else None,
        "operational": beta_score(ops, prior) if ops else None,
        "outcomes": outcomes,
        "promises_made": len(allp),
        "pending": sum(1 for p in allp if p["resolution"].get("y") is None),
        "ghost_rate": round(outcomes.get("GHOSTED", 0) / len(mine), 3) if mine else None,
        "goalpost_moves": revisions,
        "goalpost_rate": round(revisions / len(reps), 3) if reps else None,
        "hedge_ratio": round(hedged / len(allp), 3) if allp else None,
        # Median delivered/guided on revenue promises -> used to haircut new guidance
        "revenue_delivery_ratio": round(float(np.median(ratios)), 3) if ratios else None,
        "revenue_ratio_n": len(ratios),
    })
    return res


def credibility_adjusted(guided_value, company, universe_ratio=0.9, k=3.0):
    """Haircut a new revenue/growth guide by the company's history, shrunk to the universe."""
    r, n = company.get("revenue_delivery_ratio"), company.get("revenue_ratio_n", 0)
    blended = universe_ratio if r is None else (n * min(r, 1.15) + k * universe_ratio) / (n + k)
    return round(guided_value * blended, 2), round(blended, 3)


def leaderboard(resolved, tickers, asof=None):
    prior = base_rate(resolved, asof)
    rows = [company_score(resolved, t, asof, prior) for t in tickers]
    rows.sort(key=lambda r: -r["score"])
    return {"asof": (asof or date.today()).isoformat(), "base_rate": round(100 * prior, 1), "companies": rows}
