"""Fetch transcripts and financials for the expansion universe to reach 100 companies.
Multi-threaded with 8 workers for fast concurrent downloading.
"""
import concurrent.futures as cf
import io
import os
import re
import sys
import time
import requests
import pypdf
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from saydo import config, financials

NEW_TICKERS = [
    # IT & Software
    "TCS", "INFY", "HCLTECH", "TECHM", "WIPRO", "TATAELXSI", "NEWGEN", "ZENSARTECH", "CYIENT", "ROUTE",
    # Auto & Ancillaries
    "MARUTI", "BAJAJ-AUTO", "MOTHERSON", "BHARATFORG", "EXIDEIND", "APOLLOTYRE", "CEATLTD", "AMBER",
    # Consumer & Retail
    "TITAN", "DABUR", "MARICO", "GODREJCP", "BRITANNIA", "JYOTHYLAB", "BATAINDIA",
    # Healthcare & Pharma
    "CIPLA", "SUNPHARMA", "DRREDDY", "LUPIN", "AUROPHARMA", "APOLLOHOSP", "MAXHEALTH", "MEDPLUS", "JBCHEPHARM", "ERIS",
    # Capital Goods, Engineering & Industrials
    "LT", "ABB", "SIEMENS", "BHEL", "BEL", "HAL", "MAZDOCK", "COCHINSHIP", "GRSE", "SUZLON",
    "ASTRAL", "SUPREMEIND", "KEI", "TEJASNET", "ELECON", "PRAJIND", "APARINDS", "DATAPATTNS",
    "LEMONTREE", "HFCL", "CROMPTON", "KEC", "CERA",
    # Financial Services, Exchanges, Metals & Chemicals
    "CDSL", "MCX", "MUTHOOTFIN", "TITAGARH", "DLF", "AARTIIND", "PIIND", "NAVINFLUOR"
]


def get_session():
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    return s


def parse_call_month_year(date_str):
    m = re.search(r"([A-Za-z]{3})\s+(\d{4})", date_str)
    if m:
        mon = m.group(1).capitalize()
        yr = m.group(2)
        return f"{mon}_{yr}.txt"
    return None


def fetch_for_ticker(t):
    s = get_session()
    # 1. Financials
    try:
        snap = financials.fetch(t)
    except Exception as e:
        snap = None

    # 2. Concalls from Screener
    urls = [f"https://www.screener.in/company/{t}/consolidated/", f"https://www.screener.in/company/{t}/"]
    calls = []
    for u in urls:
        try:
            r = s.get(u, timeout=6)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                con_div = soup.find("div", class_="concalls")
                if con_div:
                    for li in con_div.find_all("li"):
                        date_div = li.find("div")
                        dt = date_div.text.strip() if date_div else ""
                        for a in li.find_all("a"):
                            if a.text.strip().lower().startswith("transcript"):
                                calls.append((dt, a.get("href")))
                                break
                    if calls:
                        break
        except Exception:
            pass

    t_dir = os.path.join(config.TRANSCRIPTS, t)
    os.makedirs(t_dir, exist_ok=True)

    downloaded = 0
    # Check already existing valid files
    for f in os.listdir(t_dir):
        if f.endswith(".txt") and os.path.getsize(os.path.join(t_dir, f)) > 3000:
            downloaded += 1

    # Download up to 4 recent calls if needed
    for dt, href in calls[:4]:
        if downloaded >= 3:
            break
        fname = parse_call_month_year(dt)
        if not fname:
            continue
        dest = os.path.join(t_dir, fname)
        if os.path.exists(dest) and os.path.getsize(dest) > 3000:
            continue

        try:
            pdf_r = s.get(href, headers={"Referer": "https://www.bseindia.com/"}, timeout=8)
            if pdf_r.status_code == 200 and b"%PDF" in pdf_r.content[:1024]:
                reader = pypdf.PdfReader(io.BytesIO(pdf_r.content))
                pages_text = []
                for p in reader.pages:
                    txt = p.extract_text() or ""
                    pages_text.append(txt)
                full_text = " ".join(pages_text)
                clean_text = re.sub(r"\s+", " ", full_text).strip()
                if len(clean_text) > 3000:
                    with open(dest, "w", encoding="utf-8") as f:
                        f.write(clean_text)
                    downloaded += 1
        except Exception:
            pass

    return t, downloaded, bool(snap)


def main():
    print(f"Starting concurrent fetch for {len(NEW_TICKERS)} tickers with 8 workers...")
    t0 = time.time()
    results = {}
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_for_ticker, t): t for t in NEW_TICKERS}
        for n, f in enumerate(cf.as_completed(futs), 1):
            t = futs[f]
            try:
                t, n_calls, has_fin = f.result()
                results[t] = (n_calls, has_fin)
                print(f"[{n}/{len(NEW_TICKERS)}] {t}: {n_calls} calls, financials: {'✓' if has_fin else '✗'}", flush=True)
            except Exception as e:
                print(f"[{n}/{len(NEW_TICKERS)}] {t} failed: {e}", flush=True)

    ok_calls = sum(1 for c, f in results.values() if c >= 1)
    ok_fin = sum(1 for c, f in results.values() if f)
    print(f"\nDone in {time.time()-t0:.1f}s!")
    print(f"Tickers with transcripts: {ok_calls}/{len(NEW_TICKERS)}")
    print(f"Tickers with financials: {ok_fin}/{len(NEW_TICKERS)}")


if __name__ == "__main__":
    main()
