# Third-party attribution

This file names the libraries and tools used by BuildTrust AI. Their licenses still apply. The application is AGPL-3.0-only. Public demo passwords are fictional sample data; private credentials and model files are not bundled. Documentation charts are generated from labelled sample values, and application images are actual screenshots. Existing license names and source links below are retained.

Documentation-only verification uses [Marked](https://github.com/markedjs/marked) and [Mermaid](https://github.com/mermaid-js/mermaid), both MIT-licensed. They are authoring tools, not production app dependencies. The documentation includes original diagrams and charts; it does not bundle their runtime libraries.

BuildTrust AI is distributed under AGPL-3.0-only. Dependency licenses remain with their respective authors. Exact versions and hashes are recorded in the lockfiles. The following license labels are read from installed package metadata; consult each package’s license text for full terms.

## Python components

| Package | Version | Declared license |
|---|---|---|
| fastapi | 0.143.5 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| sqlalchemy | 2.0.55 | MIT |
| alembic | 1.20.0 | MIT |
| openpyxl | 3.1.5 | MIT |
| et-xmlfile | 2.0.0 | MIT |
| pydantic | 2.14.1 | MIT |
| pydantic-settings | 2.16.0 | MIT |
| PyMuPDF | 1.28.2 | Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License |
| pwdlib | 0.3.1 | MIT License |
| argon2-cffi | 25.1.0 | MIT |
| PyJWT | 2.15.1 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| python-multipart | 0.0.32 | Apache-2.0 |
| tzdata | 2026.5 | Apache-2.0 |
| pytest | 9.1.1 | MIT |
| reportlab | 5.0.1 | BSD license (see license.txt for details), Copyright (c) 2000-2025, ReportLab Inc. |
| ruff | 0.17.1 | MIT |

PyMuPDF and MuPDF are retained under their open-source AGPL licensing. No commercial license is represented as obtained. The full project AGPL text is in LICENSE.

## JavaScript components

| Package | Installed version | Declared license |
|---|---|---|
| @playwright/test | 1.64.1 | Apache-2.0 |
| @tailwindcss/vite | 4.3.3 | MIT |
| @tanstack/react-query | 5.104.4 | MIT |
| @types/node | 24.19.2 | MIT |
| @types/react | 19.3.0 | MIT |
| @types/react-dom | 19.3.0 | MIT |
| @vitejs/plugin-react | 6.1.2 | MIT |
| lucide-react | 0.468.0 | ISC |
| openapi-typescript | 7.13.0 | MIT |
| prettier | 3.9.10 | MIT |
| react | 19.3.1 | MIT |
| react-dom | 19.3.1 | MIT |
| react-router-dom | 7.18.4 | MIT |
| recharts | 3.10.1 | MIT |
| tailwindcss | 4.3.3 | MIT |
| typescript | 5.9.3 | Apache-2.0 |
| vite | 8.3.4 | MIT |
| vitest | 5.0.5 | MIT |

React, Vite, Tailwind, Recharts, TanStack Query, React Router, Lucide, TypeScript and their dependencies retain their upstream copyright and license notices. Source distributions are reproducibly fetched through package-lock.json.

## Optional artifact tools

The optional presentation tooling is not bundled into this source project. PDF samples use ReportLab. The recorded video uses Playwright Chromium and local Windows speech synthesis; Windows speech binaries are not redistributed. Optional video muxing uses imageio-ffmpeg/FFmpeg; no FFmpeg executable is included in the release archive. These authoring tools are not needed to run the default application.

## Optional OCR models

English and Bengali Tesseract models come from [tesseract-ocr/tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast), Apache-2.0. Commit, model sizes and SHA-256 hashes are pinned in `docs/ocr-models.lock.json`. Models are installed explicitly outside tracked source, with no runtime download. PyMuPDF retains the project's existing AGPL-compatible attribution and license choice.

## Automated accessibility tooling

Development-only `@axe-core/playwright` and `axe-core` by Deque Systems are used for automated accessibility checks under MPL-2.0. See https://github.com/dequelabs/axe-core-npm and the pinned frontend lockfile. They are not imported by the production application bundle. Automated checks do not establish complete accessibility conformance.

Optional security scanning uses Gitleaks 8.30.1 (MIT license), downloaded with pinned checksums by the verification tool. Its executable is not included in the source archive. Source and license: https://github.com/gitleaks/gitleaks.

Authenticator security uses PyOTP 2.10.0 (MIT), cryptography 50.0.2 (Apache-2.0 OR BSD-3-Clause), and qrcode 8.2 (BSD, with its upstream license retained in the installed distribution). QR codes are generated locally. The locked dependencies retain their upstream copyright and license files. Sources: https://github.com/pyauth/pyotp, https://github.com/pyca/cryptography, https://github.com/lincolnloop/python-qrcode.
