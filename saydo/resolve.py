"""Turn promises + actuals + later-call evidence into outcomes.

Every outcome carries `knowable_at`: the date the market could first know it (results filing
deadline for financial promises; the date of the settling call for disclosure promises).
All scores and backtests are computed point-in-time on `knowable_at`, so nothing leaks.

Outcome -> y (delivery credit):
  DELIVERED 1.0 | PARTIAL 0.5 | LATE 0.5 | REVISED_DOWN 0.25 | MISSED / ABANDONED / GHOSTED 0.0
  PENDING -> not scored yet (still open, or no evidence either way)
  UNDATED -> never scored (no deadline: could be proven kept but never proven broken)
"""
import re
from datetime import date, timedelta

from . import financials, periods

Y = {"DELIVERED": 1.0, "PARTIAL": 0.5, "LATE": 0.5, "REVISED_DOWN": 0.25,
     "MISSED": 0.0, "ABANDONED": 0.0, "GHOSTED": 0.0}
GRACE_DAYS = 75        # a milestone confirmed on the first call after its deadline counts as on time
GHOST_MIN_CALLS = 2    # silence on this many calls after the deadline = quietly dropped

_DELTA_MARGIN_RE = re.compile(r"\b(bps|basis\s+points?|expansion|improve(?:\s+the)?\s+margin\s+by|improvement\s+in|add(?:ition)?\s+to\s+(?:the\s+)?(?:regular\s+business\s+)?ebitda)\b", re.I)
_ENTRY_RATE_RE = re.compile(r"entry\s+run[- ]?rate\s+of\s+(\d+(?:\.\d+)?)\s*%", re.I)


# ----------------------------------------------------------------------- financial promises
def _financial(p, act, today):
    per = periods.parse_period(p.get("period"), date.fromisoformat(p["call_date"]))
    if not per or per["kind"] not in ("FY", "Q", "H", "MULTI_YEAR"):
        return None
    if per["report_by"] > today:
        return {"outcome": "PENDING", "why": f"{p['period']} results not yet due ({per['report_by']})"}
    cur, prev = act.period(per)
    if not cur:
        return None
    lo, hi, cat = p.get("value_low"), p.get("value_high"), p["category"]
    if lo is None:
        return None
    unit = (p.get("unit") or "").lower()
    txt = f"{p.get('summary') or ''} {p.get('quote') or ''}"

    # Relative industry outperformance multiples (e.g. "2x industry growth") must resolve via disclosure
    if cat == "revenue_growth" and (unit == "x" or re.search(r"\b\d+(?:\.\d+)?\s*x\s+(?:of\s+)?(?:the\s+)?(?:underlying\s+)?industry\b", txt, re.I)):
        return None

    actual = None
    if cat == "revenue_growth":
        if per["kind"] == "MULTI_YEAR" or p.get("growth_basis") == "cagr":
            start = act.year(per.get("fy_start") or (per["fy"] - 3))
            n = per["fy"] - (per.get("fy_start") or (per["fy"] - 3))
            if start and start["sales"] > 0 and n > 0:
                actual = ((cur["sales"] / start["sales"]) ** (1 / n) - 1) * 100
        elif p.get("growth_basis") == "qoq" and per["kind"] == "Q":
            pq = (per["fy"], per["q"] - 1) if per["q"] > 1 else (per["fy"] - 1, 4)
            base = act.quarter(*pq)
            if base and base["sales"] > 0:
                actual = (cur["sales"] / base["sales"] - 1) * 100
        elif prev and prev["sales"] > 0:
            actual = (cur["sales"] / prev["sales"] - 1) * 100
    elif cat == "revenue_target" and unit in ("crore", "cr", ""):
        actual = cur["sales"]
    elif cat in ("ebitda_margin", "pat_margin"):
        k = "opm" if cat == "ebitda_margin" else "npm"
        actual_lvl = cur.get(k)
        if actual_lvl is None:
            return None
        # Check if guidance is a margin expansion delta (bps or percentage-point addition)
        is_delta = (p.get("growth_basis") == "delta_pp"
                    or (lo >= 25.0 and "bps" in txt.lower())
                    or (lo <= 4.0 and _DELTA_MARGIN_RE.search(txt) is not None))
        if is_delta:
            delta_pp = lo / 100.0 if lo >= 15.0 else lo
            m_entry = _ENTRY_RATE_RE.search(txt)
            base_margin = float(m_entry.group(1)) if m_entry else (prev.get(k) if prev else None)
            if base_margin is not None:
                target_lvl = base_margin + delta_pp
                gap = actual_lvl - target_lvl
                outcome = "DELIVERED" if gap >= -0.5 else "PARTIAL" if gap >= -2.0 else "MISSED"
                ratio = actual_lvl / target_lvl if target_lvl > 0 else None
                return {"outcome": outcome, "actual": round(actual_lvl, 2),
                        "ratio": round(ratio, 3) if ratio else None,
                        "knowable_at": per["report_by"].isoformat(),
                        "basis": "reported financials (Screener)",
                        "why": f"guided +{delta_pp:g}pp margin expansion (target {target_lvl:.1f}%) vs actual {actual_lvl:.1f}%"}
        actual = actual_lvl
    elif cat in ("pat_growth", "ebitda_growth"):
        k = "pat" if cat == "pat_growth" else "op_profit"
        if unit in ("crore", "cr"):
            # Absolute EBITDA/PAT target in Rs crore
            actual_cr = cur.get(k)
            if actual_cr is not None:
                ratio = actual_cr / lo if lo else None
                outcome = "DELIVERED" if ratio >= 0.97 else "PARTIAL" if ratio >= 0.90 else "MISSED"
                return {"outcome": outcome, "actual": round(actual_cr, 2),
                        "ratio": round(ratio, 3) if ratio else None,
                        "knowable_at": per["report_by"].isoformat(),
                        "basis": "reported financials (Screener)",
                        "why": f"guided {lo:g} cr vs actual {actual_cr:.1f} cr"}
        if prev and (prev.get(k) or 0) > 0 and cur.get(k) is not None:
            actual = (cur[k] / prev[k] - 1) * 100
    if actual is None:
        return None

    d = p.get("direction")
    if cat in ("ebitda_margin", "pat_margin"):          # percentage points
        gap = actual - lo if d != "at_most" else (hi or lo) - actual
        outcome = "DELIVERED" if gap >= -0.5 else "PARTIAL" if gap >= -2.0 else "MISSED"
        ratio = actual / lo if lo else None
    elif cat == "revenue_target":
        ratio = actual / lo if lo else None
        outcome = "DELIVERED" if ratio >= 0.97 else "PARTIAL" if ratio >= 0.90 else "MISSED"
    else:                                               # growth rates
        # Level ratio: revenue delivered / revenue implied by the guide (stable when growth ~0 or <0)
        ratio = (1 + actual / 100) / (1 + lo / 100) if lo > -100 else None
        tol = max(1.0, 0.10 * abs(lo))
        outcome = ("DELIVERED" if actual >= lo - tol else
                   "PARTIAL" if lo > 0 and actual >= 0.7 * lo else "MISSED")
    return {"outcome": outcome, "actual": round(actual, 2), "ratio": round(ratio, 3) if ratio else None,
            "knowable_at": per["report_by"].isoformat(), "basis": "reported financials (Screener)",
            "why": f"guided {lo:g}{'-' + format(hi, 'g') if hi not in (None, lo) else ''} vs actual {actual:.1f}"}


