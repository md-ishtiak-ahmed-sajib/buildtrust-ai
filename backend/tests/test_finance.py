from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import select
from app.money import minor, money, normalize, decimal
from app.models import (
    Invoice,
    InvoiceLine,
    Project,
    CashMovement,
    BOQItem,
    Variation,
    GoodsReceipt,
    ReceiptLine,
    PurchaseOrder,
)
from app.database import transaction
from app.finance import forecast, reconcile
from conftest import valid_invoice, prepared


def test_exact_money_and_rounding():
    assert minor("1.005") == 101
    assert money(105000000) == "1050000.00"
    with pytest.raises(ValueError):
        decimal(1.1)
    with pytest.raises(ValueError):
        minor("NaN")


def test_unit_conversion_rate_and_quantity():
    assert normalize("80", "tonnes", "70000") == (Decimal("80000"), "kg", Decimal("70"))
    with pytest.raises(ValueError):
        normalize("1", "truckload")


def test_inflated_steel_arithmetic(env):
    _, client, h = env
    invoices = client.get("/api/v1/invoices", headers=h["operator"]).json()
    steel = next(i for i in invoices if i["invoice_number"] == "INV-STEEL-095")
    r = client.post(f"/api/v1/invoices/{steel['id']}/analyze", headers=h["operator"])
    assert r.status_code == 200
    report = r.json()
    assert report["verified_amount"] == "5600000.00"
    assert report["difference"] == "1050000.00"
    assert report["comparisons"][0]["quantity_variance_percent"] == "18.75"
    assert report["comparisons"][0]["excess_quantity"] == "15000"
    assert report["status"] == "BLOCKED"
    assert len(report["comparisons"][0]["evidence"]) == 4


def test_valid_four_way_match(env):
    _, client, h = env
    invoice = valid_invoice(client, h["operator"])
    report = client.post(
        f"/api/v1/invoices/{invoice['id']}/analyze", headers=h["operator"]
    ).json()
    assert report["status"] == "VERIFIED"
    assert report["verified_amount"] == "70000.00"
    assert report["findings"] == []


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("currency", "CURRENCY_MISMATCH"),
        ("beneficiary", "BENEFICIARY_CHANGE"),
        ("price", "PRICE_MISMATCH"),
        ("total", "INVOICE_TOTAL_MISMATCH"),
    ],
)
def test_financial_controls(env, mutation, code):
    app, client, h = env
    identity = valid_invoice(client, h["operator"])["id"]
    with transaction(app.state.engine, True) as s:
        inv = s.get(Invoice, identity)
        if mutation == "currency":
            inv.currency = "USD"
        if mutation == "beneficiary":
            inv.beneficiary_fingerprint = "changed"
        if mutation == "total":
            inv.total_minor += 1
        if mutation == "price":
            s.scalar(
                select(InvoiceLine).where(InvoiceLine.invoice_id == identity)
            ).rate = "701"
    report = client.post(
        f"/api/v1/invoices/{identity}/analyze", headers=h["operator"]
    ).json()
    assert code in {f["code"] for f in report["findings"]}
    assert not report["payment_eligible"]


def test_missing_receipt(env):
    app, client, h = env
    identity = valid_invoice(client, h["operator"])["id"]
    with transaction(app.state.engine, True) as s:
        inv = s.get(Invoice, identity)
        grn = s.scalar(select(GoodsReceipt).where(GoodsReceipt.po_id == inv.po_id))
        s.delete(s.scalar(select(ReceiptLine).where(ReceiptLine.receipt_id == grn.id)))
    report = client.post(
        f"/api/v1/invoices/{identity}/analyze", headers=h["operator"]
    ).json()
    assert "UNVERIFIED_DELIVERY" in {f["code"] for f in report["findings"]}


def test_approved_variation_and_tax_retention(env):
    app, client, h = env
    identity = valid_invoice(client, h["operator"])["id"]
    with transaction(app.state.engine, True) as s:
        inv = s.get(Invoice, identity)
        boq = s.scalar(
            select(BOQItem).where(
                BOQItem.project_id == inv.project_id, BOQItem.item_code == "CEMENT-50KG"
            )
        )
        boq.quantity = "90"
        assert not reconcile(s, inv, app.state.settings)["payment_eligible"]
        s.add(
            Variation(
                boq_item_id=boq.id,
                document_id=boq.document_id,
                quantity="10",
                unit="bag",
                approved_by=1,
            )
        )
        po = s.get(PurchaseOrder, inv.po_id)
        po.tax_percent, po.retention_percent = "5", "2"
        inv.tax_minor, inv.retention_minor, inv.total_minor = (
            minor("3500"),
            minor("1400"),
            minor("72100"),
        )
        s.flush()
        report = reconcile(s, inv, app.state.settings)
        assert report["payment_eligible"], report["findings"]
        assert report["verified_amount"] == "72100.00"


def test_forecast_daily_equation_and_delay(env):
    app, _, _ = env
    with transaction(app.state.engine) as s:
        p = s.scalar(select(Project).where(Project.active.is_(True)))
        result = forecast(s, p, app.state.settings, today=date(2026, 10, 18))
        for scenario in result["scenarios"]:
            assert len(scenario["days"]) == 30
            for d in scenario["days"]:
                assert decimal(d["opening"]) + decimal(d["inflows"]) - decimal(
                    d["outflows"]
                ) == decimal(d["closing"])


def test_delayed_receivables_alone_blocks(env):
    app, client, h = env
    from app.finance import business_date

    with transaction(app.state.engine, True) as s:
        p = s.scalar(select(Project).where(Project.active.is_(True)))
        p.balance_minor = minor("200000")
        for m in s.scalars(select(CashMovement).where(CashMovement.project_id == p.id)):
            m.settled = True
        for kind, amount, days in [("INFLOW", "200000", 1), ("OUTFLOW", "100000", 2)]:
            s.add(
                CashMovement(
                    project_id=p.id,
                    kind=kind,
                    amount_minor=minor(amount),
                    currency="BDT",
                    due_date=(business_date() + timedelta(days=days)).isoformat(),
                    description=kind,
                )
            )
    inv = valid_invoice(client, h["operator"])
    report = client.post(
        f"/api/v1/invoices/{inv['id']}/analyze", headers=h["operator"]
    ).json()
    assert report["cashflow"]["scenarios"][0]["reserve_maintained"]
    assert not report["cashflow"]["scenarios"][1]["reserve_maintained"]
    assert not report["payment_eligible"]


def test_reservation_not_double_counted(env):
    p = prepared(env)
    _, client, h = env
    cash = client.get("/api/v1/cashflow/forecast", headers=h["operator"]).json()
    assert cash["reserved"] == "70000.00"
    assert cash["available_cash"] == "930000.00"
    assert (
        client.post(
            f"/api/v1/payments/{p['id']}/approve", headers=h["manager"]
        ).status_code
        == 200
    )
