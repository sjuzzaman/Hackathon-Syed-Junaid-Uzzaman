import calendar
import io
import os

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Inter if the font files are present alongside main.py
_font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"
if os.path.exists(os.path.join(_font_dir, "Inter-Regular.ttf")):
    pdfmetrics.registerFont(TTFont("Inter",     os.path.join(_font_dir, "Inter-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("Inter-Bold", os.path.join(_font_dir, "Inter-Bold.ttf")))
    _FONT, _FONT_BOLD = "Inter", "Inter-Bold"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="OpenLedger", layout="wide")

months_of_the_year = ["January","February","March","April","May","June",
                      "July","August","September","October","November","December"]

# ── Sidebar: file upload ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("OpenLedger")
    uploaded_file = st.file_uploader("Upload transaction CSV", type=["csv"])

if uploaded_file is None:
    st.title("Welcome to OpenLedger")
    st.info("Upload your transaction CSV in the sidebar to get started.")
    st.stop()

# ── Data ──────────────────────────────────────────────────────────────────────
df = pd.read_csv(uploaded_file, encoding='utf-8-sig')

# Build an ordered list of month names that actually appear in the data
months_count = sorted(df['Month'].unique())
months = [months_of_the_year[a - 1] for a in months_count]

# ── PDF generation ────────────────────────────────────────────────────────────
def _scorecard_image(on_time_rate, receipt_rate, local_pct, diverse_pct):
    """Render the compliance scorecard as a Plotly table and return PNG bytes."""
    def status(value, green, yellow):
        if value >= green:   return "✔ PASS",   "#2D7D46"
        elif value >= yellow: return "◉ REVIEW", "#B45309"
        else:                return "✘ FAIL",   "#B91C1C"

    metrics   = ["On-Time Payment Rate", "Receipt Compliance", "Local DMV Vendor Spend", "Diverse Vendor Spend"]
    values    = [f"{on_time_rate:.1f}%", f"{receipt_rate:.1f}%", f"{local_pct:.1f}%", f"{diverse_pct:.1f}%"]
    threshold = ["≥ 90%", "≥ 95%", "≥ 35%", "≥ 30%"]
    statuses  = [status(on_time_rate, 90, 75), status(receipt_rate, 95, 80),
                 status(local_pct, 35, 20),    status(diverse_pct, 30, 15)]
    status_labels = [s[0] for s in statuses]
    status_colors = [s[1] for s in statuses]

    fig = go.Figure(go.Table(
        columnwidth=[3, 1.2, 1.2, 1.2],
        header=dict(
            values=["<b>Metric</b>", "<b>Your Value</b>", "<b>Threshold</b>", "<b>Status</b>"],
            fill_color="#1C1C1C", font=dict(color="white", size=12, family="Inter, sans-serif"),
            align=["left", "center", "center", "center"], height=36,
        ),
        cells=dict(
            values=[metrics, values, threshold, status_labels],
            fill_color=[
                ["#FAFAFA", "#F3F3F3"] * 2,
                ["#FAFAFA", "#F3F3F3"] * 2,
                ["#FAFAFA", "#F3F3F3"] * 2,
                ["#FAFAFA", "#F3F3F3"] * 2,
            ],
            font=dict(
                color=[["#1A1A1A"]*4, ["#1A1A1A"]*4, ["#6B6560"]*4, status_colors],
                size=[11, 13, 10, 12],
                family="Inter, sans-serif",
            ),
            align=["left", "center", "center", "center"], height=34,
        ),
    ))
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=210, width=720,
                      paper_bgcolor="white")
    return fig.to_image(format="png", scale=2)


def generate_pdf(df, on_time_rate, receipt_rate, local_pct, diverse_pct, alerts, exceptions):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            rightMargin=0.75 * inch, leftMargin=0.75 * inch,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch)

    normal = ParagraphStyle('normal', fontName=_FONT,      fontSize=10, leading=15, spaceAfter=4)
    h1     = ParagraphStyle('h1',     fontName=_FONT_BOLD, fontSize=13, leading=18, spaceBefore=14, spaceAfter=6)
    title  = ParagraphStyle('title',  fontName=_FONT_BOLD, fontSize=22, leading=28, spaceAfter=4, textColor=colors.HexColor('#1C1C1C'))
    sub    = ParagraphStyle('sub',    fontName=_FONT,      fontSize=10, leading=14, textColor=colors.HexColor('#6B6560'))
    story  = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("OpenLedger", title))
    story.append(Paragraph(f"Compliance Report · {pd.Timestamp.now().strftime('%B %d, %Y')}", sub))
    story.append(Spacer(1, 0.08 * inch))
    # Thin accent rule under header
    story.append(Table([[""]], colWidths=[7 * inch],
                       style=TableStyle([('LINEBELOW', (0,0), (-1,-1), 2, colors.HexColor('#CC6B4E'))])))
    story.append(Spacer(1, 0.25 * inch))

    # ── Compliance scorecard (Plotly image) ───────────────────────────────────
    story.append(Paragraph("Compliance Scorecard", h1))
    story.append(Spacer(1, 0.08 * inch))
    sc_png = _scorecard_image(on_time_rate, receipt_rate, local_pct, diverse_pct)
    story.append(Image(io.BytesIO(sc_png), width=7 * inch, height=7 * inch * 210 / 720))
    story.append(Spacer(1, 0.3 * inch))

    # ── Active alerts ─────────────────────────────────────────────────────────
    critical_warning = [a for a in alerts if a["tier"] in ("critical", "warning")]
    if critical_warning:
        story.append(Paragraph("Active Alerts", h1))
        for a in critical_warning:
            dot   = "■" if a["tier"] == "critical" else "▲"
            color = "#B91C1C" if a["tier"] == "critical" else "#B45309"
            story.append(Paragraph(f"<font color='{color}'>{dot}</font>  <b>{a['title']}</b>", normal))
            story.append(Paragraph(a["detail"],
                ParagraphStyle('detail', fontName=_FONT, fontSize=9, leading=13,
                               textColor=colors.HexColor('#6B6560'), leftIndent=14, spaceAfter=8)))
        story.append(Spacer(1, 0.15 * inch))

    # ── Flagged transactions ──────────────────────────────────────────────────
    if not exceptions.empty:
        story.append(Paragraph(f"Flagged Transactions  ({len(exceptions)})", h1))
        cols      = ["Transaction ID", "Date", "Vendor Name", "Amount Spent"]
        flag_data = [cols] + [[str(row[c]) for c in cols] for _, row in exceptions.head(20).iterrows()]
        flag_tbl  = Table(flag_data, colWidths=[1.5*inch, 1*inch, 2.5*inch, 1.5*inch])
        flag_tbl.setStyle(TableStyle([
            ('BACKGROUND',     (0,0), (-1,0),  colors.HexColor('#1C1C1C')),
            ('TEXTCOLOR',      (0,0), (-1,0),  colors.white),
            ('FONTNAME',       (0,0), (-1,0),  _FONT_BOLD),
            ('FONTNAME',       (0,1), (-1,-1), _FONT),
            ('FONTSIZE',       (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F3F3')]),
            ('LINEBELOW',      (0,0), (-1,-1), 0.4, colors.HexColor('#E0E0E0')),
            ('TOPPADDING',     (0,0), (-1,-1), 6),
            ('BOTTOMPADDING',  (0,0), (-1,-1), 6),
        ]))
        story.append(flag_tbl)

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * inch))
    story.append(Table([[""]], colWidths=[7*inch],
                       style=TableStyle([('LINEABOVE', (0,0), (-1,-1), 0.5, colors.HexColor('#E0E0E0'))])))
    story.append(Paragraph(
        "Generated by OpenLedger · Confidential · For compliance review purposes only",
        ParagraphStyle('foot', fontName=_FONT, fontSize=7, textColor=colors.HexColor('#9B9B9B'), alignment=1, spaceBefore=6)))

    doc.build(story)
    buffer.seek(0)
    return buffer