# ---------------------------------------------------------------------- disclosure promises
def _is_premature_delivery(p, e_call_date, deadline):
    if deadline is None:
        return False
    cd = date.fromisoformat(e_call_date)
    pk = p.get("period_kind")
    made = date.fromisoformat(p["call_date"]) if p.get("call_date") else None
    # For annual or multi-year fiscal commitments, delivery cannot be confirmed before that fiscal year begins
    if pk in ("FY", "MULTI_YEAR"):
        return cd < (deadline - timedelta(days=365))
    # If deadline is far in the future (>1 year after promise made)
    if made and (deadline - made).days > 365:
        return cd < (deadline - timedelta(days=365))
    if not made and (deadline - cd).days > 365:
        return True
    return False


def _disclosure(p, timeline, later_calls, today):
    """timeline: evidence records for this promise sorted by call date."""
    deadline = date.fromisoformat(p["deadline"]) if p.get("deadline") else None
    grace = deadline + timedelta(days=GRACE_DAYS) if deadline else None

    # Resolver backstop:
    # 1) DELIVERED or REVISED_UP evidence dated before the target period window is downgraded to ON_TRACK
    # 2) REVISED_UP before the deadline is an interim guidance raise (ON_TRACK), not completion (DELIVERED)
    clean_timeline = []
    for e in timeline:
        st = e.get("status")
        if deadline is not None:
            cd = date.fromisoformat(e["call_date"])
            if st in ("DELIVERED", "REVISED_UP") and _is_premature_delivery(p, e["call_date"], deadline):
                e = {**e, "status": "ON_TRACK",
                     "note": (e.get("note") or "") + " [downgraded to ON_TRACK: before deadline window]"}
            elif st == "REVISED_UP" and cd < deadline:
                e = {**e, "status": "ON_TRACK",
                     "note": (e.get("note") or "") + " [REVISED_UP before deadline treated as ON_TRACK]"}
        clean_timeline.append(e)

    live = [e for e in clean_timeline if e["status"] != "NOT_MENTIONED"]
    revisions = [e for e in live if e["status"] in ("DELAYED", "REVISED_DOWN")]
    base = {"revisions": len(revisions), "evidence": live[-3:]}

    if deadline is not None:
        deliv = [e for e in live if e["status"] in ("DELIVERED", "REVISED_UP")]
        if deliv:
            e = deliv[0]
            cd = date.fromisoformat(e["call_date"])
            late = grace is not None and cd > grace
            out = "LATE" if late else "DELIVERED"
            return {**base, "outcome": out, "knowable_at": e["call_date"],
                    "why": f"confirmed on {e['call_label']}" + (" after delay" if out == "LATE" else "")}
        # Explicit abandonment can resolve before deadline
        abandoned = [e for e in live if e["status"] == "ABANDONED"]
        if abandoned:
            e = abandoned[0]
            return {**base, "outcome": "ABANDONED", "knowable_at": e["call_date"],
                    "why": f"abandoned per {e['call_label']}"}
        # If deadline is still in the future (deadline >= today), a miss cannot be declared yet — the period is still open!
        if deadline < today:
            missed = [e for e in live if e["status"] == "MISSED"]
            if missed:
                e = missed[0]
                return {**base, "outcome": e["status"], "knowable_at": e["call_date"],
                        "why": f"{e['status'].lower()} per {e['call_label']}"}

    if deadline is None:
        # Undated promises can be proven kept but never proven broken -> scoring them would bias
        # every score upward. They stay in the ledger (with status) but are not scored.
        last = live[-1]["status"] if live else "NOT_MENTIONED"
        return {**base, "outcome": "UNDATED", "status_now": last, "why": f"no deadline; latest status {last.lower()}"}
    after = [c for c in later_calls if c.date > grace]
    after_dl = [c for c in later_calls if c.date > deadline + timedelta(days=15)]
    if deadline >= today or not after:
        last = live[-1]["status"] if live else "NOT_MENTIONED"
        return {**base, "outcome": "PENDING", "status_now": last,
                "why": f"deadline {deadline} not yet tested by a later call"}
    # Deadline + grace passed and later calls exist, but no delivery was ever confirmed
    if revisions:
        e_first = revisions[0]
        e_last = revisions[-1]
        return {**base, "outcome": "REVISED_DOWN", "knowable_at": e_first["call_date"],
                "why": f"{e_last['status'].lower().replace('_', ' ')} on {e_last['call_label']}, never confirmed"}
    post_dl = [e for e in live if date.fromisoformat(e["call_date"]) >= deadline]
    if not post_dl and len(after) >= GHOST_MIN_CALLS:
        ghost_calls = after_dl if len(after_dl) >= GHOST_MIN_CALLS else after
        return {**base, "outcome": "GHOSTED", "knowable_at": ghost_calls[GHOST_MIN_CALLS - 1].date.isoformat(),
                "why": f"deadline {deadline} passed; not mentioned on {len(after)} later calls"}
    return {**base, "outcome": "PENDING", "status_now": live[-1]["status"] if live else "NOT_MENTIONED",
            "why": "deadline passed; evidence inconclusive"}


