"""Reported actuals ('the Do') from Screener.in: quarterly + annual P&L and price history.

Snapshots are cached to data/financials/<TICKER>.json so the pipeline is reproducible offline.
Caveat (stated in README): Screener serves restated figures, so a small restatement residual
remains versus what was printed on the original results date.
"""
import json
import os
import re
import time
from datetime import date

from . import config, periods

_MON = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
# Screener row names differ for banks/NBFCs ("Revenue", "Financing Profit")
# Transcript folder name -> current Screener symbol (renames)
ALIASES = {"AMARAJABAT": "ARE&M"}
_ROWS = {
    "sales": ["Sales", "Revenue", "Revenue from Operations"],
    "op_profit": ["Operating Profit", "Financing Profit"],
    "opm": ["OPM %", "Financing Margin %"],
    "pat": ["Net Profit", "Profit after tax"],
    "eps": ["EPS in Rs"],
}


def _num(s):
    s = str(s).replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _session():
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) SayDo-research"
    return s


def _table(soup, sec_id):
    sec = soup.find("section", id=sec_id)
    if not sec or not sec.find("table"):
        return [], {}
    tb = sec.find("table")
    heads = [th.text.strip() for th in tb.find_all("th")][1:]
    rows = {}
    for tr in tb.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        name = re.sub(r"[\s\xa0+]+$", "", re.sub(r"\s+", " ", tds[0].text.replace("\xa0", " "))).strip()
        rows[name] = [_num(td.text) for td in tds[1:]]
    return heads, rows


def _pick(rows, key):
    for name in _ROWS[key]:
        if name in rows:
            return rows[name]
    return []


def _parse(heads, rows, annual):
    out = {}
    cols = {k: _pick(rows, k) for k in _ROWS}
    for i, h in enumerate(heads):
        m = re.match(r"([A-Za-z]{3})\s+(\d{4})", h)
        if not m:
            continue
        mon, yr = _MON[m.group(1).lower()], int(m.group(2))
        end = date(yr, mon, 28)
        fy, q = periods.quarter_of(end)
        if annual and mon != 3:
            continue  # partial / changed fiscal year
        key = str(fy) if annual else f"{fy}Q{q}"
        rec = {k: (v[i] if i < len(v) else None) for k, v in cols.items()}
        if rec.get("sales") is None:
            continue
        # Screener prints OPM rounded to whole %; recompute it precisely where possible
        if rec.get("op_profit") is not None and rec["sales"]:
            rec["opm"] = round(rec["op_profit"] / rec["sales"] * 100, 2)
        if rec.get("pat") is not None and rec["sales"]:
            rec["npm"] = rec["pat"] / rec["sales"] * 100
        out[key] = rec
    return out


def fetch(ticker, refresh=False):
    path = os.path.join(config.FINANCIALS, f"{ticker}.json")
    if os.path.exists(path) and not refresh:
        try:
            with open(path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached.get("quarters") or cached.get("annual") or cached.get("prices"):
                return cached
        except Exception:
            pass
    if os.environ.get("SAYDO_OFFLINE", "0") == "1":
        return None
    try:
        from bs4 import BeautifulSoup
        s = _session()
    except Exception:
        return None
    slug = ALIASES.get(ticker, ticker).replace("&", "%26")
    snap = None
    for url in (f"https://www.screener.in/company/{slug}/consolidated/", f"https://www.screener.in/company/{slug}/"):
        r = None
        for attempt in range(2):
            try:
                r = s.get(url, timeout=5)
            except Exception:
                r = None
                break
            if r is not None and r.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            break
        if r is None or r.status_code != 200:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        qh, qr = _table(soup, "quarters")
        ah, ar = _table(soup, "profit-loss")
        quarters, annual = _parse(qh, qr, False), _parse(ah, ar, True)
        if len(quarters) < 4 and not annual:
            continue  # consolidated page empty for standalone-only companies
        m = re.search(r'data-company-id="(\d+)"', r.text)
        h1 = soup.find("h1")
        snap = {"ticker": ticker, "name": h1.text.strip() if h1 else ticker, "source": url,
                "fetched": date.today().isoformat(), "company_id": m.group(1) if m else None,
                "quarters": quarters, "annual": annual, "prices": []}
        break
    if not snap:
        return None
    if snap["company_id"]:
        try:
            j = s.get(f"https://www.screener.in/api/company/{snap['company_id']}/chart/?q=Price&days=1825",
                      timeout=5).json()
            for ds in j.get("datasets", []):
                if ds.get("metric") == "Price":
                    snap["prices"] = [[d, float(p)] for d, p in ds["values"]]
        except Exception:
            pass
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=1)
    time.sleep(0.5)
    return snap


