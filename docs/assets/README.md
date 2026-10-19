# Documentation visuals

These visuals explain the real app and verified fictional examples. They do not show customer results, live market prices or production benchmarks.

| File | Meaning |
|---|---|
| payment-flow.svg | Document checks, reservations, independent approval and atomic sandbox settlement |
| estimate-flow.svg | Measurement, prices, forecast preview and independent budget approval |
| architecture.svg | Browser, permission checks, services and private financial storage |
| payment-cash.svg | BDT 1,000,000 opening cash, 70,000 payment, 930,000 closing cash and 100,000 reserve |
| estimate-impact.svg | The 20-tonne rate change, BDT 80,000 increase and forecast change with no recorded cash movement |

`demo-values.json` holds the numeric inputs and evidence references. The charts share one BDT scale within each image and keep exact values in adjacent Markdown tables. SVG titles/descriptions and image alternative text explain the content.

Rebuild with `uv run --project backend python scripts/build_doc_visuals.py`. The script contains the editable flow descriptions and checks the sample arithmetic. Actual application screenshots are under `submission/screenshots/` with their own source notes.

The optional documentation check uses the bundled authoring runtime's Marked library and Mermaid 12.2.0 installed under ignored `data/docs-tools`. It renders Markdown, validates local images/links and parses Mermaid without using the working database. These authoring tools are not required to start the app.
