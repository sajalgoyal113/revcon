"""End-to-end Say-Do pipeline.

  python -m saydo.pipeline extract   # SAY: Muse extracts promises from every call   (LLM)
  python -m saydo.pipeline judge     # DO:  Muse checks later calls for each promise (LLM)
  python -m saydo.pipeline forecast  # Muse forecasts P(kept) per promise, names masked (LLM)
  python -m saydo.pipeline build     # resolve + score + predictor + market tests    (no LLM)
  python -m saydo.pipeline all
Options: --tickers KAYNES DIXON ...   --today 2026-11-01

All LLM calls are cached in data/cache, so re-runs are free and reproducible.
"""
import argparse
import json
import os
import time
from datetime import date

from . import config, extract, financials, forecast, judge, llm, market, predict, resolve, score, transcripts


def _p(name):
    return os.path.join(config.OUT, name)


def _load(name, default=None):
    return json.load(open(_p(name))) if os.path.exists(_p(name)) else default


def _save(name, obj):
    json.dump(obj, open(_p(name), "w"), indent=1, default=str)


def flat_promises(tickers=None):
    raw = _load("promises.json", {})
    out = [p for r in raw.values() for p in r["promises"]]
    return [p for p in out if (not tickers or p["ticker"] in tickers) and p["ticker"] not in config.EXCLUDE]


def stage_extract(calls):
    res = extract.extract_all(calls)
    old = _load("promises.json", {})
    old.update(res)
    _save("promises.json", old)


def stage_judge(calls, tickers):
    ev = judge.judge_all(calls, flat_promises(tickers))
    old = [e for e in _load("evidence.json", []) if tickers and e["promise_id"].split(":")[0] not in tickers]
    _save("evidence.json", old + ev)


def stage_forecast(calls, tickers):
    snaps = {t: financials.fetch(t) for t in calls}
    fc = forecast.forecast_all(flat_promises(tickers), snaps)
    old = _load("forecasts.json", {})
    old.update(fc)
    _save("forecasts.json", old)
    print(f"forecasts: {len(fc)}")


def stage_build(calls, tickers, today):
    snaps = {t: financials.fetch(t) for t in calls}
    snaps = {t: s for t, s in snaps.items() if s}
    promises = flat_promises(tickers)
    evidence = _load("evidence.json", [])
    resolved = resolve.resolve_all(promises, evidence, calls, snaps, today)
    _save("resolved.json", resolved)

    board = score.leaderboard(resolved, list(calls), today)
    # Point-in-time history (score as of each quarter-end) for the dashboard
    hist = {}
    for t in calls:
        hist[t] = []
        for d in sorted({c.date for c in calls[t]}):
            cs = score.company_score(resolved, t, d)
            hist[t].append({"date": d.isoformat(), "score": cs["score"], "n": cs["n"]})
    board["history"] = hist
    _save("scores.json", board)

    model = predict.train(resolved, snaps, _load("forecasts.json", {}))
    if model:
        predict.save(model, _p("model.json"))
    mk = {"cross_section": market.cross_section(resolved, calls, snaps),
          "event_study": market.event_study(resolved, snaps)}
    _save("market.json", mk)

    # Corpus stats for the README / app
    raw = _load("promises.json", {})
    outcomes = {}
    for p in resolved:
        o = p["resolution"]["outcome"]
        outcomes[o] = outcomes.get(o, 0) + 1
    stats = {"companies": len(calls), "calls": sum(len(v) for v in calls.values()),
             "promises": len(resolved), "unverifiable_dropped": sum(r["dropped_unverified"] for r in raw.values()),
             "evidence_records": len(evidence),
             "evidence_with_status": sum(1 for e in evidence if e["status"] != "NOT_MENTIONED"),
             "outcomes": outcomes, "scored": sum(1 for p in resolved if p["resolution"].get("y") is not None),
             "built": time.strftime("%Y-%m-%d %H:%M"), "today": today.isoformat(),
             "models": {"extract": config.EXTRACT_MODEL, "judge": config.JUDGE_MODEL}}
    _save("stats.json", stats)
    print(json.dumps(stats, indent=1))
    if model:
        print(json.dumps(model["evaluation"], indent=1))
        print("coefficients:", model["coefficients"][:10])
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in mk.items()}, indent=1))
    print("\nTop 5:", [(r["ticker"], r["score"], r["grade"], r["n"]) for r in board["companies"][:5]])
    print("Bottom 5:", [(r["ticker"], r["score"], r["grade"], r["n"]) for r in board["companies"][-5:]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["extract", "judge", "forecast", "build", "all"])
    ap.add_argument("--tickers", nargs="*")
    ap.add_argument("--today", default=None)
    a = ap.parse_args()
    today = date.fromisoformat(a.today) if a.today else date.today()
    calls = transcripts.load_calls(a.tickers)
    t0 = time.time()
    if a.stage in ("extract", "all"):
        stage_extract(calls)
    if a.stage in ("judge", "all"):
        stage_judge(calls, a.tickers)
    if a.stage in ("forecast", "all"):
        stage_forecast(calls, a.tickers)
    if a.stage in ("build", "all"):
        stage_build(calls, a.tickers, today)
    print(f"\n[{a.stage}] done in {time.time() - t0:.0f}s | Meta API usage: {llm.USAGE}")
    if llm.USAGE["calls"]:
        u = _load("usage.json", {})
        u[a.stage] = {k: u.get(a.stage, {}).get(k, 0) + v for k, v in llm.USAGE.items()}
        _save("usage.json", u)


if __name__ == "__main__":
    main()
