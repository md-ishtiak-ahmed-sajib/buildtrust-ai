import { useState } from "react";
import { Plus } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useWorkspace } from "./App";
import { api, post, formatMoney, titleCase } from "./api";
import {
  PageTitle,
  Panel,
  Modal,
  Status,
  ConfirmButton,
  Loading,
  ErrorState,
} from "./ui";
import { Field, useAction } from "./advanced/shared";
import type { components } from "./types/api.generated";
import { commercialConfig } from "./controls/commercialConfig";
import { ScopeEditor } from "./controls/ScopeEditor";
import { OpeningRulesEditor } from "./controls/OpeningRulesEditor";
import { ControlEvidence } from "./controls/ControlEvidence";
import { ForecastScheduleEditor } from './controls/ForecastScheduleEditor';
type Control = components["schemas"]["ControlResponse"];
type Option = { id: number; label: string; version?: number };
type Source = {
  cost_sources: { id: number; type: string; label: string; version: number; link_version: number | null; cost_code_id: number | null }[];
  receipt_lines: {
    id: number;
    receipt: string;
    po: string;
    item_code: string;
    quantity: string;
    unit: string;
    recognized: number | null;
  }[];
  recognitions: {
    id: number;
    invoice_id: number | null;
    receipt_line_id: number;
    amount: string;
    remaining_quantity: string;
  }[];
  invoices: { id: number; number: string; amount: string }[];
};
type Balances = {
  payables: {
    id: number;
    invoice_id: number | null;
    certificate_id: number | null;
    version: number;
    amount: string;
    paid: string;
    remaining: string;
    retention: string;
    supplier_credit: string;
    currency: string;
  }[];
  receivables: {
    id: number;
    certificate_id: number;
    version: number;
    remaining: string;
    currency: string;
  }[];
};
type Summary = {
  recorded_cash: string;
  incurred_cost: string | null;
  recognized_revenue: string | null;
  accrued_liability: string | null;
  accounts_payable: string | null;
  accounts_receivable: string | null;
  notice: string;
};
import { config, numericIds, date } from "./controls/formConfig";

