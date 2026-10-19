## 3. New Codex master prompt — upgrade the existing application

The following prompt is designed to work directly with your already completed BuildTrust AI repository. It instructs Codex to inspect your code, preserve existing functionality, and implement new production-style modules.

Its technical references include the official RICS measurement suite, ICE's CESMM4, AACE's estimate classifications, Google's shopping data through SerpApi/DataForSEO, and PMI's earned-value methodology.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://www.rics.org\&sz=32)

RICS

+5



One important design decision: the app must not claim that online prices are verified supplier quotations unless they truly are. Some construction materials have no published retail price, and pricing may require a formal RFQ.

# BUILDTRUST AI — ADVANCED FINANCIAL, QUANTITY SURVEYING & LIVE PRICE INTELLIGENCE UPGRADE

## MASTER CODEX IMPLEMENTATION PROMPT

### 1. YOUR ROLE

Act as a multidisciplinary principal engineering and financial technology team consisting of:

- Principal full-stack software architect
- Senior Python/FastAPI engineer
- Senior React/TypeScript engineer
- Chartered quantity surveying specialist
- Construction cost estimator
- Construction contracts and commercial management specialist
- Senior SME financial advisor and treasury analyst
- Procurement and supply-chain specialist
- AI-agent and data integration engineer
- Fintech cybersecurity architect
- Senior QA automation and DevOps engineer

You are working inside an **existing, functioning application called BuildTrust AI — Construction SME Finance Copilot**.

**This is an enhancement project, not a new project.**

The previous application has already been developed. Your job is to inspect its architecture, identify its existing capabilities, and implement advanced features without damaging previous functionality.

Do not recreate the old application. Do not delete existing working features, tests, API endpoints, databases, user accounts, payment controls, or documentation.

## 2. PRIMARY OBJECTIVE

Transform BuildTrust AI into a unified platform combining:

1. Online construction material price intelligence
2. Multi-source supplier price comparison
3. AI-assisted rate recommendations
4. International-standard quantity surveying
5. Professional construction cost estimation
6. Material, labor, equipment and productivity rate analysis
7. Advanced financial planning
8. Construction cash-flow management
9. Budget and cost control
10. Supplier procurement and quotation analysis
11. Earned Value Management
12. Interim payment certification
13. Contract variations and change control
14. Financial risk management
15. AI-powered financial and quantity-surveying assistance
16. Financial source verification and auditability

The platform must connect estimating, procurement, and finance in a single data workflow:

**Measured Quantity → Material Selection → Online Price Discovery → Source Verification → Rate Analysis → Cost Estimate → Budget Approval → Procurement → Invoice Verification → Payment → Cash-Flow and Project-Cost Updates.**

The highest-priority objective is a genuinely functional material-price comparison system.

When a user clicks a material in a BOQ, the application must provide multiple available prices from external sources, display source links and technical comparability, recommend an appropriate rate, and let the user select a price for the project estimate.

The selected price must be stored with a persistent evidence snapshot.

---

## 3. WORK ON THE EXISTING REPOSITORY

Before modifying code:

1. Inspect the complete repository structure.
2. Read README.md, AGENTS.md, package manifests, API routes, database models and tests.
3. Identify the current frontend/backend architecture.
4. Identify the existing BOQ, document, invoice, payment, cash-flow and audit capabilities.
5. Inspect database migrations and relationships.
6. Run current tests and record the baseline.
7. Prepare a dependency map showing which existing modules must be extended.
8. Identify any feature already implemented and reuse it.

Create:

`docs/advanced-upgrade-plan.md`

The document should include:

- Existing capabilities
- Missing capabilities
- Integration points
- Required database changes
- Migration risks
- New API routes
- New frontend pages
- Planned test coverage
- Implementation priorities

Do not introduce a second application, duplicate backend, duplicate user system, or incompatible database.

Use additive database migrations and preserve existing data.

If an existing implementation conflicts with the requirements, refactor it carefully with tests.

---

# PART A — ONLINE MATERIAL PRICE INTELLIGENCE

## 4. MATERIAL PRICE SEARCH ENGINE

Develop a material-price intelligence engine capable of discovering and comparing prices from multiple online sources.

The user experience must work as follows:

1. The user opens a project estimate or BOQ.
2. The user clicks a material or rate-analysis component.
3. A side panel or modal opens.
4. The application identifies the selected material's specifications.
5. The user can set country, city, currency, delivery location, and quantity.
6. The backend requests matching prices from configured sources.
7. The interface displays all usable results.
8. The application evaluates specification compatibility and total landed cost.
9. The recommendation engine identifies a suitable price.
10. The user clicks **Select This Price** or **Use Recommended Price**.
11. The application saves the selection and source evidence.
12. The affected rate analysis and estimate are recalculated.
13. The financial dashboard reflects the updated estimate.

This must be a real connected workflow, not a simulated frontend-only interaction.

## 5. PRICE DATA SOURCES

Implement a modular provider system.

### Provider A — SerpApi Google Shopping

Reference:

