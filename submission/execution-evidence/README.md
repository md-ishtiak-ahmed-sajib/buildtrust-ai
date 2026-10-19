# Execution evidence

These are actual local sandbox and hosted-check results. They do not show real bank transfers. Raw logs and JSON keep their technical field names so a reviewer can trace the results.

| Start here | What it shows |
|---|---|
| verification-summary.json | Current counts and links between verification stages |
| manifest.json; scenario-a through scenario-h.json/.md | Actual API requests/results, source fingerprint, cash before/after and audit IDs |
| backend-tests.log; frontend-tests.log; browser-tests.log | Actual test output |
| clean-install.json/.log; archive-install-handoff.json/.log | Fresh setup and the exact archive installed |
| final-archive-acceptance.json/.log; final-source-agreement.json | Post-package checks for the final archive, kept beside the archive in the GitHub repository |
| public-demo-install.json | Four public passwords, independent payment, repeat startup, port error and private-copy preservation |
| public-demo-browser.json | Four real browser logins against the separate public profile |
| public-demo-private-preservation.json | Unchanged working tables, credentials, signing secret and uploads |
| documentation-check.json/.log | Rendered guides, links/images, Mermaid, SVG text bounds and mobile checks |
| contract-drift.json | Generated contracts agree with the source |
| hosted-ci.json; hosted-ci-summary.json | Actual Windows/Ubuntu jobs and platform-startup output for the tested Git revision |
| github-publication.json; github-checkout.json | Verified publication and a fresh source/document/media download |
| presentation-qa.json | Nine slides/notes, two editable tables, source hash and actual render review |
| video-provenance.json; video-qa.json | Real recording source, duration, decoding and application hashes |
| source-agreement.json | Source fingerprint and archive agreement |
| migration-recovery.log; local-upgrade-preservation.json | Earlier migration/recovery and preserved original records |
| load-measurements.json | Earlier synthetic workload; not production capacity |
| live-fx-acceptance.json | Actual dated free USD/BDT retrieval/storage with attribution |
| npm-audit.log; python-audit.log | Known-advisory scan output |
| docker-check.log; ollama-availability.json | Actual unavailable local environment checks |

Screenshot, HTTP, public-demo, recording and hosted runs use separate IDs and databases. Their mock references and timestamps can differ while the financial expectations agree. Compatibility log aliases contain the corresponding actual current output.

Archive receipts name the archive tested. The final acceptance files are created after packaging and kept beside it in the repository, so they do not create a circular checksum inside the archive. The release manifest covers packaged files. Remote receipts identify the tested application revision; later documentation-only commits are recorded in Git history.

Published public passwords are deliberately fictional sample data. Private credentials, signing secrets, databases and uploads are excluded. Do not edit raw results to make a failure look successful. Rerun the checks and retain actual results.

See [verification](../../docs/completion-verification.md), [security limits](../../docs/security-self-assessment.md) and [remaining work](../../docs/remaining-work.md).
