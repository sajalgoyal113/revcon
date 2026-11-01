"""Company track-record ('persistence') features, strictly point-in-time.

For a company and a cutoff date, summarise everything the market could know
about its promise-keeping from outcomes and interim concall disclosures with
dates <= cutoff:
- Symmetric point-in-time delivery rate (combining matured resolutions and
  interim DELAYED/REVISED_DOWN/MISSED/ABANDONED disclosures on calls <= cutoff,
  eliminating pre-deadline early-bragging survivorship bias).
- Category-group-specific track record (`cat_kept_shrunk`) matching the domain
  of the guidance being evaluated (financials, build/capex, commercial, other).
- Trajectory (recent vs early), goalpost/ghost behaviour, ambition calibration
  and guidance style. Thin histories fall back to calibrated priors.
"""
from datetime import date, timedelta

import numpy as np

from . import score
from .extract import FINANCIAL

KAPPA = 6.0
REV_CATS = {"revenue_growth", "revenue_target"}
MARGIN_CATS = {"ebitda_margin", "pat_margin", "ebitda_growth", "pat_growth"}
CAPEX_CATS = {"capex", "capacity", "commissioning", "expansion"}
COMM_CATS = {"order_book", "order_inflow", "customer_win", "product_launch", "market_share"}

GROUPS = {
    "fin": REV_CATS | MARGIN_CATS,
    "build": CAPEX_CATS,
    "commercial": COMM_CATS,
}
GRP_PRIORS = {"fin": 0.55, "build": 0.38, "commercial": 0.42, "other": 0.40}

HIST_FEATURES = [
    "kept_shrunk", "cat_kept_shrunk", "fin_spread", "ops_spread", "trend", "recent4", "streak",
    "goalpost_rate", "ghost_rate", "hedge_share", "firm_share",
    "rev_ratio", "rev_n", "eff_n",
]


def _cat_grp(cat):
    for g, s in GROUPS.items():
        if cat in s:
            return g
    return "other"


def _shrunk(items, prior, k=KAPPA):
    if not items:
        return float(prior)
    w = np.array([w for w, _ in items])
    y = np.array([y for _, y in items])
    return float(((w * y).sum() + k * prior) / (w.sum() + k))


def _kept(p):
    return 1.0 if p["resolution"]["y"] >= 0.75 else 0.0