[https://serpapi.com/shopping-results](https://serpapi.com/shopping-results)

Use the supported Google Shopping API when a valid API key is configured.

Extract available fields including:

- Product title
- Price
- Merchant/source name
- Product URL
- Currency
- Delivery information
- Brand
- Product identifiers
- Image URL, if allowed
- Query location
- Retrieval timestamp

Do not assume every result includes a unit, delivery charge, direct seller URL or usable construction specification.

### Provider B — DataForSEO

Documentation:

[https://docs.dataforseo.com/v3/merchant-google-products-overview/](https://docs.dataforseo.com/v3/merchant-google-products-overview/)

Implement DataForSEO as an alternative or additional authorized shopping-data source, using the currently documented API endpoints.

Normalize its output to the application's common quotation schema.

If credentials are absent, disable this provider gracefully.

### Provider C — Bangladesh PWD Schedule of Rates

Official reference:

[https://ss.pwd.gov.bd/sor](https://ss.pwd.gov.bd/sor)

Build an official-rate reference catalogue importer.

Support importing legally accessible, user-provided CSV/XLSX/PDF rate documents, preserving edition, chapter, item code, zone and effective date when supplied.

Official schedule rates may represent work-item rates or composite rates, not material-only supplier prices.

Never compare a composite construction work rate directly with the raw price of cement, steel or sand.

Do not assume all schedules are current. Obtain and display their edition and effective date.

### Provider D — Bangladesh LGED Schedule of Rates

Official reference:

[https://lged.gov.bd/pages/static-pages/6922df17933eb65569e1fcb8](https://lged.gov.bd/pages/static-pages/6922df17933eb65569e1fcb8)

Support official reference-rate import with edition and locality metadata.

Keep the reference-rate category separate from live marketplace quotations.

### Provider E — User-Verified Supplier Quotations

Allow upload or manual entry of supplier quotations from construction suppliers.

Store:

- Supplier name
- Quotation number
- Product specification
- Unit price
- Unit
- Currency
- Minimum order quantity
- Delivery charges
- Tax basis
- Quotation date
- Expiry date
- Attachment
- Supplier page URL, where available
- Verification status

Supplier quotes must not automatically become verified merely because a document was uploaded.

### Provider F — Internal Historical Price Database

Allow searching prior rates from the application's own records.

Show:

- Historical rate
- Original supplier
- Project
- Purchase date
- Unit
- Currency
- Age
- Evidence reference

Label these results **Historical Internal Rate**.

### Provider G — Demonstration Provider

Create a deterministic, clearly labeled mock catalogue for offline demonstrations and integration testing.

Mock entries may include:

- Cement
- Reinforcement steel
- Sand
- Stone aggregate
- Bricks
- Concrete blocks
- Ready-mix concrete
- Structural steel
- Formwork materials
- Paint
- Tiles
- Pipes
- Electrical cables

These are synthetic rates, not live market prices.

Never display them as current online offers.

## 6. SOURCE INTEGRITY AND ACCESS

Use official APIs, licensed datasets, permitted public documents, authorized supplier feeds, and manual quotations.

Do not bypass CAPTCHA, authentication, anti-bot systems, usage limits, robots restrictions, or website terms.

Do not implement indiscriminate HTML scraping.

If no valid provider is available, clearly display:

"No currently verifiable online prices available for this material and location."

Offer:

- Search source website
- Request a supplier quotation
- Import an official reference rate
- Enter a manual quotation
- View historical rates

Do not manufacture merchant offers or prices to fill an empty result list.

The backend must store API credentials securely.

Include provider timeout, retry, caching, rate-limit handling, and failure isolation.

---

# PART B — MATERIAL MATCHING AND RECOMMENDATIONS

## 7. MATERIAL MASTER CATALOGUE

Create a structured construction material catalogue.

Each material should support:

- Material ID
- Material name
- Category
- Description
- Technical specification
- Applicable material standard
- Grade or strength
- Brand or manufacturer, if relevant
- Nominal size
- Diameter or thickness
- Canonical measurement unit
- Packaging quantity
- Typical applications
- Search keywords
- Equivalent names
- Approved alternatives
- Country
- Project restrictions

Example:

Material: Reinforcement Steel\
Grade: B500B\
Diameter: 16 mm\
Unit: metric tonne\
Required Standard: Project-specified standard\
Delivery Location: Dhaka\
Required Quantity: 20 tonnes

A result for generic mild steel, a different grade, or a different diameter must not be silently treated as equivalent.

## 8. MATERIAL MATCHING ENGINE

Create a hybrid matching system:

1. Deterministic attribute validation
2. Unit validation
3. Technical specification comparison
4. Optional AI-assisted product-name interpretation
5. Compatibility classification

Classify results as:

- Exact Match
- Approved Equivalent
- Requires Technical Review
- Incompatible
- Insufficient Information

Only exact matches and independently approved equivalents should qualify for automatic rate recommendation.

AI similarity alone is not evidence of engineering equivalence.

Always display reasons for matching decisions.

## 9. PRICE NORMALIZATION

Prices may differ by:

- Currency
- Packaging
- Unit
- Country
- Delivery location
- Brand
- Product grade
- Sales tax
- Delivery charges
- Minimum order quantity
- Validity date

Create a normalization engine.

Examples:

- BDT per bag to BDT per kg where actual bag weight is specified
- BDT per kg to BDT per tonne
- USD per tonne to BDT per tonne using a recorded exchange rate
- Price per 1,000 bricks to price per brick
- Price per cubic foot to price per cubic metre

Do not convert bags to kilograms without known packaging weight.

Do not convert cubic metres to tonnes without a suitable material-specific density and moisture/bulk-density assumptions.

Store all conversion factors, precision rules and source assumptions.

Use Decimal for financial calculations.

## 10. LANDED COST CALCULATION

For comparison purposes, calculate a normalized landed unit cost:

Landed Unit Cost =\
(Product Cost + Applicable Freight + Nonrecoverable Tax + Handling + Other Applicable Procurement Costs) / Usable Received Quantity

Important:

- Distinguish recoverable and nonrecoverable tax.
- Do not silently add unknown delivery or tax costs as zero.
- Do not double-count freight or tax already included in quotations.
- Keep procurement wastage separate from the purchased-unit price when appropriate.
- Show a cost breakdown.

Unknown major cost components must cause the quotation to be marked as partially comparable.

## 11. RECOMMENDED PRICE ENGINE

Build a transparent recommendation algorithm.

Consider:

- Technical compatibility
- Source credibility
- Geographic relevance
- Price freshness
- Supplier quotation validity
- Delivery suitability
- Minimum-order compatibility
- Comparable landed cost
- Evidence completeness
- User-approved supplier preferences

Never recommend solely on the lowest displayed price.

Suggested logic:

1. Exclude technically incompatible results.
2. Exclude expired firm quotations.
3. Flag stale public listings.
4. Separate fixed quotations from indicative online listings.
5. Normalize valid comparable units and costs.
6. Rank feasible options by a documented weighted methodology.
7. Select the most suitable option where sufficient evidence exists.
8. Return a textual explanation and structured scoring breakdown.

If only one credible quotation exists, show:

"Single-source indicative recommendation — additional quotation recommended."

If no comparable credible quotation exists, do not generate a fake recommended price.

Allow an authorized estimator to select another price with a documented reason.

## 12. PRICE COMPARISON UI

Create an attractive, functional interface with a side drawer or dedicated detail page.

Each quotation should show:

- Supplier
- Product title
- Brand and specification
- Original price and currency
- Normalized unit price
- Delivery and tax assumptions
- Total landed unit cost
- Source type
- Retrieval date
- Valid-until date, when known
- Technical match status
- Recommendation explanation
- Link to original source

Buttons:

**View Source**\
**Compare**\
**Use This Price**\
**Request Quotation**

Clearly distinguish:

- Recommended
- Lowest comparable landed price
- Official reference
- Historical rate
- Requires review
- Demo data

Add sorting and filtering by cost, source, location, specification, freshness and credibility.

When a user selects a rate, persist an immutable price-selection snapshot with source, cost breakdown, exchange rate, timestamp, chosen material specification and user.

Reopening the historical estimate must not silently replace the original selected rate with the latest online price.

Instead offer **Refresh Price** and display the change before the user approves an update.

---

# PART C — INTERNATIONAL QUANTITY SURVEYING

## 13. INTERNATIONAL STANDARD FRAMEWORK

Implement an internationally oriented measurement and estimation engine.

Support selectable standards profiles.

### RICS NRM 1

Purpose:

Order-of-cost estimating and elemental cost planning for capital building works.

Official reference:

[https://www.rics.org/profession-standards/rics-standards-and-guidance/sector-standards/construction-standards/nrm](https://www.rics.org/profession-standards/rics-standards-and-guidance/sector-standards/construction-standards/nrm)

### RICS NRM 2

Purpose:

Detailed measurement for building works and bills of quantities.

Use this as the default detailed measurement profile for building-project demonstrations.

### RICS NRM 3

Purpose:

Cost estimating and cost planning for building maintenance works.

### CESMM4

Purpose:

Measurement and BOQ preparation for civil engineering works.

Official reference:

[https://ice.org.uk/areas-of-interest/infrastructure-delivery/civil-engineering-standard-measurement](https://ice.org.uk/areas-of-interest/infrastructure-delivery/civil-engineering-standard-measurement)

### ICMS 3

Purpose:

International cost classification and comparable reporting, including cost and carbon dimensions.

Official reference:

[https://icms-coalition.org/the-standard/](https://icms-coalition.org/the-standard/)

ICMS must not be misrepresented as a detailed work-item measurement method.

### National and Project-Specific Rules

Support configurable profiles for:

- Bangladesh PWD
- Bangladesh LGED
- Project-specific measurement agreements
- User-defined measurement rules

### Standards integrity

Do not claim professional certification or exact standards compliance unless the applicable clauses have been implemented and verified.

Do not reproduce substantial copyrighted measurement tables without authorization.

Build the software around configurable rule definitions with:

- Standard name
- Edition
- Work category
- Measurement unit
- Measurement rule ID
- Source or clause reference, if legitimately available
- Deduction treatment
- Assumptions
- Effective date
- Verification status

Where a rule is not verified, flag it for professional review rather than inventing a supposedly standard measurement rule.

---

## 14. QUANTITY TAKEOFF ENGINE

Develop a deterministic quantity-takeoff calculator.

Support:

### Earthworks

- Excavation
- Trench excavation
- Backfilling
- Earth disposal
- Compaction quantities

### Concrete

- Footings
- Columns
- Beams
- Slabs
- Staircases
- Walls

### Reinforcement

- Bar bending schedules
- Bar lengths
- Bar counts
- Nominal diameters
- Unit weight
- Total mass
- Lap and anchorage allowances as supplied by engineering design

### Formwork

- Footing formwork
- Column formwork
- Beam side and soffit formwork
- Slab soffit formwork

### Masonry

- Brickwork
- Blockwork
- Wall volume or area
- Opening deductions under the selected verified measurement rules

### Finishes

- Plastering
- Painting
- Tiling
- Flooring
- Waterproofing

### Other Works

- Doors and windows
- Pipe lengths
- Electrical cable lengths
- Structural steel mass
- Roofing
- External pavement

Provide a reusable calculation-sheet interface.

For each measured item, persist:

- Project
- Element
- Location
- Drawing reference
- Revision
- Measurement standard profile
- Formula
- Input dimensions
- Units
- Quantity
- Deduction calculation
- Assumptions
- Prepared by
- Checked by
- Timestamp

## 15. ENGINEERING CALCULATIONS

Implement exact, unit-aware geometric calculations.

Examples:

Rectangular volume:

V = L × B × H

Area:

A = L × B

Circular cross-sectional area:

A = πD² / 4

Rebar nominal mass:

Mass = Length × Unit Mass per Metre

Support the common engineering approximation for steel bar unit mass in kg/m:

Unit Mass ≈ D² / 162

where D is in millimetres, but identify this as an approximation and allow specified nominal mass tables or density-based calculations.

No reinforcement quantity should be described as structurally adequate merely because its mass has been calculated.

Cover, anchorage, laps, hooks, bends and cutting lengths must be based on approved bar-bending schedules or design inputs.

Avoid universal deduction and wastage rules. Apply those from the chosen, verified measurement profile.

Maintain dimensional correctness throughout calculations.

Flag invalid units, negative quantities, missing dimensions and questionable inputs.

## 16. BOQ MANAGEMENT

Provide a professional BOQ editor supporting:

- Hierarchical work sections
- Element and work-item codes
- Descriptions
- Units
- Measured quantity
- Unit rate
- Amount
- Provisional sums
- Prime cost items where applicable
- Notes
- Reference drawings
- Cost codes
- Revisions
- Approval status

Support:

- Add/edit/delete items
- Quantity calculation from takeoff
- Link to rate analysis
- Link to selected supplier rate
- Revised BOQ
- Version comparison
- Import/export CSV and XLSX
- Printable/PDF estimate where tooling exists
- Automatic recalculation

Allow the user to navigate directly from an item to its measurement sheet, source rates, and supporting documentation.

---

# PART D — PROFESSIONAL COST ESTIMATION

## 17. RATE ANALYSIS ENGINE

Create detailed analysis of rates for each BOQ work item.

Separate:

A. Materials\
B. Labor\
C. Equipment\
D. Subcontract services\
E. Transport and handling\
F. Waste allowances\
G. Site overhead\
H. General overhead\
I. Profit or mark-up\
J. Applicable tax

Each cost component must include quantity/consumption factor, unit, unit price, line amount and source.

Make percentage mark-ups configurable.

Avoid applying profit, overhead, taxes or wastage twice.

Use a configurable cost build-up policy.

Example: Concrete work should be analyzed using its stated mix design or approved production assumptions, not an invented universal cement-sand-aggregate ratio.

For each work-item rate, show:

- Material subtotal
- Labor subtotal
- Equipment subtotal
- Other direct costs
- Indirect costs
- Applicable mark-ups
- Final analyzed unit rate
- Cost breakdown percentages
- Evidence and assumptions

A material price selected from online comparison should update its linked component only, with correct propagation through the rate analysis.

## 18. ESTIMATE MANAGEMENT

Support:

- Preliminary estimate
- Detailed estimate
- Engineer's estimate
- Contractor's tender estimate
- Revised estimate
- Estimate at completion
- Historical cost comparison

Use AACE International cost-estimate classification as a framework for describing estimate maturity.

Reference:

[https://library.aacei.org/pgd01/pgd01.shtml](https://library.aacei.org/pgd01/pgd01.shtml)

Do not automatically claim an AACE class based only on a project's name or stage.

Estimate classification should reflect scope definition, available inputs and documented uncertainty.

Store a Basis of Estimate containing assumptions, inclusions, exclusions, contingencies, source dates, pricing basis and calculation methods.

## 19. COST SENSITIVITY ANALYSIS

Create sensitivity controls for:

- Steel price changes
- Cement price changes
- Labor escalation
- Fuel and transport increases
- Foreign exchange fluctuations
- Material wastage
- Procurement delay

Calculate the financial impact of changes on:

- Work-item rates
- BOQ totals
- Project estimate
- Contingency requirements
- Expected margin
- Cash flow

Provide interactive scenarios with actual calculations.

Do not present arbitrary sensitivity percentages as observed market forecasts.

---

# PART E — ADVANCED CONSTRUCTION FINANCE

## 20. FINANCIAL COMMAND CENTER

Expand the current BuildTrust AI financial dashboard.

Include:

- Original project budget
- Approved revised budget
- Committed cost
- Actual incurred cost
- Paid cash
- Accrued liabilities
- Remaining commitment
- Forecast cost to complete
- Estimate at completion
- Variance at completion
- Accounts payable
- Accounts receivable
- Supplier payment schedule
- Customer payment schedule
- Project cash balance
- Cash-flow forecast
- Gross profit projection
- Financial risk alerts

Distinguish cash payments from accrued costs and contractual commitments.

Avoid double-counting purchase orders, received goods, invoices and payments as separate expenses for the same underlying obligation.

## 21. BUDGET CONTROL AND COST CODING

Create structured cost codes that connect:

BOQ Item → Estimate → Approved Budget → Purchase Order → Goods Receipt → Invoice → Payment → Actual Cost

Show:

- Budget vs commitment
- Budget vs actual
- Forecast vs budget
- Variations
- Available budget
- Projected overrun

Generate a warning when an authorized action exceeds remaining approved budget.

Budget alerts should not automatically change the existing payment-control policy.

## 22. EARNED VALUE MANAGEMENT

Implement:

- Planned Value (PV)
- Earned Value (EV)
- Actual Cost (AC)
- Budget at Completion (BAC)
- Cost Variance (CV)
- Schedule Variance (SV)
- Cost Performance Index (CPI)
- Schedule Performance Index (SPI)
- Estimate at Completion (EAC)
- Estimate to Complete (ETC)
- Variance at Completion (VAC)

Use:

CV = EV − AC

SV = EV − PV

CPI = EV / AC

SPI = EV / PV

Support documented EAC forecasting methods, including:

EAC = BAC / CPI

when its assumptions are appropriate.

Do not divide by zero.

Show the forecast method and assumptions.

Use real project baseline and progress data where available.

Reference:

[https://www.pmi.org/blog/earned-value-management](https://www.pmi.org/blog/earned-value-management)

## 23. CASH-FLOW FORECASTING

Expand the existing cash-flow module rather than replacing it.

Support forecasts for:

- 7 days
- 30 days
- 90 days
- Project duration

Include:

- Opening cash
- Expected customer receipts
- Certified receivables
- Supplier liabilities
- Payroll
- Equipment hire
- Loan repayments
- Retention releases
- Tax obligations
- Approved procurement
- Contingency assumptions

Include scenarios:

- Normal operations
- Delayed client payments
- Material price increases
- Supplier payment acceleration
- Project delay
- Combined adverse scenario

Generate:

- Minimum projected balance
- Liquidity gap
- Date of potential cash shortage
- Required cash reserve
- Suggested payment sequencing

Recommendations must be explanatory and subject to financial approval.

Never guarantee future liquidity.

## 24. PAYMENT CERTIFICATE MANAGEMENT

Introduce interim payment certificate functionality for construction contracts.

Support:

- Work performed to date
- Previous certified value
- Current-period valuation
- Approved variations
- Materials on site where contractually eligible
- Advance payment recovery
- Retention
- Contractual adjustments
- Applicable tax
- Net amount due

Reference FIDIC-style workflows where relevant, but use configurable contract conditions.

Do not claim every construction project follows the same FIDIC clause or payment formula.

Store supporting measurement certificates and authorized approvals.

Connect certified amounts to receivables or payables according to whether the project user is the contractor, employer or subcontractor.

## 25. VARIATION ORDER FINANCE

Create variation management.

Track:

- Variation number
- Contract reference
- Reason
- Changed quantity
- Changed rate
- Claimed amount
- Reviewed amount
- Approved amount
- Approval date
- Financial impact
- Time impact, when known

Unapproved variations must not silently increase the authorized project budget.

## 26. PROCUREMENT AND SUPPLIER RFQ

Implement:

- Request for quotation
- Supplier quotation register
- Technical compliance comparison
- Commercial bid comparison
- Purchase recommendation
- Procurement approval
- PO integration

Supplier comparison must consider:

- Compliant technical specification
- Price
- Delivery
- Tax
- Warranty or quality evidence where applicable
- Minimum order quantity
- Lead time
- Supplier approval status

An AI recommendation must be explainable.

Do not assert supplier reliability unless relevant evidence exists.

## 27. PROFITABILITY AND FINANCIAL RATIOS

Implement useful construction SME reporting.

Examples:

- Gross margin
- Forecast project margin
- Cash conversion cycle, where data permits
- Days sales outstanding
- Days payable outstanding
- Project cost overrun percentage
- Budget utilization
- Retention outstanding
- Working-capital requirement
- Accounts receivable aging
- Accounts payable aging

Clearly indicate insufficient data rather than displaying fabricated ratios.

## 28. MULTI-CURRENCY FINANCE

Support configurable project currencies.

Start with BDT and optional:

- USD
- EUR
- GBP
- INR
- CNY

Use an exchange-rate adapter with a documented provider, such as:

[https://frankfurter.dev/](https://frankfurter.dev/)

Check that the provider actually supports the requested currency pair.

Store exchange-rate source, date, base currency, quote currency and conversion factor.

If the pair is unavailable, request an explicitly sourced/manual exchange rate or leave the conversion unavailable.

Never invent today's foreign exchange rate.

Allow estimates to preserve the rate at the time of approval.

---

# PART F — AI FINANCIAL AND QUANTITY SURVEYING ASSISTANT

## 29. ADVANCED COPILOT

Extend the existing AI agent.

Provide capabilities such as:

"Find current available prices for 16 mm B500B reinforcement steel in Dhaka."

"Compare available cement prices from different sources."

"Calculate the concrete volume of 20 columns with specified dimensions."

"Prepare a rate analysis for reinforced concrete."

"Why is our project estimate increasing?"

"What is our forecast project gross margin?"

"Which BOQ items are over budget?"

"Show the financial impact of a 10% rise in steel prices."

"Which supplier quote is the most cost-effective compliant option?"

"Prepare a draft interim payment certificate."

"Which project expenses could create a cash-flow shortfall?"

The agent must use actual tools and database records.

Every price-related response must provide source links or explicitly acknowledge unavailable evidence.

Financial calculations must use deterministic backend functions, not unverified LLM arithmetic.

The AI should explain the calculation, reference evidence, and flag missing information.

It must not automatically approve procurement, payment certificates, budgets or payments.

---

# PART G — SOFTWARE ARCHITECTURE

## 30. NEW MODULE STRUCTURE

Inspect the existing repository and add compatible modules.

Do not unnecessarily relocate or rewrite existing working files.

Suggested additions:

```
backend/app/
  api/
    materials.py
    market_prices.py
    takeoff.py
    estimates.py
    rate_analysis.py
    procurement.py
    cost_control.py
    earned_value.py
    certifications.py
    variations.py
    financial_reports.py

  models/
    material_catalog.py
    price_quotes.py
    price_selections.py
    measurement.py
    estimate.py
    cost_code.py
    procurement.py
    certification.py
    variation.py

  services/
    price_intelligence/
      base_provider.py
      provider_registry.py
      serpapi_provider.py
      dataforseo_provider.py
      official_rate_importer.py
      supplier_quote_provider.py
      historical_rate_provider.py
      demo_provider.py
      price_normalizer.py
      material_matcher.py
      recommendation_engine.py
      provenance_service.py

    quantity_surveying/
      measurement_engine.py
      unit_engine.py
      measurement_profiles.py
      boq_engine.py
      takeoff_engine.py
      reinforcement_engine.py

    estimating/
      rate_analysis_engine.py
      estimate_engine.py
      sensitivity_engine.py
      estimate_versioning.py

    finance/
      cost_control_engine.py
      evm_engine.py
      payment_certificate_engine.py
      variation_engine.py
      financial_metrics_engine.py
      fx_engine.py

frontend/src/
  pages/
    MaterialsPage.tsx
    PriceIntelligencePage.tsx
    QuantityTakeoffPage.tsx
    EstimateBuilderPage.tsx
    RateAnalysisPage.tsx
    ProcurementPage.tsx
    CostControlPage.tsx
    EarnedValuePage.tsx
    CertificatesPage.tsx
    FinancialReportsPage.tsx

  components/
    materials/
    price-comparison/
    quantity-takeoff/
    estimates/
    procurement/
    cost-control/
    financial-charts/

backend/tests/
  test_price_providers.py
  test_price_matching.py
  test_price_normalization.py
  test_price_recommendations.py
  test_price_provenance.py
  test_measurement_engine.py
  test_rate_analysis.py
  test_budget_control.py
  test_earned_value.py
  test_payment_certificates.py
  test_fx_conversion.py
  test_estimate_integration.py

docs/
  price-source-integrations.md
  quantity-surveying-standards.md
  measurement-rule-register.md
  estimating-methodology.md
  financial-controls.md
  advanced-feature-tests.md
```

Adapt these paths to the existing codebase.

Use the current application's database, authentication, authorization and audit framework.

---

## 31. DATABASE EXTENSIONS

Create entities or extend equivalent existing entities for:

- Materials
- MaterialSpecifications
- PriceProviders
- PriceObservations
- SupplierQuotations
- PriceSelections
- ExchangeRateObservations
- MeasurementProfiles
- MeasurementRules
- TakeoffSheets
- TakeoffMeasurements
- BOQVersions
- RateAnalysisComponents
- EstimateVersions
- EstimateAssumptions
- CostCodes
- BudgetVersions
- CostCommitments
- ProjectProgress
- EarnedValueSnapshots
- PaymentCertificates
- ContractVariations
- ProcurementRFQs

For price observations, persist:

- Observation ID
- Provider
- Provider result ID
- Original product title
- Supplier name
- Source URL
- Source category
- Raw observed price
- Currency
- Product unit and package quantity
- Normalized unit price, where possible
- Technical specification
- Location
- Delivery and tax assumptions
- Retrieval timestamp
- Publication/validity date if available
- Cache status
- Evidence completeness
- Result hash

Price selections must preserve a historical snapshot, not simply reference the mutable latest observation.

Use additive database migrations.

Preserve old project and payment records.

---

## 32. REQUIRED API EXTENSIONS

Adapt endpoints to the existing route conventions.

Suggested endpoints:

```
GET    /api/v1/materials
GET    /api/v1/materials/{id}
POST   /api/v1/materials

GET    /api/v1/materials/{id}/prices
POST   /api/v1/materials/{id}/prices/refresh
POST   /api/v1/materials/{id}/prices/select

GET    /api/v1/prices/providers
GET    /api/v1/prices/history

GET    /api/v1/measurement/profiles
POST   /api/v1/takeoff/calculate
GET    /api/v1/takeoff/sheets

GET    /api/v1/estimates
POST   /api/v1/estimates
GET    /api/v1/estimates/{id}
POST   /api/v1/estimates/{id}/recalculate
POST   /api/v1/estimates/{id}/approve

GET    /api/v1/rate-analysis/{boq_item_id}
POST   /api/v1/rate-analysis/{boq_item_id}

GET    /api/v1/procurement/rfqs
POST   /api/v1/procurement/rfqs

GET    /api/v1/finance/cost-control
GET    /api/v1/finance/earned-value
GET    /api/v1/finance/reports

GET    /api/v1/certificates
POST   /api/v1/certificates

GET    /api/v1/variations
POST   /api/v1/variations
```

Add authentication and entity-level permissions.

Price refresh operations should use appropriate server-side rate limiting.

Validate externally supplied URLs and restrict any server-side URL fetching to prevent SSRF.

All expensive operations should have timeouts and controlled failure behavior.

---

# PART H — UI/UX REQUIREMENTS

## 33. PROFESSIONAL PRODUCT DESIGN

Retain the existing visual identity while improving the application.

Use a cohesive professional visual system appropriate for construction finance.

Recommended navigation:

**Overview**

- Executive Dashboard
- AI Finance Copilot

**Estimation & QS**

- Quantity Takeoff
- BOQ Management
- Rate Analysis
- Project Estimates
- Material Catalogue

**Market Intelligence**

- Live Price Search
- Source Comparison
- Selected Rates
- Price History

**Procurement**

- RFQs
- Supplier Quotations
- Purchase Orders

**Financial Management**

- Budget & Cost Control
- Cash-Flow Forecast
- Payment Certificates
- Earned Value
- Financial Reports

**Security**

- Payment Authorization
- Audit & Compliance

The interface must provide:

- Real functional filters
- Search
- Export actions
- Data tables
- Interactive charts
- Expandable estimate calculations
- Source links
- Clear unit labels
- Clearly marked live/historical/demo price types
- Role-based actions
- Responsive navigation
- Error states
- Loading states
- Provider-unavailable messages

Avoid creating navigation items that lead to empty pages.

## 34. MATERIAL PRICE INTERACTION

This is the flagship feature.

When clicking a material in the BOQ:

Open a panel displaying:

**Material:** 16 mm Reinforcement Steel\
**Required Grade:** B500B\
**Project Location:** Dhaka\
**Quantity Required:** 20 tonnes

Below that, show available quotation cards.

Each card must expose its source and comparison basis.

The panel should contain:

- Search again
- Technical compatibility
- Quotation currency
- Normalized price
- Total landed cost
- Delivery assumptions
- Source URL
- Last retrieved date
- Recommendation explanation
- Select Price action

Display an honest empty state if no current external results exist.

Once a price is selected, provide a confirmation showing:

- Old rate
- New selected rate
- Percentage difference
- Updated BOQ item amount
- Updated estimate total
- Source reference
- User confirmation requirement

After confirmation, update persistent project records and refresh all affected dashboard calculations.

---

# PART I — SECURITY, VALIDATION AND TESTING

## 35. FINANCIAL SECURITY

Preserve existing payment controls.

Add:

- Estimator and approver permissions
- Controlled quotation overrides
- Approved estimate version locking
- Source-provenance audit events
- Rate-change history
- Financial threshold checks
- Separation of duties for budget approval
- Approval invalidation after material financial changes
- Server-side validation of all cost calculations

Never allow a price-selection action to bypass an approved purchase order or previously approved financial commitment.

Changes to cost estimates should not silently modify already executed financial transactions.

## 36. TEST REQUIREMENTS

Create automated tests for at least these cases:

1. SerpApi adapter parses a recorded test response.
2. DataForSEO adapter parses a recorded test response.
3. Missing provider credentials fail gracefully.
4. No online results return an honest empty state.
5. Shopping source links are preserved correctly.
6. Invalid external URLs are rejected or safely handled.
7. Price normalization from kg to tonne.
8. Currency conversion with recorded exchange-rate source.
9. Incorrect material grade is excluded.
10. Missing package weight prevents bag-to-kg conversion.
11. Expired supplier quotation is flagged.
12. Unknown tax or freight prevents false landed-cost precision.
13. Recommended price selects only eligible offers.
14. Selected price persists after a search refresh.
15. Rate selection recalculates linked BOQ cost.
16. Original estimate version remains unchanged.
17. Concrete volume calculation is correct.
18. Reinforcement weight calculation is correct.
19. Formwork geometry calculation is correct.
20. Selected measurement profile and assumptions are saved.
21. Rate-analysis totals reconcile.
22. Budget overrun is detected.
23. Earned Value calculations are correct.
24. Cash-flow scenarios produce reproducible results.
25. Unauthorized cost approval is rejected.
26. Existing sandbox payment workflows still pass.
27. Provider timeout does not crash the application.
28. Historical/demo data is not mislabeled as live.
29. Procurement quotations link to source evidence.
30. Audit history records rate-selection decisions.

Use fixtures instead of paid API calls for automated tests.

A separate opt-in integration test may call real services only when configured with valid credentials.

Run the original test suite and the new test suite.

Report actual results.

---

# PART J — IMPLEMENTATION PRIORITIES

## 37. BUILD ORDER

Implement in this sequence.

### Phase 1 — Integrate price intelligence

Highest priority:

- Material catalogue
- Price-provider abstraction
- SerpApi integration
- Additional provider adapter
- User quotation imports
- Price comparison UI
- Source links
- Price normalization
- Recommendation engine
- Select Price workflow
- Persistent provenance

### Phase 2 — Quantity surveying and estimating

- Measurement profiles
- Takeoff calculations
- BOQ integration
- Rate analysis
- Source-linked estimate recalculation
- Estimate versioning
- Export

### Phase 3 — Financial integration

- Budget and cost control
- Committed vs actual cost
- Cash-flow improvements
- EVM
- Financial dashboard

### Phase 4 — Commercial management

- RFQs
- Supplier comparison
- Payment certificates
- Variations
- Advanced profitability reports

### Phase 5 — Refinement and delivery

- UI consistency
- End-to-end tests
- Documentation
- Updated architecture
- Security verification
- Screenshots where actually captured
- Competition demo scenarios

If time is insufficient, complete Phases 1 and 2 and integrate them with existing finance functionality before expanding further.

Do not prioritize optional features over a working main workflow.

---

# PART K — ACCEPTANCE CRITERIA

## 38. DEFINITION OF DONE

The upgrade is only complete if:

- Existing BuildTrust AI features still operate.
- Existing tests have been executed.
- Users can open a material from an existing BOQ.
- Online prices are retrieved when configured providers return data.
- Multiple offers appear when the source returns multiple offers.
- Every displayed external quotation has its correct source attribution.
- Source links open the corresponding reference.
- Currency and units are normalized correctly.
- Technical mismatches are identified.
- Recommendation is supported by transparent rules.
- A user can select a quotation.
- The chosen source and price snapshot persist.
- The BOQ and rate analysis update correctly.
- Project estimate totals update correctly.
- Quantity takeoff performs genuine calculations.
- Measurement profiles and assumptions are recorded.
- Financial dashboards consume actual persisted data.
- Budget and cash-flow implications are shown.
- Old approved estimate versions remain reproducible.
- Price changes are auditable.
- External API failures are handled safely.
- Demo and historical rates are distinguished from current online prices.
- New automated tests pass.
- Security checks pass.
- Updated documentation is available.

Do not claim the product is complete unless the core end-to-end workflow has actually been tested.

---

# PART L — FINAL DEVELOPMENT INSTRUCTIONS

## 39. EXECUTE, DO NOT ONLY PLAN

You are operating as a coding agent.

After inspecting the existing repository:

1. Create the implementation plan.
2. Identify the minimal compatible backend additions.
3. Build and test the new price-intelligence engine.
4. Connect it to the existing frontend.
5. Implement price selection and BOQ recalculation.
6. Add quantity-surveying and estimation services.
7. Integrate the financial modules.
8. Run old and new tests.
9. Fix failures.
10. Update documentation.
11. Prepare a demonstration walkthrough.

Do not ask for approval after each file.

Ask only when an essential external credential, a licensed standards document, or an irreversible operation requires user input.

If API credentials are missing, implement the adapter, a documented setup process, and labeled offline demonstration mode.

The application must never pretend to retrieve live prices when it is using fixture data.

## 40. REQUIRED FINAL DELIVERABLES

When finished, provide:

1. Summary of changes
2. Updated project file structure
3. Database migrations
4. New API endpoints
5. Working provider integrations
6. Instructions for setting API keys
7. Description of measurement standards support and limitations
8. New financial features
9. Commands to start the application
10. Test commands and actual results
11. End-to-end demonstration instructions
12. Known issues and unimplemented features
13. Exact paths of updated documentation

The final demonstration must show:

**A user opens a BOQ item, searches available online material prices, compares technically valid quotations with source links, selects a recommended rate, updates the construction estimate, and immediately sees its effect on project financial forecasts.**

This is the primary business workflow and should receive the greatest development attention.

**BEGIN BY INSPECTING THE EXISTING BUILDTRUST AI REPOSITORY. IMPLEMENT THE UPGRADE. DO NOT REBUILD THE ORIGINAL APPLICATION.**

## 4. Recommended implementation decision

Use SerpApi as the first online-price adapter, because its documented shopping results include merchant, price and product-link fields. Add DataForSEO as an alternative, and implement official schedules and supplier quotations as separate rate categories.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://serpapi.com\&sz=32)

SerpApi

+1



For the competition, the strongest new demonstration is this:

Click a BOQ material

Compare source-backed prices and specifications

Approve a recommended material rate

Automatically recalculate the project estimate

Display the budget, profitability and cash-flow impact

This connects quantity surveying, real-world price evidence and financial decision-making—the main capability that can distinguish BuildTrust AI from a conventional estimating or finance dashboard.

Important: Codex can build all the connectors and workflows, but live quotations depend on API credentials, source coverage and actual available offers. Proper implementation should show missing data rather than inventing prices.