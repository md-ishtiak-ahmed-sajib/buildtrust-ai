# Sample documents and public accounts

All sample companies, suppliers, beneficiary tokens and payments are fictional. Files contain real PDF, CSV or JSON data. Renaming a file does not change its contents.

`public-accounts.json` defines the four intentionally public logins for the separate demo. Ordinary setup still creates random private passwords. See the [README](../README.md) to start the correct profile.

## Document examples

Fixtures are available in PDF, CSV and JSON. `expected_results.json` records independent headline expectations. `document.schema.json` is generated from the real import model.

| Type | Required facts |
|---|---|
| BOQ | Item code/specification, unit, quantity and rate |
| PO | Supplier, PO number, currency and item lines |
| GRN/receipt | PO number, receipt number and accepted item quantities |
| Invoice | Supplier, PO, invoice number/date, beneficiary, totals and lines |
| Quantity variation | Supported source item and separately authorized quantity change |

## JSON

Use one object with `document_type` and an `items` list. Types are BOQ, PO, GRN, INVOICE or VARIATION. Financial/quantity inputs are strings rather than binary JSON floats.

```json
{"document_type":"BOQ","items":[{"item_code":"CEMENT-50KG","description":"Portland Cement 50 kg bag","quantity":"100","unit":"bag","unit_rate":"700","amount":"70000"}]}
```

Use the complete invoice fixtures for working fictional supplier fingerprints. Do not invent a new beneficiary to make an invoice pass. The approved supplier record is authoritative. Headline sample tax and retention are explicitly zero. Fixed discounts are per invoice; whole-order progressive discount allocation is unsupported.

## CSV and PDF

CSV uses UTF-8, one row per item and identical repeated document metadata. Item columns include `item_code,description,quantity,unit,unit_rate,amount`. Conflicting row metadata is rejected. Use the full sample files rather than an incomplete header fragment.

Machine-readable PDFs use labelled headers and line records such as:

```text
ITEM|CEMENT-50KG|Portland Cement 50 kg bag|100|bag|700|70000
```

The parser also extracts supported tables. Suggestions need human review. Arbitrary visual layouts are not automatically understood. Scans without usable OCR enter NEEDS_REVIEW and allow manual correction.

## Bounds and trust

File limit: 10 MB. PDF limit: 50 pages. Parsing normally times out after 15 seconds. Optional configured OCR allows bounded longer processing and at most five scanned pages. OCR models are not bundled; setup pins their hashes and runtime performs no downloads. Protected previews show page images or escaped text, never public original-file URLs.

BOQ/variations require Admin confirmation. PO/receipts require Manager/Admin confirmation. An `approved` word inside a file grants nothing. Confirmed procurement is immutable. Corrections retain revisions and invalidate affected proposals.

Duplicate file contents or invoice identities are held without creating a second payable invoice. Blocked invoices consume no quantity. Valid pending proposals reserve supported quantities until settlement or release.

See [financial rules](../docs/financial-rules.md), [quotation imports](../docs/price-source-integrations.md) and [OCR limits](../docs/quantity-surveying-standards.md).