# ── Latest Day ────────────────────────────────────────────────────────────────
st.title("Latest Day")
st.caption("The most recent date recorded in the transaction log, so you know how fresh this data is.")
col1, col2, col3 = st.columns(3)
last = df.iloc[-1]
col1.metric("Month", months_of_the_year[int(last["Month"]) - 1])
col2.metric("Day", int(last["Day"]))
col3.metric("Year", int(last["Year"]))

# ── Smart Alerts ──────────────────────────────────────────────────────────────
st.title("Smart Alerts")
st.caption("Warnings, recommendations, and strengths computed live from the transaction data — not pre-set flags, but rules run against the numbers every time this loads.")

with st.expander("Legend", expanded=False):
    st.markdown(
        "🚨 **Critical** — overdue invoices, projected budget overrun, receipt gaps over $10k  \n"
        "⚠️ **Warning** — payments due within 7 days, approval backlog, chronic late-paying vendors  \n"
        "💡 **Recommendation** — vendor concentration risk, diverse-vendor spend below contract thresholds  \n"
        "✅ **Strength** — call-outs worth citing in a bid packet (e.g. strong local/diverse vendor spend)"
    )

alerts = []

# Parse dates once so every alert block can reuse them
date_parsed = pd.to_datetime(df["Date"], format="%m/%d/%Y")
due_parsed = pd.to_datetime(df["Payment Due Date"], format="%m/%d/%Y", errors="coerce")
today = date_parsed.max()