def history_features(resolved, ticker, asof, prior=None, uni_rev=0.95, category=None):
    if isinstance(asof, str):
        asof = date.fromisoformat(asof)
    cut_str = asof.isoformat()
    # Use a stationary calibrated prior (0.48) when prior is not explicitly forced,
    # avoiding Simpson's paradox from early right-censored base_rate drift.
    base_prior = 0.48 if prior is None else float(prior)
    g_cur = _cat_grp(category) if category else "other"

    made_p = [q for q in resolved if q["ticker"] == ticker and q.get("call_date", "9999") <= cut_str]
    if not made_p:
        return {
            "kept_shrunk": base_prior,
            "cat_kept_shrunk": GRP_PRIORS.get(g_cur, base_prior) if prior is None else base_prior,
            "fin_spread": 0.0,
            "ops_spread": 0.0,
            "trend": 0.0,
            "recent4": base_prior,
            "streak": 0.0,
            "goalpost_rate": 0.0,
            "ghost_rate": 0.0,
            "hedge_share": 0.0,
            "firm_share": 0.0,
            "rev_ratio": float(uni_rev),
            "rev_n": 0.0,
            "eff_n": 0.0,
            "grp_kept": {gr: (GRP_PRIORS[gr] if prior is None else base_prior) for gr in GRP_PRIORS},
        }

    good_w = 0.0
    bad_w = 0.0
    fin_g = fin_b = ops_g = ops_b = 0.0
    grp_gb = {gr: [0.0, 0.0] for gr in ("fin", "build", "commercial", "other")}
    seq_outcomes = []
    revs_cnt = 0.0
    ghost_cnt = 0.0
    ratios = []

    for q in sorted(made_p, key=lambda x: (x.get("call_date", ""), x.get("id", ""))):
        w = score.weight(q)
        r = q.get("resolution", {})
        gr = _cat_grp(q.get("category"))
        is_fin = (q.get("category") in FINANCIAL and q.get("verifiable_by") == "financials")
        evs_by_cut = [e for e in (r.get("evidence") or []) if e.get("call_date", "9999") <= cut_str]
        bad_evs = [e for e in evs_by_cut if e.get("status") in ("DELAYED", "REVISED_DOWN", "MISSED", "ABANDONED")]
        deliv_evs = [e for e in evs_by_cut if e.get("status") == "DELIVERED"]
        dl = date.fromisoformat(q["deadline"]) if q.get("deadline") else None
        ka = r.get("knowable_at")

        if any(e.get("status") in ("DELAYED", "REVISED_DOWN") for e in evs_by_cut) or (
            ka and ka <= cut_str and r.get("revisions", 0) > 0
        ):
            revs_cnt += 1.0

        # 1. Financial promises or synthetic test rows without an evidence list
        if (is_fin or not r.get("evidence")) and ka and ka <= cut_str and r.get("y") is not None:
            if q.get("category") in REV_CATS and str(q.get("unit") or "").lower() != "x" and r.get("ratio") and 0.4 <= r["ratio"] <= 1.6:
                ratios.append(min(max(r["ratio"], 0.70), 1.15))
            if r["y"] >= 0.75 and not bad_evs:
                good_w += w
                if is_fin:
                    fin_g += w
                else:
                    ops_g += w
                grp_gb[gr][0] += w
                seq_outcomes.append((ka, q.get("id", ""), 1.0))
            else:
                bad_w += w
                if is_fin:
                    fin_b += w
                else:
                    ops_b += w
                grp_gb[gr][1] += w
                seq_outcomes.append((ka, q.get("id", ""), 0.0))
                if r.get("outcome") == "GHOSTED":
                    ghost_cnt += 1.0
            continue

        # 2. Explicit interim or final adverse evidence on calls <= cut_str
        if bad_evs:
            bad_w += w
            ops_b += w
            grp_gb[gr][1] += w
            seq_outcomes.append((bad_evs[0]["call_date"], q.get("id", ""), 0.0))
            continue

        # 3. Matured disclosure deadline (dl <= asof) eliminate pre-deadline bragging survivorship bias
        if dl is not None and dl <= asof:
            if deliv_evs or (ka and ka <= cut_str and (r.get("y") or 0) >= 0.75):
                good_w += w
                ops_g += w
                grp_gb[gr][0] += w
                dt_ev = deliv_evs[0]["call_date"] if deliv_evs else (ka or cut_str)
                seq_outcomes.append((dt_ev, q.get("id", ""), 1.0))
            elif (asof - dl).days >= 60 or (ka and ka <= cut_str and r.get("y") is not None and r["y"] < 0.75):
                bad_w += w
                ops_b += w
                grp_gb[gr][1] += w
                seq_outcomes.append((ka or cut_str, q.get("id", ""), 0.0))
                if r.get("outcome") == "GHOSTED" or not evs_by_cut:
                    ghost_cnt += 1.0

    tot_w = good_w + bad_w
    eff_prior = 0.45 if prior is None else float(prior)
    kept = float((good_w + KAPPA * eff_prior) / (tot_w + KAPPA)) if tot_w > 0 else base_prior
    fin_s = float((fin_g + 4.0 * (0.55 if prior is None else base_prior)) / (fin_g + fin_b + 4.0) - kept)
    ops_s = float((ops_g + 4.0 * (0.38 if prior is None else base_prior)) / (ops_g + ops_b + 4.0) - kept)

    grp_kept = {}
    for gr in ("fin", "build", "commercial", "other"):
        gp = GRP_PRIORS[gr] if prior is None else base_prior
        grp_kept[gr] = float((grp_gb[gr][0] + 4.0 * gp) / (grp_gb[gr][0] + grp_gb[gr][1] + 4.0))

    n_seq = len(seq_outcomes)
    ks_vals = [x[2] for x in seq_outcomes]
    if n_seq >= 4:
        h_mid = n_seq // 2
        trend = float(np.mean(ks_vals[h_mid:]) - np.mean(ks_vals[:h_mid]))
    else:
        trend = 0.0
    recent4 = float(np.mean(ks_vals[-4:])) if n_seq >= 2 else eff_prior

    streak = 0
    for _, _, o_val in reversed(sorted(seq_outcomes, key=lambda x: (x[0], x[1]))):
        if o_val >= 0.5:
            streak += 1
        else:
            break
    streak = min(streak, 6)

    n_made = len(made_p)
    gp_rate = float((revs_cnt + 4.0 * 0.15) / (n_made + 4.0)) if prior is None else (revs_cnt / max(1, n_made))
    gh_rate = float((ghost_cnt + 4.0 * 0.06) / (max(1, n_seq) + 4.0)) if prior is None else (ghost_cnt / max(1, n_seq))
    hedge_sh = float(np.mean([1.0 if q.get("strength") in ("hedged", "aspirational") else 0.0 for q in made_p]))
    firm_sh = float(np.mean([1.0 if q.get("strength") == "firm" else 0.0 for q in made_p]))

    rev_n = len(ratios)
    rev_prior = 0.98 if (prior is None and uni_rev == 0.95) else float(uni_rev)
    rev_ratio = float((np.mean(ratios) * rev_n + rev_prior * 4.0) / (rev_n + 4.0)) if ratios else float(uni_rev)

    return {
        "kept_shrunk": kept,
        "cat_kept_shrunk": grp_kept.get(g_cur, kept),
        "fin_spread": fin_s,
        "ops_spread": ops_s,
        "trend": trend,
        "recent4": recent4,
        "streak": float(streak),
        "goalpost_rate": gp_rate,
        "ghost_rate": gh_rate,
        "hedge_share": hedge_sh,
        "firm_share": firm_sh,
        "rev_ratio": rev_ratio,
        "rev_n": float(rev_n),
        "eff_n": float(tot_w),
        "grp_kept": grp_kept,
    }


