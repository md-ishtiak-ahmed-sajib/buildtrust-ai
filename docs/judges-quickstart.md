# Judge quickstart

1. Install Python 3.12, uv, and Node.js 24. Run `scripts/setup.ps1`, then `scripts/run_demo.ps1` from the source directory.
2. Open http://127.0.0.1:8000. Setup prints passwords; retrieve them again from the local `data/demo-credentials.json` file. No paid key, Docker, or model download is needed.
3. Sign in as Operator. **Invoice Intelligence → INV-STEEL-095** shows the 95-tonne invoice against 80 tonnes of BOQ, PO, and accepted delivery. Confirm **BDT 1,050,000 excess**, **18.75%**, and a blocking result. Inspect the BOQ/PO/GRN/invoice evidence links.
4. Select **INV-CEMENT-070 → Run financial workflow → Open prepared payment**. It prepares BDT 70,000 and waits for human approval. Operator has no active approval/execution action.
5. Sign out, sign in as Finance Manager, open Payment Center, approve, and execute the simulation. The mock receipt shows BDT 70,000 and **BDT 930,000 cash after settlement**.
6. Open Cash-Flow Forecast and compare all three scenarios. Open Audit & Security and click **Verify audit chain**.
7. Switch to **Liquidity Stress Case — Demo Project** to inspect a financially matched invoice blocked by reserve requirements. The main project also includes beneficiary-change and prompt-injection examples.
8. Admin can reset from Audit & Security. Reset creates fresh project records and preserves earlier history. Archived projects are read-only.

## Reproduce the evidence

`uv run --project backend python scripts/collect_evidence.py` launches a separate HTTP server/database and executes A–H. Inspect `submission/execution-evidence/manifest.json`, scenario JSON/Markdown, HTTP operation log, and runtime log. This does not alter the interactive judge workspace.

`scripts/run_tests.ps1` runs backend tests, frontend tests, and the production build. Browser tests require a running judge server and Playwright Chromium; see the README. Actual test logs and counts are in the submission evidence and test-results report.

All companies, accounts, beneficiary tokens, and transfers are fictional. `MOCK-…` is explicitly a simulated transaction reference. The default agent is a persisted deterministic tool workflow; optional LLM prose is not needed to reproduce the demonstration.


## Extended workflows

- Open **BOQ & Estimates**, **Materials & Prices** and **Quantity Takeoff** for the fictional 20-tonne upgrade example. Demonstration offers are explicit. An 80,000 estimate increase changes the scheduled forecast from 600,000 to 520,000 while cash stays 2,000,000.
- Open **Commercial Management → Prepare control** for component forecast links, quantity/value authority, protected PO amendments, source certificate reversals and separate accepted-cost corrections. Each submission needs Operator preparation, independent Manager checking and an independent Admin approval.
- Open **Performance & Scenarios** for mapped cost/tax/retention/advance details and unscheduled exposure. **Review Inbox** provides project-scoped search and paginated registers.
- Review the 16 actual browser workflows and source-linked acceptance evidence in [completion-verification.md](completion-verification.md). Professional acceptance remains separate.
- For a fresh recording, synthesize the supplied narration, prepare scene timing, then run `uv run --project backend python scripts/record_demo.py`. The wrapper starts its own database/server on port 8013. Do not point recording tools at your working database. `scripts/mux_video.py` verifies source hashes, decoding and actual duration.
