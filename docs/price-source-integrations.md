# Price sources and evidence

The app starts without scraping, paid subscriptions or an external AI model. The public demo disables paid providers. Private users can configure optional adapters in their local `.env` and restart.

```dotenv
BUILDTRUST_SERPAPI_KEY=
BUILDTRUST_DATAFORSEO_LOGIN=
BUILDTRUST_DATAFORSEO_PASSWORD=
BUILDTRUST_PRICE_TIMEOUT_SECONDS=15
```

Keep keys out of Git, documents and screenshots. Provider status returns enabled/disabled flags, never keys. Missing keys show unavailable status; they never silently activate fake online results.

## Source types

| Source | How it works | Important limit |
|---|---|---|
| SerpApi | Google Shopping search through a fixed API origin | Preserve the supplied merchant/product link; it may lead to Google Shopping |
| DataForSEO | Validate location, submit a Merchant product task, persist its ID, retrieve results | An uncertain paid submission is not blindly repeated |
| Official schedules | Import legally supplied reference files with edition, locality and dates | Composite/work rates are not raw material offers |
| Supplier quotations | Manual entry or CSV/XLSX/PDF suggestions, then independent verification | A listing is not a verified quotation |
| Internal history | Append approved PO rates and settlement context | Whole-invoice cash is context, not a line unit rate |
| Synthetic catalogue | Explicitly select demonstration mode | All offers are fictional, not live market results |
| Frankfurter FX | Fetch a supported dated rate and store attribution | Not a guaranteed bank execution rate; unsupported pairs stay unavailable |

The app calls fixed HTTPS origins. It does not fetch arbitrary user-supplied URLs. External source links are validated and displayed safely.

## Search and recovery

Refresh returns **202** with a saved search ID. Poll status and request prices for that search. Display its material, quantity, unit, destination, mode and timestamp so users know which search they are viewing.

Equivalent searches cache for one hour. Public listings become stale after 24 hours. Limits are five new searches per user/project/minute, two simultaneous requests per provider/process, 2 MB responses and at most 50 offers per adapter. Connect timeout is three seconds; request timeout defaults to 15 seconds. Safe retrieval has one transient retry.

DataForSEO uses location discovery, `task_post` and `task_get/advanced/{id}`. Known remote IDs resume retrieval through saved jobs or explicit retry. Jobs retain leases, attempts and bounded backoff. An `UNKNOWN_SUBMISSION` needs provider-account reconciliation before another paid submission. No automatic paid-account reconciliation is claimed.

Disabled, unsupported-location, empty, waiting, timeout and error states remain distinct. Coverage for Dhaka construction materials is not guaranteed.

## Importing quotation/reference files

Use one header row and at most 500 data rows. CSV/XLSX required fields are `supplier,title`. Usable prices also need `price,currency,unit,quoted_quantity` and sufficient costs/specifications. Other fields follow OpenAPI. Unknown columns and duplicate/missing headers return actionable errors.

Specifications use a JSON `specification` column or fields such as `spec_grade`, `spec_diameter_mm` and `spec_standard`. Dates use YYYY-MM-DD, booleans true/false and financial inputs decimal strings. Freight/tax bases are INCLUDED, EXCLUDED or UNKNOWN. Known zero charges must be explicit; missing charges stay unknown.

Files are limited to 10 MB, PDFs to 50 pages and XLSX expansion to 20 MB. XLSX formulas are rejected. Normal PDF parsing has a 15-second timeout; configured OCR uses bounded longer processing. Suggestions retain page evidence. Scans and unusual layouts need review.

Official references need `source_type=OFFICIAL_REFERENCE`, edition, effective date and source URL; retain chapter/item/locality where available. Set `rate_category` to MATERIAL, WORK_ITEM or COMPOSITE. The app does not crawl official schedules.

Corrections keep revisions. A different authorized reviewer verifies a quotation before it becomes an immutable observation. Retained contributors cannot verify their own work. Unknown costs cannot be invented during listing-to-quotation conversion.

## Comparable cost and eligibility

Use explicit kg/tonne, known package weights, each/thousand and cubic-foot/cubic-metre conversions. Density and moisture/bulk assumptions are required for mass/volume conversions. A fixed order charge for another quantity needs fresh review.

Recoverable included tax needs its amount so the app can remove it from cost. Nonrecoverable included tax remains in price. Material waste belongs in rate analysis, not hidden in the purchase observation.

Eligible offers need an exact match or independently approved equivalent, usable units, complete comparable cost, suitable delivery/location/quantity and valid dates. Public listings also need a usable source link. Missing inputs, incompatibility and expiry cannot be overcome by a high score. Official/historical observations remain references for reviewed manual rates in this release.

## Recommendation policy

| Part | Maximum score | Calculation |
|---|---:|---|
| Comparable landed cost | 50 | 50 × lowest eligible cost / offer cost |
| Source evidence | 25 | 25 for human-verified supplier or explicit demo; 15 for indicative public evidence |
| Delivery suitability | 15 | Awarded after delivery eligibility passes |
| Freshness | 10 | Valid firm quote: 10; otherwise 10 × max(0, 1 − age-hours/24) |

Rank by total descending, then cost ascending, then observation ID. Demo offers compare only with demo offers. One eligible source shows a warning. This is decision support, not supplier reliability or fraud probability.

Another eligible selection needs a reason. A saved selection keeps original/normalized prices, specifications, costs, conversions, FX, policy, source hash, user and time. Refresh never rewrites it.

Protocol references: [SerpApi](https://serpapi.com/shopping-results), [DataForSEO task submission](https://docs.dataforseo.com/v3/merchant/google/products/task_post/), [Frankfurter](https://frankfurter.dev/). See [current live/fixture status](completion-verification.md) and [remaining work](../docs/remaining-work.md).