export function ControlsPage({ commercial = false }: { commercial?: boolean }) {
  const { project, user } = useWorkspace(),
    client = useQueryClient(),
    action = useAction();
  const [creating, setCreating] = useState(false),
    [kind, setKind] = useState(commercial ? "COMMERCIAL_CONTRACT" : "ACCOUNTING_POLICY"),
    [name, setName] = useState(""),
    [values, setValues] = useState<Record<string, unknown>>({}),
    [evidence, setEvidence] = useState("");
  const [codeName, setCodeName] = useState(""),
    [code, setCode] = useState(""),
    [amounts, setAmounts] = useState<Record<number, string>>({});
  const [editing, setEditing] = useState<Control>();
  const estimateLines = useQuery({
    queryKey: ["control-estimate-lines", project.id, values.estimate_id],
    enabled: Number(values.estimate_id) > 0,
    queryFn: () => api<{ fields: { lines: { id: string; code: string; description: string; quantity: string; unit: string; components: {id:string; description:string; unit:string}[] }[] } }>(`/estimates/${Number(values.estimate_id)}`),
  });
  const estimates = useQuery({
    queryKey: ["estimates", project.id],
    queryFn: () =>
      api<{ id: number; name: string; status: string }[]>(
        `/estimates?project_id=${project.id}`,
      ),
  });
  const records = useQuery({
    queryKey: ["controls", project.id],
    queryFn: () => api<Control[]>(`/controls?project_id=${project.id}`),
  });
  const sources = useQuery({
    queryKey: ["accounting-sources", project.id],
    queryFn: () => api<Source>(`/accounting/sources?project_id=${project.id}`),
  });
  const codes = useQuery({
    queryKey: ["cost-codes", project.id],
    queryFn: () =>
      api<{ id: number; code: string; name: string }[]>(
        `/accounting/cost-codes?project_id=${project.id}`,
      ),
  });
  const balances = useQuery({
    queryKey: ["accounting-balances", project.id],
    queryFn: () =>
      api<Balances>(`/accounting/balances?project_id=${project.id}`),
  });
  const summary = useQuery({
    queryKey: ["accounting-summary", project.id],
    queryFn: () => api<Summary>(`/accounting/summary?project_id=${project.id}`),
  });
  const codePosition = useQuery({ queryKey: ["cost-code-position", project.id], queryFn: () => api<{
    rows: { id: number; code: string; name: string; budget: string | null; commitment: string; cost: string; accrual: string; payable: string; paid: string; remaining_commitment: string }[];
    exceptions: string[]; notice: string;
  }>(`/accounting/cost-code-position?project_id=${project.id}`) });
  const suppliers = useQuery({
    queryKey: ["supplier-masters", project.id],
    queryFn: () =>
      api<{ id: number; version: number; code: string; name: string }[]>(
        `/suppliers?project_id=${project.id}`,
      ),
  });
  const commercialSources = useQuery({
    queryKey: ["commercial-sources", project.id],
    queryFn: () => api<Record<string, Option[]>>(`/commercial/sources?project_id=${project.id}`),
  });
  const visibleRecords = records.data?.filter(r => (r.kind in commercialConfig) === commercial);
  const canPrepare = project.active && user.role !== "AUDITOR";
  async function reload() {
    await client.invalidateQueries();
  }
  function reset(selected: string) {
    setEditing(undefined);
    setKind(selected);
    setValues({
      effective_date: date(),
      start_date: date(),
      recognition_date: date(),
      received_date: date(),
      as_of: date(),
      tax_treatment: "ZERO",
      tax_percent: "0",
      retention_percent: "0",
      output_tax: "0",
      retention: "0",
      retention_credit: "0",
      material_percent: "0",
      labour_percent: "0",
      equipment_percent: "0",
      transport_percent: "0",
      fx_percent: "0",
      waste_points: "0",
      delay_days: 0,
      direction: selected === "COMMERCIAL_CONTRACT" ? "SUPPLIER" : "OUTFLOW",
      category: "PAYROLL",
      payment_terms_days: 30, advance_recovery_percent: "0", country: "BD", city: "Dhaka",
      closing_date: date(), delivery_date: date(), time_impact_days: 0,
      materials_on_site: "0", advance_recovery: "0", adjustment: "0", acceptance_ids: [], bid_ids: [],
      reprice_quantity: "0",
      additional_quantity: '0', extra_value: '0', replacement_quantity: '0', replacement_rate: '0', discount: '0',
      tax_amount: '0', retention_amount: '0', advance_amount: '0', schedule: [],
      cost_method: "APPROVED_ESTIMATE", customer_contract_ids: [],
      materials_on_site_allowed: false, incorporated_acceptance_ids: [], materials_acceptance_ids: [],
      source_type: "BOQ_ITEM",
      historical_estimate_ids: [],
      opening_rules: [],
      lines: selected === "INTERIM_CERTIFICATE" ? [{ item_code: "", cumulative_quantity: "0" }] :
        [{ code: "", description: "", quantity: "1", unit: "m3", rate: "0", cost_code_id: "", boq_item_id: null }],
      planned_values: [{ date: date(), value: "0" }],
      entries: [
        { account: "PROJECT_COST", debit: "0", credit: "0" },
        { account: "ACCRUED_LIABILITY", debit: "0", credit: "0" },
      ],
    });
  }
  function options(source: string): Option[] {
    if (source === 'certificate') return (records.data || []).filter(r => ['INTERIM_CERTIFICATE', 'CUSTOMER_CERTIFICATE'].includes(r.kind) && r.status === 'APPROVED').map(r => ({id:r.id,label:`#${r.id} · ${r.name}`}));
    if (source === "cost_source") return (sources.data?.cost_sources || []).filter(row => row.type === values.source_type).map(row => ({ id: row.id, label: row.label }));
    if (source === "CUSTOMER_CONTRACT") return (records.data || []).filter(r => r.kind === "COMMERCIAL_CONTRACT" && r.status === "APPROVED" && "direction" in r.payload && r.payload.direction === "CUSTOMER").map(r => ({ id: r.id, label: r.name }));
    if (commercialSources.data?.[source]) return commercialSources.data[source];
    if (source in commercialConfig) return (records.data || []).filter(r => r.kind === source && r.status === "APPROVED").map(r => ({ id: r.id, label: `#${r.id} · ${r.name}` }));
    if (source === "estimate" || source === "approved_estimate")
      return (estimates.data || [])
        .filter((r) => source === "estimate" || r.status === "APPROVED")
        .map((r) => ({ id: r.id, label: r.name }));
    if (source === "baseline")
      return (records.data || [])
        .filter(
          (r) => r.kind === "PERFORMANCE_BASELINE" && r.status === "APPROVED",
        )
        .map((r) => ({ id: r.id, label: r.name }));
    if (source === "policy")
      return (records.data || [])
        .filter(
          (r) => r.kind === "ACCOUNTING_POLICY" && r.status === "APPROVED",
        )
        .map((r) => ({ id: r.id, label: r.name }));
    if (source === "receipt")
      return (sources.data?.receipt_lines || [])
        .filter((r) => !r.recognized)
        .map((r) => ({
          id: r.id,
          label: `${r.receipt} · ${r.item_code} · ${r.quantity} ${r.unit}`,
        }));
    if (source === "recognition")
      return (sources.data?.recognitions || [])
        .filter((r) => Number(r.remaining_quantity) > 0)
        .map((r) => ({
          id: r.id,
          label: `Accepted cost #${r.id} · quantity remaining ${r.remaining_quantity} · ${r.amount} ${project.currency}`,
        }));
    if (source === "invoice")
      return (sources.data?.invoices || []).map((r) => ({
        id: r.id,
        label: `${r.number} · ${r.amount}`,
      }));
    if (source === "code")
      return (codes.data || []).map((r) => ({
        id: r.id,
        label: `${r.code} · ${r.name}`,
      }));
    if (source === "payable")
      return (balances.data?.payables || []).map((r) => ({
        id: r.id,
        label: `Payable #${r.id} · remaining ${r.remaining} · retention ${r.retention}`,
      }));
    if (source === "receivable")
      return (balances.data?.receivables || []).map((r) => ({
        id: r.id,
        label: `Certificate #${r.certificate_id} · remaining ${r.remaining}`,
      }));
    return (suppliers.data || []).map((r) => ({
      id: r.id,
      label: `${r.code} · ${r.name}`,
    }));
  }
  async function create() {
    const payload: Record<string, unknown> = { kind, evidence };
    for (const field of config[kind]) {
      const value = values[field.key];
      if (field.optional && (value === "" || value == null)) continue;
      payload[field.key] = numericIds.has(field.key) ? Number(value) : value;
    }
    if (["ACCOUNTING_POLICY", "OBLIGATION", "COMMERCIAL_CONTRACT"].includes(kind))
      payload.currency = project.currency;
    if (values.payable_id)
      payload.expected_payable_version = balances.data?.payables.find(
        (p) => p.id === Number(values.payable_id),
      )?.version;
    if (values.receivable_id)
      payload.expected_receivable_version = balances.data?.receivables.find(
        (p) => p.id === Number(values.receivable_id),
      )?.version;
    if (values.supplier_id)
      payload.expected_supplier_version = suppliers.data?.find(
        (p) => p.id === Number(values.supplier_id),
      )?.version;
    if (kind === "COST_CODE_ASSIGNMENT") {
      const source = sources.data?.cost_sources.find(row => row.type === values.source_type && row.id === Number(values.source_id));
      payload.expected_source_version = source?.version;
      payload.expected_link_version = source?.link_version;
    }
    if (kind === 'PROCUREMENT_AUTHORIZATION') payload.expected_boq_version = options('boq').find(r => r.id===Number(values.boq_item_id))?.version;
    if (kind === 'PROCUREMENT_AMENDMENT') payload.expected_po_version = options('procurement_lines').find(r => r.id===Number(values.po_line_id))?.version;
    if (kind === 'CERTIFICATE_CORRECTION') payload.expected_balance_version = [...(balances.data?.payables || []), ...(balances.data?.receivables || [])].find(r => r.certificate_id===Number(values.certificate_id))?.version;
    if (kind === 'OBLIGATION_SCHEDULE_CHANGE') payload.expected_obligation_version = options('obligations').find(r => r.id===Number(values.obligation_id))?.version;
    await api(editing ? `/controls/${editing.id}` : "/controls", {
      method: editing ? "PATCH" : "POST",
      body: JSON.stringify({
        project_id: project.id,
        name,
        payload,
        expected_version: editing?.version,
      }),
    });
    setCreating(false);
    await reload();
  }
  return (
    <>
      <PageTitle
        eyebrow={commercial ? "CONTRACTS & INDEPENDENT REVIEW" : "ACCOUNTING & INDEPENDENT CONTROLS"}
        title={commercial ? "Commercial Management" : "Cost Control & Accounting"}
        description={commercial ? "Contracts, local RFQs, verified bids, purchase awards, measured work, cumulative certificates and prospective variations." : "Accepted costs, certified revenue, liabilities and cash have separate evidence and approval."}
        action={
          canPrepare ? (
            <button
              className="button primary"
              onClick={() => {
                reset(kind);
                setCreating(true);
              }}
            >
              <Plus size={16} />
              Prepare control
            </button>
          ) : undefined
        }
      />
      {action.feedback}
      {commercial && <Panel title="Commercial workflow">
        <p>Prepare and independently approve a contract, then an RFQ, verified supplier bids, a purchase recommendation and a PO award. Purchase awards require separately authorized procurement BOQ scope.</p>
        <p>Supplier certificates reconcile independently accepted work or deliveries. Customer certificates recognize revenue. Every cash installment still requires separate approval in Payment Center.</p>
      </Panel>}
      <Panel title="Recognized accounting position">
        {summary.error ? (
          <ErrorState error={summary.error} onRetry={() => { void summary.refetch(); }} />
        ) : summary.data ? (
          <>
            <div className="advanced-facts">
              {(
                [
                  "recorded_cash",
                  "incurred_cost",
                  "recognized_revenue",
                  "accrued_liability",
                  "accounts_payable",
                  "accounts_receivable",
                ] as const
              ).map((key) => (
                <div key={key}>
                  <span>{titleCase(key)}</span>
                  <strong>
                    {summary.data[key] === null
                      ? "Insufficient data"
                      : `${formatMoney(summary.data[key]!)} ${project.currency}`}
                  </strong>
                </div>
              ))}
            </div>
            <p className="muted">{summary.data.notice}</p>
          </>
        ) : (
          <Loading />
        )}
      </Panel>
      <Panel title="Cost codes">
        {canPrepare && (
          <form
            className="advanced-inline"
            onSubmit={(e) => {
              e.preventDefault();
              void action.run(async () => {
                await post("/accounting/cost-codes", {
                  project_id: project.id,
                  code,
                  name: codeName,
                });
                setCode("");
                setCodeName("");
                await reload();
              }, "Cost code saved");
            }}
          >
            <Field label="Cost code">
              <input
                required
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </Field>
            <Field label="Cost code name">
              <input
                required
                value={codeName}
                onChange={(e) => setCodeName(e.target.value)}
              />
            </Field>
            <button className="button" disabled={action.busy}>
              Add cost code
            </button>
          </form>
        )}
        <p>
          {codes.data?.map((r) => `${r.code}: ${r.name}`).join(" · ") ||
            "Add project cost codes before recognizing deliveries."}
        </p>
      </Panel>
      <Panel title="Cost-code reconciliation">
        {codePosition.error ? <ErrorState error={codePosition.error} onRetry={() => { void codePosition.refetch(); }} /> : !codePosition.data ? <Loading /> : <>
          <div className="table-scroll"><table><caption>Cost basis, commitments, recognized liabilities and allocated cash by code</caption><thead><tr>
            <th>Cost code</th>{["Budget", "Commitment", "Incurred cost", "Accrual", "Payable", "Paid cash", "Remaining commitment"].map(label => <th key={label}>{label}</th>)}
          </tr></thead><tbody>{codePosition.data.rows.map(row => <tr key={row.id}><td>{row.code} · {row.name}</td>
            {(["budget", "commitment", "cost", "accrual", "payable", "paid", "remaining_commitment"] as const).map(key => <td key={key}>{row[key] === null ? "Insufficient data" : formatMoney(row[key]!)}</td>)}
          </tr>)}</tbody></table></div>
          <p>{codePosition.data.notice}</p>
          {!!codePosition.data.exceptions.length && <details><summary>Unresolved mappings and historical gaps ({codePosition.data.exceptions.length})</summary><ul>{codePosition.data.exceptions.map(message => <li key={message}>{message}</li>)}</ul></details>}
        </>}
      </Panel>
      <Panel title="Payables and installment preparation">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Payable</th>
                <th>Recognized</th>
                <th>Paid</th>
                <th>Remaining</th>
                <th>Retention</th>
                <th>Supplier credit</th>
                <th>Next installment</th>
              </tr>
            </thead>
            <tbody>
              {balances.data?.payables.map((p) => (
                <tr key={p.id}>
                  <td>#{p.id}</td>
                  <td>{formatMoney(p.amount)}</td>
                  <td>{formatMoney(p.paid)}</td>
                  <td>{formatMoney(p.remaining)}</td>
                  <td>{formatMoney(p.retention)}</td>
                  <td>{formatMoney(p.supplier_credit)}</td>
                  <td>
                    {canPrepare && Number(p.remaining) > 0 ? (
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          void action.run(async () => {
                            await post(`/payables/${p.id}/installments`, {
                              expected_version: p.version,
                              amount: amounts[p.id] || p.remaining,
                            });
                            await reload();
                          }, "Installment prepared; independent payment approval is required");
                        }}
                      >
                        <input
                          aria-label={`Installment amount for payable ${p.id}`}
                          inputMode="decimal"
                          value={amounts[p.id] ?? p.remaining}
                          onChange={(e) =>
                            setAmounts((v) => ({
                              ...v,
                              [p.id]: e.target.value,
                            }))
                          }
                        />
                        <button className="button" disabled={action.busy}>
                          Prepare installment
                        </button>
                      </form>
                    ) : (
                      "No unpaid balance"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!balances.data?.payables.length && (
          <p>
            No reconciled payables. Recognize accepted delivery costs, then
            reconcile the supported invoice.
          </p>
        )}
      </Panel>
      <Panel title="Independently reviewed controls">
        {records.error ? (
          <ErrorState error={records.error} onRetry={() => { void records.refetch(); }} />
        ) : records.isPending ? (
          <Loading />
        ) : !visibleRecords?.length ? (
          <p>
            Prepare an accounting policy first. Historical records require
            explicit reviewed opening balances.
          </p>
        ) : (
          visibleRecords.map((r) => {
            const contributor = r.contributors.includes(user.id),
              canCheck =
                project.active &&
                !contributor &&
                ["ADMIN", "FINANCE_MANAGER"].includes(user.role),
              canApprove =
                project.active &&
                !contributor &&
                user.role === "ADMIN" &&
                r.checked_by !== user.id;
            const transition = (next: string) =>
              action.run(
                async () => {
                  await post(`/controls/${r.id}/${next}`, {
                    expected_version: r.version,
                  });
                  await reload();
                },
                `${titleCase(next)} recorded`,
              );
            return (
              <article className="control-card" key={r.id}>
                <div className="advanced-inline">
                  <h3>{r.name}</h3>
                  <Status value={r.status} />
                  <span>
                    {titleCase(r.kind)} · v{r.version}
                  </span>
                </div>
                <details>
                  <summary>Evidence and calculations</summary>
                  <ControlEvidence record={r} records={records.data || []} />
                </details>
                <div className="advanced-inline">
                  {r.status === "DRAFT" && canPrepare && (
                    <button
                      className="button"
                      onClick={() => {
                        setEditing(r);
                        setKind(r.kind);
                        setName(r.name);
                        setEvidence(r.payload.evidence);
                        setValues({ ...r.payload });
                        setCreating(true);
                      }}
                    >
                      Edit draft
                    </button>
                  )}
                  {r.status === "DRAFT" && canPrepare && (
                    <ConfirmButton
                      title="Submit this control?"
                      description="Submission locks evidence and calculations for independent checking."
                      onConfirm={() => transition("submit").then(() => {})}
                    >
                      Submit for checking
                    </ConfirmButton>
                  )}
                  {r.status === "SUBMITTED" && (
                    <button
                      className="button"
                      disabled={!canCheck || action.busy}
                      title={
                        canCheck
                          ? "Record independent checking"
                          : "Retained contributors cannot check their work"
                      }
                      onClick={() => void transition("check")}
                    >
                      Check control
                    </button>
                  )}
                  {r.status === "CHECKED" && (
                    <ConfirmButton
                      title="Approve and publish this control?"
                      description="This posts the bound accounting or governance change. All payment connectivity remains simulated."
                      disabled={!canApprove || action.busy}
                      onConfirm={() => transition("approve").then(() => {})}
                    >
                      Approve control
                    </ConfirmButton>
                  )}
                  {["SUBMITTED", "CHECKED", "REJECTED"].includes(r.status) &&
                    canPrepare && (
                      <button
                        className="button"
                        onClick={() => void transition("revise")}
                      >
                        Create revision
                      </button>
                    )}
                  {contributor &&
                    ["SUBMITTED", "CHECKED"].includes(r.status) && (
                      <small>
                        An independent reviewer must act on your retained
                        contributions.
                      </small>
                    )}
                </div>
              </article>
            );
          })
        )}
      </Panel>
      {creating && (
        <Modal
          title="Prepare independently reviewed control"
          onClose={() => !action.busy && setCreating(false)}
        >
          <form
            className="advanced-form"
            onSubmit={(e) => {
              e.preventDefault();
              void action.run(create, "Draft prepared");
            }}
          >
            <Field label="Control type">
              <select
                disabled={!!editing}
                value={kind}
                onChange={(e) => reset(e.target.value)}
              >
                {Object.keys(config).filter(k => (k in commercialConfig) === commercial).map((k) => (
                  <option key={k} value={k}>
                    {titleCase(k)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Control name">
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={200}
              />
            </Field>
            {config[kind].map((field) => (
              <Field key={field.key} label={field.label}>
                {field.key === "estimate_line_id" ? (
                  <select required value={String(values.estimate_line_id || "")} onChange={event => setValues(v => ({ ...v, estimate_line_id: event.target.value }))}>
                    <option value="">Select a recorded BOQ item</option>
                    {estimateLines.data?.fields.lines.map(line => <option key={line.id} value={line.id}>{line.code} · {line.description} · {line.quantity} {line.unit}</option>)}
                  </select>
                ) : field.key === 'component_id' ? (
                  <select value={String(values.component_id || '')} onChange={event => setValues(v => ({...v, component_id:event.target.value}))}>
                    <option value="">Whole BOQ item</option>
                    {estimateLines.data?.fields.lines.find(r => r.id===values.estimate_line_id)?.components.map(comp => <option key={comp.id} value={comp.id}>{comp.description} · {comp.unit}</option>)}
                  </select>
                ) : field.type === 'forecast-schedule' ? (
                  <ForecastScheduleEditor rows={(values.schedule || []) as {quantity:string;due_date:string|null}[]} onChange={schedule => setValues(v => ({...v,schedule}))} />
                ) : field.source ? (
                  <select
                    required={!field.optional}
                    multiple={field.type === "multiple"}
                    value={
                      field.type === "multiple"
                        ? ((values[field.key] as number[]) || []).map(String)
                        : String(values[field.key] || "")
                    }
                    onChange={(e) =>
                      setValues((v) => ({
                        ...v,
                        ...(field.key === "estimate_id" ? { estimate_line_id: "" } : {}),
                        [field.key]:
                          field.type === "multiple"
                            ? [...e.target.selectedOptions].map((o) =>
                                Number(o.value),
                              )
                            : e.target.value,
                      }))
                    }
                  >
                    {field.type !== "multiple" && (
                      <option value="">Select a recorded source</option>
                    )}
                    {options(field.source).map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                ) : field.options ? (
                  <select
                    value={String(values[field.key] || field.options[0])}
                    onChange={(e) =>
                      setValues((v) => ({ ...v, [field.key]: e.target.value, ...(field.key === "source_type" ? { source_id: "" } : {}) }))
                    }
                  >
                    {field.options.map((o) => (
                      <option key={o}>{o}</option>
                    ))}
                  </select>
                ) : field.type === "opening-rules" ? (
                  <OpeningRulesEditor rows={(values.opening_rules || []) as { calculation: string; threshold_m2: string; comparison: string; multiply_selected_faces: boolean }[]}
                    onChange={opening_rules => setValues(v => ({ ...v, opening_rules }))} />
                ) : ["contract-lines", "certificate-lines"].includes(field.type || "") ? (
                  <ScopeEditor certificate={field.type === "certificate-lines"}
                    rows={(values.lines || []) as Record<string, string | number | null>[]}
                    onChange={lines => setValues(v => ({ ...v, lines }))}
                    codes={options("code")} boq={commercialSources.data?.boq || []} />
                ) : field.type === "journal" ? (
                  <div>
                    {(
                      (values.entries || []) as {
                        account: string;
                        debit: string;
                        credit: string;
                      }[]
                    ).map((entry, index) => (
                      <div className="advanced-grid" key={index}>
                        <select
                          aria-label={`Journal account row ${index + 1}`}
                          value={entry.account}
                          onChange={(e) =>
                            setValues((v) => ({
                              ...v,
                              entries: (v.entries as (typeof entry)[]).map(
                                (r, i) =>
                                  i === index
                                    ? { ...r, account: e.target.value }
                                    : r,
                              ),
                            }))
                          }
                        >
                          {[
                            "PROJECT_COST",
                            "CASH",
                            "ACCRUED_LIABILITY",
                            "ACCOUNTS_PAYABLE",
                            "REVENUE",
                            "ACCOUNTS_RECEIVABLE",
                            "RETENTION_PAYABLE",
                            "RETENTION_RECEIVABLE",
                            "ADVANCE",
                            "CUSTOMER_ADVANCE",
                            "RECOVERABLE_TAX",
                            "OUTPUT_TAX",
                            "OPENING_EQUITY",
                          ].map((a) => (
                            <option key={a}>{a}</option>
                          ))}
                        </select>
                        <input
                          aria-label={`Journal debit row ${index + 1}`}
                          value={entry.debit}
                          onChange={(e) =>
                            setValues((v) => ({
                              ...v,
                              entries: (v.entries as (typeof entry)[]).map(
                                (r, i) =>
                                  i === index
                                    ? { ...r, debit: e.target.value }
                                    : r,
                              ),
                            }))
                          }
                        />
                        <input
                          aria-label={`Journal credit row ${index + 1}`}
                          value={entry.credit}
                          onChange={(e) =>
                            setValues((v) => ({
                              ...v,
                              entries: (v.entries as (typeof entry)[]).map(
                                (r, i) =>
                                  i === index
                                    ? { ...r, credit: e.target.value }
                                    : r,
                              ),
                            }))
                          }
                        />
                      </div>
                    ))}
                    <button
                      className="button"
                      type="button"
                      onClick={() =>
                        setValues((v) => ({
                          ...v,
                          entries: [
                            ...(v.entries as object[]),
                            {
                              account: "PROJECT_COST",
                              debit: "0",
                              credit: "0",
                            },
                          ],
                        }))
                      }
                    >
                      Add journal line
                    </button>
                  </div>
                ) : field.type === "planned" ? (
                  <textarea
                    required
                    value={(
                      (values.planned_values || []) as {
                        date: string;
                        value: string;
                      }[]
                    )
                      .map((p) => `${p.date},${p.value}`)
                      .join("\n")}
                    onChange={(e) =>
                      setValues((v) => ({
                        ...v,
                        planned_values: e.target.value
                          .split("\n")
                          .map((row) => {
                            const [date, value] = row.split(",");
                            return { date, value };
                          }),
                      }))
                    }
                  />
                ) : field.type === "references" ? (
                  <textarea
                    required
                    value={((values.input_evidence as string[]) || []).join(
                      "\n",
                    )}
                    onChange={(e) =>
                      setValues((v) => ({
                        ...v,
                        input_evidence: e.target.value.split("\n"),
                      }))
                    }
                  />
                ) : field.type === "checkbox" ? (
                  <input
                    type="checkbox"
                    required={!field.optional}
                    checked={!!values[field.key]}
                    onChange={(e) =>
                      setValues((v) => ({
                        ...v,
                        [field.key]: e.target.checked,
                      }))
                    }
                  />
                ) : field.type === "templates" ? (
                  <input
                    required
                    placeholder="MASONRY, FINISHES"
                    value={((values.templates as string[]) || []).join(", ")}
                    onChange={(e) =>
                      setValues((v) => ({
                        ...v,
                        templates: e.target.value
                          .split(",")
                          .map((t) => t.trim())
                          .filter(Boolean),
                      }))
                    }
                  />
                ) : (
                  <input
                    required={!field.optional}
                    type={field.type || "text"}
                    value={String(values[field.key] ?? "")}
                    onChange={(e) =>
                      setValues((v) => ({ ...v, [field.key]: e.target.value }))
                    }
                  />
                )}
              </Field>
            ))}
            <Field label="Source evidence and assumptions">
              <textarea
                required
                minLength={10}
                value={evidence}
                onChange={(e) => setEvidence(e.target.value)}
              />
            </Field>
            {action.feedback}
            <button className="button primary" disabled={action.busy}>
              Save control draft
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}
