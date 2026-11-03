"""The Say-Do Credibility Scoring Engine for US Equities.

Applies point-in-time, uncertainty-aware Beta-Binomial Bayesian credibility scoring:
    score = 100 x posterior mean of delivery rate
    prior = universe base rate with KAPPA pseudo-promises
    computes 80% credible interval via Monte Carlo posterior draws.
Also measures revenue delivery ratio (sandbagging vs over-promising), ghost rate,
and goalpost moving frequency.
"""
from datetime import date
import numpy as np

KAPPA = 6.0
GRADES = [(80, "A"), (68, "B"), (55, "C"), (42, "D"), (0, "F")]
FINANCIAL_CATEGORIES = {
    "revenue_growth", "revenue_target", "eps_guidance", "operating_margin",
    "gross_margin", "fcf_guidance", "capex_guidance"
}
STRENGTH_WEIGHTS = {
    "firm": 1.0,
    "target": 0.85,
    "approx": 0.75,
    "hedged": 0.50,
    "aspirational": 0.40,
}


def weight_promise(p):
    """Calculates specific weight of a guidance promise."""
    w = STRENGTH_WEIGHTS.get(p.get("strength"), 0.8)
    specific = p.get("value_low") is not None or p.get("deadline") is not None
    # Cluster shrinkage to avoid double counting repeated guidance
    cluster_scale = max(1, p.get("cluster_size", 1)) ** 0.5
    return w * (1.0 if specific else 0.7) / cluster_scale


def get_scored_promises(resolved, asof=None, ticker=None):
    """Filter resolved promises knowable on `asof` date."""
    out = []
    for p in resolved:
        r = p.get("resolution", {})
        if r.get("y") is None or (ticker and p.get("ticker") != ticker):
            continue
        if asof is not None:
            k_date = r.get("knowable_at")
            if not k_date or date.fromisoformat(k_date) > asof:
                continue
        out.append(p)
    return out


def calculate_base_rate(resolved, asof=None):
    """Calculates universe-wide base rate of weighted delivery credit."""
    s = get_scored_promises(resolved, asof)
    if not s:
        return 0.75
    w = np.array([weight_promise(p) for p in s])
    y = np.array([p["resolution"]["y"] for p in s])
    if w.sum() == 0:
        return 0.75
    raw = float((w * y).sum() / w.sum())
    return float(np.clip(raw, 0.10, 0.95))


def beta_score(items, prior):
    """Computes Bayesian Beta-Binomial posterior mean and 80% credible interval."""
    prior = float(np.clip(prior, 0.05, 0.95))
    a0 = prior * KAPPA
    b0 = (1 - prior) * KAPPA

    if items:
        w = np.array([weight_promise(p) for p in items])
        y = np.array([p["resolution"]["y"] for p in items])
        a = max(0.01, a0 + (w * y).sum())
        b = max(0.01, b0 + (w * (1 - y)).sum())
    else:
        w = np.zeros(0)
        y = np.zeros(0)
        a, b = a0, b0

    rng = np.random.default_rng(42)
    draws = rng.beta(a, b, 20000)
    score_val = round(100 * a / (a + b), 1)
    ci80 = [
        round(100 * float(np.quantile(draws, 0.10)), 1),
        round(100 * float(np.quantile(draws, 0.90)), 1)
    ]
    return {
        "score": score_val,
        "ci80": ci80,
        "n": len(items),
        "effective_n": round(float(w.sum()), 1) if len(items) else 0.0,
    }


def grade_score(score_val):
    """Translates numerical score to Letter Grade (A, B, C, D, F)."""
    return next(g for cut, g in GRADES if score_val >= cut)


def score_company(resolved, ticker, asof=None, prior=None):
    """Computes institutional Say-Do score & guidance analytics for a single company."""
    if prior is None:
        prior = calculate_base_rate(resolved, asof)

    mine = get_scored_promises(resolved, asof, ticker)
    all_company_promises = [
        p for p in resolved if p["ticker"] == ticker and
        (asof is None or date.fromisoformat(p["call_date"]) <= asof)
    ]

    res = beta_score(mine, prior)

    fin_promises = [p for p in mine if p.get("category") in FINANCIAL_CATEGORIES]
    ops_promises = [p for p in mine if p.get("category") not in FINANCIAL_CATEGORIES]

    outcomes = {}
    for p in mine:
        outcome = p["resolution"]["outcome"]
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    # Ratio of delivered vs guided revenue / EPS (Wall Street Sandbagging Index)
    ratios = []
    for p in fin_promises:
        r = p["resolution"].get("ratio")
        if r is not None and 0.4 <= r <= 2.0:
            ratios.append(r)

    reps = [p for p in all_company_promises if p.get("repeat_index", 0) == 0]
    revisions = sum(1 for p in reps if p.get("resolution", {}).get("revisions", 0) > 0)
    hedged = sum(1 for p in all_company_promises if p.get("strength") in ("hedged", "aspirational"))

    res.update({
        "ticker": ticker,
        "grade": grade_score(res["score"]),
        "financial": beta_score(fin_promises, prior) if fin_promises else None,
        "operational": beta_score(ops_promises, prior) if ops_promises else None,
        "outcomes": outcomes,
        "promises_made": len(all_company_promises),
        "resolved_count": len(mine),
        "pending": sum(1 for p in all_company_promises if p.get("resolution", {}).get("y") is None),
        "ghost_rate": round(outcomes.get("GHOSTED", 0) / len(mine), 3) if mine else 0.0,
        "goalpost_moves": revisions,
        "goalpost_rate": round(revisions / len(reps), 3) if reps else 0.0,
        "hedge_ratio": round(hedged / len(all_company_promises), 3) if all_company_promises else 0.0,
        "delivery_ratio": round(float(np.median(ratios)), 3) if ratios else 1.0,
        "delivery_ratio_samples": len(ratios),
    })
    return res
