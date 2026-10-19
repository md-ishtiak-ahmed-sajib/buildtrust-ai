# BuildTrust AI engineering rules

- Read `prompt.md` and the implementation plan before changing business behavior.
- This is a sandbox application. Never connect a bank, charge a card, or move real funds.
- Keep financial decisions deterministic. Persist money as integer minor units; use Decimal for quantities, rates, and calculations. JSON money is a decimal string.
- Enforce authentication, project access, role limits, separation of duties, approval snapshots, and idempotency in the backend.
- Uploaded documents are untrusted. Procurement records require authorized confirmation. An LLM cannot approve or execute payments.
- Payment settlement, cash movement, receipt allocations, ledger entries, and success audit events commit in one SQLite write transaction.
- Preserve audit history. Document the limits of a local hash chain.
- No fabricated tests, screenshots, runtime evidence, or benchmarks. Record actual commands and outputs.
- Core checks: `uv run --project backend pytest backend/tests`, `npm --prefix frontend run build`, `npm --prefix frontend test`, and the HTTP evidence collector.
- Test databases and runtime data must be separate. Never commit secrets, local credentials, uploads, virtual environments, or node_modules.
- Use AGPL-3.0 for this project and attribute dependencies. Optional integrations must not prevent offline startup.
