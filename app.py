"""
International Cost of Capital App
---------------------------------
Compares a project's cost of equity, cost of debt and WACC in USD and in the
currency of a selected country.

Data sources (fetched live, cached, refreshable):
  * Unlevered industry betas  - Aswath Damodaran (betas.xls, U.S. industries)
  * BBB (Baa2) USD spread     - Aswath Damodaran (ratings.html, large non-financial firms)
  * Statutory corporate tax   - OECD Corporate Tax Statistics 2024
  * 10-year government yields - Trading Economics (tradingeconomics.com/bonds)

Every fetched number can be overwritten with a manual input in the sidebar.
"""

import io
import re
import datetime as dt

import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="International Cost of Capital", layout="wide")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BETA_URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls"
RATINGS_URL = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html"
OECD_URL = ("https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/"
            "full-report/statutory-corporate-income-tax-rates_440f9286.html#chapter-d1e2342-08e74a33fb")
TE_URL = "https://tradingeconomics.com/bonds"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

DEFAULT_INDUSTRY = "Software (System & Application)"
DEFAULT_COUNTRY = "United States"
DEFAULT_ERP = 6.5      # %
DEFAULT_DEBT = 30      # %

# Bundled copies of the source downloads (used when a live fetch fails)
import os
APP_DIR = os.path.dirname(os.path.abspath(__file__))


def find_betas_file():
    """Find the bundled Damodaran betas file (any .xls name) in data/ or next to app.py."""
    for folder in (os.path.join(APP_DIR, "data"), APP_DIR):
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                if f.lower().endswith((".xls", ".xlsx")) and "beta" in f.lower():
                    return os.path.join(folder, f)
    return None


BETAS_FILE = find_betas_file()                   # Damodaran, updated 2026-01-05
# OECD Corporate Tax Statistics 2024, Figure 2.1: statutory combined CIT rates, 2024 (%).
# Measured from the PDF's vector bars (tools/extract_oecd_rates.py), accuracy +/-0.05 pp.
OECD_CIT_2024 = {
    "Albania": 15, "Andorra": 10, "Angola": 25, "Anguilla": 0, "Antigua and Barbuda": 25,
    "Argentina": 30, "Armenia": 18, "Aruba": 22, "Australia": 30, "Austria": 23,
    "Azerbaijan": 20, "Bahamas": 0, "Bahrain": 0, "Barbados": 9, "Belgium": 25, "Belize": 0,
    "Benin": 30, "Bermuda": 0, "Bosnia and Herzegovina": 10, "Botswana": 22, "Brazil": 34,
    "British Virgin Islands": 0, "Brunei": 18.5, "Bulgaria": 10, "Burkina Faso": 27.5,
    "Cabo Verde": 22.5, "Cameroon": 33, "Canada": 26.16, "Cayman Islands": 0, "Chile": 27,
    "China": 25, "Colombia": 35, "Congo": 28, "Cook Islands": 20, "Costa Rica": 30,
    "Cote d'Ivoire": 25, "Croatia": 18, "Curacao": 22, "Czech Republic": 21, "DR Congo": 30,
    "Denmark": 22, "Djibouti": 25, "Dominica": 25, "Dominican Republic": 27, "Egypt": 22.5,
    "Estonia": 20, "Eswatini": 27.5, "Faroe Islands": 18, "Finland": 20, "France": 25.82,
    "Gabon": 30, "Georgia": 15, "Germany": 29.93, "Gibraltar": 12.5, "Greece": 22,
    "Greenland": 26.5, "Grenada": 28, "Guernsey": 0, "Haiti": 30, "Honduras": 30,
    "Hong Kong": 16.5, "Hungary": 9, "Iceland": 21, "India": 25.14, "Indonesia": 22,
    "Ireland": 12.5, "Isle of Man": 0, "Israel": 23, "Italy": 27.76, "Jamaica": 25,
    "Japan": 29.7, "Jersey": 0, "Jordan": 20, "Kazakhstan": 20, "Kenya": 30, "Kuwait": 15,
    "Latvia": 20, "Liberia": 25, "Liechtenstein": 12.5, "Lithuania": 15, "Luxembourg": 24.91,
    "Macau": 12, "Malaysia": 24, "Maldives": 15, "Malta": 35, "Mauritania": 25,
    "Mauritius": 15, "Mexico": 30, "Monaco": 25, "Mongolia": 25, "Montenegro": 15,
    "Montserrat": 30, "Morocco": 32, "Namibia": 32, "Netherlands": 25.82, "New Zealand": 28,
    "Nigeria": 30, "North Macedonia": 10, "Norway": 22, "Oman": 15, "Pakistan": 29,
    "Panama": 25, "Papua New Guinea": 30, "Paraguay": 10, "Peru": 29.5, "Philippines": 25,
    "Poland": 19, "Portugal": 31.5, "Qatar": 10, "Romania": 16, "Saint Kitts and Nevis": 25,
    "Saint Lucia": 30, "Saint Vincent and the Grenadines": 28, "Samoa": 27, "San Marino": 17,
    "Saudi Arabia": 20, "Senegal": 30, "Serbia": 15, "Seychelles": 25, "Sierra Leone": 25,
    "Singapore": 17, "Slovakia": 21, "Slovenia": 22, "South Africa": 27, "South Korea": 26.39,
    "Spain": 25, "Sri Lanka": 30, "Sweden": 20.56, "Switzerland": 19.6, "Thailand": 20,
    "Togo": 27, "Trinidad and Tobago": 30, "Tunisia": 15, "Turkey": 20,
    "Turks and Caicos Islands": 0, "Ukraine": 18, "United Arab Emirates": 9,
    "United Kingdom": 25, "United States": 25.59, "Uruguay": 25, "Uzbekistan": 15,
    "Vietnam": 20, "Zambia": 30,
}
BBB_FALLBACK = (0.0111, "January 2026")                      # Damodaran ratings.html, Baa2/BBB

