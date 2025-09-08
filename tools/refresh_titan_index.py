import zipfile, os, re, sys, uuid
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependency: beautifulsoup4")
    sys.exit(1)

# ---- Inputs/Outputs (filenames matter) ----
BASELINE_ZIP = Path("titan-index-with-whos-better-emojis.zip")  # must be in repo root
OUT_ZIP      = Path("titan-index-sept5-final.zip")              # will be attached to the Release

# ---- Sept 5, 2025 values (kept consistent with our project) ----
SEPT = {
    "30-Year Mortgage Rate (%)": 6.50,
    "Avg Home Price ($)": 422400,
    "DJIA": 45621.29,
    "S&P 500": 6502.08,
    "NASDAQ": 21707.69,
    "Unemployment Rate (%)": 4.3,
    "Consumer Confidence": 97.4,
    "Presidential Approval (%)": 44.1,
    "Avg Gas Price ($/gal)": 3.204,
    "Big Mac ($)": 5.79,
    "Milk ($/gal)": 4.162,
    "Eggs ($/dozen)": 3.28,
}

GOOD_WHEN_DOWN = {
    "30-year mortgage rate (%)","avg home price ($)","home price-to-income ratio","big mac ($)",
    "avg gas price ($/gal)","milk ($/gal)","eggs ($/dozen)","unemployment rate (%)"
}

ALIASES = {
    "average home price ($)": "Avg Home Price ($)",
    "avg gas price ($/gal)": "Avg Gas Price ($/gal)",
    "gas price (avg, $/gal)": "Avg Gas Price ($/gal)",
    "big mac price ($)": "Big Mac ($)",
    "milk (avg, $/gal)": "Milk ($/gal)",
    "eggs (avg, $/dozen)": "Eggs ($/dozen)",
    "presidential approval (%)": "Presidential Approval (%)",
    "consumer confidence index": "Consumer Confidence",
    "30-year fixed mortgage rate (%)": "30-Year Mortgage Rate (%)",
}

def norm(s): return re.sub(r"\s+"," ", (s or "")).strip().lower()

def parse_num(txt):
    if txt is None: return None
    t = str(txt)
    if "—" in t: return None
    t = t.replace("🟥","").replace("🟢","").replace("➖","")
    t = t.replace("$","").replace("%","").replace(",","").strip()
    m = re.search(r"[-+]?\d*\.?\d+", t)
    return float(m.group(0)) if m else None

def fmt(x): return f"{x:.2f}".rstrip("0").rstrip(".")

def good_when_down(ind_name):
    n = norm(ind_name)
    if n in GOOD_WHEN_DOWN: return True
    if any(k in n for k in ["djia","nasdaq","s&p","confidence","approval","income"]): return False
    if any(k in n for k in ["price","rate","mortgage","ratio"]): return True
    return False

def map_key(nname):
    for k in SEPT:
        if norm(k) == nname: return k
    return ALIASES.get(nname)

def read_series(content):
    m_labels = re.search(r"const\s+labels\s*=\s*(\[[^\]]*\])\s*;", content)
    m_actual = re.search(r"const\s+actual\s*=\s*(\[[^\]]*\])\s*;", content)
    return (m_labels.group(1), m_actual.group(1)) if (m_labels and m_actual) else (None, None)

def parse_js_array(js_array_str):
    inner = js_array_str.strip()[1:-1].strip()
    if not inner: return []
    parts = re.split(r',(?![^\\[\\]]*\\])', inner)
    out = []
    for p in parts:
        s = p.strip()
        if s.lower() == "null": out.append(None)
        elif s.startswith(("'", '"')) and s.endswith(("'", '"')): out.append(s[1:-1])
        else:
            try: out.append(float(s))
            except: out.append(s)
    return out

def to_js_array(lst):
    def conv(x):
        if x is None: return "null"
        if isinstance(x, str): return '"' + x.replace('"','\\"') + '"'
        if isinstance(x, float) and x.is_integer(): return str(int(x))
        return str(x)
    return "[" + ", ".join(conv(x) for x in lst) + "]"

