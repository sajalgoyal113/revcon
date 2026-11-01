"""Indian fiscal calendar (FY ends 31 March) and period-label parsing.

FY26 = 1 Apr 2025 .. 31 Mar 2026.  Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar.
Also supports Calendar Year (CY) quarters/halves/years, quarter ranges (resolving to the end
of the range), month-year strings (e.g. MAR2026, DEC'26, 2026-03), and text-based timeframe
inference when the structured period field is omitted.
"""
import calendar
import re
from datetime import date, timedelta

# Results are filed within 45 days of quarter end (60 days for Q4/annual) under SEBI LODR.
QUARTER_LAG_DAYS = 45
ANNUAL_LAG_DAYS = 60

_MON_MAP = {
    "JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6,
    "JUL": 7, "JULY": 7, "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OCT": 10, "OCTOBER": 10, "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12,
}


def fy_of(d):
    return d.year + 1 if d.month >= 4 else d.year


def quarter_end(fy, q):
    """Calendar end date of fiscal quarter q (1-4) of fiscal year fy."""
    return {1: date(fy - 1, 6, 30), 2: date(fy - 1, 9, 30),
            3: date(fy - 1, 12, 31), 4: date(fy, 3, 31)}[q]


def cy_quarter_end(cy, q):
    """Calendar end date of calendar quarter q (1-4) of calendar year cy."""
    return {1: date(cy, 3, 31), 2: date(cy, 6, 30),
            3: date(cy, 9, 30), 4: date(cy, 12, 31)}[q]


def quarter_of(d):
    """(fy, q) containing date d."""
    fy = fy_of(d)
    q = {4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 3, 11: 3, 12: 3, 1: 4, 2: 4, 3: 4}[d.month]
    return fy, q


def last_reported_quarter(call_date):
    """The quarter an earnings call held on call_date discusses (the one just ended)."""
    fy, q = quarter_of(call_date)
    q -= 1
    if q == 0:
        fy, q = fy - 1, 4
    return fy, q


def _fy(num, ref_fy):
    n = int(num)
    if n < 100:
        n += 2000
    return n if abs(n - ref_fy) <= 15 else None


