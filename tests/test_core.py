"""Deterministic core tests (no network, no LLM).  python -m pytest tests -q  (or python tests/test_core.py)"""
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from saydo import financials, history, periods, predict, resolve, score, transcripts  # noqa: E402


def test_fiscal_calendar():
    assert periods.fy_of(date(2025, 4, 1)) == 2026
    assert periods.fy_of(date(2026, 3, 31)) == 2026
    assert periods.last_reported_quarter(date(2025, 7, 31)) == (2026, 1)   # Q1FY26 call
    assert periods.last_reported_quarter(date(2025, 1, 20)) == (2025, 3)   # Q3FY25 call
    assert periods.last_reported_quarter(date(2025, 5, 16)) == (2025, 4)   # Q4FY25 call


def test_parse_period():
    cd = date(2025, 8, 1)
    assert periods.parse_period("FY27", cd)["end"] == date(2027, 3, 31)
    q = periods.parse_period("Q3FY26", cd)
    assert (q["kind"], q["end"]) == ("Q", date(2025, 12, 31))
    # Quarter range resolves to END of range, not start
    qr = periods.parse_period("Q2FY26-Q4FY26", cd)
    assert (qr["kind"], qr["end"], qr["q_start"]) == ("Q", date(2026, 3, 31), 2)
    # Calendar Year (CY) quarters, halves, and bare years
    assert periods.parse_period("H1CY27", cd)["end"] == date(2027, 6, 30)
    assert periods.parse_period("Q4CY26-Q1CY27", cd)["end"] == date(2027, 3, 31)
    assert periods.parse_period("2027", cd)["end"] == date(2027, 3, 31)
    assert periods.parse_period("MAR2026", cd)["end"] == date(2026, 3, 31)
    assert periods.parse_period("H2FY26", cd)["end"] == date(2026, 3, 31)
    assert periods.parse_period("2025-12", cd)["end"] == date(2025, 12, 31)
    m = periods.parse_period("FY25-FY28", cd)
    assert (m["kind"], m["fy"], m["fy_start"]) == ("MULTI_YEAR", 2028, 2025)
    assert periods.parse_period(None, cd) is None
    assert periods.parse_period("soon", cd) is None
    # Text inference fallback
    assert periods.infer_period_from_text("Deliver 25% growth in next quarter", cd) == "Q3FY26"
    assert periods.infer_period_from_text("Complete capex within 12 months", cd) == "FY27"


def test_quote_verifier_rejects_invented_quotes():
    text = ("Page 3 of 18 Jairam Sampath: We maintain our consolidated revenue guidance of Rs. 4,500 crores "
            "plus for FY '26 and EBITDA margins should stay at 16%. Page 4 of 18")
    tn = transcripts.norm(text)
    assert transcripts.verify_quote("We maintain our consolidated revenue guidance of Rs. 4,500 crores plus for FY '26", tn) == "exact"
    assert transcripts.verify_quote("We will double revenue to Rs 9,000 crores by FY27 with 20% margins", tn) is None
    assert transcripts.verify_quote("short", tn) is None


def _acts():
    snap = {"quarters": {}, "prices": [],
            "annual": {"2025": {"sales": 2722.0, "opm": 15.3, "npm": 10.8, "pat": 293.0, "op_profit": 416.0},
                       "2026": {"sales": 3626.0, "opm": 15.9, "npm": 10.0, "pat": 364.0, "op_profit": 578.0}}}
    return financials.Actuals(snap)


def _promise(**kw):
    p = {"id": "X:2025-07-31#0", "ticker": "X", "call_date": "2025-07-31", "period": "FY26", "unit": "crore",
         "direction": "at_least", "growth_basis": None, "strength": "firm", "verifiable_by": "financials"}
    p.update(kw)
    return p