ALIASES = {
    "korea": "south korea", "republic of korea": "south korea",
    "czechia": "czech republic", "türkiye": "turkey", "turkiye": "turkey",
    "united states of america": "united states", "usa": "united states",
    "us": "united states", "uae": "united arab emirates", "u.k.": "united kingdom", "slovak republic": "slovakia",
    "hong kong, china": "hong kong", "hong kong (china)": "hong kong",
    "china (people's republic of)": "china", "viet nam": "vietnam",
}


def norm(name: str) -> str:
    """Normalise country names so OECD and Trading Economics names match."""
    n = re.sub(r"\s+", " ", str(name)).strip().lower()
    n = re.sub(r"\s*\d+y$", "", n)          # e.g. "united states 10y"
    return ALIASES.get(n, n)


MONTH_RE = (r"(January|February|March|April|May|June|July|August|September|"
            r"October|November|December)\s+\d{4}")


def now_str():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def read_tables(html):
    """pd.read_html with lxml, falling back to BeautifulSoup/html5lib."""
    try:
        return pd.read_html(io.StringIO(html))
    except ImportError:
        return pd.read_html(io.StringIO(html), flavor="bs4")


# ---------------------------------------------------------------------------
# Data fetchers (cached for 12 hours; "Refresh data" clears the cache)
# ---------------------------------------------------------------------------
def parse_betas(content: bytes):
    """Parse Damodaran betas.xls bytes -> (DataFrame[Industry, Unlevered beta], date string)."""
    xls = None
    for engine in ("calamine", "xlrd"):   # pandas 3 reads .xls via python-calamine
        try:
            xls = pd.ExcelFile(io.BytesIO(content), engine=engine)
            break
        except Exception:  # noqa: BLE001
            continue
    if xls is None:
        raise ImportError("Install python-calamine or xlrd to read betas.xls")
    sheet = next((s_ for s_ in xls.sheet_names if "industry" in s_.lower()), xls.sheet_names[0])
    raw = xls.parse(sheet, header=None)

    # Header row = the row whose first cell is "Industry Name"
    first = raw.iloc[:, 0].astype("string").fillna("").str.strip()
    hdr = int(first[first.str.lower() == "industry name"].index[0])

    # "Date updated:" label -> next non-empty cell in that row
    data_date = "n/a"
    for i in range(hdr):
        if "date" in str(raw.iat[i, 0]).lower():
            vals = [v for v in raw.iloc[i, 1:].tolist() if pd.notna(v)]
            if vals:
                v = vals[0]
                data_date = v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v)
            break

    df = xls.parse(sheet, header=hdr)
    df.columns = [str(c).strip() for c in df.columns]
    name_col = next(c for c in df.columns if "industry" in c.lower())
    ub_col = next(c for c in df.columns
                  if c.lower().startswith("unlevered beta") and "cash" not in c.lower())
    out = df[[name_col, ub_col]].rename(columns={name_col: "Industry", ub_col: "Unlevered beta"})
    out["Unlevered beta"] = pd.to_numeric(out["Unlevered beta"], errors="coerce")
    out = out.dropna()
    out["Industry"] = out["Industry"].astype(str).str.strip()
    out = out[~out["Industry"].str.contains("Total Market", case=False)].reset_index(drop=True)
    return out, data_date


