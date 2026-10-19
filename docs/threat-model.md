# Threat model

This guide asks what can go wrong and where the app checks trust. All examples use fictional data.

| Possible actor/action | Main boundary and protection |
|---|---|
| Supplier inflates or duplicates an invoice | Match approved scope, PO, accepted delivery, supplier and prior allocations |
| Operator tries to approve or cross projects | Reload role/membership on the server; deny and audit unauthorized operations |
| Document tells AI to bypass checks | Treat text as untrusted data; AI has no approval or settlement authority |
| Authorized person makes a mistake | Independent review, exact snapshots, source references and current revalidation |
| Two requests try to pay the same balance | Serialized transaction, database constraints and required idempotency key |
| Malicious file consumes resources | Bound intake and parsing in a restricted child process |
| Someone knows a published demo password | Access only the deliberately separate local fictional profile; no private-password reuse |
| Host/database administrator rewrites history | Local verification is limited; an independent retained checkpoint is required for stronger assurance |

Supplier files enter private storage. Human confirmation publishes procurement facts. Automation can explain facts and prepare proposals. Independent people approve exact actions. Sandbox settlement commits cash, ledger, receipt, allocations and success audit together. Failed actions roll back money and retain separate evidence.

The public launcher binds localhost and uses a separate marked database. It does not make the app safe for public hosting. It disables paid providers so copied README passwords cannot create paid search tasks through that profile.

This app cannot verify physical delivery, prove a real beneficiary identity, defend a compromised operating system or certify legal compliance. See [security controls](security-self-assessment.md) and [limits](limitations.md).