def test_financial_resolution():
    today = date(2026, 11, 1)
    r = resolve._financial(_promise(category="revenue_target", value_low=4500, value_high=4500), _acts(), today)
    assert r["outcome"] == "MISSED" and abs(r["ratio"] - 3626 / 4500) < 1e-3
    r = resolve._financial(_promise(category="revenue_growth", value_low=30, value_high=30, unit="%"), _acts(), today)
    assert r["outcome"] == "DELIVERED"          # 33.2% actual vs 30% guided
    r = resolve._financial(_promise(category="ebitda_margin", value_low=16.8, value_high=16.8, unit="%"), _acts(), today)
    assert r["outcome"] == "PARTIAL"            # 15.9 vs 16.8: within 2pp
    r = resolve._financial(_promise(category="revenue_target", value_low=4500, value_high=4500), _acts(), date(2026, 4, 30))
    assert r["outcome"] == "PENDING"            # FY26 results not due until end-May
    # Margin expansion delta in bps
    r_bps = resolve._financial(
        _promise(category="ebitda_margin", value_low=0.5, value_high=0.5, unit="%",
                 summary="About 50 bps expansion in EBITDA margin in FY26"),
        _acts(), today
    )
    assert r_bps["outcome"] == "DELIVERED" and 0.95 <= r_bps["ratio"] <= 1.05
    # Absolute EBITDA in crore on ebitda_growth category
    r_eb = resolve._financial(
        _promise(category="ebitda_growth", value_low=500, value_high=500, unit="crore",
                 summary="Deliver INR 500 crore plus EBITDA in FY26"),
        _acts(), today
    )
    assert r_eb["outcome"] == "DELIVERED" and r_eb["actual"] == 578.0
    # Relative industry multiple ("2x industry growth") returns None from _financial so _disclosure handles it
    r_mult = resolve._financial(
        _promise(category="revenue_growth", value_low=2.0, value_high=2.0, unit="x",
                 summary="Outperform industry growth by 2x in FY26"),
        _acts(), today
    )
    assert r_mult is None


def test_pending_never_leaks_into_point_in_time_score():
    mk = lambda i, y, k: {"id": f"A:{i}", "ticker": "A", "call_date": "2025-01-01", "category": "capex",
                          "verifiable_by": "disclosure", "strength": "firm", "deadline": "2025-06-30",
                          "resolution": {"y": y, "knowable_at": k, "outcome": "DELIVERED" if y else "MISSED"}}
    led = [mk(1, 1.0, "2025-05-01"), mk(2, 0.0, "2025-09-01"), mk(3, None, None)]
    assert len(score.scored(led, date(2025, 6, 1))) == 1
    assert len(score.scored(led, date(2025, 10, 1))) == 2


def test_shrinkage_small_samples():
    def led(n_kept, n_broken, t):
        out = []
        for i in range(n_kept + n_broken):
            out.append({"id": f"{t}:{i}", "ticker": t, "call_date": "2025-01-01", "category": "capex",
                        "verifiable_by": "disclosure", "strength": "firm", "deadline": "2025-06-30",
                        "resolution": {"y": 1.0 if i < n_kept else 0.0, "knowable_at": "2025-07-01",
                                       "outcome": "DELIVERED" if i < n_kept else "MISSED"}})
        return out
    small = score.company_score(led(2, 0, "S"), "S", prior=0.6)
    big = score.company_score(led(27, 3, "B"), "B", prior=0.6)
    assert big["score"] > small["score"]                 # 27/30 beats 2/2
    assert small["ci80"][1] - small["ci80"][0] > big["ci80"][1] - big["ci80"][0]


def test_repeat_clustering():
    a = {"id": "T:1#0", "ticker": "T", "call_date": "2025-01-01", "category": "revenue_target", "period": "FY26",
         "value_low": 400.0, "summary": "CSMT project revenue Rs 400 crore in FY26"}
    b = {**a, "id": "T:2#0", "call_date": "2025-05-01", "summary": "Rs 400 crore from CSMT in FY26"}
    c = {**a, "id": "T:3#0", "category": "capex", "value_low": 50.0, "summary": "capex Rs 50 crore"}
    resolve.cluster_repeats([a, b, c])
    assert a["cluster_size"] == 2 and b["repeat_index"] == 1 and c["cluster_size"] == 1