# Overdue invoices — still pending after their due date
overdue = df[(df["Payment Status"] == "Pending") & (due_parsed < today)]
if not overdue.empty:
    alerts.append({
        "tier": "critical", "icon": "🚨", "title": f"{len(overdue)} invoice(s) overdue",
        "detail": f"${overdue['Amount Spent'].sum():,.2f} past due — pay these first to protect vendor "
                   "relationships and your on-time rate."
    })

# Payments due within 7 days
upcoming = df[(df["Payment Status"] == "Pending") & (due_parsed >= today) & (due_parsed <= today + pd.Timedelta(days=7))]
if not upcoming.empty:
    vendor_list = ", ".join(upcoming["Vendor Name"].tolist())
    alerts.append({
        "tier": "warning", "icon": "⚠️", "title": f"{len(upcoming)} payment(s) due within 7 days",
        "detail": f"${upcoming['Amount Spent'].sum():,.2f} owed to {vendor_list} — schedule now to stay on-time."
    })

# Missing receipts — audit / grant-compliance risk
alert_expenses = df[df["Categorization Status"] != "Not Applicable"]
missing_receipts = alert_expenses[alert_expenses["Receipt Attached"] == "No"]
if not missing_receipts.empty:
    missing_total = missing_receipts["Amount Spent"].sum()
    alerts.append({
        "tier": "critical" if missing_total > 10000 else "warning", "icon": "🧾",
        "title": f"{len(missing_receipts)} expense(s) missing a receipt",
        "detail": f"${missing_total:,.2f} in spend without documentation — an auditor or grant reviewer "
                   "will flag this before you do."
    })

# Approval backlog — transactions still sitting in Pending Review
pending_approval = alert_expenses[alert_expenses["Approval Status"] == "Pending Review"]
if not pending_approval.empty:
    approvers = ", ".join(pending_approval["Approver"].unique())
    alerts.append({
        "tier": "warning", "icon": "⏳", "title": f"{len(pending_approval)} transaction(s) awaiting approval",
        "detail": f"${pending_approval['Amount Spent'].sum():,.2f} stuck in the queue with {approvers} — follow up."
    })

# Budget pace projection — extrapolate current spend rate to end of month
latest_idx = date_parsed.idxmax()
current_month = int(df.loc[latest_idx, "Month"])
current_year = int(df.loc[latest_idx, "Year"])
month_df = df[df["Month"] == current_month]
days_elapsed = month_df["Day"].max()
days_in_month = calendar.monthrange(current_year, current_month)[1]
budget = month_df["Monthly Budget"].iloc[0]
spent_so_far = month_df["Amount Spent"].sum()
projected_spend = spent_so_far / days_elapsed * days_in_month if days_elapsed else 0
if projected_spend > budget:
    alerts.append({
        "tier": "critical", "icon": "📉", "title": "On pace to exceed the monthly budget",
        "detail": f"At the current spending rate, {months_of_the_year[current_month - 1]} lands around "
                   f"${projected_spend:,.2f} against a ${budget:,.2f} budget."
    })

# Chronic late payments — vendors paid late on 50%+ of 3+ transactions
alert_paid = df[df["Payment Status"] != "Not Applicable"]
late_stats = alert_paid.groupby("Vendor Name").agg(
    late_rate=("On-Time Payment", lambda x: (x == "No").mean()),
    n=("On-Time Payment", "count")
).reset_index()
chronic_late = late_stats[(late_stats["n"] >= 3) & (late_stats["late_rate"] >= 0.5)].sort_values("late_rate", ascending=False)
if not chronic_late.empty:
    names = ", ".join(f"{r['Vendor Name']} ({r['late_rate'] * 100:.0f}% late)" for _, r in chronic_late.iterrows())
    alerts.append({
        "tier": "warning", "icon": "🕒", "title": "Chronic late payments to local vendors",
        "detail": f"{names} — tightening AP timing here protects the relationship and any early-pay discounts."
    })

