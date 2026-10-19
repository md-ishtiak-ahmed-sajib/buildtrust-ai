# Source document formats

All provided records are fictional. Each fixture exists as PDF, CSV, and JSON. `expected_results.json` contains independently specified headline expectations; `document.schema.json` is exported from the actual Pydantic import model.

## JSON

One object contains `document_type` (`BOQ`, `PO`, `GRN`, `INVOICE`, or `VARIATION`) and an `items` list. Numeric inputs must be strings, not binary JSON floats.

```json
{"document_type":"INVOICE","invoice_number":"NEW-001","invoice_date":"2026-10-18","supplier_code":"DEMO-CEMENT","po_number":"PO-CEMENT-001","currency":"BDT","beneficiary_fingerprint":"COPY_THE_FICTIONAL_APPROVED_FINGERPRINT_FROM_PROJECT_DETAILS","subtotal":"70000","grand_total":"70000","items":[{"item_code":"CEMENT-50KG","description":"Portland Cement 50 kg bag","quantity":"100","unit":"bag","unit_rate":"700","amount":"70000"}]}
```

The full working examples contain the actual fictional fingerprints. The master supplier record remains authoritative; different invoice instructions cause a block.

BOQ items require code, specification, unit, quantity, and rate. A PO additionally requires supplier code and PO number. A receipt requires PO number and receipt number; its item quantities represent accepted delivery. An invoice requires supplier, PO, number, date, beneficiary, positive total, and line items. Tax and retention percentages are explicit PO terms, defaulting to zero in the examples. `discount` is a fixed per-invoice contractual adjustment; progressive allocation of a whole-order discount is not implemented.

## CSV

Use UTF-8 and one row per line item. Repeat identical document metadata on every row. Columns match the JSON field names; flatten item fields into `item_code`, `description`, `quantity`, `unit`, `unit_rate`, and optional `amount`. The sample CSV files are complete importable examples. Conflicting metadata between rows is rejected.

## PDF

The supported automatic parser reads actual machine-readable text. The examples use labeled headers (`Invoice Number: ...`) and line records:

```text
ITEM|CEMENT-50KG|Portland Cement 50 kg bag|100|bag|700|70000
```

PyMuPDF also extracts detected tables for intake audit evidence. Arbitrary visual layouts are not claimed as automatically understood. All PDF suggestions require review. Blank/scanned PDFs enter `NEEDS_REVIEW`; complete the fields and line items manually. No OCR model is bundled.

PDF processing and preview run in child processes with a 15-second timeout, at most 50 pages, and bounded preview dimensions. File uploads are limited to 10 MB. Previews are authenticated PNGs or plain text; original uploads are not publicly served.

## Trust and revisions

An invoice import creates a claim, not payment authority. BOQ/variation confirmation requires Admin; PO/receipt confirmation requires Finance Manager or Admin. An `approved` label inside a file grants nothing. Confirmed procurement sources are immutable. Missing/ambiguous fields and unknown units require review. Corrections retain provenance revisions and invalidate outstanding invoice proposals.

Duplicate raw file hashes or supplier/invoice business identities are held without creating a second payable invoice. A blocked invoice never reserves accepted quantities. A pending proposal does reserve them until settlement, rejection, failure, or expiry.