@st.cache_data(ttl=43200, show_spinner=False)
def fetch_betas():
    """Damodaran U.S. industry betas: live download, else the bundled data/betas.xls."""
    try:
        r = requests.get(BETA_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        out, data_date = parse_betas(r.content)
        return {"data": out, "date": data_date, "fetched": now_str(), "ok": True,
                "msg": f"Live: {len(out)} industries"}
    except Exception as e:  # noqa: BLE001
        live_err = str(e)[:80]
    try:
        if BETAS_FILE is None:
            raise FileNotFoundError("No betas .xls file found in the repo")
        with open(BETAS_FILE, "rb") as f:
            out, data_date = parse_betas(f.read())
        return {"data": out, "date": data_date, "fetched": now_str(), "ok": True,
                "msg": f"Bundled download {os.path.basename(BETAS_FILE)} ({len(out)} industries); live failed: {live_err}"}
    except Exception as e:  # noqa: BLE001
        return {"data": pd.DataFrame(columns=["Industry", "Unlevered beta"]),
                "date": "n/a", "fetched": now_str(), "ok": False, "msg": str(e)}


@st.cache_data(ttl=43200, show_spinner=False)
def fetch_bbb_spread():
    """Damodaran ratings.html -> Baa2/BBB spread (decimal) for large non-financial firms."""
    try:
        r = requests.get(RATINGS_URL, headers=HEADERS, timeout=30)
        if r.status_code != 200:   # the link given in class omits the "~"
            r = requests.get(RATINGS_URL.replace("/~adamodar", "/adamodar"),
                             headers=HEADERS, timeout=30)
        r.raise_for_status()
        text = r.text
        m = re.search(MONTH_RE, re.sub(r"<[^>]+>", " ", text))
        data_date = m.group(0) if m else "n/a"
        tables = read_tables(text)
        # The FIRST table containing Baa2/BBB is the large non-financial table
        for t in tables:
            flat = t.astype(str)
            mask = flat.apply(lambda row: row.str.contains("Baa2/BBB", regex=False).any(), axis=1)
            if mask.any():
                row = list(flat[mask].iloc[0])
                pct = [v for v in row if re.search(r"-?\d+(\.\d+)?\s*%", v)]
                val = pct[-1] if pct else row[-1]
                spread = float(re.sub(r"[^\d.\-]", "", val)) / 100
                return {"data": spread, "date": data_date, "fetched": now_str(), "ok": True,
                        "msg": "Baa2/BBB, large non-financial service firms"}
        raise ValueError("Baa2/BBB row not found")
    except Exception as e:  # noqa: BLE001
        return {"data": BBB_FALLBACK[0], "date": BBB_FALLBACK[1], "fetched": now_str(),
                "ok": True, "msg": f"Value from downloaded page (Baa2/BBB 1.11%); live failed: {str(e)[:60]}"}


@st.cache_data(ttl=43200, show_spinner=False)
def fetch_tax_rates():
    """OECD statutory CIT rates -> dict{normalised country: decimal}."""
    try:
        r = requests.get(OECD_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        tables = read_tables(r.text)
        rates = {}
        for t in tables:
            if t.shape[1] < 2:
                continue
            c0 = t.columns[0]
            for col in t.columns[1:]:
                vals = pd.to_numeric(t[col].astype(str).str.replace("%", ""), errors="coerce")
                if vals.notna().sum() >= 10 and vals.between(0, 60).all(skipna=True):
                    for name, v in zip(t[c0], vals):
                        if pd.notna(v):
                            rates[norm(name)] = float(v) / 100
                    break
        if len(rates) < 10:
            raise ValueError("No parsable tax table on OECD page (chart-only page)")
        return {"data": rates, "date": "Corporate Tax Statistics 2024", "fetched": now_str(),
                "ok": True, "msg": f"{len(rates)} jurisdictions parsed live"}
    except Exception as e:  # noqa: BLE001
        rates = {norm(c): v / 100 for c, v in OECD_CIT_2024.items()}
        return {"data": rates, "date": "Corporate Tax Statistics 2024 (tax year 2024)",
                "fetched": now_str(), "ok": True,
                "msg": ("Embedded OECD 2024 table (PDF Figure 2.1, "
                        f"{len(rates)} jurisdictions); live page blocked: {str(e)[:50]}")}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_yields():
    """Trading Economics /bonds -> dict{normalised country: (display name, yield decimal, date)}."""
    try:
        r = requests.get(TE_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
        try:
            tables = read_tables(r.text)
        except ValueError:
            tables = []
        if not any("Yield" in [str(c).strip() for c in t.columns] for t in tables):
            # Fallback: parse rows that link to "/<country>/government-bond-yield"
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "html.parser")
            out = {}
            for tr in soup.find_all("tr"):
                a = tr.find("a", href=re.compile(r"government-bond-yield"))
                if not a:
                    continue
                for td in tr.find_all("td"):
                    try:
                        y = float(td.get_text(strip=True).replace(",", ""))
                        name = a.get_text(strip=True)
                        out.setdefault(norm(name), (name, y / 100, "n/a"))
                        break
                    except ValueError:
                        continue
            if "united states" not in out:
                raise ValueError("No yield table found on Trading Economics page")
            return {"data": out, "date": "Latest quotes", "fetched": now_str(), "ok": True,
                    "msg": f"{len(out)} countries loaded (row parser)"}
        frames = []
        for t in tables:
            cols = [str(c).strip() for c in t.columns]
            t.columns = cols
            if "Yield" not in cols:
                continue
            sub = pd.DataFrame({
                "Country": t[cols[0]].astype(str).str.strip(),
                "Yield": pd.to_numeric(t["Yield"], errors="coerce"),
                "Date": t["Date"].astype(str) if "Date" in cols else "n/a",
            })
            frames.append(sub)
        df = pd.concat(frames).dropna(subset=["Yield"])
        df = df.drop_duplicates(subset="Country", keep="first")
        out = {norm(c): (c, y / 100, d) for c, y, d in zip(df["Country"], df["Yield"], df["Date"])}
        if "united states" not in out:
            raise ValueError("United States yield not found")
        return {"data": out, "date": f"Latest quotes (US quote date: {out['united states'][2]})",
                "fetched": now_str(), "ok": True, "msg": f"{len(out)} countries loaded"}
    except Exception as e:  # noqa: BLE001
        return {"data": {}, "date": "n/a", "fetched": now_str(), "ok": False, "msg": str(e)}


# ---------------------------------------------------------------------------
# Core calculation (all inputs in DECIMALS)
# ---------------------------------------------------------------------------
def compute(beta_u, tax, debt_share, erp, y_us, y_fc, spread_usd,
            spread_fc_override=None):
    """
    Formulas from class (Rebelo, Case Packet 2026, slides 564-585):
      Relevering:            bE = bU * [1 + (1 - t) * D/E],  D/E = d / (1 - d)
      USD cost of equity:    Re = Rf + bE * ERP
      USD cost of debt:      Rd = Rf + s
      Conversion factor:     F = (1 + Rf*) / (1 + Rf)
      FC cost of equity:     1 + Re* = (1 + Re) * F
      FC spread (default):   s* = s * F      ->  Rd* = Rf* + s*
                             (equivalent to 1 + Rd* = (1 + Rd) * F)
      FC spread (override):  Rd* = Rf* + s*_manual
      WACC:                  (1 - d) Re + d Rd (1 - t)
    """
    d = debt_share
    e = 1 - d
    de = d / e if e > 0 else np.inf
    beta_l = beta_u * (1 + (1 - tax) * de)
    F = (1 + y_fc) / (1 + y_us)

    ke_usd = y_us + beta_l * erp
    kd_usd = y_us + spread_usd
    ke_fc = (1 + ke_usd) * F - 1
    spread_fc_auto = spread_usd * F
    spread_fc = spread_fc_auto if spread_fc_override is None else spread_fc_override
    kd_fc = y_fc + spread_fc

    res = {}
    for cur, y, ke, sp, kd in (("USD", y_us, ke_usd, spread_usd, kd_usd),
                               ("FC", y_fc, ke_fc, spread_fc, kd_fc)):
        kd_at = kd * (1 - tax)
        res[cur] = {
            "10Y government yield (risk-free proxy)": y,
            "Unlevered beta": beta_u,
            "Relevered equity beta": beta_l,
            "Equity risk premium": erp,
            "Cost of equity": ke,
            "BBB borrowing spread": sp,
            "Pre-tax cost of debt": kd,
            "Project tax rate": tax,
            "After-tax cost of debt": kd_at,
            "Equity weight (1 - d)": e,
            "Debt weight (d)": d,
            "WACC": e * ke + d * kd_at,
        }
    res["FC_spread_auto"] = spread_fc_auto
    res["F"] = F
    return res


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
st.title("International Cost of Capital")
st.caption("Cost of equity, cost of debt and WACC for a project in USD and in a selected "
           "country's currency.")

top_l, top_r = st.columns([1, 5])
with top_l:
    if st.button("🔄 Refresh data", help="Clear the cache and re-fetch all sources"):
        st.cache_data.clear()
        st.rerun()

with st.spinner("Fetching data from Damodaran, OECD and Trading Economics..."):
    betas_src = fetch_betas()
    spread_src = fetch_bbb_spread()
    tax_src = fetch_tax_rates()
    yld_src = fetch_yields()

betas_df = betas_src["data"]
tax_rates = tax_src["data"]
yields = yld_src["data"]

# Country list: countries with a yield (needed for FC), else the tax list
if yields:
    country_names = sorted({v[0] for v in yields.values()} | {DEFAULT_COUNTRY})
else:
    country_names = sorted({c.title() for c in tax_rates})
# Use "United States" as the display label for the U.S. regardless of TE label
country_names = [c for c in country_names if norm(c) != "united states"]
country_names = [DEFAULT_COUNTRY] + country_names

industries = list(betas_df["Industry"]) if not betas_df.empty else [DEFAULT_INDUSTRY]

# ---------------------------------------------------------------------------
# Sidebar inputs
# ---------------------------------------------------------------------------
sb = st.sidebar
sb.header("Project settings")
industry = sb.selectbox("Industry", industries,
                        index=industries.index(DEFAULT_INDUSTRY) if DEFAULT_INDUSTRY in industries else 0)
country = sb.selectbox("Target country", country_names, index=0)
erp_pct = sb.number_input("Equity risk premium (%)", 0.0, 20.0, DEFAULT_ERP, 0.1)
debt_pct = sb.slider("Target debt share D/(D+E) (%)", 0, 90, DEFAULT_DEBT, 1)
tax_choice = sb.radio("Project tax rate", ["U.S. tax rate", "Selected-country tax rate"], index=0,
                      help="The same tax rate is used for both currencies.")

# Fetched values
beta_fetched = (float(betas_df.loc[betas_df["Industry"] == industry, "Unlevered beta"].iloc[0])
                if not betas_df.empty else None)
tax_us_fetched = tax_rates.get("united states")
tax_fc_fetched = tax_rates.get(norm(country))
spread_fetched = spread_src["data"]
y_us_fetched = yields.get("united states", (None, None, None))[1]
y_fc_fetched = yields.get(norm(country), (None, None, None))[1]


def override(label, fetched, default, key, step=0.01, fmt="%.2f", pct=True):
    """Checkbox + number input. Returns the value in DECIMALS (or raw if pct=False)."""
    missing = fetched is None
    shown = (fetched * 100 if pct else fetched) if not missing else default
    if missing:
        sb.caption(f"⚠️ {label}: fetch unavailable — manual input required")
        on = True
    else:
        on = sb.checkbox(f"Override {label}", value=False, key=f"ov_{key}")
    if on:
        v = sb.number_input(f"{label}{' (%)' if pct else ''}", value=float(round(shown, 4)),
                            step=step, format=fmt, key=f"val_{key}")
        return (v / 100 if pct else v), True
    sb.caption(f"Fetched {label}: **{shown:.{2 if pct else 4}f}{'%' if pct else ''}**")
    return fetched, False


sb.header("Manual overrides")
beta_u, ov_beta = override("unlevered beta", beta_fetched, 1.0, "beta", pct=False)
tax_us, ov_tus = override("U.S. tax rate", tax_us_fetched, 25.59, "tus")
tax_fc, ov_tfc = override(f"{country} tax rate", tax_fc_fetched, 25.0, f"tfc_{norm(country)}")
spread_usd, ov_sp = override("USD BBB spread", spread_fetched, 1.5, "sp")
y_us, ov_yus = override("U.S. 10Y yield", y_us_fetched, 4.0, "yus")
if norm(country) == "united states":
    y_fc, ov_yfc = override("selected-country 10Y yield", y_us, 4.0, "yfc")
    if not ov_yfc:
        y_fc = y_us
else:
    y_fc, ov_yfc = override(f"{country} 10Y yield", y_fc_fetched, 4.0, f"yfc_{norm(country)}")

tax = tax_us if tax_choice.startswith("U.S.") else tax_fc
erp = erp_pct / 100
debt = debt_pct / 100

# Foreign-currency spread: auto unless overridden
auto_res = compute(beta_u, tax, debt, erp, y_us, y_fc, spread_usd, None)
sb.header("Foreign-currency BBB spread")
ov_sfc = sb.toggle("Override foreign-currency spread", value=False)
if ov_sfc:
    sfc_pct = sb.number_input(f"{country} BBB spread (%)",
                              value=float(round(auto_res["FC_spread_auto"] * 100, 4)),
                              step=0.01, format="%.2f")
    spread_fc_override = sfc_pct / 100
else:
    sb.caption(f"Auto-calculated FC spread: **{auto_res['FC_spread_auto'] * 100:.4f}%** "
               f"= USD spread × F, with F = (1 + Rf*)/(1 + Rf) = {auto_res['F']:.6f}")
    spread_fc_override = None

res = compute(beta_u, tax, debt, erp, y_us, y_fc, spread_usd, spread_fc_override)

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
fc_label = f"{country} currency"
st.subheader(f"{industry} — USD vs {fc_label}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Cost of equity (USD)", f"{res['USD']['Cost of equity']:.2%}")
c2.metric(f"Cost of equity ({country})", f"{res['FC']['Cost of equity']:.2%}",
          f"{(res['FC']['Cost of equity'] - res['USD']['Cost of equity']) * 1e4:+.0f} bp vs USD")
c3.metric("WACC (USD)", f"{res['USD']['WACC']:.2%}")
c4.metric(f"WACC ({country})", f"{res['FC']['WACC']:.2%}",
          f"{(res['FC']['WACC'] - res['USD']['WACC']) * 1e4:+.0f} bp vs USD")

rows = list(res["USD"].keys())
table = pd.DataFrame({"USD": [res["USD"][k] for k in rows],
                      fc_label: [res["FC"][k] for k in rows]}, index=rows)
non_pct = {"Unlevered beta", "Relevered equity beta"}
display = table.copy().astype(object)
for k in rows:
    for col in display.columns:
        v = table.loc[k, col]
        display.loc[k, col] = f"{v:.3f}" if k in non_pct else f"{v:.2%}"
st.table(display)

overrides_used = [n for n, f in [("unlevered beta", ov_beta), ("U.S. tax", ov_tus),
                                  (f"{country} tax", ov_tfc), ("USD spread", ov_sp),
                                  ("U.S. yield", ov_yus), (f"{country} yield", ov_yfc),
                                  ("FC spread", ov_sfc)] if f]
st.caption("Manual overrides active: " + (", ".join(overrides_used) if overrides_used else "none"))

# Download of results with inputs
inputs = pd.DataFrame({
    "Input": ["Industry", "Target country", "Tax choice", "Conversion factor F", "ERP",
              "Debt share", "Overrides"],
    "Value": [industry, country, tax_choice, f"{res['F']:.6f}", f"{erp:.2%}", f"{debt:.0%}",
              ", ".join(overrides_used) or "none"],
})
csv_buf = io.StringIO()
inputs.to_csv(csv_buf, index=False)
csv_buf.write("\n")
table.to_csv(csv_buf)
st.download_button("⬇️ Download results (CSV)", csv_buf.getvalue(),
                   file_name=f"cost_of_capital_{norm(country).replace(' ', '_')}.csv",
                   mime="text/csv")

# ---------------------------------------------------------------------------
# Assumptions
# ---------------------------------------------------------------------------
with st.expander("Main assumptions and formulas", expanded=True):
    st.markdown(f"""
**Formulas** (d = target debt share, τ = project tax rate, * = foreign currency)
- Relevered beta: βE = βU × [1 + (1 − τ) × D/E], with D/E = d/(1 − d)
- USD cost of equity: Re = Rf + βE × ERP  · USD pre-tax cost of debt: Rd = Rf + s
- Conversion factor: F = (1 + Rf*)/(1 + Rf) = **{res['F']:.6f}**
- Foreign cost of equity: 1 + Re* = (1 + Re) × F
- Foreign borrowing spread: s* = s × F (default) or manual override; Rd* = Rf* + s*
- WACC = (1 − d) Re + d Rd (1 − τ), computed in each currency with the same d, τ and ERP

**Key approximations**
- Risk is measured relative to the U.S. market; U.S. industry betas proxy for project risk.
- 10-year government yields are the risk-free proxies; they include liquidity and term
  premia and may include sovereign default risk.
- Currency conversion assumes equal real rates and relative PPP, so the yield ratio
  reflects expected depreciation. No separate currency-risk premium (FX betas ≈ 0).
- No separate country equity risk premium.
- Target leverage is constant, interest deductions are fully usable, and unlevering
  assumes a zero debt beta.
""")

# ---------------------------------------------------------------------------
# All-industry comparison
# ---------------------------------------------------------------------------
st.subheader("All-industry comparison")
if betas_df.empty:
    st.info("Industry betas could not be fetched; only the manual beta is available.")
else:
    recs = []
    for ind, bu in zip(betas_df["Industry"], betas_df["Unlevered beta"]):
        r_ = compute(bu, tax, debt, erp, y_us, y_fc, spread_usd, spread_fc_override)
        recs.append({"Industry": ind, "Unlevered beta": bu,
                     "Relevered beta": r_["USD"]["Relevered equity beta"],
                     "Cost of equity USD": r_["USD"]["Cost of equity"],
                     f"Cost of equity {country}": r_["FC"]["Cost of equity"],
                     "WACC USD": r_["USD"]["WACC"],
                     f"WACC {country}": r_["FC"]["WACC"]})
    all_df = pd.DataFrame(recs).sort_values("WACC USD", ascending=False).reset_index(drop=True)
    st.caption("Uses the current country, tax, ERP, debt-share and spread settings. "
               "Note: if the unlevered-beta override is on, this table still uses each "
               "industry's fetched beta.")
    pct_cols = [c for c in all_df.columns if c.startswith(("Cost", "WACC"))]
    st.dataframe(all_df.style.format({**{c: "{:.2%}" for c in pct_cols},
                                      "Unlevered beta": "{:.3f}", "Relevered beta": "{:.3f}"}),
                 width="stretch", height=380)
    st.bar_chart(all_df.set_index("Industry")[["WACC USD", f"WACC {country}"]].head(25) * 100,
                 y_label="WACC (%) — top 25 industries", stack=False)
    st.download_button("⬇️ Download all-industry comparison (CSV)",
                       all_df.to_csv(index=False),
                       file_name=f"all_industries_{norm(country).replace(' ', '_')}.csv",
                       mime="text/csv")

# ---------------------------------------------------------------------------
# Built-in verification checks
# ---------------------------------------------------------------------------
with st.expander("Verification checks (run live on current inputs)"):
    eq = compute(beta_u, tax, debt, erp, y_us, y_us, spread_usd, None)
    chk1 = np.isclose(eq["USD"]["WACC"], eq["FC"]["WACC"]) and \
        np.isclose(eq["USD"]["Cost of equity"], eq["FC"]["Cost of equity"])
    z = compute(beta_u, tax, 0.0, erp, y_us, y_fc, spread_usd, spread_fc_override)
    chk2 = np.isclose(z["USD"]["WACC"], z["USD"]["Cost of equity"]) and \
        np.isclose(z["FC"]["WACC"], z["FC"]["Cost of equity"])
    o = compute(beta_u, tax, debt, erp, y_us, y_fc, spread_usd, 0.05)
    chk3 = all(np.isclose(o["USD"][k], res["USD"][k]) for k in rows if k in o["USD"])
    col = compute(0.80, 0.35, 0.30, 0.065, 0.04, 0.12, 0.015)
    chk0 = (round(col["USD"]["WACC"] * 100, 4) == 8.5265 and
            round(col["FC"]["WACC"] * 100, 4) == 16.0670)
    st.write(f"{'✅' if chk0 else '❌'} Class Colombia example (βU 0.80, d 30%, τ 35%, ERP 6.5%, "
             f"Rf 4%, Rf* 12%, s 1.5%): WACC USD {col['USD']['WACC']:.4%} (slide: 8.5265%), "
             f"COP {col['FC']['WACC']:.4%} (slide: 16.0670%); Re* {col['FC']['Cost of equity']:.4%}, "
             f"s* {col['FC']['BBB borrowing spread']:.4%}")
    st.write(f"{'✅' if chk1 else '❌'} Equal 10Y yields (FC spread override off) → identical "
             f"USD and FC results (WACC {eq['USD']['WACC']:.4%} vs {eq['FC']['WACC']:.4%})")
    st.write(f"{'✅' if chk2 else '❌'} Zero debt → WACC equals cost of equity "
             f"(USD {z['USD']['WACC']:.4%} = {z['USD']['Cost of equity']:.4%})")
    st.write(f"{'✅' if chk3 else '❌'} Overriding the FC spread (test value 5.00%) leaves all "
             f"USD results unchanged (USD WACC {o['USD']['WACC']:.4%})")

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
st.subheader("Data sources")
src = pd.DataFrame([
    ["U.S. industry unlevered betas", "Aswath Damodaran", BETA_URL, betas_src["date"],
     betas_src["fetched"], "✅" if betas_src["ok"] else "⚠️", betas_src["msg"]],
    ["BBB (Baa2) USD spread", "Aswath Damodaran", RATINGS_URL, spread_src["date"],
     spread_src["fetched"], "✅" if spread_src["ok"] else "⚠️", spread_src["msg"]],
    ["Statutory corporate tax rates", "OECD", OECD_URL, tax_src["date"],
     tax_src["fetched"], "✅" if tax_src["ok"] else "⚠️", tax_src["msg"]],
    ["10Y government bond yields", "Trading Economics", TE_URL, yld_src["date"],
     yld_src["fetched"], "✅" if yld_src["ok"] else "⚠️", yld_src["msg"]],
], columns=["Data", "Provider", "URL", "Data date", "Fetched", "Status", "Note"])
st.dataframe(src, width="stretch", hide_index=True,
             column_config={"URL": st.column_config.LinkColumn("URL")})
st.caption("Notes say whether each value is live or from the bundled source downloads in the repo's data/ folder. "
           "Any source marked ⚠️ could not be loaded; use the sidebar overrides for those values.")
