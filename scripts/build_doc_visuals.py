"""Rebuild simple, accessible SVG charts and diagrams from documented demo values."""

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/assets"
VALUES = json.loads((OUT / "demo-values.json").read_text(encoding="utf-8"))


def svg(name, title, description, body, height=460):
    markup = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>
<rect width="1000" height="{height}" fill="#f7f9f7"/>
<g font-family="Arial, sans-serif" fill="#19343f"><text x="40" y="48" font-size="28" font-weight="bold">{escape(title)}</text>
{body}
<text x="40" y="{height - 24}" font-size="16" fill="#526971">Fictional local demo. BDT = Bangladeshi taka. See the text table for exact values.</text></g></svg>'''
    (OUT / name).write_text(markup, encoding="utf-8", newline="\n")


def bars(name, title, rows, maximum, note):
    body = f'<text x="40" y="82" font-size="18">{escape(note)}</text>'
    for index, (label, value, color) in enumerate(rows):
        y = 128 + index * 85
        width = value / maximum * 470
        body += f'<text x="40" y="{y + 25}" font-size="20">{escape(label)}</text><rect x="310" y="{y}" width="{width:.2f}" height="38" fill="{color}"/><text x="{326 + width:.2f}" y="{y + 26}" font-size="20" font-weight="bold">{value:,.0f}</text>'
    svg(
        name,
        title,
        note + ". " + "; ".join(f"{label}: {value:,.0f}" for label, value, _ in rows),
        body,
        max(420, 165 + len(rows) * 85),
    )


def flow(name, title, nodes, description):
    body = '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#286e62"/></marker></defs>'
    for i, (heading, detail) in enumerate(nodes):
        y = 94 + i * 92
        body += f'<rect x="40" y="{y}" width="920" height="65" rx="6" fill="#e6efea" stroke="#85a89c"/><text x="62" y="{y + 27}" font-size="22" font-weight="bold">{escape(heading)}</text><text x="62" y="{y + 51}" font-size="17">{escape(detail)}</text>'
        if i < len(nodes) - 1:
            body += f'<path d="M 500 {y + 66} V {y + 89}" stroke="#286e62" stroke-width="2" marker-end="url(#arrow)"/>'
    # Flow diagrams explain real behavior, rather than illustrating a numeric result.
    svg(name, title, description, body, 145 + len(nodes) * 92)


p, e = VALUES["payment"], VALUES["estimate"]
assert p["opening_cash"] - p["payment"] == p["closing_cash"]
assert e["tonnes"] * (e["new_rate"] - e["old_rate"]) == e["difference"]
assert e["recorded_cash"] - e["new_total"] == e["new_forecast"]
bars(
    "payment-cash.svg",
    "Cash before and after one approved payment",
    [
        ("Cash before payment", p["opening_cash"], "#60777d"),
        ("Cash after payment", p["closing_cash"], "#286e62"),
        ("Required reserve", p["reserve"], "#a65c2d"),
    ],
    p["opening_cash"],
    "A BDT 70,000 sandbox payment reduces recorded cash once.",
)
bars(
    "estimate-impact.svg",
    "A new material rate changes the estimate",
    [
        ("Original estimate", e["old_total"], "#60777d"),
        ("Updated estimate", e["new_total"], "#286e62"),
        ("Earlier forecast cash", e["old_forecast"], "#60777d"),
        ("Updated forecast cash", e["new_forecast"], "#286e62"),
    ],
    e["new_total"],
    "20 tonnes: BDT 70,000 to 74,000 per tonne. Recorded cash stays at BDT 2,000,000.",
)
flow(
    "payment-flow.svg",
    "How a payment reaches sandbox settlement",
    [
        (
            "1. Read and confirm documents",
            "Review the bill of quantities, purchase order, delivery receipt and invoice.",
        ),
        (
            "2. Check the claim and cash",
            "Compare supported quantities and prices. Keep the cash reserve in both required scenarios.",
        ),
        (
            "3. Prepare an exact proposal",
            "Reserve its cash and supported delivery quantities. The Operator cannot approve it.",
        ),
        (
            "4. Obtain independent human approval",
            "A different authorized person reviews the exact amount, supplier and evidence.",
        ),
        (
            "5. Recheck, settle and keep evidence",
            "Update cash, payment, ledger and audit together. A retry cannot pay twice.",
        ),
    ],
    "Document review, deterministic checks, preparation, independent approval and atomic sandbox settlement.",
)
flow(
    "estimate-flow.svg",
    "How an estimate becomes an approved budget",
    [
        (
            "1. Measure and prepare",
            "Record dimensions, drawing references, quantities, rate components and assumptions.",
        ),
        (
            "2. Compare suitable prices",
            "Check grade, unit, full known costs, dates and source evidence before choosing a rate.",
        ),
        (
            "3. Review totals and forecast",
            "Show cost and tender totals separately. No real cash changes during the preview.",
        ),
        (
            "4. Submit, check and approve",
            "Lock the version. A separate Finance Manager checks and an independent Admin approves.",
        ),
    ],
    "Measurement and rate evidence lead to a locked estimate and independent budget approval.",
)
flow(
    "architecture.svg",
    "How the application works",
    [
        (
            "Browser: React workspace",
            "14 application areas share login, project access and clear review steps.",
        ),
        (
            "Server: FastAPI and deterministic services",
            "Document, price, measurement, accounting and payment services check every write.",
        ),
        (
            "Human approval gate",
            "An uploaded document, forecast or language model cannot grant financial authority.",
        ),
        (
            "Storage: SQLite and private files",
            "Exact financial records, source versions, reservations, receipts and a local audit chain.",
        ),
    ],
    "React calls FastAPI, which checks project permissions and uses SQLite and private source storage.",
)
print("Built five SVG diagrams/charts from labelled demo data")
