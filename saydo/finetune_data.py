"""Build SFT data to distil Muse (teacher) into an open Llama student.

Task "extract": transcript chunk -> verified promise JSON (teacher = muse-spark outputs that
passed the verbatim-quote verifier, so the student learns only grounded extractions).

Split is by TIME (calls before the cutoff train, later calls evaluate) so the eval measures
generalisation to calls the student has never seen.

  python -m saydo.finetune_data --cutoff 2026-04-01
Writes data/out/sft_train.jsonl, data/out/sft_eval.jsonl (chat-format messages).
"""
import argparse
import json
import os

from . import config, extract, transcripts

STUDENT_SYSTEM = ("Extract every forward-looking commitment made by company management in this "
                  "earnings-call excerpt. Return JSON {\"promises\": [{quote, speaker, role, category, "
                  "summary, value_low, value_high, unit, direction, growth_basis, segment, period, "
                  "strength, conditions, reiteration, verifiable_by}]}. Quotes must be verbatim.")
KEEP = ["quote", "speaker", "role", "category", "summary", "value_low", "value_high", "unit", "direction",
        "growth_basis", "segment", "period", "strength", "conditions", "reiteration", "verifiable_by"]


def build(cutoff):
    raw = json.load(open(os.path.join(config.OUT, "promises.json")))
    calls = {c.id: c for cs in transcripts.load_calls().values() for c in cs}
    train, ev = [], []
    for cid, r in raw.items():
        c = calls.get(cid)
        if not c:
            continue
        by_chunk = {}
        for p in r["promises"]:
            by_chunk.setdefault(p.get("chunk", 0), []).append({k: p.get(k) for k in KEEP})
        for i, ch in enumerate(c.chunks()):
            user = f"Company: {c.ticker}. {extract._calendar(c)}\n<<<\n{ch}\n>>>"
            ex = {"call_id": cid, "chunk": i, "messages": [
                {"role": "system", "content": STUDENT_SYSTEM},
                {"role": "user", "content": user},
                {"role": "assistant", "content": json.dumps({"promises": by_chunk.get(i, [])}, ensure_ascii=False)}]}
            (train if c.date.isoformat() < cutoff else ev).append(ex)
    for name, rows in (("sft_train.jsonl", train), ("sft_eval.jsonl", ev)):
        with open(os.path.join(config.OUT, name), "w") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"train {len(train)} chunks, eval {len(ev)} chunks (cutoff {cutoff})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", default="2026-04-01")
    build(ap.parse_args().cutoff)
