# BuildTrust AI submission

**A working construction-finance copilot, with evidence you can follow.**

The application is implemented. Security hardening and the recorded local and hosted checks are complete for the judge package. The examples use fictional projects and simulated settlement. People approve financial actions. No bank or real money is connected.

## Start with the story, then try the app

1. Read [the project overview](../docs/project-overview.md) or its PDF below.
2. Watch the **4:18 demonstration** to see an unsupported claim blocked and an eligible payment reviewed.
3. Open the **nine-slide presentation** with its speaker notes.
4. Try the public demo using [the README command and four passwords](../README.md#try-the-public-demo).
5. Use the technical report, security assessment and execution evidence to examine the decisions.

## Submission files

| Deliverable | File | What the reader gets |
|---|---|---|
| Technical documentation | [Technical report](BuildTrustAI_Technical_Documentation.pdf) | Working architecture, financial rules, storage, APIs and six security diagrams |
| Security self-assessment | [Security report](BuildTrustAI_Security_Self_Assessment.pdf) | Implemented protections, completed checks and the two explicit checklist exceptions |
| Presentation | [Nine-slide deck](BuildTrustAI_Presentation.pptx) | The problem, working examples and evidence, with notes for an eight-to-nine-minute talk |
| Demonstration | [4:18 video](BuildTrustAI_Demo.mp4) | Actual isolated app interactions with disclosed local synthetic English narration |
| Source code | [Source ZIP](BuildTrustAI_Source.zip) and [GitHub](https://github.com/md-ishtiak-ahmed-sajib/buildtrust-ai) | Source, setup instructions, tests, samples, AGPL license and attribution |
| Execution evidence | [Execution-evidence ZIP](BuildTrustAI_Execution_Evidence.zip) and [readable index](execution-evidence/README.md) | Actual requests, results, balances, audit references, scans and test output |
| Optional introduction | [Project overview](BuildTrustAI_Project_Overview.pdf) | A short explanation for readers who want the main idea first |

All seven delivery files are available directly in this folder. The local email-attachment folder contains the same files. [Delivery checksums](checksums.json), the [source archive checksum](BuildTrustAI_Source.zip.sha256), release manifest and post-package receipts identify the verified files. Source ZIP and GitHub exclude private runtime data, `prompt/` and `AGENTS.md`; existing Git history is retained.

To refresh the standalone evidence ZIP and keep the email folder identical after packaging and acceptance, run `uv run --project backend python scripts/sync_submission.py --refresh --sync-email`. The source ZIP excludes the standalone evidence ZIP and delivery checksums to avoid duplicate contents and circular hashes.

## Completed verification

| Check | Recorded result |
|---|---|
| Local tests | 251 backend, 10 frontend and 20 browser workflows passed |
| Public demo | Four browser logins passed without MFA; private data stayed separate |
| Payment examples | All eight A–H HTTP scenarios passed |
| Security | Implemented MFA, request/access protections, scans and private backup/restore passed their recorded checks |
| Hosted Windows and Linux | Both passed [the October 20 run](https://github.com/md-ishtiak-ahmed-sajib/buildtrust-ai/actions/runs/39419213954); each skipped one optional OCR model test |
| Media and package | Rendered reports/deck, decoded video, source fingerprints and fresh archive installation have acceptance receipts |

The newer 19-control checklist records **17 verified controls**. Native database RLS is **deferred** while SQLite is used. Webhook signatures are **not applicable** because incoming webhooks are disabled. There is no independent penetration-test or public-hosting certification claim.

## What remains outside the local package

Paid-provider live trials, representative Bengali documents, professional/security/accessibility reviews, Docker validation and phone enrollment need their stated prerequisites. See [remaining work](../docs/remaining-work.md) for owners and next actions.

The team has sent its registration email. Organizer confirmation, presenter details, rehearsal and final project submission remain human actions. The supplied deadline is **October 20, 2026, 21:59 Dhaka / 23:59 Beijing**. Prepared files do not mean that the final email has been sent.
