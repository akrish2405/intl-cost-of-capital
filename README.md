# International Cost of Capital App

A Streamlit app that compares a project's **cost of equity, cost of debt and WACC in USD and
in the currency of any selected country**.

**Live app:** _paste your Streamlit link here_

## Data sources (fetched live, with dates and a Refresh button)
| Data | Source |
|---|---|
| U.S. industry unlevered betas | Aswath Damodaran, [betas.xls](https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls) |
| Baa2/BBB USD spread (large non-financial firms) | Aswath Damodaran, [ratings.html](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html) |
| Statutory corporate tax rates | [OECD Corporate Tax Statistics 2024](https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html) |
| 10-year government bond yields | [Trading Economics](https://tradingeconomics.com/bonds) (scraped, no API key) |

### Bundled source downloads (`data/` folder)
Some sites block automated downloads from Streamlit Cloud, so the app falls back to copies of the
source data kept in the repo:
| File | Content |
|---|---|
| `data/betas.xls` | Damodaran U.S. industry betas, downloaded file (updated 2026-01-05) |
| `data/oecd_cit_2024.csv` | Statutory combined CIT rates for 143 jurisdictions, OECD *Corporate Tax Statistics 2024*, Figure 2.1. The figure has no printed values, so rates were measured from the PDF's vector bar lengths (`tools/extract_oecd_rates.py`), calibrated on known round rates; accuracy ±0.05 pp. Check e.g. U.S. 25.59% |
| BBB spread fallback | Baa2/BBB = 1.11%, large non-financial firms, Damodaran ratings page (data as of January 2026) |

The Data sources table in the app says whether each value is live or from these files. Every value
can also be overridden manually in the sidebar.

## Features
- Choose industry, target country, equity risk premium and target debt share
- Manual overrides for unlevered beta, U.S. and foreign tax rates, USD BBB spread and both 10Y yields
- Foreign-currency BBB spread: auto-calculated, or overridden with a manual value
- Switch the project tax rate between U.S. and selected-country rate (same rate used for both currencies)
- Side-by-side USD vs local-currency results, assumptions panel, all-industry comparison, CSV downloads
- Built-in verification checks

**Defaults:** Software (System & Application), United States, U.S. tax rate, ERP 6.5%, 30% debt.

## Formulas (from class: Rebelo, Case Packet 2026)
- Relevered beta: βE = βU × [1 + (1 − τ) × D/E], D/E = d/(1 − d)
- USD cost of equity: Re = Rf + βE × ERP; USD pre-tax cost of debt: Rd = Rf + s
- Conversion factor: F = (1 + Rf*)/(1 + Rf)
- Foreign cost of equity: 1 + Re* = (1 + Re) × F
- Foreign spread: s* = s × F (default) or manual override; Rd* = Rf* + s*
- WACC = (1 − d) Re + d Rd (1 − τ)

Check: the class Colombia example (βU 0.80, d 30%, τ 35%, ERP 6.5%, Rf 4%, Rf* 12%, s 1.5%)
gives WACC 8.5265% (USD) and 16.0670% (COP), as in the slides.

## Repository layout
```
app.py
requirements.txt
README.md
data/betas.xls
data/oecd_cit_2024.csv
tools/extract_oecd_rates.py
```

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Verification
1. Equal government yields (FC spread override off) → identical USD and FC results
2. Zero debt → WACC = cost of equity
3. Overriding the FC spread leaves USD results unchanged

All three are checked live in the app's "Verification checks" panel.
