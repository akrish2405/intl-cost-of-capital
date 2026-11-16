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

If a source cannot be reached, the app flags it (⚠️) and asks for a manual input. The OECD
page is mostly charts, so if its table cannot be parsed the app uses embedded OECD 2024 rates.

## Features
- Choose industry, target country, equity risk premium and target debt share
- Manual overrides for unlevered beta, U.S. and foreign tax rates, USD BBB spread and both 10Y yields
- Foreign-currency BBB spread: auto-calculated, or overridden with a manual value
- Switch the project tax rate between U.S. and selected-country rate (same rate used for both currencies)
- Side-by-side USD vs local-currency results, assumptions panel, all-industry comparison, CSV downloads
- Built-in verification checks

**Defaults:** Software (System & Application), United States, U.S. tax rate, ERP 6.5%, 30% debt.

## Formulas
- Levered beta: βL = βU × [1 + (1 − t) × D/E]
- USD cost of equity: ke$ = y_US + βL × ERP
- USD pre-tax cost of debt: kd$ = y_US + BBB spread
- Foreign currency (default, multiplicative): (1 + k_FC) = (1 + k$) × (1 + y_FC) / (1 + y_US)
  (an additive option k_FC = k$ + y_FC − y_US is also available)
- FC cost of debt with spread override: kd_FC = y_FC + override spread
- WACC = E/V × ke + D/V × kd × (1 − t)

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
