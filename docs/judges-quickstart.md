# Judge quickstart

**Ready to try:** the local application, its security hardening and the recorded checks are complete. The public trial uses fictional projects, fixed README passwords and no MFA. Private Admin and Finance accounts require MFA. For the short story, read the [project overview](project-overview.md).


BuildTrust AI is a working local sandbox. All sample companies and payments are fictional. No bank is connected.

## Start the easy public demo

1. Install Python 3.12, uv and Node.js 24. See the [README](../README.md) for links.
2. Open PowerShell in the project folder.
3. Run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\try_demo.ps1`.
4. Open **http://127.0.0.1:8003**.
5. Use the four [README demo logins](../README.md#public-demo-logins).

The public demo uses `data/public-demo` and keeps records on later starts. The original private app uses port 8000 and random local passwords. Public passwords do not change those private accounts.

The four public accounts do not need an authenticator. Private Admin and Finance Manager accounts do. Their first sign-in opens local authenticator setup and shows ten recovery codes once. See [account security](account-security.md). Use the public profile for the simplest judge trial.

## Stop an inflated claim

1. Sign in as Operator and select the Metro Commercial Building project.
2. Open Invoice Intelligence and choose `INV-STEEL-095`.
3. Run the workflow: 95 tonnes claimed, 80 supported.
4. Inspect the BDT 1,050,000 excess and 18.75% variance. Payment stays blocked.
5. Ask why it was blocked and open the supporting records.

## Approve one valid payment

1. As Operator, select `INV-CEMENT-070` and run its workflow.
2. Open the BDT 70,000 proposal. The Operator cannot approve it.
3. Sign out and sign in as Finance Manager.
4. Open Payment Center. Approve, confirm, execute the simulation and confirm again.
5. Read the receipt: BDT 1,000,000 becomes BDT 930,000 once.
6. Verify the chain in Audit & Security.

If the sample was already paid, inspect its saved receipt. Admin can reset the fictional run; old runs remain readable. Reset does not change passwords.

## Update a price and estimate

1. As Admin, open Materials & Prices and create/locate the upgrade demo.
2. Select Price & QS Upgrade — Fictional Demo.
3. As Operator, open BOQ & Estimates and click the steel material.
4. Choose Synthetic demonstration catalogue, search and select the eligible BDT 74,000/tonne offer.
5. Confirm the preview: 20 tonnes now cost BDT 1,480,000 instead of BDT 1,400,000. Forecast cash falls from BDT 600,000 to BDT 520,000. Recorded cash remains BDT 2,000,000.
6. Submit as Operator, check as Finance Manager and approve as an independent Admin.

## Other areas and judge files

Open Review Inbox, Quantity Takeoff, Cost Control & Accounting, Commercial Management, Team & Access and Performance & Scenarios. See [all 14 areas](../features.md) and [tested examples](completion-verification.md).

The submission folder contains a nine-slide presentation with notes, a demonstration below five minutes, source archive, screenshots and actual evidence. [The checklist](../submission/submission-checklist.md) separates prepared files from registration, presenter details, rehearsal and upload.

Paid search, representative Bengali scans and professional acceptance need separate prerequisites. A database owner can rewrite the local audit chain. Read the [limits](limitations.md).
