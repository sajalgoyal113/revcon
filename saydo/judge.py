"""DO (disclosure side): follow every open promise through the company's LATER calls.

For each later call we hand Muse the full transcript plus the list of earlier promises still
open, and ask for a status per promise with a verbatim evidence quote. Evidence quotes are
verified against the later transcript; unverifiable evidence is downgraded to NOT_MENTIONED.

This produces a status timeline per promise (e.g. ON_TRACK -> DELAYED -> DELIVERED), which
resolve.py turns into a final outcome and the "goalpost-moving" signal.
"""
import concurrent.futures as cf
from datetime import date, timedelta

from . import config, llm, transcripts

STATUSES = ["DELIVERED", "ON_TRACK", "DELAYED", "REVISED_DOWN", "REVISED_UP", "MISSED", "ABANDONED",
            "NOT_MENTIONED"]
# When a long transcript is judged in two halves, keep the most informative status
_PRIORITY = {s: i for i, s in enumerate(
    ["DELIVERED", "MISSED", "ABANDONED", "REVISED_DOWN", "DELAYED", "REVISED_UP", "ON_TRACK", "NOT_MENTIONED"])}
OPEN_WINDOW_DAYS = 240      # keep tracking a promise this long past its deadline
MAX_AGE_DAYS = 540          # undated promises are tracked for ~6 quarters
BATCH = 18

SYSTEM = """You are a forensic analyst checking whether company management kept earlier promises.
You get (1) a list of promises management made on EARLIER earnings calls and (2) the transcript
of a LATER call. For EVERY promise, decide what THIS later call says about it:

DELIVERED     management explicitly confirms it is concretely done, achieved, commissioned, or launched.
              - NO DELIVERED before the promised window or deadline period! If a target is for a future period
                (e.g. FY28, FY30, or multi-year horizon), early progress, intermediate capex spend, or initial tranches
                are strictly ON_TRACK, NOT DELIVERED.
              - Discrete completion milestones (e.g. closing an asset sale, securing a regulatory approval/document,
                closing a transaction, reaching a ceiling like leverage < 3.0x within 12 months) that are concretely
                achieved within the guided timeframe are DELIVERED.
              - Outperformance / exceeding beneficial guidance: if the metric is beneficial (e.g. impairment write-back/recovery,
                cost savings, debt reduction, asset sale proceeds, lower borrowing rate), delivering a BETTER or HIGHER number
                (e.g. INR 83 Cr reversal vs INR 50-60 Cr guided, or net debt down further than targeted) is strictly DELIVERED,
                NEVER MISSED. Outperforming guidance in a favorable direction is full delivery.
              - Substantial completion rule: for multi-step capital projects, mark DELIVERED only if management
                confirms concrete operational completion (e.g. commercial production has started or primary facility is live).
              - Continuation rule: ongoing multi-year commitments remain ON_TRACK during active phases and are only
                DELIVERED upon concrete completion at the conclusion of the targeted horizon.
ON_TRACK      reiterated or concrete progress reported, not yet complete, or within an ongoing multi-year commitment, no delay admitted.
DELAYED       timeline pushed out, "taking longer", "now expected in <later period>"
REVISED_DOWN  target/number/scope lowered (e.g. growth guidance cut from 25% to 18%)
REVISED_UP    target raised
MISSED        admits the target was not met or period ended without achieving the target. Intermediate work still in progress while timeline is open is DELAYED, NOT MISSED.
ABANDONED     dropped, cancelled, deprioritised, "no longer pursuing"
NOT_MENTIONED this call says nothing about it

SPEAKER ATTRIBUTION RULES (CRITICAL):
- The evidence quote MUST come strictly from COMPANY MANAGEMENT (executives: CEO, CFO, MD, COO, Chairman, etc.).
- Analyst questions, comments, or moderator/operator statements (e.g., questions asking "did you spend X?" or inquiries
  ending in "?") are NOT evidence. If an analyst brings up a topic but management does not concretely confirm delivery in their
  reply, mark NOT_MENTIONED. Delivery proof must come strictly from management's mouth.

Be strict: only DELIVERED if management clearly and concretely confirms completion in the promised window. Early progress is ON_TRACK.
Judge what management SAYS in this call; do not use outside knowledge.
Return JSON {"results": [{"id": "...", "status": "...",
  "evidence_quote": "EXACT verbatim sentence(s) of MANAGEMENT speech from the LATER transcript, or null if NOT_MENTIONED",
  "new_value": number or null (revised/achieved figure if stated), "new_period": "e.g. Q1FY27 or null",
  "note": "<=20 words why"}]}"""


