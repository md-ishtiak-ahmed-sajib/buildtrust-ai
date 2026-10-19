import csv
from io import StringIO

from test_advanced_upgrade import demo, estimate


def test_export_context_and_nonzero_allowance_roundtrip_does_not_double_markup(env):
    _, client, headers = env
    data = demo(env)
    current = estimate(client, headers, data["estimate_id"])
    fields = current["fields"]
    fields.update(site_overhead_percent="5", general_overhead_percent="3", profit_percent="10", contingency_percent="2", tax_percent="0")
    updated = client.patch(f"/api/v1/estimates/{current['id']}", headers=headers["operator"],
                         json={"expected_version": current["version"], "name": "Sourced markup roundtrip", "fields": fields})
    assert updated.status_code == 200, updated.text
    current = updated.json()
    exported = client.get(f"/api/v1/estimates/{current['id']}/export?format=csv", headers=headers["auditor"])
    assert exported.status_code == 200
    rows = list(csv.DictReader(StringIO(exported.content.decode("utf-8-sig"))))
    assert rows[0]["estimate_name"] == current["name"]
    assert rows[0]["currency"] == "BDT" and rows[0]["estimate_status"] == "DRAFT"
    assert rows[0]["estimate_cost_total"] == current["cost_total"]
    assert rows[0]["estimate_tender_total"] == current["tender_total"]
    imported = client.post(f"/api/v1/estimates/{current['id']}/import", headers=headers["operator"],
                           data={"expected_version": current["version"]}, files={"file": ("context.csv", exported.content, "text/csv")})
    assert imported.status_code == 200, imported.text
    assert imported.json()["total"] == current["total"]
    assert imported.json()["cost_total"] == current["cost_total"]