# Vendor concentration risk — single vendor dominates spend
alert_vendors = df[df["Vendor Name"] != "Not Applicable"]
vendor_spend_series = alert_vendors.groupby("Vendor Name")["Amount Spent"].sum().sort_values(ascending=False)
top_share = vendor_spend_series.iloc[0] / vendor_spend_series.sum() * 100
if top_share > 10:
    alerts.append({
        "tier": "recommendation", "icon": "💡", "title": "Vendor concentration risk",
        "detail": f"{vendor_spend_series.index[0]} accounts for {top_share:.1f}% of total spend — a disruption there "
                   "would hit hard. Worth lining up a backup supplier."
    })

# Local & diverse vendor spend — flag as strength or gap vs DMV thresholds
diverse = alert_vendors[~alert_vendors["Vendor Ownership Classification"].isin(["Not Applicable", "Not Disclosed"])]
diverse_pct = diverse["Amount Spent"].sum() / alert_vendors["Amount Spent"].sum() * 100
local_pct_alert = (alert_vendors["DMV Local Vendor"] == "Yes").mean() * 100
if diverse_pct >= 40 and local_pct_alert >= 80:
    alerts.append({
        "tier": "strength", "icon": "✅", "title": "Strong local & diverse vendor spend",
        "detail": f"{local_pct_alert:.0f}% local, {diverse_pct:.0f}% to diverse-owned vendors — this clears "
                   "most DMV contract set-aside thresholds. Worth citing in bid packets or grant applications."
    })
elif diverse_pct < 30:
    alerts.append({
        "tier": "recommendation", "icon": "💡", "title": "Diverse vendor spend below typical contract thresholds",
        "detail": f"Only {diverse_pct:.0f}% of spend goes to diverse-owned vendors — many DMV set-aside programs "
                   "require 30%+. Consider sourcing more from women/minority/veteran-owned vendors."
    })

# Sort alerts by severity and render them
tier_rank = {"critical": 0, "warning": 1, "recommendation": 2, "strength": 3}
alerts.sort(key=lambda alert: tier_rank[alert["tier"]])
tier_counts = {tier: sum(1 for a in alerts if a["tier"] == tier) for tier in tier_rank}

m1, m2, m3, m4 = st.columns(4)
m1.metric("Critical", tier_counts["critical"])
m2.metric("Warnings", tier_counts["warning"])
m3.metric("Recommendations", tier_counts["recommendation"])
m4.metric("Strengths", tier_counts["strength"])

if not alerts:
    st.success("No active alerts — everything is within normal thresholds.")
else:
    render = {"critical": st.error, "warning": st.warning, "recommendation": st.info, "strength": st.success}
    for a in alerts:
        render[a["tier"]](f"**{a['title']}**\n\n{a['detail']}", icon=a["icon"])

# ── Business Overview ─────────────────────────────────────────────────────────
st.title("Business Overview")
st.caption("Revenue vs. spending trends for the selected month, plus totals across the year, so you can see where the money moves.")

# Month and day filters sit side-by-side above the charts
filter_col1, filter_col2 = st.columns(2)
with filter_col1:
    selected_month = st.select_slider("Select a month", options=months)

month_num = months.index(selected_month) + 1
monthly = df[df['Month'] == month_num].groupby("Day").agg(
    {'Revenue': 'sum', 'Amount Spent': 'sum', 'Monthly Budget Remaining': 'last'}
).reset_index()

with filter_col2:
    selected_day = st.slider("Select a day", min_value=1, max_value=int(df[df['Month'] == month_num]['Day'].max()), value=1)

# Daily line chart with a vertical marker for the selected day
fig = px.line(monthly, x="Day", y=["Revenue", "Amount Spent"],
              title=f"Revenue by Month — {selected_month}",
              labels={"value": "Amount ($)", "variable": ""},
              color_discrete_map={"Revenue": "blue", "Amount Spent": "red"})
fig.add_vline(x=selected_day, line_dash="dash", line_color="green",
              annotation_text=f"Day {selected_day}", annotation_position="top")
fig.update_xaxes(tickvals=monthly["Day"])
st.plotly_chart(fig, use_container_width=True)