def guidance_track_record(resolved, ticker, asof=None):
    """Institutional report of a company's past management guidance accuracy."""
    if asof is None:
        asof = date.today()
    elif isinstance(asof, str):
        asof = date.fromisoformat(asof)

    past = score.scored(resolved, asof, ticker)
    if not past:
        return {"ticker": ticker, "total_guided": 0, "status": "Insufficient historical guidance records"}

    by_made = sorted(past, key=lambda p: (p["call_date"], p["id"]))
    n = len(by_made)
    ks = [_kept(p) for p in by_made]
    delivery_rate = float(np.mean(ks))

    # Revenue guidance delivery
    revs = [p for p in by_made if p["category"] in REV_CATS]
    rev_ratios = [p["resolution"]["ratio"] for p in revs
                  if str(p.get("unit") or "").lower() != "x"
                  and p["resolution"].get("ratio") is not None
                  and 0.35 <= p["resolution"]["ratio"] <= 1.8]
    rev_delivery = float(np.mean([_kept(p) for p in revs])) if revs else None
    rev_ratio_median = float(np.median(rev_ratios)) if rev_ratios else None

    # Margin guidance delivery
    margins = [p for p in by_made if p["category"] in MARGIN_CATS]
    margin_delivery = float(np.mean([_kept(p) for p in margins])) if margins else None

    # Capex / Capacity guidance delivery
    capex = [p for p in by_made if p["category"] in CAPEX_CATS]
    capex_delivery = float(np.mean([_kept(p) for p in capex])) if capex else None

    # Ghosting & Goalpost moves
    ghosts = sum(1 for p in by_made if p["resolution"]["outcome"] == "GHOSTED")
    revisions = sum(1 for p in by_made if p["resolution"].get("revisions", 0) > 0)

    # Style classification
    if rev_ratio_median is not None:
        if rev_ratio_median >= 1.03 and delivery_rate >= 0.55:
            style = "Conservative / Sandbagger (under-promises, consistently beats)"
        elif rev_ratio_median < 0.95 or delivery_rate < 0.35:
            style = "Aggressive / Over-Promiser (habitual optimism gap, misses targets)"
        else:
            style = "Disciplined Guide (delivers within narrow tolerance)"
    elif delivery_rate >= 0.60:
        style = "Reliable Executor (high operational delivery)"
    else:
        style = "Volatile Delivery (mixed operational follow-through)"

    return {
        "ticker": ticker,
        "total_guided": n,
        "delivery_rate": round(delivery_rate * 100, 1),
        "style": style,
        "revenue_guidance": {
            "count": len(revs),
            "delivery_rate_pct": round(rev_delivery * 100, 1) if rev_delivery is not None else None,
            "median_accuracy_ratio": round(rev_ratio_median, 2) if rev_ratio_median is not None else None,
        },
        "margin_guidance": {
            "count": len(margins),
            "delivery_rate_pct": round(margin_delivery * 100, 1) if margin_delivery is not None else None,
        },
        "capex_guidance": {
            "count": len(capex),
            "delivery_rate_pct": round(capex_delivery * 100, 1) if capex_delivery is not None else None,
        },
        "behavior": {
            "ghosted_count": ghosts,
            "ghost_rate_pct": round(100 * ghosts / n, 1),
            "revised_down_count": revisions,
            "revision_rate_pct": round(100 * revisions / n, 1),
        }
    }