def test_undated_promises_are_never_scored():
    p = {"id": "U:1#0", "deadline": None}
    ev = [{"status": "DELIVERED", "call_date": "2025-09-01", "call_label": "Q1"}]
    r = resolve._disclosure(p, ev, [], date(2026, 11, 1))
    assert r["outcome"] == "UNDATED" and resolve.Y.get(r["outcome"]) is None


def test_ghosted_after_deadline_silence():
    class C:
        def __init__(self, d):
            self.date = d
    p = {"id": "G:1#0", "deadline": "2025-06-30"}
    later = [C(date(2025, 11, 10)), C(date(2026, 2, 10))]
    r = resolve._disclosure(p, [], later, date(2026, 11, 1))
    assert r["outcome"] == "GHOSTED" and r["knowable_at"] == "2026-02-10"


def _hist_row(i, t, y, known, **kw):
    p = {"id": f"{t}:{i}", "ticker": t, "call_date": "2025-01-01", "category": "capex",
         "verifiable_by": "disclosure", "strength": "firm", "deadline": "2025-06-30",
         "value_low": 10.0, "cluster_size": 1,
         "resolution": {"y": y, "knowable_at": known, "outcome": "DELIVERED" if y else "MISSED",
                        "revisions": 0}}
    p.update(kw)
    return p


def test_history_uses_only_knowable_past():
    led = [_hist_row(1, "A", 1.0, "2025-02-01"), _hist_row(2, "A", 0.0, "2025-12-01"),
           _hist_row(3, "B", 1.0, "2025-02-01")]
    h = history.history_features(led, "A", "2025-06-01", prior=0.5)
    assert h["eff_n"] > 0 and h["kept_shrunk"] > 0.5  # only the kept Feb outcome counts
    h2 = history.history_features([r for r in led if r["id"] != "A:2"], "A", "2025-06-01",
                                  prior=0.5)
    assert h["kept_shrunk"] == h2["kept_shrunk"]  # December outcome invisible at June cutoff


def test_history_empty_and_nan_free():
    h = history.history_features([], "Z", "2025-06-01", prior=0.5)
    assert h["kept_shrunk"] == 0.5 and h["rev_ratio"] == 0.95 and h["eff_n"] == 0.0
    led = [_hist_row(1, "A", 1.0, "2025-02-01")]  # no revenue promises -> no ratios
    import math
    h = history.history_features(led, "A", "2025-06-01", prior=0.5)
    assert all(math.isfinite(v) for k, v in h.items() if isinstance(v, (int, float)))


def test_early_delivered_downgraded_to_on_track():
    # Promise has deadline FY28 (2028-03-31)
    p = {"id": "E:1#0", "deadline": "2028-03-31"}
    # Later call in May 2026 reports DELIVERED (well before deadline - 75 days = ~Jan 2028)
    ev_early = [{"status": "DELIVERED", "call_date": "2026-05-15", "call_label": "Q4FY26 call",
                 "evidence_quote": "We have invested initial capital"}]
    # Evaluated as of 2026-11-01: should be PENDING, not DELIVERED
    r = resolve._disclosure(p, ev_early, [], date(2026, 11, 1))
    assert r["outcome"] == "PENDING"
    assert r["status_now"] == "ON_TRACK"

    # Confirmed within the deadline window (Feb 2028): resolves as DELIVERED
    ev_window = [{"status": "DELIVERED", "call_date": "2028-02-15", "call_label": "Q3FY28 call",
                  "evidence_quote": "Capacity is fully operational"}]
    r2 = resolve._disclosure(p, ev_window, [], date(2028, 5, 1))
    assert r2["outcome"] == "DELIVERED"
    assert r2["knowable_at"] == "2028-02-15"


def test_tie_aware_auc():
    # Constant predictions must yield exact 0.500 ROC AUC (not 0.116 due to index tie-breaking)
    y = [1.0, 0.0, 1.0, 0.0, 0.0]
    s = [0.5, 0.5, 0.5, 0.5, 0.5]
    assert abs(predict.auc(y, s) - 0.5) < 1e-9


class TestCore(unittest.TestCase):
    def test_all_core_functions(self):
        for name, fn in list(globals().items()):
            if name.startswith("test_") and callable(fn):
                fn()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
