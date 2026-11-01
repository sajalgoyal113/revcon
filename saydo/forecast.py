"""Gemini 3.8 / Frontier LLM as a forecaster: P(this promise will be kept in full and on time),
judged from the promise itself at the moment it was made (language, ambition, conditions, horizon,
and trailing financial trajectory).

Leakage control: company names/tickers are masked and no later information is given.
"""
import concurrent.futures as cf
import re

from . import config, financials, llm

SYSTEM = """You are an institutional equity research analyst auditing Indian corporate management credibility.
For each management promise/guidance below (company anonymised as [CO]), estimate the probability (0.0 to 1.0)
that management will deliver it IN FULL and ON TIME.
Evaluate:
1. Specificity & quantitative grounding vs vague aspirational hand-waving
2. Ambition vs trailing financial capacity (stretch vs lay-up)
3. Management hedging language ('attempting', 'subject to', 'market conditions', 'hopefully')
4. Horizon duration and external supply chain / execution dependencies
Base rate: approximately 35-45% of earnings call commitments are fully kept on schedule.
Return JSON {"forecasts": [{"id": "...", "p": 0.0-1.0, "reason": "<=15 words explaining key driver"}]}"""
BATCH = 25


def _mask(text, names):
    for n in names:
        if n and len(n) > 2:
            text = re.sub(re.escape(n), "[CO]", text, flags=re.I)
    return text


def _names(ticker, snaps):
    nm = (snaps.get(ticker) or {}).get("name", "")
    words = [w for w in re.split(r"\s+", nm) if w.lower() not in ("ltd", "limited", "india", "of", "the", "&", "and")]
    return [ticker, nm, " ".join(words[:2]), words[0] if words else ""]


def forecast_all(promises, snaps, workers=4):
    groups = {}
    for p in promises:
        groups.setdefault(p["ticker"], []).append(p)
    jobs = []
    acts = {t: financials.Actuals(s) for t, s in snaps.items() if s}
    for t, ps in groups.items():
        names = _names(t, snaps)
        act = acts.get(t)
        for b in range(0, len(ps), BATCH):
            jobs.append((names, ps[b:b + BATCH], act))

    def run(job):
        names, ps, act = job
        lines = []
        for p in ps:
            val = f"{p['value_low']:g}{'-' + format(p['value_high'], 'g') if p.get('value_high') not in (None, p['value_low']) else ''} {p.get('unit') or ''}" \
                if p.get("value_low") is not None else "n/a"
            context_note = ""
            if act is not None and p.get("call_date"):
                import datetime
                try:
                    c_date = datetime.date.fromisoformat(p["call_date"])
                    tg = act.trailing_growth(c_date)
                    tm = act.trailing_opm(c_date)
                    if tg is not None:
                        context_note += f" | trailing 3Y growth ~{tg:.0f}%"
                    if tm is not None:
                        context_note += f" | trailing margin ~{tm:.1f}%"
                except Exception:
                    pass
            lines.append(f'- id={p["id"]} | {p["category"]} | promised on call in {p["call_date"][:7]} | '
                         f'by {p.get("period") or "no date"} | value {val}{context_note} | {p.get("strength")} | '
                         f'speaker {p.get("role")} | section {p.get("section")} | conditions: {p.get("conditions") or "none"}\n'
                         f'  quote: "{_mask(p["quote"], names)}"')
        out = llm.chat_json(SYSTEM, "PROMISES:\n" + "\n".join(lines), model=config.EXTRACT_MODEL, max_tokens=10000)
        res = {}
        for f in (out or {}).get("forecasts", []) if isinstance(out, dict) else []:
            try:
                res[f["id"]] = max(0.0, min(1.0, float(f["p"])))
            except (KeyError, TypeError, ValueError):
                continue
        return res

    allres = {}
    with cf.ThreadPoolExecutor(workers) as ex:
        for i, r in enumerate(ex.map(run, jobs), 1):
            allres.update(r)
            if i % 10 == 0:
                print(f"   [forecast] {i}/{len(jobs)} batches", flush=True)
    return allres