# Day-level metrics with delta vs the previous day
day_row = monthly[monthly["Day"] == selected_day]
prev_row = monthly[monthly["Day"] == selected_day - 1]

if not day_row.empty:
    rev = day_row["Revenue"].values[0]
    spent = day_row["Amount Spent"].values[0]
    budget_remaining = day_row["Monthly Budget Remaining"].values[0]

    if not prev_row.empty:
        rev_delta_str = f"${rev - prev_row['Revenue'].values[0]:+,.2f}"
        spent_delta_str = f"${spent - prev_row['Amount Spent'].values[0]:+,.2f}"
        budget_delta_str = f"${budget_remaining - prev_row['Monthly Budget Remaining'].values[0]:+,.2f}"
    else:
        rev_delta_str = spent_delta_str = budget_delta_str = None

    col1, col2, col3 = st.columns(3)
    col1.metric("Revenue", f"${rev:,.2f}", rev_delta_str)
    col2.metric("Amount Spent", f"${spent:,.2f}", spent_delta_str, delta_color="inverse")
    col3.metric("Budget Remaining", f"${budget_remaining:,.2f}", budget_delta_str, delta_color="inverse")

# Monthly bar charts — total spend and total revenue across all months
spent_by_month = df.groupby("Month")["Amount Spent"].sum().reset_index()
spent_by_month["Month Name"] = spent_by_month["Month"].apply(lambda m: months_of_the_year[m - 1])

fig_spent = px.bar(spent_by_month, x="Month Name", y="Amount Spent",
                   title="Total Amount Spent per Month", text="Amount Spent",
                   color_discrete_sequence=["red"])
fig_spent.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
fig_spent.update_yaxes(title="Amount Spent ($)")
st.plotly_chart(fig_spent, use_container_width=True)

revenue_by_month = df.groupby("Month")["Revenue"].sum().reset_index()
revenue_by_month["Month Name"] = revenue_by_month["Month"].apply(lambda m: months_of_the_year[m - 1])

fig_rev = px.bar(revenue_by_month, x="Month Name", y="Revenue",
                 title="Total Revenue per Month", text="Revenue",
                 color_discrete_sequence=["blue"])
fig_rev.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
fig_rev.update_yaxes(title="Revenue ($)")
st.plotly_chart(fig_rev, use_container_width=True)

# ── Fair Operations ───────────────────────────────────────────────────────────
st.title("Fair Operations")
st.caption("How reliably vendors get paid and how spending is distributed across ownership groups — the fairness and equity story behind the numbers.")

# Exclude rows where payment tracking doesn't apply
paid = df[df["Payment Status"] != "Not Applicable"]
on_time_rate = (paid["On-Time Payment"] == "Yes").mean() * 100
late = paid[paid["On-Time Payment"] == "No"]

col1, col2 = st.columns(2)
col1.metric("On-Time Payment Rate", f"{on_time_rate:.1f}%")
col2.metric("Avg Days Late (when late)", f"{late['Days to Pay'].mean():.0f} days")

# Payment status pie chart
status_counts = paid["Payment Status"].value_counts().reset_index()
status_counts.columns = ["Payment Status", "Count"]
fig = px.pie(status_counts, values="Count", names="Payment Status",
             title="Payment Status Breakdown", color="Payment Status",
             color_discrete_map={"Paid On Time": "green", "Paid Late": "red", "Pending": "orange"})
st.plotly_chart(fig, use_container_width=True)

# Vendor ownership spend breakdown
ownership = df[~df["Vendor Ownership Classification"].isin(["Not Applicable"])]
ownership_spend = ownership.groupby("Vendor Ownership Classification")["Amount Spent"].sum().reset_index()
fig = px.pie(ownership_spend, values="Amount Spent", names="Vendor Ownership Classification",
             title="Spend by Vendor Ownership Classification")
st.plotly_chart(fig, use_container_width=True)

# ── Needs Your Attention ──────────────────────────────────────────────────────
st.title("Needs Your Attention")
st.caption("Transactions the system flagged as unusual — anomalies, large expenses, or budget alerts — that a human should double-check.")
exceptions = df[df["Review Required"] == "Yes"]
st.metric("Transactions Flagged for Review", len(exceptions))

st.dataframe(
    exceptions[["Transaction ID", "Date", "Vendor Name", "Amount Spent",
                "Category Anomaly Flag", "Large Expense Flag", "Budget Alert", "Fair Operations Note"]],
    use_container_width=True
)

