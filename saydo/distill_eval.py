"""Compare the fine-tuned Llama student (served on Baseten or Modal) against the Muse teacher
on held-out calls: promise recall/precision (quote overlap), category agreement, latency.

  SAYDO_STUDENT_URL=https://model-xxxx.api.baseten.co/environments/production/sync/v1 \
  SAYDO_STUDENT_KEY=... python -m saydo.distill_eval --n 40
"""
import argparse
import json
import os
import time

from openai import OpenAI

from . import config, llm, transcripts


def _match(a, b):
    na, nb = transcripts.norm(a)[:80], transcripts.norm(b)[:80]
    return bool(na) and bool(nb) and (na[:50] in transcripts.norm(b) or nb[:50] in transcripts.norm(a))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--model", default=os.environ.get("SAYDO_STUDENT_MODEL", "saydo-student"))
    a = ap.parse_args()
    cli = OpenAI(base_url=os.environ["SAYDO_STUDENT_URL"], api_key=os.environ["SAYDO_STUDENT_KEY"], timeout=300)
    rows = [json.loads(l) for l in open(os.path.join(config.OUT, "sft_eval.jsonl"))][:a.n]
    tp = fp = fn = cat_ok = 0
    lat, valid = [], 0
    for r in rows:
        teacher = json.loads(r["messages"][2]["content"])["promises"]
        t0 = time.time()
        out = cli.chat.completions.create(model=a.model, messages=r["messages"][:2], max_tokens=4000, temperature=0)
        lat.append(time.time() - t0)
        parsed = llm.parse_json(out.choices[0].message.content) or {}
        student = parsed.get("promises", []) if isinstance(parsed, dict) else []
        valid += bool(parsed)
        used = set()
        for s in student:
            j = next((i for i, t in enumerate(teacher) if i not in used and _match(s.get("quote", ""), t["quote"])), None)
            if j is None:
                fp += 1
            else:
                used.add(j)
                tp += 1
                cat_ok += s.get("category") == teacher[j]["category"]
        fn += len(teacher) - len(used)
    p, rc = tp / max(1, tp + fp), tp / max(1, tp + fn)
    res = {"chunks": len(rows), "json_valid": valid / max(1, len(rows)), "precision_vs_teacher": round(p, 3),
           "recall_vs_teacher": round(rc, 3), "f1": round(2 * p * rc / max(1e-9, p + rc), 3),
           "category_agreement": round(cat_ok / max(1, tp), 3),
           "median_latency_s": round(sorted(lat)[len(lat) // 2], 2) if lat else None}
    json.dump(res, open(os.path.join(config.OUT, "distill_eval.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