_STOP = set("the a an of to in for and by on with from at be will our we is are this that its it into fy".split())


def _toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in _STOP and len(w) > 2}


def cluster_repeats(promises):
    """Management repeats the same promise on several calls. Group repeats so one promise said
    four times is not scored as four independent promises (score weights each by 1/sqrt(k))."""
    groups = []
    for p in sorted(promises, key=lambda x: x["call_date"]):
        tk = _toks(p.get("summary"))
        hit = None
        for g in groups:
            q = g[0]
            if q["ticker"] != p["ticker"] or q["category"] != p["category"]:
                continue
            same_period = (q.get("period") == p.get("period"))
            if not same_period and q.get("deadline") and p.get("deadline"):
                same_period = abs((date.fromisoformat(q["deadline"]) - date.fromisoformat(p["deadline"])).days) <= 45
            if not same_period:
                continue
            same_val = p.get("value_low") is not None and p.get("value_low") == q.get("value_low")
            tq = _toks(q.get("summary"))
            jac = len(tk & tq) / max(1, len(tk | tq))
            if same_val or jac >= 0.5:
                hit = g
                break
        if hit:
            hit.append(p)
        else:
            groups.append([p])
    for g in groups:
        for i, p in enumerate(g):
            p["cluster"] = g[0]["id"]
            p["cluster_size"] = len(g)
            p["repeat_index"] = i
    return promises


def resolve_all(promises, evidence, calls_by_ticker, snaps, today=None):
    cluster_repeats(promises)
    today = today or date.today()
    tl = {}
    for e in evidence:
        tl.setdefault(e["promise_id"], []).append(e)
    for v in tl.values():
        v.sort(key=lambda e: e["call_date"])
    acts = {t: financials.Actuals(s) for t, s in snaps.items()}
    out = []
    for p in promises:
        t = p["ticker"]
        made = date.fromisoformat(p["call_date"])
        later = [c for c in calls_by_ticker.get(t, []) if c.date > made]
        r = None
        if p["verifiable_by"] == "financials" and t in acts:
            r = _financial(p, acts[t], today)
            if r and r["outcome"] != "PENDING":
                # transcript revisions still count toward goalpost-moving
                live = [e for e in tl.get(p["id"], []) if e["status"] in ("DELAYED", "REVISED_DOWN")]
                r["revisions"] = len(live)
                r["evidence"] = [e for e in tl.get(p["id"], []) if e["status"] != "NOT_MENTIONED"][-3:]
        if r is None or (r["outcome"] == "PENDING" and p["verifiable_by"] != "financials"):
            r = _disclosure(p, tl.get(p["id"], []), later, today)
        r["y"] = Y.get(r["outcome"])
        out.append({**p, "resolution": r})
    return out