def indicator_from_filename(fn):
    base = fn.replace(".html","").lower()
    if base.startswith("30-year-mortgage-rate-"): return "30-Year Mortgage Rate (%)"
    if base == "djia": return "DJIA"
    if base == "nasdaq": return "NASDAQ"
    if base in ["s&p-500","s&p 500","s&p_500"]: return "S&P 500"
    if "unemployment" in base: return "Unemployment Rate (%)"
    if "consumer-confidence" in base: return "Consumer Confidence"
    if "presidential-approval" in base: return "Presidential Approval (%)"
    if "avg-home-price" in base or "average-home-price" in base: return "Avg Home Price ($)"
    if "avg-gas-price" in base: return "Avg Gas Price ($/gal)"
    if "big-mac" in base: return "Big Mac ($)"
    if "milk" in base: return "Milk ($/gal)"
    if "eggs" in base: return "Eggs ($/dozen)"
    return None

def main():
    if not BASELINE_ZIP.exists():
        print("ERROR: Baseline ZIP missing in repo root:", BASELINE_ZIP)
        sys.exit(1)

    work_dir = Path(f"_titan_index_build_{uuid.uuid4().hex[:6]}")
    work_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(BASELINE_ZIP, "r") as z:
        z.extractall(work_dir)

    index_path = work_dir / "index.html"
    charts_dir = work_dir / "charts"
    if not index_path.exists():
        print("ERROR: index.html not found inside baseline ZIP.")
        sys.exit(1)

    # ---- Update tables with Sep 1 + values + emojis + Overall
    html = index_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    for table in soup.find_all("table"):
        thead = table.find("thead")
        if not thead: continue
        headers = [th.get_text(" ", strip=True) for th in thead.find_all("th")]
        if not headers or norm(headers[0]) != "indicator": continue

        if "Sep 1" not in headers:
            overall_idx = next((i for i,h in enumerate(headers) if norm(h).startswith("overall")), None)
            sep_th = soup.new_tag("th"); sep_th.string = "Sep 1"
            if overall_idx is not None:
                thead.find_all("tr")[0].find_all("th")[overall_idx].insert_before(sep_th)
            else:
                thead.find_all("tr")[0].append(sep_th)
            for tr in table.find("tbody").find_all("tr"):
                new_td = soup.new_tag("td"); new_td.string = "—"
                if overall_idx is not None:
                    tr.find_all("td")[overall_idx-1].insert_after(new_td)
                else:
                    tr.append(new_td)

        headers = [th.get_text(" ", strip=True) for th in thead.find_all("th")]
        sep_idx = headers.index("Sep 1")
        feb_idx = headers.index("Feb 1") if "Feb 1" in headers else 1
        aug_idx = headers.index("Aug 1") if "Aug 1" in headers else None
        overall_idx = next((i for i,h in enumerate(headers) if norm(h).startswith("overall")), None)

        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if not tds: continue
            ind_name = tds[0].get_text(" ", strip=True)
            key = map_key(norm(ind_name))

            if sep_idx-1 < len(tds):
                if key and key in SEPT:
                    val = SEPT[key]
                    aug_val = parse_num(tds[aug_idx-1].get_text(" ", strip=True)) if (aug_idx and aug_idx-1 < len(tds)) else None
                    emoji = "➖"
                    if aug_val is not None:
                        delta = val - aug_val
                        emoji = "🟢" if ((delta < 0) if good_when_down(ind_name) else (delta > 0)) else ("➖" if abs(delta) < 1e-9 else "🟥")
                    tds[sep_idx-1].string = f"{emoji} {fmt(val)}"

            if overall_idx is not None and overall_idx-1 < len(tds):
                feb_val = parse_num(tds[feb_idx-1].get_text(" ", strip=True)) if feb_idx-1 < len(tds) else None
                latest_val = parse_num(tds[sep_idx-1].get_text(" ", strip=True)) if sep_idx-1 < len(tds) else None
                if latest_val is None or feb_val is None:
                    tds[overall_idx-1].string = "—"
                else:
                    diff = latest_val - feb_val
                    emoji_over = "🟢" if ((diff < 0) if good_when_down(ind_name) else (diff > 0)) else ("➖" if abs(diff) < 1e-9 else "🟥")
                    sign = "+" if diff > 0 else ""
                    tds[overall_idx-1].string = f"{emoji_over} {sign}{fmt(diff)}"

    index_path.write_text(str(soup), encoding="utf-8")

    # ---- Update Who's Better vs Worse
    soup2 = BeautifulSoup(index_path.read_text(encoding="utf-8"), "html.parser")
    header = None
    for h in soup2.find_all(["h2","h3","h4"]):
        t = (h.get_text(strip=True) or "").lower().replace("’","'")
        if "who's better vs. worse" in t or "who’s better vs. worse" in t:
            header = h; break
    if header:
        ul = header.find_next("ul")
        new_ul = soup2.new_tag("ul")
        new_ul['style'] = 'margin:8px 0 0 18px;line-height:1.5;'
        new_ul.append(BeautifulSoup('<li>💎 <strong>Upper class — Better off:</strong> Stock gains and property wealth buffer higher costs; mortgage swings matter less.</li>', "html.parser"))
        new_ul.append(BeautifulSoup('<li>🏠 <strong>Middle class — Squeezed:</strong> Paychecks up but affordability tight: elevated home prices, ~7% mortgages, and essential costs bite.</li>', "html.parser"))
        new_ul.append(BeautifulSoup('<li>💸 <strong>Lower class — Worse off:</strong> Little benefit from markets; rents, gas, and groceries weigh most even with strong job availability.</li>', "html.parser"))
        if ul: ul.replace_with(new_ul)
        else: header.insert_after(new_ul)
        if "color:" not in (header.get("style","")):
            header["style"] = (header.get("style","") + " color:#fbbf24;").strip()

    index_path.write_text(str(soup2), encoding="utf-8")

    # ---- Update charts with a Sep 1 point
    def patch_chart(fpath):
        content = fpath.read_text(encoding="utf-8", errors="ignore")
        m_labels = re.search(r"const\s+labels\s*=\s*(\[[^\]]*\])\s*;", content)
        m_actual = re.search(r"const\s+actual\s*=\s*(\[[^\]]*\])\s*;", content)
        if not m_labels or not m_actual: return
        def parse_js_array(js):
            inner = js.strip()[1:-1].strip()
            if not inner: return []
            parts = re.split(r',(?![^\\[\\]]*\\])', inner)
            out = []
            for p in parts:
                s = p.strip()
                if s.lower() == "null": out.append(None)
                elif s.startswith(("'", '"')) and s.endswith(("'", '"')): out.append(s[1:-1])
                else:
                    try: out.append(float(s))
                    except: out.append(s)
            return out
        def to_js_array(lst):
            def conv(x):
                if x is None: return "null"
                if isinstance(x, str): return '"' + x.replace('"','\\"') + '"'
                if isinstance(x, float) and x.is_integer(): return str(int(x))
                return str(x)
            return "[" + ", ".join(conv(x) for x in lst) + "]"
        labels = parse_js_array(m_labels.group(1))
        actual = parse_js_array(m_actual.group(1))
        if "Sep 1" not in labels: labels.append("Sep 1")
        # map filename to indicator
        base = fpath.name.replace(".html","").lower()
        ind_key = None
        if base.startswith("30-year-mortgage-rate-"): ind_key = "30-Year Mortgage Rate (%)"
        elif base == "djia": ind_key = "DJIA"
        elif base == "nasdaq": ind_key = "NASDAQ"
        elif base in ["s&p-500","s&p 500","s&p_500"]: ind_key = "S&P 500"
        elif "unemployment" in base: ind_key = "Unemployment Rate (%)"
        elif "consumer-confidence" in base: ind_key = "Consumer Confidence"
        elif "presidential-approval" in base: ind_key = "Presidential Approval (%)"
        elif "avg-home-price" in base or "average-home-price" in base: ind_key = "Avg Home Price ($)"
        elif "avg-gas-price" in base: ind_key = "Avg Gas Price ($/gal)"
        elif "big-mac" in base: ind_key = "Big Mac ($)"
        elif "milk" in base: ind_key = "Milk ($/gal)"
        elif "eggs" in base: ind_key = "Eggs ($/dozen)"
        val = float(SEPT[ind_key]) if ind_key in SEPT else None
        while len(actual) < len(labels) - 1: actual.append(None)
        if len(actual) == len(labels) - 1: actual.append(val)
        else: actual[-1] = val
        new_c = re.sub(r"const\s+labels\s*=\s*\[[^\]]*\]\s*;", f"const labels = {to_js_array(labels)};", content, count=1)
        new_c = re.sub(r"const\s+actual\s*=\s*\[[^\]]*\]\s*;", f"const actual = {to_js_array(actual)};", new_c, count=1)
        fpath.write_text(new_c, encoding="utf-8")

    charts_dir = Path(work_dir/"charts")
    if charts_dir.exists():
        for f in charts_dir.glob("*.html"):
            patch_chart(f)

    # ---- Package final ZIP
    if OUT_ZIP.exists(): OUT_ZIP.unlink()
    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(work_dir):
            for name in files:
                p = Path(root) / name
                z.write(p, arcname=str(p.relative_to(work_dir)))
    print("Built:", OUT_ZIP.resolve())

if __name__ == "__main__":
    main()
