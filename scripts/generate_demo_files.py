"""Generate the documented synthetic source files; no filename-dependent parsing."""

import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.seed import demo_payloads
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4


def generate():
    directory = ROOT / "demo" / "fixtures"
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in demo_payloads().items():
        (directory / (name + ".json")).write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
        rows = [
            {**{k: v for k, v in data.items() if k != "items"}, **item}
            for item in data["items"]
        ]
        keys = list(dict.fromkeys(key for row in rows for key in row))
        with (directory / (name + ".csv")).open(
            "w", encoding="utf-8", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
        pdf = canvas.Canvas(str(directory / (name + ".pdf")), pagesize=A4)
        pdf.setTitle("BuildTrust fictional " + data["document_type"])
        pdf.setFillColor(HexColor("#19343f"))
        pdf.rect(0, 750, 595, 92, fill=1, stroke=0)
        pdf.setFillColor(HexColor("#ffffff"))
        pdf.setFont("Helvetica-Bold", 24)
        pdf.drawString(44, 795, "BuildTrust Demo Construction Ltd.")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(44, 773, "Fictional construction finance source record")
        pdf.setFillColor(HexColor("#2f675c"))
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(
            44,
            712,
            {
                "BOQ": "Approved bill of quantities",
                "PO": "Purchase order",
                "GRN": "Goods received note",
                "INVOICE": "Supplier invoice",
            }.get(data["document_type"], data["document_type"]),
        )
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(HexColor("#657b82"))
        pdf.drawString(44, 689, "Metro Commercial Building - Phase 1 | Currency: BDT")
        y = 653
        pdf.setFont("Courier", 8.5)
        pdf.setFillColor(HexColor("#324d59"))
        for key, value in data.items():
            if key in ("items", "notes"):
                continue
            pdf.drawString(44, y, key.replace("_", " ").title() + ": " + str(value))
            y -= 20
        y -= 8
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(44, y, "Line records")
        y -= 22
        pdf.setFont("Helvetica", 8)
        pdf.drawString(
            44,
            y,
            "Code | Specification | Quantity | Unit | Contract/claim rate | Line amount",
        )
        y -= 20
        pdf.setFont("Courier", 8.5)
        for item in data["items"]:
            values = [
                item.get(k, "0")
                for k in (
                    "item_code",
                    "description",
                    "quantity",
                    "unit",
                    "unit_rate",
                    "amount",
                )
            ]
            pdf.drawString(44, y, "ITEM|" + "|".join(values))
            y -= 22
        if data.get("notes"):
            y -= 14
            pdf.setFont("Courier", 7.5)
            pdf.drawString(44, y, "Notes: " + data["notes"])
        pdf.setStrokeColor(HexColor("#dce6e2"))
        pdf.line(44, 82, 551, 82)
        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(HexColor("#869b94"))
        pdf.drawString(
            44, 61, "FICTIONAL DEMO ONLY - No real bank details or settlement authority"
        )
        pdf.drawRightString(551, 44, "1 / 1")
        pdf.save()
    (ROOT / "demo" / "expected_results.json").write_text(
        json.dumps(
            {
                "A": {
                    "claimed": "6650000.00",
                    "verified": "5600000.00",
                    "excess": "1050000.00",
                    "variance_percent": "18.75",
                    "status": "BLOCKED",
                },
                "B": {
                    "amount": "70000.00",
                    "balance_before": "1000000.00",
                    "balance_after": "930000.00",
                    "status": "SETTLED",
                },
                "C": {"status": "DUPLICATE"},
                "D": {"finding": "BENEFICIARY_CHANGE"},
                "E": {"finding": "INSUFFICIENT_FUNDS"},
                "F": {"finding": "SUSPICIOUS_INSTRUCTIONS"},
                "G": {"http_status": 403},
                "H": {"settlement_count": 1},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Generated 9 PDF, 9 CSV, and 9 JSON documents in {directory}")


if __name__ == "__main__":
    generate()
