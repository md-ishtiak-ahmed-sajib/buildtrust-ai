# Your guide to BuildTrust AI

**The application and its security hardening are implemented and tested.** Read the [project overview](project-overview.md) for a short introduction, or jump into a guide below.

New to the app? Start with the [README](../README.md), [feature list](../features.md) and [judge guide](judges-quickstart.md). Use the [glossary](glossary.md) for unfamiliar terms.

| Guide | What it explains |
|---|---|
| [Judge quickstart](judges-quickstart.md) | Public logins and short demonstrations |
| [All features](../features.md) | The 14 app areas, roles, examples and screenshots |
| [Demo script](demo-script.md) | Recorded demonstration and narration |
| [Presentation outline](presentation-outline.md) | Nine slides and speaking times |
| [Document formats](../demo/README.md) | PDF, CSV and JSON examples |
| [Financial rules](financial-rules.md) | Supported claims, rounding, cash and payment checks |
| [Financial permissions](financial-controls.md) | Who prepares, checks and approves |
| [Accounting and contracts](accounting-and-controls.md) | Cost, liabilities, installments, certificates and corrections |
| [Estimating](estimating-methodology.md) | Rates, cost/tender totals and forecast previews |
| [Price sources](price-source-integrations.md) | Listings, quotations, references, history and providers |
| [Quantity surveying](quantity-surveying-standards.md) | Calculations and professional review |
| [Measurement rules](measurement-rule-register.md) | Profile evidence and explicit deductions |
| [Technical guide](technical-documentation.md) | Setup, storage, services and operations |
| [Architecture](architecture.md) | How the services connect |
| [API guide](api-reference.md) | Routes, authentication, errors and contracts |
| [Generated OpenAPI](openapi.json) | Exact request and response definitions |
| [Accounts and private backups](account-security.md) | Sign-out, one-time recovery, usage limits and restore |
| [Security self-assessment](security-self-assessment.md) | Controls and known risks |
| [Threat model](threat-model.md) | Trust boundaries and possible misuse |
| [Current verification](completion-verification.md) | Actual test results and release evidence |
| [Test commands](test-results.md) | How to run isolated checks |
| [Limits](limitations.md) | What this local sandbox does not prove |

## Status and history

- [Remaining work](../docs/remaining-work.md) contains unresolved tasks and their owners.
- [Implementation ledger](all-suggestions-implementation.md) records the 42 recommendations and completed evidence.
- [Handoff record](completion-handoff-plan.md) explains the release and GitHub process.
- [Earlier upgrade plan](advanced-upgrade-plan.md) and [earlier tests](advanced-feature-tests.md) are dated background, not the current backlog.
- Private planning notes and local engineering instructions are excluded from the repository and source archive.
- [Submission checklist](../submission/submission-checklist.md) separates prepared files from human submission steps.

All payments are simulated. Public passwords work only in the separate public demo. Keep private runtime files out of Git.

## Ready-to-read submission reports

- [Security self-assessment PDF](../submission/BuildTrustAI_Security_Self_Assessment.pdf)
- [Technical documentation PDF](../submission/BuildTrustAI_Technical_Documentation.pdf)

The reports separate the earlier 20-item review from the newer 19-control checklist. MFA and request protections now have local acceptance evidence. Native database RLS remains deferred; incoming webhooks are not applicable. Each report includes six simple diagrams and the same status language as its editable Markdown guide.
