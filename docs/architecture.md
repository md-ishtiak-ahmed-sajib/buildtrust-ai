# Architecture guide

The full system description is in `technical-documentation.md`; the editable Mermaid source is `architecture.mmd`.

## Responsibilities

- `backend/app/main.py`: API boundary, explicit serialization, authenticated project access, structured denial auditing, and local static serving.
- `documents.py` / `pdf_worker.py`: real-content intake, versioned field provenance, trusted-source publication, private raster preview, and bounded native parsing.
- `finance.py` / `money.py`: deterministic matching, quantity/rate normalization, exact money, risk findings, cash scenarios, and source snapshots.
- `payments.py`: reservations, separation of duties, approval limits and snapshots, current revalidation, idempotency, and atomic local settlement.
- `audit.py`: canonical chained audit records and integrity verification.
- `workflow.py`: observable persisted tool stages, grounded questions, and optional explanation adapter.
- `models.py` / `alembic`: relational constraints and explicit schema installation.
- `frontend/src`: six connected financial screens, role-aware actions, protected evidence viewing, and generated API contracts.

The database is the source of financial truth. Frontend calculations and optional model prose do not authorize or alter settlement.
