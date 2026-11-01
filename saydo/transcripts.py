"""Load, de-duplicate, date and chunk earnings-call transcripts.

Corpus layout: data/transcripts/<TICKER>/<Mon>_<YYYY>.txt  (filing month; text from BSE PDFs).
"""
import hashlib
import os
import re
from datetime import date, datetime

from . import config, periods

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2}),?\s+(20\d{2})\b", re.I)
_PAGE_RE = re.compile(r"Page\s+\d+\s+of\s+\d+", re.I)
_QA_RE = re.compile(r"(first question|question-and-answer|question and answer session|open the floor|"
                    r"question[- ]and[- ]answer|begin the q&a|q&a session|questions? (?:is|comes) from the line)", re.I)


def norm(text):
    """Normalisation used for verbatim-quote verification (both sides)."""
    t = _PAGE_RE.sub(" ", text or "")
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-")
    return re.sub(r"[^a-z0-9%]+", "", t.lower())


def verify_quote(quote, text_norm):
    """'exact' | 'fuzzy' | None. Anti-hallucination gate: a promise or evidence whose quote
    is not in the transcript is discarded, so the model cannot invent what management said."""
    q = norm(quote)
    if len(q) < 25:
        return None
    if q in text_norm:
        return "exact"
    # PDF line-break / page-header artefacts: accept if most 30-char shingles are present
    step = 30
    parts = [q[i:i + step] for i in range(0, len(q) - step + 1, step)] or [q]
    hits = sum(1 for p in parts if p in text_norm)
    return "fuzzy" if hits / len(parts) >= 0.7 else None


class Call:
    def __init__(self, ticker, path, text, call_date, quarter):
        self.ticker, self.path, self.text = ticker, path, text
        self.date = call_date                    # date of the call
        self.fy, self.q = quarter                # quarter discussed
        self.id = f"{ticker}:{call_date.isoformat()}"
        self.text_norm = norm(text)
        m = _QA_RE.search(text)
        self.qa_start = m.start() if m and m.start() > len(text) * 0.1 else None

    @property
    def label(self):
        return f"Q{self.q}FY{self.fy % 100:02d} call ({self.date:%d %b %Y})"

    def section_of(self, quote):
        """'prepared' or 'qa' for a quote, by position."""
        if self.qa_start is None:
            return "unknown"
        i = self.text.lower().find((quote or "")[:40].lower())
        if i == -1:
            return "unknown"
        return "qa" if i >= self.qa_start else "prepared"

    def chunks(self, size=22000, overlap=1500):
        """Overlapping chunks cut at sentence boundaries."""
        t, out, i = self.text, [], 0
        while i < len(t):
            j = min(len(t), i + size)
            if j < len(t):
                k = t.rfind(". ", i + size - 3000, j)
                j = k + 1 if k != -1 else j
            out.append(t[i:j])
            if j >= len(t):
                break
            i = max(j - overlap, i + 1)
        return out

    def passages(self, size=1400):
        """Small passages for retrieval when checking later calls for evidence."""
        t = _PAGE_RE.sub(" ", self.text)
        sents = re.split(r"(?<=[.?!])\s+", t)
        out, cur = [], ""
        for s in sents:
            if len(cur) + len(s) > size and cur:
                out.append(cur.strip())
                cur = ""
            cur += " " + s
        if cur.strip():
            out.append(cur.strip())
        return out


def _call_date(text, fname):
    """Prefer the call date printed in the transcript; fall back to the filing month."""
    head = text[:6000]
    m_file = re.match(r"([A-Za-z]{3})_(\d{4})", fname)
    file_dt = date(int(m_file.group(2)), MONTHS[m_file.group(1).lower()], 15) if m_file else None
    cands = []
    for m in _DATE_RE.finditer(head):
        try:
            d = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date()
        except ValueError:
            continue
        if file_dt is None or -75 <= (file_dt - d).days <= 75:
            cands.append(d)
    # "results for the quarter ended September 30" is not the call date
    qe = {(3, 31), (6, 30), (9, 30), (12, 31)}
    non_qe = [d for d in cands if (d.month, d.day) not in qe]
    if non_qe or cands:
        # The call precedes the filing letter; the earliest plausible header date is the call.
        return min(non_qe or cands)
    return file_dt


def _quarter(text, call_date):
    # Title formats vary ("Q1 FY '26", "Q1 FY 2025-2026", "Q1FY26"); the call date is reliable
    # because results calls happen within ~60 days of quarter end.
    return periods.last_reported_quarter(call_date)


def load_calls(tickers=None, root=None):
    """{ticker: [Call sorted by date]} with exact-duplicate transcripts removed
    (e.g. AMARAJABAT and ARE&M are the same company after a rename)."""
    root = root or config.TRANSCRIPTS
    seen, out = {}, {}
    for t in sorted(os.listdir(root)):
        d = os.path.join(root, t)
        if not os.path.isdir(d) or (tickers and t not in tickers) or t in config.EXCLUDE:
            continue
        calls = []
        for f in sorted(os.listdir(d)):
            if not f.endswith(".txt"):
                continue
            text = open(os.path.join(d, f), errors="ignore").read()
            if len(text) < 5000:
                continue
            h = hashlib.md5(text.encode()).hexdigest()
            if h in seen:
                continue
            seen[h] = t
            cd = _call_date(text, f)
            if not cd:
                continue
            calls.append(Call(t, os.path.join(d, f), text, cd, _quarter(text, cd)))
        if calls:
            calls.sort(key=lambda c: c.date)
            # Same call filed twice in different months -> keep the first
            uniq = []
            for c in calls:
                if uniq and (c.fy, c.q) == (uniq[-1].fy, uniq[-1].q) and (c.date - uniq[-1].date).days < 20:
                    continue
                uniq.append(c)
            out[t] = uniq
    return out
