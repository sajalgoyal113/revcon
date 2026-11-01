"""Credibility memo: Muse Wonder (Meta frontier reasoning) writes an analyst note from the
company's promise ledger. Every claim must cite promise ids from the ledger; ids that do not
exist are stripped, so the memo cannot invent a track record."""
from . import config, llm

SYSTEM = """You are the head of forensic research at an institutional investor. You receive a
company's PROMISE LEDGER: every forward-looking commitment management made on earnings calls,
and what actually happened (from reported financials or later calls). Write a sharp, fair
credibility memo. Rules: use ONLY the ledger; cite promise ids in square brackets for every
factual claim; distinguish delivered, late, revised-down, missed and quietly-dropped (GHOSTED)
promises; note patterns (e.g. capex timelines slip but margins are delivered; guidance cut
quietly after Q2). No price targets, no buy/sell advice.
Return JSON {"headline": "<=14 words", "verdict": "Reliable|Mostly reliable|Mixed|Unreliable",
 "patterns": ["... [id]"], "red_flags": ["... [id]"], "credit_where_due": ["... [id]"],
 "watch_next_call": ["specific open promise to check, with its deadline [id]"]}"""


def _line(p):
    r = p["resolution"]
    return (f'[{p["id"]}] {p["call_label"]} | {p["category"]} | {p["summary"]} | by {p.get("period") or "-"} '
            f'| {p.get("strength")} | OUTCOME: {r["outcome"]} ({r.get("why", "")})')


def credibility_memo(ticker, resolved, company_score, model=None):
    mine = [p for p in resolved if p["ticker"] == ticker]
    if not mine:
        return None
    # Representatives of repeat-clusters only, resolved first
    reps = [p for p in mine if p.get("repeat_index", 0) == 0]
    reps.sort(key=lambda p: (p["resolution"]["outcome"] == "PENDING", p["call_date"]))
    ledger = "\n".join(_line(p) for p in reps[:160])
    user = (f"Company: {ticker}. Say-Do score {company_score['score']} (grade {company_score['grade']}, "
            f"80% CI {company_score['ci80']}, {company_score['n']} resolved promises; outcomes "
            f"{company_score['outcomes']}).\n\nPROMISE LEDGER:\n{ledger}")
    out = llm.chat_json(SYSTEM, user, model=model or config.FRONTIER_MODEL, max_tokens=12000,
                        reasoning_effort="medium")
    if not isinstance(out, dict):
        return None
    ids = {p["id"] for p in mine}
    import re
    for k in ("patterns", "red_flags", "credit_where_due", "watch_next_call"):
        clean = []
        for s in out.get(k, []) or []:
            cited = [c for grp in re.findall(r"\[([^\]]+)\]", str(s)) for c in re.split(r"[,;]\s*", grp)]
            if cited and all(c.strip() in ids for c in cited):
                clean.append(s)
        out[k] = clean
    out["model"] = model or config.FRONTIER_MODEL
    return out