# ── Vendor Transparency ───────────────────────────────────────────────────────
st.title("Vendor Transparency")
st.caption("Who the business actually spends money with — how much goes to local DMV vendors versus outside ones.")

vendors = df[df["Vendor Name"] != "Not Applicable"]
vendor_spend = vendors.groupby(["Vendor Name", "DMV Local Vendor"]).agg(
    {"Amount Spent": "sum", "Transaction ID": "count"}
).reset_index().rename(columns={"Transaction ID": "Transactions"})
vendor_spend = vendor_spend.sort_values("Amount Spent", ascending=False)

local_pct = (vendors["DMV Local Vendor"] == "Yes").mean() * 100
col1, col2 = st.columns(2)
col1.metric("Local DMV Vendor Rate", f"{local_pct:.1f}%")
col2.metric("Unique Vendors", vendors["Vendor Name"].nunique())

fig = px.bar(vendor_spend.head(10), x="Vendor Name", y="Amount Spent",
             color="DMV Local Vendor", title="Top 10 Vendors by Spend")
st.plotly_chart(fig, use_container_width=True)

# ── Back-Office Automation & Integrity ───────────────────────────────────────
st.title("Back-Office Automation & Integrity")
st.caption("How much of the bookkeeping runs itself — auto-approvals, receipt compliance, and duplicate-transaction catches — versus what still needs a person.")

expenses = df[df["Categorization Status"] != "Not Applicable"]

col1, col2, col3, col4 = st.columns(4)

# Auto-approval rate — share of expenses approved by the policy engine, not a human
auto_approved_rate = (expenses["Approval Status"] == "Auto-Approved").mean() * 100
col1.metric("Auto-Approval Rate", f"{auto_approved_rate:.1f}%")

# Straight-through processing — no anomaly, no budget alert, no duplicate, no pending approval
straight_through = ((expenses["Category Anomaly Flag"] == "No") &
                    (expenses["Budget Alert"] == "No") &
                    (expenses["Duplicate Flag"] == "No") &
                    (expenses["Approval Status"] != "Pending Review")).mean() * 100
col2.metric("Straight-Through Processing", f"{straight_through:.1f}%")

receipts = expenses[expenses["Receipt Attached"] != "Not Applicable"]
receipt_rate = (receipts["Receipt Attached"] == "Yes").mean() * 100
col3.metric("Receipt Compliance", f"{receipt_rate:.1f}%")

duplicate_count = (df["Duplicate Flag"] == "Yes").sum()
col4.metric("Duplicate Transactions Caught", int(duplicate_count))

col1, col2 = st.columns(2)

approval_counts = expenses["Approval Status"].value_counts().reset_index()
approval_counts.columns = ["Approval Status", "Count"]
fig = px.pie(approval_counts, values="Count", names="Approval Status",
             title="Expense Approval Breakdown", color="Approval Status",
             color_discrete_map={"Auto-Approved": "green", "Approved": "blue", "Pending Review": "orange"})
col1.plotly_chart(fig, use_container_width=True)

workflow_counts = expenses["Automation Status"].value_counts().reset_index()
workflow_counts.columns = ["Automation Status", "Count"]
fig = px.bar(workflow_counts, x="Count", y="Automation Status", orientation="h",
             title="Automation Workflow Paths")
fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin={"l": 10})
col2.plotly_chart(fig, use_container_width=True)

# Compliance gaps table — expenses missing a receipt or flagged as a duplicate
st.subheader("Compliance Gaps")
gaps = expenses[(expenses["Receipt Attached"] == "No") | (expenses["Duplicate Flag"] == "Yes")]
st.dataframe(
    gaps[["Transaction ID", "Date", "Vendor Name", "Amount Spent",
          "Receipt Attached", "Duplicate Flag", "Approval Status"]],
    use_container_width=True
)

# ── Sidebar: PDF download ─────────────────────────────────────────────────────
with st.sidebar:
    st.divider()
    st.subheader("Compliance Report")
    st.caption("Downloads a PDF scorecard with your key compliance metrics, active alerts, and flagged transactions.")
    pdf_buffer = generate_pdf(df, on_time_rate, receipt_rate, local_pct, diverse_pct, alerts, exceptions)
    st.download_button(
        label="Download PDF Report",
        data=pdf_buffer,
        file_name="openledger_compliance_report.pdf",
        mime="application/pdf",
    )