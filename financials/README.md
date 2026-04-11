# Financials Module

This module provides a complete **Financial Model and Break-Even Analysis**
framework for the Prime Coastal Funding OSINT Lead Generation platform.

---

## Package Structure

```
financials/
├── __init__.py                  # Exports UnitEconomics, BreakEvenCalculator, RevenueProjections
├── unit_economics.py            # Unit economics data and margin calculations
├── break_even.py                # Platform & buyer break-even analysis
├── projections.py               # 12-month revenue projections & scenario comparison
├── financial_streamlit_tab.py   # Streamlit dashboard tab (4 sub-tabs)
└── README.md                    # This file
```

---

## 1. Unit Economics (`unit_economics.py`)

### What it calculates

For every sub-vertical (e.g., HVAC, Hard Money, Enterprise B2B) the module
derives:

| Metric | Formula |
|--------|---------|
| **Gross Margin %** | `(lead_price − CAC) / lead_price` |
| **Gross Profit / Lead** | `lead_price − CAC` |
| **CAC : LTV Ratio** | `CAC / LTV` |
| **LTV : CAC Ratio** | `LTV / CAC` |
| **Payback Period (months)** | `CAC / (close_rate × avg_value / 12)` |

### How to interpret gross margin

- **≥ 70 % (S-tier)** — excellent; prioritise these sub-verticals
- **55–70 % (A-tier)** — healthy; standard marketing spend justified
- **40–55 % (B-tier)** — acceptable; monitor customer acquisition costs
- **< 40 % (C-tier)** — thin; requires volume to offset fixed costs

### How to update assumptions

All source data lives in `VERTICAL_ECONOMICS` at the top of
`unit_economics.py`. Update any value there and all downstream
calculations (including the Streamlit UI) will reflect the change
immediately — no other edits required.

```python
VERTICAL_ECONOMICS["home_services"]["hvac"]["lead_price"] = 195.0  # new price
```

---

## 2. Break-Even Calculator (`break_even.py`)

### Platform break-even

Call `BreakEvenCalculator().calculate_platform_breakeven()` to determine
how many leads need to be sold to cover fixed monthly costs.

**Fixed costs defaults** (editable in the UI or by passing a dict):

| Cost | Default |
|------|---------|
| ATTOM API | $299 / mo |
| Bubble.io | $119 / mo |
| Google Maps | $50 / mo |
| Other | $100 / mo |

**Lead mix**: supply a list of `{vertical, sub_vertical, volume}` dicts.
Each sub-vertical's CAC is treated as the variable cost per lead.

### Buyer break-even

`calculate_buyer_breakeven(lead_price, close_rate, avg_deal_value,
origination_pct)` answers the buyer's question:

> "How many leads do I need to buy before I've recouped my investment?"

Key outputs:

- **ROI per Lead** — expected return as a fraction of lead cost
- **Cost per Closed Lead** — `lead_price / close_rate`
- **Leads to Break Even** — minimum leads to cover investment
- **Payback Period (days)** — approximate days to recoup

### Sensitivity analysis

`sensitivity_analysis(base_scenario, variable, range_pct=0.30)` sweeps
one variable (e.g., `close_rate`) ±30 % in 10 equal steps and returns
the resulting ROI and P&L at each point.

---

## 3. Revenue Projections (`projections.py`)

### 12-month model assumptions

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| Initial buyers | 10 | Conservative early-stage count |
| Monthly buyer growth | 15 % | Mid-stage SaaS benchmark |
| Avg spend / buyer | $1 200 / mo | Blended across lead packages |
| Churn rate | 5 % / mo | Typical B2B lead-gen churn |
| COGS | 12 % of revenue | API + infrastructure |
| OpEx fixed | $2 000 / mo | Staff + tooling |
| OpEx variable | 8 % of revenue | Sales commissions, support |

### Changing assumptions

Pass keyword arguments to `build_12_month_projection()`:

```python
from financials.projections import RevenueProjections

rp = RevenueProjections()
df = rp.build_12_month_projection(
    initial_buyers=20,
    monthly_buyer_growth_rate=0.20,
    avg_spend_per_buyer=1500.0,
    churn_rate=0.03,
)
```

To change COGS or OpEx percentages, update the class attributes:

```python
RevenueProjections.COGS_PCT = 0.10          # 10 % COGS
RevenueProjections.OPEX_VARIABLE_PCT = 0.06  # 6 % variable OpEx
```

### Scenario comparison

Three built-in scenarios are compared with `build_scenario_comparison()`:

| Scenario | Growth Rate |
|----------|------------|
| Conservative | 10 % / mo |
| Base | 15 % / mo |
| Aggressive | 25 % / mo |

---

## 4. Streamlit Dashboard (`financial_streamlit_tab.py`)

The `render_financial_tab(df)` function adds a **💰 Financial Model** tab
to the main app with four sub-tabs:

| Sub-tab | Contents |
|---------|----------|
| 📊 Unit Economics | Margin table, tier badges, bar chart, LTV vs CAC scatter |
| ⚖️ Break-Even Calculator | Fixed cost editor, lead volume sliders, waterfall P&L chart, Buyer ROI tool |
| 📈 12-Month Projections | Three-scenario MRR chart, net profit bar chart, full data table, CSV export |
| 🎯 Vertical Ranker | Top N sub-verticals ranked with tier badges, horizontal bar chart, CSV export |

---

## Running the tests

```bash
pytest tests/test_financials.py -v
```

All financial calculation tests are self-contained and do not require
Playwright, ATTOM API credentials, or an active Streamlit session.
