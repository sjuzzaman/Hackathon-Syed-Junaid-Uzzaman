# OpenLedger — Transparent Finances for the Small Businesses That Power the DMV

## Inspiration

Small businesses in the DC–Maryland–Virginia area are the backbone of a regional economy that runs on government and institutional contracts — and those contracts almost always come with strings attached: prove your spend is local, prove a share of it goes to minority/women/veteran-owned vendors, prove your books are clean enough to survive an audit. Most small operators don't have a controller on staff to produce that proof. They have a spreadsheet, a bookkeeper they talk to once a month, and a gut feeling about whether things are okay.

The hackathon challenge — *"transparent finances, fair operations, and back-office automation for the small businesses that power the DMV"* — mapped almost exactly onto that gap. We didn't want to build another generic expense dashboard. We wanted something that could sit in front of a business owner and say, in plain language: *here is what's true about your money, here is what's fair, and here is what still needs a human.*

## What It Does

OpenLedger is a Streamlit dashboard over a transaction ledger that answers three questions:

1. **Transparent Finances** — where does revenue and spend actually go, month over month, day by day?
2. **Fair Operations** — are vendors (especially local and diverse-owned ones) getting paid on time, and is spend equitably distributed?
3. **Back-Office Automation** — how much of the bookkeeping runs itself, and where does it still break?

Sitting on top of all three is a **Smart Alerts** engine — a small rule system that evaluates the ledger live and surfaces critical issues, warnings, recommendations, and strengths, instead of making the owner go hunting for them across six charts.

## How We Built It

The stack is deliberately small: **Streamlit** for the UI, **pandas** for aggregation, **Plotly Express** for charts. No backend, no database — the whole thing runs off a single CSV, which was the right call for a hackathon timeline but is also, honestly, the thing we'd change first if this became a real product (more on that below).

The build went in three passes:

**Pass 1 — descriptive.** Revenue/spend over time, payment status breakdown, vendor spend, ownership-classification breakdown. This is the "here's what happened" layer, and it's what most finance dashboards stop at.

**Pass 2 — the automation layer.** We noticed the dataset already had columns like `Automation Status`, `Approval Status`, and `Duplicate Flag` that *looked* like automation output but were just static labels in the CSV. We built a section that computed real rates from them instead of just re-printing them, e.g.:

$$
\text{Auto-Approval Rate} = \frac{\text{count}(\textit{Approval Status} = \text{Auto-Approved})}{\text{count}(\text{expenses requiring a workflow})} \times 100\%
$$

$$
\text{Straight-Through Processing} = \frac{\text{count}(\text{no anomaly, no budget alert, no duplicate, not pending})}{\text{count}(\text{total expenses})} \times 100\%
$$

**Pass 3 — prescriptive.** This is the part we're proudest of. A business owner doesn't need eight charts; they need a short list of "do this." So we built a rule engine — `Smart Alerts` — that runs live checks and emits ranked alerts:

$$
\text{Projected Monthly Spend} = \frac{\text{Spend So Far}}{\text{Days Elapsed}} \times \text{Days in Month}, \quad \text{flag if } > \text{Monthly Budget}
$$

$$
\text{Vendor Concentration} = \frac{\max_i(\text{Spend}_i)}{\sum_i \text{Spend}_i} \times 100\%, \quad \text{flag if} > 10\%
$$

Each rule outputs a `(tier, title, detail)` tuple, tiers are sorted `critical → warning → recommendation → strength`, and rendered with matching Streamlit components (`st.error`, `st.warning`, `st.info`, `st.success`). It turns eight independent facts about the ledger into one prioritized feed.

## Challenges We Faced

- **Trusting the data too much, at first.** The dataset ships columns like `Duplicate Flag` and `Category Anomaly Flag` as if a system already computed them. Early on we just displayed them. It took a step back to realize that's not "automation" — that's reading someone else's homework. The fix was to compute our own thresholds and logic (chronic late-payment rate per vendor, receipt-compliance rate, budget pace) directly from the raw transaction fields, so the insight is actually earned from the data rather than replayed from a label.

- **Encoding gremlins.** The CSV is UTF-8 with a BOM and contains em dashes (`—`) inside category labels like `Spending Category`. Any quick Python inspection script that didn't force UTF-8 output crashed with `UnicodeEncodeError` against Windows' default `cp1252` console encoding. Small thing, but it ate real debugging time before we started writing probe scripts to file with explicit `encoding='utf-8'`.

- **Uneven calendars.** A naive "days remaining in month" calculation breaks the moment you compare February against any 31-day month. We pulled in `calendar.monthrange(year, month)` rather than hard-coding 30, since the budget-pace projection is only meaningful if the days-in-month denominator is exact.

- **Picking thresholds that mean something.** It's easy to write `if x > 0.5: warn()` and call it an alert system. We instead computed the actual distributions first (e.g., vendor late-payment rates, top-vendor spend share) and picked thresholds that were defensible against real procurement/compliance norms (10% vendor concentration, 30% diverse-spend as a common set-aside floor) rather than numbers that just happened to fire on our sample.

- **Where do interactive controls even go?** The month/day sliders started in the sidebar by convention, but that buried the one control that changes the main chart directly above it. Moving them inline, right above the "Revenue by Month" chart, was a small UX call but made the cause-and-effect between slider and chart obvious without a mental hop to the sidebar.

## What We Learned

The biggest lesson wasn't technical — it was about what "automation" and "transparency" actually mean as product features, not just dashboard sections. A column called `Automation Status` is not automation; a chart labeled "Transparency" is not transparent unless the number behind it is one you computed and can defend, not one you inherited. Once we treated every metric as something we had to *derive*, not *display*, the dashboard stopped being a report and started being closer to an actual back-office assistant — the difference between "here's your data" and "here's what to do about it."

## What's Next

If we kept building: real data ingestion (QuickBooks/Wave/Plaid instead of a static CSV), multi-tenant support so a bookkeeper can run this across several clients, exportable compliance reports formatted for grant and contract reviewers, and wiring the critical/warning alert tiers into actual notifications (email/Slack) so a business doesn't have to remember to open the dashboard to find out something is wrong.