class Actuals:
    """Point-in-time aware accessor over a financial snapshot."""

    def __init__(self, snap):
        self.snap = snap or {"quarters": {}, "annual": {}, "prices": []}
        self.q = self.snap.get("quarters", {})
        self.a = self.snap.get("annual", {})

    def quarter(self, fy, q):
        return self.q.get(f"{fy}Q{q}")

    def year(self, fy):
        rec = self.a.get(str(fy))
        if rec:
            return rec
        qs = [self.quarter(fy, i) for i in (1, 2, 3, 4)]
        if all(qs):  # build from quarters if the annual column is missing
            sales = sum(x["sales"] for x in qs)
            pat = sum((x.get("pat") or 0) for x in qs)
            op = sum((x.get("op_profit") or 0) for x in qs)
            return {"sales": sales, "pat": pat, "op_profit": op, "opm": op / sales * 100 if sales else None,
                    "npm": pat / sales * 100 if sales else None}
        return None

    def half(self, fy, half):
        qs = [self.quarter(fy, i) for i in ((1, 2) if half == 1 else (3, 4))]
        if not all(qs):
            return None
        sales = sum(x["sales"] for x in qs)
        op = sum((x.get("op_profit") or 0) for x in qs)
        pat = sum((x.get("pat") or 0) for x in qs)
        return {"sales": sales, "op_profit": op, "pat": pat,
                "opm": op / sales * 100 if sales else None, "npm": pat / sales * 100 if sales else None}

    def period(self, p):
        """(current, prior-year comparable) records for a parsed period dict."""
        if p["kind"] in ("FY", "MULTI_YEAR"):
            return self.year(p["fy"]), self.year(p["fy"] - 1)
        if p["kind"] == "H":
            return self.half(p["fy"], p["half"]), self.half(p["fy"] - 1, p["half"])
        return self.quarter(p["fy"], p["q"]), self.quarter(p["fy"] - 1, p["q"])

    def _available_quarter(self, asof=None):
        """Find the latest reported quarter strictly knowable on or before `asof`."""
        if asof is None:
            asof = date.today()
        elif isinstance(asof, str):
            asof = date.fromisoformat(asof)
        avail = sorted([(int(k[:4]), int(k[-1])) for k in self.q.keys()
                        if len(k) == 6 and k[:4].isdigit() and k[-1].isdigit()
                        and periods.quarter_end(int(k[:4]), int(k[-1])) <= asof])
        if avail:
            return avail[-1]
        all_q = sorted([(int(k[:4]), int(k[-1])) for k in self.q.keys()
                        if len(k) == 6 and k[:4].isdigit() and k[-1].isdigit()])
        return all_q[-1] if all_q else None

    def trailing_growth(self, asof=None):
        """Revenue growth of the last 4 reported quarters vs the 4 before, knowable at `asof`."""
        if asof is None:
            asof = date.today()
        elif isinstance(asof, str):
            asof = date.fromisoformat(asof)
        latest = self._available_quarter(asof)
        if latest:
            fy, q = latest
            keys = []
            for _ in range(8):
                keys.append((fy, q))
                q -= 1
                if q == 0:
                    fy, q = fy - 1, 4
            recs = [self.quarter(f, x) for f, x in keys]
            if all(recs):
                cur, prev = sum(r["sales"] for r in recs[:4]), sum(r["sales"] for r in recs[4:])
                if prev > 0:
                    return (cur / prev - 1) * 100
        # Fallback to annual series knowable on or before asof
        avail_fy = sorted([int(y) for y in self.a.keys() if str(y).isdigit() and date(int(y), 3, 31) <= asof])
        if not avail_fy:
            avail_fy = sorted([int(y) for y in self.a.keys() if str(y).isdigit()])
        if len(avail_fy) >= 2:
            c_rec, p_rec = self.a.get(str(avail_fy[-1])), self.a.get(str(avail_fy[-2]))
            if c_rec and p_rec and (p_rec.get("sales") or 0) > 0:
                return (c_rec["sales"] / p_rec["sales"] - 1) * 100
        return self.snap.get("trailing_growth")

    def trailing_opm(self, asof=None):
        if asof is None:
            asof = date.today()
        elif isinstance(asof, str):
            asof = date.fromisoformat(asof)
        latest = self._available_quarter(asof)
        if latest:
            rec = self.quarter(*latest)
            if rec and rec.get("opm") is not None:
                return rec.get("opm")
        avail_fy = sorted([int(y) for y in self.a.keys() if str(y).isdigit() and date(int(y), 3, 31) <= asof])
        if not avail_fy:
            avail_fy = sorted([int(y) for y in self.a.keys() if str(y).isdigit()])
        if avail_fy:
            rec = self.a.get(str(avail_fy[-1]))
            if rec and rec.get("opm") is not None:
                return rec.get("opm")
        return self.snap.get("trailing_opm")

    def latest_sales(self, asof=None):
        """Latest annual sales knowable at `asof` (for converting revenue_target to implied growth)."""
        if asof is None:
            asof = date.today()
        elif isinstance(asof, str):
            asof = date.fromisoformat(asof)
        avail_fy = sorted([int(y) for y in self.a.keys() if str(y).isdigit() and date(int(y), 3, 31) <= asof])
        if not avail_fy:
            avail_fy = sorted([int(y) for y in self.a.keys() if str(y).isdigit()])
        if avail_fy:
            rec = self.a.get(str(avail_fy[-1]))
            if rec and rec.get("sales"):
                return float(rec["sales"])
        return None

    def price_on(self, d):
        """Last close on or before d."""
        best = None
        for ds, p in self.snap.get("prices", []):
            if ds <= d.isoformat():
                best = p
            else:
                break
        return best
