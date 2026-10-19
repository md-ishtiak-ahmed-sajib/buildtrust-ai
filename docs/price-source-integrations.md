# Material price sources and evidence

Price intelligence runs in the existing backend. No scraping, paid subscription or
LLM is required to start the app. External adapters call fixed HTTPS origins only.

## Configuration

Set values locally in `.env`, then restart the backend:

```dotenv
BUILDTRUST_SERPAPI_KEY=
BUILDTRUST_DATAFORSEO_LOGIN=
BUILDTRUST_DATAFORSEO_PASSWORD=
BUILDTRUST_PRICE_TIMEOUT_SECONDS=15
```

Do not paste keys into documents, browser code, Git, or screenshots. Provider status
returns enabled/disabled flags, never credential values. Missing credentials display
an unavailable state and never activate the demonstration provider automatically.

- SerpApi: `GET https://serpapi.com/search.json?engine=google_shopping`. Merchant and
  product links are preserved; a Google Shopping link is not represented as a direct
  merchant quotation. Reference: https://serpapi.com/shopping-results
- DataForSEO: authenticated Merchant `google/locations`, `google/products/task_post`
  and `google/products/task_get/advanced/{id}`. A supported city/country must be found
  before task submission. Remote task IDs persist before polling. Pending tasks can
  resume; ambiguous submissions block repetition. No public callbacks are required.
  Reference: https://docs.dataforseo.com/v3/merchant/google/products/task_post/
- Frankfurter v2: `/v2/rate/{base}/{quote}` with provider attribution. A recorded daily
  rate is an estimate assumption, not a bank execution rate. Unsupported pairs remain
  unavailable or accept a Finance Manager/Admin sourced manual rate.
  Reference: https://frankfurter.dev/

Coverage and valid offers depend on each provider; Dhaka construction materials are
not guaranteed to be present. Public listing fields frequently lack units, grades,
shipping or tax. Such observations can be displayed but cannot be recommended until
sufficient evidence exists. Supplier confirmation is a separate reviewed quotation.

## Search behavior

POST refresh returns 202 and a persisted search ID. Poll its status and GET the
material prices with `search_id`. Equivalent searches cache for one hour. Refresh is
limited to five new searches per user/project/minute. Concurrency is two external
requests per provider per process, responses are bounded to 2 MB and at most 50 offers
per adapter. Connect timeout is 3 seconds, total request timeout defaults to 15 seconds.
Safe GET retrieval gets one transient-network retry. Paid POST submission is never
blindly retried. A known DataForSEO task polls after 0/2/5/10 seconds; WAITING resumes
through the explicit retry endpoint. Restarted queued/running searches are interrupted.

`UNKNOWN_SUBMISSION` requires checking the provider account/task state before another
submission. There is no automatic reconciliation with the provider account in v1.
Keys are not included in persisted payloads, user-visible errors or audit details.

## Imports

Quotation imports accept CSV/XLSX tables (one header row, up to 500 data rows) or
labeled machine-readable PDFs. Upload limit: 10 MB; PDF bounds: 50 pages, 15 seconds.
XLSX expansion is limited to 20 MB and formula cells are rejected.

Required table fields: `supplier,title`; set `price,currency,unit,quoted_quantity` to
make the rate usable. Other fields match QuotationInput in OpenAPI. Specifications
use a JSON `specification` column or columns such as `spec_grade,spec_diameter_mm,
spec_standard`. Dates are ISO YYYY-MM-DD. Booleans use true/false. Financial values
are decimal strings. Extra fields are rejected. Freight/tax basis is INCLUDED,
EXCLUDED or UNKNOWN. Handling/other charges require an explicit zero when known zero.

For official schedules, set `source_type=OFFICIAL_REFERENCE` and supply `edition`,
`effective_date`, `source_url`, chapter/item/locality where available, and
`rate_category=MATERIAL|WORK_ITEM|COMPOSITE`. These are reference rates, not live
supplier offers. Composite/work-item rates cannot price a raw material component.
The official importer uses legally provided documents, not a crawler of PWD/LGED.

PDF suggestions recognize Supplier, Quotation Number, Product, Unit Price, Currency,
Unit, Quantity, Quotation Date and Valid Until labels, saving page evidence. Unusual
layouts/scans require manual fields. Original attachments and corrections remain
private; verification publishes an immutable observation. The preparer cannot verify
their own quotation. Uploaded instruction text has no execution or approval authority.

## Normalization and recommendation

Canonical units are explicit. Package/mass conversion requires package weight;
volume/mass requires material density and a recorded moisture/bulk assumption.
Fixed order charges for a different order quantity require fresh review. Recoverable
included tax requires its amount so it can be removed; nonrecoverable included tax
remains within the product price. Wastage is applied in rate analysis, not hidden in
the observed purchase price.

Eligibility gates run before scoring: exact/independently approved equivalent,
known comparable costs and units, delivery confirmation, MOQ, location, valid quote,
and a usable source link for public listings. Public listings become stale after
24 hours. Official/historical observations are reference-only in this release; use
their documented basis in a manual estimate rate after professional review.

Policy recommendation-v1: cost = 50 × lowest eligible landed cost / offer cost;
source = 25 for human-verified supplier or explicit synthetic demo, 15 for indicative
public evidence; delivery = 15 after eligibility; freshness = 10 for valid firm
quotes, otherwise 10 × max(0, 1 − age_hours/24). Rank by total descending, cost
ascending, observation ID ascending. Demo scores compare synthetic entries only,
never live offers. A single eligible source carries an additional-quotation warning.
This is decision support, not a fraud probability or supplier reliability assessment.

Selected snapshots preserve original payload, specification, conversions, cost
breakdown, policy, hash, user and time. Refresh never rewrites a selection. Nonrecommended
eligible choices require a reason. Ineligible offers cannot supply a selected rate.
