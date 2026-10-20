# Plain-English glossary

| Term | Meaning in this app |
|---|---|
| BDT / taka | Bangladeshi taka, the default currency |
| BOQ | Bill of quantities: work items, quantities and rates |
| PO | Purchase order: an approved supplier order |
| GRN | Goods received note: a record of accepted delivery |
| Invoice | A supplier claim, not payment approval |
| Entitlement | Quantity and value supported by approved records |
| Takeoff | Calculating quantities from supplied dimensions and drawings |
| Rate analysis | Building a rate from material, labour and other costs |
| Cost total | Estimated project cost, excluding profit and taxes that are not cost |
| Tender total | Selling price, including configured profit and output tax |
| Commitment | An approved contractual obligation, such as a PO |
| Accepted cost | Cost recognized from approved delivery/work acceptance |
| Accrual | Liability for accepted work before final invoice reconciliation |
| Payable / AP | Money owed to a supplier |
| Receivable / AR | Money owed by a customer |
| Revenue | Approved customer certification value, separate from cash collected |
| Retention | An amount held back under recorded contract terms |
| Advance | Evidenced money provided before later work; recovery needs a supported allocation |
| Certificate | A reviewed statement of contract work and amounts due |
| Credit note | A source-linked reduction; it does not automatically refund cash |
| Forecast | Expected cash movements calculated from records and assumptions |
| Reserve | Minimum cash that payment policy must preserve |
| Reservation | Cash/delivery quantity held for a proposal; not a payment |
| Snapshot | Saved exact inputs and evidence used for approval |
| Version | Revision number used to detect conflicting changes |
| Idempotency key | Request ID that makes settlement retries return the original result |
| Atomic transaction | Changes that all succeed together or all roll back |
| Audit hash chain | Linked fingerprints used to find inconsistent retained events |
| OCR | Reading text from scanned page images |
| FX | Dated exchange-rate evidence |
| EVM | Comparing planned work, completed work and recognized cost |
| BAC / PV / EV / AC | Budget at completion / planned value / earned value / actual cost |
| CV / SV | Cost variance / schedule variance, in cost-value units |
| CPI / SPI | Cost performance index / schedule performance index |
| EAC / ETC / VAC / TCPI | Estimate at completion / estimate to complete / variance at completion / to-complete performance index |
| NRM / CESMM | Published measurement frameworks; a profile is not blanket certification |
| PWD / LGED | Bangladesh reference sources; imported schedules need edition/locality evidence |
| ICMS | Cost-reporting classification, not a detailed measurement method |
| AACE class | Professional estimate classification requiring evidence; not assigned automatically |
| JWT / token | Signed, short-lived login token checked by the API |
| CI | Automated checks run by a service such as GitHub Actions |
| Fixture | Fictional sample used for a demo or test |
| Sandbox | Test environment without a real payment connection |
| Deterministic | The same validated inputs and rules produce the same financial result |
| Minor unit | Smallest stored money unit; 100 minor units make BDT 1.00 |
| API / HTTP | The server interface and request protocol used by the browser and test tools |
| Schema | The defined fields and rules for a document or request |
| WAL | SQLite write-ahead logging, used with consistent backups and transaction controls |
| Rollback | Undoing an unsuccessful transaction before it becomes a saved financial change |
| Checksum / fingerprint | A hash used to compare file contents or saved evidence |
| MFA | Multi-factor authentication: a password plus an authenticator or one-time recovery code. Required for private Admin and Finance accounts. |
| TLS | Encrypted network transport. Required before any remote deployment; the judge package binds to localhost. |

See [financial rules](financial-rules.md) for formulas and [features](../features.md) for examples.
