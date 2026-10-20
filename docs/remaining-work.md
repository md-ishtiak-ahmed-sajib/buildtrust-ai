# Remaining work

Only unfinished tasks belong here. Completed work and test evidence are recorded in the [implementation ledger](all-suggestions-implementation.md) and [verification guide](completion-verification.md).

## External services and real documents

| Task | Owner | What is needed next |
|---|---|---|
| Test live SerpApi and DataForSEO searches | Provider account owner | Supply backend credentials and explicit paid-test permission. Then verify real links, supported locations, task recovery and uncertain submissions in an isolated run. |
| Test a real Ollama model | Local environment owner | Install/provide a model and its local endpoint. Then record actual explanation and fallback checks. The deterministic copilot already works. |
| Check representative Bengali scans and reference/supplier documents | Document owner | Supply authorized files, expected readings and reviewer permission. Synthetic OCR tests do not establish field accuracy. |
| Obtain professional acceptance | Qualified QS/engineer and finance reviewers | Review source editions, measurement rules, project policies, real supplier/beneficiary attestations and maturity evidence. Role-based app tests are not professional approval. |

## Platforms and independent assessment

| Task | Owner | What is needed next |
|---|---|---|
| Confirm MFA on the team authenticator | Private account owner | Enroll with the actual phone, confirm its clock and store the recovery codes privately. Automated TOTP/browser checks passed; representative phone acceptance is separate. |
| Validate Docker | Local environment administrator | Start a working Docker engine, then run the isolated checks. The installed CLI currently cannot reach its engine. Do not modify Docker's managed WSL distribution. |
| Perform a real screen-reader and first-user assessment | Accessibility reviewer and representative users | Use suitable assistive technology and actual users. Keyboard/mobile and automated scans cover a narrower scope. |
| Obtain an independent deployment security review | Independent security reviewer | Review the proposed hosting environment before any wider deployment. Local tests and known-advisory scans are not a penetration-test certificate. |

## Team and competition submission

| Task | Owner | What is needed next |
|---|---|---|
| Obtain organizer confirmation and finalize presenter details | Team | Registration email sent by the team. Await organizer confirmation and finalize the presenter information. |
| Rehearse | Presenter/team | Run the nine-slide talk and demonstration, check timing and add the real team introduction. |
| Upload the final package | Team | Supply the authorized destination, upload the required files and keep confirmation before the supplied deadline. |


## Deferred database protection

Native database RLS requires a future PostgreSQL release, new policies, migrations and acceptance. SQLite currently uses tested server-side project isolation. Incoming webhooks remain disabled; signature verification is not applicable.