def _promise_line(p):
    val = ""
    if p.get("value_low") is not None:
        lo, hi = p["value_low"], p.get("value_high")
        val = f" | value: {lo:g}" + (f"-{hi:g}" if hi not in (None, lo) else "") + f" {p.get('unit') or ''}"
    return (f'- id={p["id"]} | made {p["call_label"]} | {p["category"]} | "{p["summary"]}"'
            f'{val} | by: {p.get("period") or "no date"}')


def open_promises(promises, ticker, at):
    """Earlier promises of `ticker` that are still worth tracking on a call held on `at`."""
    out = []
    for p in promises:
        if p["ticker"] != ticker:
            continue
        made = date.fromisoformat(p["call_date"])
        if made >= at:
            continue
        if p.get("deadline"):
            if date.fromisoformat(p["deadline"]) + timedelta(days=OPEN_WINDOW_DAYS) < at:
                continue
        elif (at - made).days > MAX_AGE_DAYS:
            continue
        out.append(p)
    return out


def judge_call(call, promises):
    """Statuses of `promises` (made earlier) as of this later call."""
    if not promises:
        return []
    halves = call.chunks(size=60000, overlap=2000)
    merged = {}
    for b in range(0, len(promises), BATCH):
        batch = promises[b:b + BATCH]
        plist = "\n".join(_promise_line(p) for p in batch)
        for hi, part in enumerate(halves):
            user = (f"Company: {call.ticker}. LATER call: {call.label}.\n\nEARLIER PROMISES:\n{plist}\n\n"
                    f"LATER TRANSCRIPT (part {hi + 1}/{len(halves)}):\n<<<\n{part}\n>>>")
            out = llm.chat_json(SYSTEM, user, model=config.JUDGE_MODEL, max_tokens=14000)
            for r in (out or {}).get("results", []) if isinstance(out, dict) else []:
                pid, st = r.get("id"), str(r.get("status", "")).upper()
                if pid not in {p["id"] for p in batch} or st not in STATUSES:
                    continue
                if st != "NOT_MENTIONED":
                    v = transcripts.verify_quote(r.get("evidence_quote") or "", call.text_norm)
                    if not v:
                        st = "NOT_MENTIONED"   # evidence must exist in the later call
                    r["quote_check"] = v
                rec = {"promise_id": pid, "call_id": call.id, "call_date": call.date.isoformat(),
                       "call_label": call.label, "status": st,
                       "evidence_quote": r.get("evidence_quote") if st != "NOT_MENTIONED" else None,
                       "new_value": r.get("new_value"), "new_period": r.get("new_period"),
                       "note": r.get("note")}
                prev = merged.get(pid)
                if prev is None or _PRIORITY[st] < _PRIORITY[prev["status"]]:
                    merged[pid] = rec
    # Promises the model skipped count as not mentioned
    for p in promises:
        merged.setdefault(p["id"], {"promise_id": p["id"], "call_id": call.id,
                                    "call_date": call.date.isoformat(), "call_label": call.label,
                                    "status": "NOT_MENTIONED", "evidence_quote": None})
    return list(merged.values())


def judge_all(calls_by_ticker, promises, workers=None):
    jobs = []
    for t, calls in calls_by_ticker.items():
        for c in calls:
            ops = open_promises(promises, t, c.date)
            if ops:
                jobs.append((c, ops))
    evidence = []
    with cf.ThreadPoolExecutor(workers or config.CONCURRENCY) as ex:
        futs = {ex.submit(judge_call, c, ops): (c, ops) for c, ops in jobs}
        for n, f in enumerate(cf.as_completed(futs), 1):
            c, ops = futs[f]
            try:
                ev = f.result()
            except Exception as e:
                print(f"   [judge] {c.id} failed: {e}")
                continue
            evidence.extend(ev)
            moved = sum(1 for e in ev if e["status"] != "NOT_MENTIONED")
            print(f"   [{n}/{len(jobs)}] {c.id}: {len(ops)} open promises, {moved} with evidence", flush=True)
    return evidence
