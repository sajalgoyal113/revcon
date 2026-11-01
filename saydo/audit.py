"""Human audit of the Muse judge: measure accuracy instead of assuming it.

  python -m saydo.audit sample --n 50     # writes data/out/audit.csv (stratified by outcome)
  # open the CSV, fill `human_outcome` (same vocabulary) for each row after reading both quotes
  python -m saydo.audit score             # agreement overall and per outcome -> data/out/audit.json
"""
import argparse
import csv
import json
import os
import random

from . import config

FIELDS = ["id", "ticker", "said_on", "promise", "by", "said_quote", "model_outcome", "model_why",
          "evidence_call", "evidence_quote", "human_outcome", "notes"]


def sample(n):
    r = json.load(open(os.path.join(config.OUT, "resolved.json")))
    pool = [p for p in r if p["resolution"].get("y") is not None and p["verifiable_by"] == "disclosure"]
    by = {}
    for p in pool:
        by.setdefault(p["resolution"]["outcome"], []).append(p)
    rng = random.Random(11)
    per = max(1, n // max(1, len(by)))
    pick = [p for ps in by.values() for p in rng.sample(ps, min(per, len(ps)))]
    with open(os.path.join(config.OUT, "audit.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        for p in pick:
            z = p["resolution"]
            ev = (z.get("evidence") or [{}])[-1]
            w.writerow({"id": p["id"], "ticker": p["ticker"], "said_on": p["call_label"], "promise": p["summary"],
                        "by": p.get("period"), "said_quote": p["quote"], "model_outcome": z["outcome"],
                        "model_why": z.get("why"), "evidence_call": ev.get("call_label"),
                        "evidence_quote": ev.get("evidence_quote"), "human_outcome": "", "notes": ""})
    print(f"wrote {len(pick)} rows to data/out/audit.csv")


def score():
    rows = list(csv.DictReader(open(os.path.join(config.OUT, "audit.csv"))))
    done = [r for r in rows if r["human_outcome"].strip()]
    kept = lambda o: o.strip().upper() in ("DELIVERED",)
    exact = sum(r["human_outcome"].strip().upper() == r["model_outcome"] for r in done)
    binary = sum(kept(r["human_outcome"]) == kept(r["model_outcome"]) for r in done)
    per = {}
    for r in done:
        d = per.setdefault(r["model_outcome"], [0, 0])
        d[0] += r["human_outcome"].strip().upper() == r["model_outcome"]
        d[1] += 1
    res = {"labelled": len(done), "exact_agreement": round(exact / max(1, len(done)), 3),
           "kept_vs_not_agreement": round(binary / max(1, len(done)), 3),
           "per_model_outcome": {k: f"{a}/{b}" for k, (a, b) in per.items()}}
    json.dump(res, open(os.path.join(config.OUT, "audit.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "score"])
    ap.add_argument("--n", type=int, default=50)
    a = ap.parse_args()
    sample(a.n) if a.cmd == "sample" else score()
