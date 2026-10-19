import { commercialConfig } from "./commercialConfig";
export type FieldSpec = {
  key: string;
  label: string;
  type?: string;
  options?: string[];
  source?: string;
  optional?: boolean;
};
export const date = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Dhaka" }).format(
    new Date(),
  );
export const config: Record<string, FieldSpec[]> = {
  ...commercialConfig,
  ACCOUNTING_POLICY: [
    { key: "effective_date", label: "Effective date", type: "date" },
    {
      key: "tax_treatment",
      label: "Tax treatment",
      options: ["ZERO", "RECOVERABLE", "NONRECOVERABLE"],
    },
    { key: "tax_percent", label: "Tax percent" },
    { key: "retention_percent", label: "Retention percent" },
  ],
  ACCEPTANCE: [
    { key: "policy_id", label: "Approved accounting policy", source: "policy" },
    { key: "receipt_line_id", label: "Confirmed delivery", source: "receipt" },
    { key: "cost_code_id", label: "Cost code", source: "code" },
    { key: "recognition_date", label: "Actual recognition date", type: "date" },
  ],
  INVOICE_RECONCILIATION: [
    { key: "policy_id", label: "Approved accounting policy", source: "policy" },
    { key: "invoice_id", label: "Supplier invoice", source: "invoice" },
    {
      key: "acceptance_ids",
      label: "Accepted cost records",
      source: "recognition",
      type: "multiple",
    },
    { key: "recognition_date", label: "Reconciliation date", type: "date" },
    {
      key: "due_date",
      label: "Contractual due date",
      type: "date",
      optional: true,
    },
  ],
  CUSTOMER_CERTIFICATE: [
    { key: "policy_id", label: "Approved accounting policy", source: "policy" },
    { key: "customer", label: "Customer" },
    { key: "certificate_number", label: "Certificate number" },
    { key: "revenue", label: "Certified revenue" },
    { key: "output_tax", label: "Output tax" },
    { key: "retention", label: "Held retention" },
    { key: "recognition_date", label: "Certification date", type: "date" },
    {
      key: "due_date",
      label: "Contractual due date",
      type: "date",
      optional: true,
    },
  ],
  CUSTOMER_RECEIPT: [
    {
      key: "receivable_id",
      label: "Outstanding customer certificate",
      source: "receivable",
    },
    { key: "amount", label: "Simulated amount received" },
    { key: "received_date", label: "Receipt date", type: "date" },
    { key: "reference", label: "Receipt reference" },
  ],
  CREDIT_NOTE: [
    { key: "payable_id", label: "Supplier payable", source: "payable" },
    { key: "amount", label: "Credit amount" },
    { key: "tax_amount", label: "Tax included in total credit (explicit for taxable sources)", optional: true },
    { key: "retention_credit", label: "Portion applied to held retention" },
    { key: "allocation_evidence", label: "Tax and retention allocation evidence", optional: true },
    { key: "cost_code_id", label: "Cost code", source: "code" },
    { key: "recognition_date", label: "Credit date", type: "date" },
    { key: "reference", label: "Credit note reference" },
  ],
  RETENTION_RELEASE: [
    { key: "payable_id", label: "Supplier payable", source: "payable" },
    { key: "amount", label: "Retention amount to release" },
    { key: "recognition_date", label: "Release date", type: "date" },
  ],
  SUPPLIER_CHANGE: [
    {
      key: "supplier_id",
      label: "Existing supplier (leave blank for onboarding)",
      source: "supplier",
      optional: true,
    },
    { key: "code", label: "Supplier code" },
    { key: "name", label: "Supplier name" },
    {
      key: "beneficiary_token",
      label: "Verified sandbox beneficiary reference",
    },
    {
      key: "verification_reference",
      label: "Independent beneficiary verification evidence",
    },
    {
      key: "verification_attested",
      label: "I attest that beneficiary verification evidence was obtained",
      type: "checkbox",
    },
  ],
  RULE_PROFILE: [
    { key: "code", label: "New edition-specific profile code" },
    { key: "name", label: "Profile name" },
    { key: "edition", label: "Source edition" },
    { key: "source_url", label: "Source link", type: "url" },
    { key: "rule_reference", label: "Exact reviewed rule reference" },
    { key: "reviewer_evidence", label: "Reviewer qualifications and evidence" },
    {
      key: "templates",
      label: "Reviewed deterministic templates",
      type: "templates",
    },
    { key: "opening_rules", label: "Edition-specific reviewed opening rules", type: "opening-rules" },
  ],
  OPENING_BALANCE: [
    {
      key: "recognition_date",
      label: "Opening recognition date",
      type: "date",
    },
    { key: "entries", label: "Reviewed opening journal", type: "journal" },
  ],
  PERFORMANCE_BASELINE: [
    { key: "bac", label: "Budget at completion (cost basis)" },
    {
      key: "approved_estimate_id",
      label: "Approved cost estimate (optional sourced baseline)",
      source: "approved_estimate",
      optional: true,
    },
    {
      key: "planned_values",
      label: "Dated cumulative planned values (date, amount)",
      type: "planned",
    },
  ],
  PROGRESS: [
    {
      key: "baseline_id",
      label: "Approved cost-performance baseline",
      source: "baseline",
    },
    { key: "as_of", label: "Progress observation date", type: "date" },
    {
      key: "earned_value",
      label: "Baseline cost value of independently measured completed work",
    },
    {
      key: "physical_progress_evidence",
      label: "Measurement and valuation evidence",
    },
    {
      key: "bottom_up_remaining",
      label: "Sourced bottom-up remaining cost",
      optional: true,
    },
    {
      key: "bottom_up_source",
      label: "Bottom-up source and assumptions",
      optional: true,
    },
  ],
  SENSITIVITY: [
    { key: "estimate_id", label: "Source estimate", source: "estimate" },
    { key: "material_percent", label: "Material price change percent" },
    { key: "labour_percent", label: "Labour change percent" },
    { key: "equipment_percent", label: "Equipment change percent" },
    { key: "transport_percent", label: "Transport change percent" },
    { key: "fx_percent", label: "Foreign-source FX change percent" },
    { key: "waste_points", label: "Material waste percentage points change" },
    { key: "delay_days", label: "Estimated cost delay days", type: "number" },
  ],
  ESTIMATE_MATURITY: [
    { key: "estimate_id", label: "Source estimate", source: "estimate" },
    { key: "historical_estimate_ids", label: "Approved historical estimates to compare", source: "approved_estimate", type: "multiple", optional: true },
    {
      key: "design_definition",
      label: "Design definition and available detail",
    },
    {
      key: "input_evidence",
      label: "Input source references (one per line)",
      type: "references",
    },
    { key: "uncertainty_basis", label: "Uncertainty basis" },
    {
      key: "claimed_classification",
      label: "Sourced maturity classification",
      optional: true,
    },
    {
      key: "classification_source",
      label: "Classification source and professional review",
      optional: true,
    },
  ],
  OBLIGATION: [
    {
      key: "direction",
      label: "Cash direction",
      options: ["OUTFLOW", "INFLOW"],
    },
    {
      key: "category",
      label: "Obligation category",
      options: [
        "PAYROLL",
        "EQUIPMENT",
        "LOAN",
        "TAX",
        "RETENTION",
        "PROCUREMENT",
        "RECEIVABLE",
        "OTHER",
      ],
    },
    { key: "amount", label: "Outstanding obligation amount" },
    {
      key: "due_date",
      label: "Contractual due date (blank remains unscheduled)",
      type: "date",
      optional: true,
    },
  ],
  PROJECT_SCHEDULE: [
    { key: "start_date", label: "Recorded project start", type: "date" },
    { key: "completion_date", label: "Recorded project completion", type: "date" },
  ],
  OBLIGATION_SCHEDULE_CHANGE: [
    { key: 'obligation_id', label: 'Outstanding source obligation', source: 'obligations' },
    { key: 'due_date', label: 'Revised payment date (blank makes it unscheduled)', type: 'date', optional: true },
    { key: 'reason', label: 'Reviewed schedule change reason' },
  ],
  COST_CODE_ASSIGNMENT: [
    { key: "source_type", label: "Procurement source type", options: ["BOQ_ITEM", "PO_LINE", "RECEIPT_LINE", "INVOICE_LINE"] },
    { key: "source_id", label: "Source record to classify", source: "cost_source" },
    { key: "cost_code_id", label: "Reviewed cost code", source: "code" },
  ],
  FINANCIAL_FORECAST: [
    { key: "customer_contract_ids", label: "Complete approved customer contract scope", source: "CUSTOMER_CONTRACT", type: "multiple" },
    { key: "cost_method", label: "Forecast total cost method", options: ["APPROVED_ESTIMATE", "remaining_at_budget", "cpi_based", "combined_cpi_spi", "bottom_up"] },
    { key: "estimate_id", label: "Approved cost estimate (estimate method)", source: "approved_estimate", optional: true },
    { key: "as_of", label: "Forecast observation date", type: "date" },
    { key: "complete_scope_confirmed", label: "The recorded contracts and cost source cover the complete forecast scope", type: "checkbox" },
  ],
};
export const numericIds = new Set([
  "policy_id",
  "receipt_line_id",
  "cost_code_id",
  "invoice_id",
  "receivable_id",
  "payable_id",
  "supplier_id",
  "baseline_id",
  "estimate_id",
  "approved_estimate_id",
  "delay_days",
  "contract_id", "rfq_id", "material_id", "observation_id", "selected_bid_id",
  "recommendation_id", "measurement_id", "advance_source_id", "advance_assignment_id", "payment_terms_days", "time_impact_days",
  "source_id",
  'boq_item_id', 'po_line_id', 'certificate_id', 'financial_correction_id', 'acceptance_id', 'supersedes_id', 'obligation_id',
]);