def parse_period(label, call_date):
    """Normalise a model-produced period label into a deadline.
    Returns dict(kind, fy, q, end, report_by) or None for vague periods.
    kind: 'FY' | 'Q' | 'H' | 'DATE' | 'MULTI_YEAR'
    end: last day of the promised period; report_by: date by which actuals are public.
    """
    if not label:
        return None
    s = str(label).upper().replace("’", "'").replace("‘", "'").replace(" ", "")
    ref = fy_of(call_date)

    # 1. Quarter range (FY or CY), e.g. Q2FY26-Q4FY26, Q4CY26-Q1CY27 -> deadline is the END quarter
    m = re.search(r"Q([1-4])(FY|CY|')?(\d{2,4})[-–TO]+Q([1-4])(FY|CY|')?(\d{2,4})", s)
    if m:
        q1, cal1, y1, q2, cal2, y2 = int(m.group(1)), m.group(2), m.group(3), int(m.group(4)), m.group(5), m.group(6)
        is_cy = (cal2 == "CY" or (not cal2 and cal1 == "CY"))
        yr = _fy(y2, ref)
        if yr:
            end = cy_quarter_end(yr, q2) if is_cy else quarter_end(yr, q2)
            fy_end, fq_end = quarter_of(end)
            lag = ANNUAL_LAG_DAYS if fq_end == 4 else QUARTER_LAG_DAYS
            return {"kind": "Q", "fy": fy_end, "q": fq_end, "q_start": q1,
                    "end": end, "report_by": end + timedelta(days=lag)}

    # 2. Single Quarter (FY or CY), e.g. Q3FY26, Q3'26, 3QFY26, Q4CY26
    m = re.search(r"Q([1-4])(FY|CY|')?(\d{2,4})", s) or re.search(r"([1-4])Q(FY|CY)?(\d{2,4})", s)
    if m:
        q = int(m.group(1))
        cal_type = m.group(2) or "FY"
        yr = _fy(m.group(3), ref)
        if yr:
            end = cy_quarter_end(yr, q) if cal_type == "CY" else quarter_end(yr, q)
            fy_end, fq_end = quarter_of(end)
            lag = ANNUAL_LAG_DAYS if fq_end == 4 else QUARTER_LAG_DAYS
            return {"kind": "Q", "fy": fy_end, "q": fq_end, "end": end, "report_by": end + timedelta(days=lag)}

    # 3. Half year (FY or CY), e.g. H2FY26, H1CY27, H1'26
    m = re.search(r"H([12])(FY|CY|')?(\d{2,4})", s)
    if m:
        half = int(m.group(1))
        cal_type = m.group(2) or "FY"
        yr = _fy(m.group(3), ref)
        if yr:
            if cal_type == "CY":
                end = date(yr, 6, 30) if half == 1 else date(yr, 12, 31)
                fy_end, fq_end = quarter_of(end)
            else:
                fq_end = 2 if half == 1 else 4
                end = quarter_end(yr, fq_end)
                fy_end = yr
            return {"kind": "H", "fy": fy_end, "q": fq_end, "half": half,
                    "end": end, "report_by": end + timedelta(days=ANNUAL_LAG_DAYS if fq_end == 4 else QUARTER_LAG_DAYS)}

    # 4. Multi-year horizon (FY, CY, or bare years), e.g. "FY25-FY28", "CY26-CY28", "2027-2028", "BYFY30"
    m = re.search(r"(?:FY|CY)?(\d{2,4})[-–TO]+(?:FY|CY)?(\d{2,4})", s)
    if m and not re.match(r"^20\d{2}-\d{2}$", s):
        fy1, fy2 = _fy(m.group(1), ref), _fy(m.group(2), ref)
        if fy2 and (not fy1 or fy2 >= fy1):
            is_cy = "CY" in s
            end = date(fy2, 12, 31) if is_cy else quarter_end(fy2, 4)
            fy_end, fq_end = quarter_of(end)
            return {"kind": "MULTI_YEAR", "fy": fy_end, "fy_start": fy1 or (fy_end - 2), "q": fq_end,
                    "end": end, "report_by": end + timedelta(days=ANNUAL_LAG_DAYS)}

    # 5. Calendar date YYYY-MM, e.g. 2026-03, 2025-12
    m = re.search(r"(20\d{2})-(\d{2})", s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            last_day = calendar.monthrange(y, mo)[1]
            end = date(y, mo, last_day)
            return {"kind": "DATE", "fy": fy_of(end), "q": quarter_of(end)[1],
                    "end": end, "report_by": end + timedelta(days=QUARTER_LAG_DAYS)}

    # 6. Month name + Year, e.g. MAR2026, DEC'26, DECEMBER2025
    m = re.search(r"(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|SEPT|OCTOBER|NOVEMBER|DECEMBER|JAN|FEB|MAR|APR|JUN|JUL|AUG|SEP|OCT|NOV|DEC)['\-]?(20\d{2}|\d{2})\b", s)
    if m:
        mo = _MON_MAP[m.group(1)]
        yr = _fy(m.group(2), ref)
        if yr:
            last_day = calendar.monthrange(yr, mo)[1]
            end = date(yr, mo, last_day)
            return {"kind": "DATE", "fy": fy_of(end), "q": quarter_of(end)[1],
                    "end": end, "report_by": end + timedelta(days=QUARTER_LAG_DAYS)}

    # 7. Fiscal year or Calendar year, e.g. FY26, FY2026, F26, CY26, CY2026, or bare 4-digit year 2026..2035
    m = re.search(r"(FY|F|CY)(\d{2,4})", s)
    if m:
        cal_type = m.group(1)
        yr = _fy(m.group(2), ref)
        if yr:
            end = date(yr, 12, 31) if cal_type == "CY" else quarter_end(yr, 4)
            fy_end, fq_end = quarter_of(end)
            return {"kind": "FY", "fy": fy_end, "q": fq_end, "end": end,
                    "report_by": end + timedelta(days=ANNUAL_LAG_DAYS)}

    m = re.match(r"^(20[23]\d)$", s)
    if m:
        yr = _fy(m.group(1), ref)
        if yr:
            end = quarter_end(yr, 4)
            return {"kind": "FY", "fy": yr, "q": 4, "end": end,
                    "report_by": end + timedelta(days=ANNUAL_LAG_DAYS)}

    return None


def infer_period_from_text(text, call_date):
    """Fallback period inference from summary/quote when the structured period field is null."""
    if not text:
        return None
    t = str(text)
    # Explicit QxFYxx / HxFYxx / FYxx in text
    for pat in (
        r"\b(Q[1-4]\s*(?:FY|CY)?\s*'?\d{2,4})\b",
        r"\b(H[12]\s*(?:FY|CY)?\s*'?\d{2,4})\b",
        r"\b(FY\s*'?\d{2}\s*[-–to]+\s*(?:FY\s*'?)?\d{2})\b",
        r"\b(FY\s*'?\d{2,4})\b",
    ):
        m = re.search(pat, t, re.I)
        if m:
            lbl = re.sub(r"\s+", "", m.group(1))
            per = parse_period(lbl, call_date)
            if per and per["end"] >= call_date:
                return lbl

    # Relative expressions anchored to call_date
    cur_fy = fy_of(call_date)
    fy, q = quarter_of(call_date)
    nfy, nq = (fy, q + 1) if q < 4 else (fy + 1, 1)
    tl = t.lower()
    if re.search(r"\b(next\s+quarter|coming\s+quarter)\b", tl):
        return f"Q{nq}FY{nfy % 100:02d}"
    if re.search(r"\b(this\s+quarter|current\s+quarter)\b", tl):
        return f"Q{q}FY{fy % 100:02d}"
    if re.search(r"\b(this\s+(?:fiscal|financial\s+year|year)|current\s+(?:fiscal|financial\s+year|year))\b", tl):
        return f"FY{cur_fy % 100:02d}"
    if re.search(r"\b(next\s+(?:fiscal|financial\s+year|year)|coming\s+(?:fiscal|financial\s+year|year)|next\s+12\s+months|within\s+12\s+months)\b", tl):
        return f"FY{(cur_fy + 1) % 100:02d}"
    return None


def months_between(a, b):
    return (b.year - a.year) * 12 + (b.month - a.month) + (b.day - a.day) / 30.0
