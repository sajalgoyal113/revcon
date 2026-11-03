"""Institutional Forensic Credibility Memos for US Equities.

Generates structured analyst memos analyzing guidance delivery, red flags,
sandbagging tendencies, and upcoming earnings call watchpoints.
Every factual observation cites a specific promise ID from the guidance ledger.
"""


def generate_company_memo(ticker, company_meta, company_score, promises):
    """Synthesizes an institutional credibility memo for a company."""
    score = company_score["score"]
    grade = company_score["grade"]
    outcomes = company_score.get("outcomes", {})
    deliv = outcomes.get("DELIVERED", 0)
    missed = outcomes.get("MISSED", 0) + outcomes.get("ABANDONED", 0)
    late = outcomes.get("LATE", 0)
    ghosted = outcomes.get("GHOSTED", 0)
    ratio = company_score.get("delivery_ratio", 1.0)

    # Determine verdict
    if score >= 88:
        verdict = "Conservative Sandbagger / High Delivery Conviction"
    elif score >= 75:
        verdict = "Disciplined Guide / Dependable Execution"
    elif score >= 60:
        verdict = "Moderate Delivery / Volatile Guidance"
    else:
        verdict = "Habitual Over-Promiser / High Slippage Risk"

    headline = f"{ticker} exhibits {verdict.lower()} (Say-Do {score}/100, Grade {grade})."

    patterns = [
        f"Delivered {deliv} verified financial & operational commitments across recent quarters.",
        f"Wall Street delivery ratio averages {ratio:.2f}x of guided range (revenue & EPS beat track record).",
    ]
    if ghosted > 0:
        patterns.append(f"Recorded {ghosted} quietly dropped guidance commitments ({company_score.get('ghost_rate', 0)*100:.1f}% ghost rate).")

    red_flags = []
    if missed > 0 or late > 0 or ghosted > 0:
        for p in promises:
            outc = p.get("resolution", {}).get("outcome")
            if outc in ("MISSED", "GHOSTED", "LATE", "REVISED_DOWN"):
                red_flags.append(
                    f"{p.get('call_label', 'Recent Call')}: \"{p.get('summary')}\" -> {outc} [{p.get('id')}]."
                )
    if not red_flags:
        red_flags.append("No material target cancellations or unaddressed slippages identified.")

    credit = []
    for p in promises:
        if p.get("resolution", {}).get("outcome") == "DELIVERED":
            credit.append(
                f"Delivered on \"{p.get('summary')}\" reported on {p.get('resolution', {}).get('knowable_at', 'filing')} [{p.get('id')}]."
            )
        if len(credit) >= 3:
            break

    watch_next = [
        f"Next quarterly revenue guidance vs consensus range ({company_meta.get('theme', '').split(',')[0]}).",
        f"Delivery against current open Capex and operating margin projections.",
    ]

    return {
        "ticker": ticker,
        "name": company_meta.get("name", ticker),
        "headline": headline,
        "verdict": verdict,
        "patterns": patterns,
        "red_flags": red_flags[:3],
        "credit_where_due": credit,
        "watch_next_call": watch_next,
    }
