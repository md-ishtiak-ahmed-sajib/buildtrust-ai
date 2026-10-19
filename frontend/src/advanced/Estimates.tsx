import { EstimateBoqTable } from './EstimateBoqTable';
import { SearchSelect } from '../controls/SearchSelect';
import { EstimateRateEditor } from './EstimateRateEditor';
import { EstimateBasisEditor } from './EstimateBasisEditor';
import { EstimateForecastPanel } from './EstimateForecastPanel';
import { useEffect, useState } from "react";
import { useDraftRegistration } from "../DraftGuard";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Save,
  FileDown,
  Upload,
} from "lucide-react";
import { useWorkspace } from "../App";
import { api, post, downloadFile, formatMoney } from "../api";
import {
  PageTitle,
  Panel,
  Status,
  Modal,
  Loading,
  ErrorState,
  ConfirmButton,
} from "../ui";
import type { Forecast } from "../types";
import { PriceDrawer } from "./PriceDrawer";
import { EstimateCopilot } from "./Copilot";
import {
  Field,
  Facts,
  useAction,
  type Estimate,
  type Material,
  type Line,
  type Profile,
} from "./shared";

type Calculated = {
  total: string;
  policy: string;
  lines: {
    id: string;
    code: string;
    unit_rate: string;
    amount: string;
    categories: Record<string, string>;
    build_up: Record<string, unknown>;
    components: { id: string; amount: string }[];
  }[];
};
type Preview = {
  unscheduled_commitments?: Record<string,string|number>[];
  estimated_overlay?: import("./ForecastBreakdown").ForecastPart[];
  recorded_cash: string;
  unscheduled_estimated_cost: string;
  notice: string;
  warnings: string[];
  base: Forecast;
  scenarios: Forecast["scenarios"];
};
type Control = {
  original_budget: string;
  approved_estimate_budget: string | null;
  current_estimate: string | null;
  forecast_vs_budget: string | null;
  budget_overrun: boolean;
  po_line_commitment: string;
  paid_cash: string;
  actual_incurred_cost: string | null;
  notice: string;
};
type Sheet = {
  id: number;
  status: string;
  fields: { name: string };
  result: { quantity: string; unit: string };
};

export function EstimatesPage() {
  const { project, user } = useWorkspace(),
    client = useQueryClient(),
    action = useAction();
  const [selectedId, setSelectedId] = useState<number>(),
    [draft, setDraft] = useState<Estimate>(),
    [dirty, setDirty] = useState(false),
    [expanded, setExpanded] = useState<string>(),
    [creating, setCreating] = useState(false),
    [name, setName] = useState(""),
    [importBoq, setImportBoq] = useState(true),
    [price, setPrice] = useState<{
      material: Material;
      lineId: string;
      componentId: string;
      quantity: string;
    }>(),
    [otherId, setOtherId] = useState<number>();
  const list = useQuery({
    queryKey: ["estimates", project.id],
    queryFn: () => api<Estimate[]>(`/estimates?project_id=${project.id}`),
  });
  const materials = useQuery({
    queryKey: ["materials", project.id],
    queryFn: () => api<Material[]>(`/materials?project_id=${project.id}`),
  });
  const costCodes = useQuery({ queryKey: ["cost-codes", project.id], queryFn: () => api<{ id: number; code: string; name: string }[]>(`/accounting/cost-codes?project_id=${project.id}`) });
  const sheets = useQuery({
    queryKey: ["takeoff-sheets", project.id],
    queryFn: () => api<Sheet[]>(`/takeoff/sheets?project_id=${project.id}`),
  });
  const selected =
    list.data?.find((e) => e.id === selectedId) || list.data?.[0];
  useEffect(() => {
    setSelectedId(undefined);
    setDraft(undefined);
    setDirty(false);
    setPrice(undefined);
  }, [project.id]);
  useEffect(() => {
    if (selected) {
      setDraft(structuredClone(selected));
      setDirty(false);
    }
  }, [selected?.id, selected?.version]);
  const forecast = useQuery({
    queryKey: ["estimate-forecast", selected?.id, selected?.version],
    queryFn: () => api<Preview>(`/estimates/${selected!.id}/forecast`),
    enabled: !!selected,
  });
  const control = useQuery({
    queryKey: ["cost-control", project.id, selected?.version],
    queryFn: () =>
      api<Control>(`/finance/cost-control?project_id=${project.id}`),
  });
  const difference = useQuery({
    queryKey: ["estimate-compare", selected?.id, otherId],
    queryFn: () =>
      api<{ total_difference: string; items: unknown[] }>(
        `/estimates/${selected!.id}/compare?other_id=${otherId}`,
      ),
    enabled: !!selected && !!otherId,
  });
  const canWrite = project.active && user.role !== "AUDITOR",
    editable = canWrite && draft?.status === "DRAFT";
  const calc = draft?.calculated as unknown as Calculated | undefined;
  function update(work: (e: Estimate) => void) {
    setDraft((old) => {
      if (!old) return old;
      const copy = structuredClone(old);
      work(copy);
      return copy;
    });
    setDirty(true);
  }
  function lineChange(id: string, key: keyof Line, value: unknown) {
    update((e) => {
      const line = e.fields.lines?.find((l) => l.id === id);
      if (line) Object.assign(line, { [key]: value });
    });
  }
  async function reload() {
    await client.invalidateQueries({ queryKey: ["estimates"] });
    await client.invalidateQueries({ queryKey: ["cost-control"] });
    await client.invalidateQueries({ queryKey: ["estimate-forecast"] });
    await client.invalidateQueries({ queryKey: ["selected-rates"] });
  }
  async function save() {
    if (!draft) return;
    const result = await api<Estimate>(`/estimates/${draft.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        expected_version: draft.version,
        name: draft.name,
        fields: draft.fields,
      }),
    });
    setDraft(result);
    setDirty(false);
    await reload();
  }
  const guardAction = useDraftRegistration(dirty, save, () => {
    setDraft(structuredClone(selected));
    setDirty(false);
  });
  async function transition(kind: string) {
    if (!draft) return;
    const result = await post<Estimate>(`/estimates/${draft.id}/${kind}`, {
      expected_version: draft.version,
    });
    setSelectedId(result.id);
    setDraft(result);
    setDirty(false);
    await reload();
  }
  function addLine() {
    const id = crypto.randomUUID();
    update((e) => {
      e.fields.lines = [
        ...(e.fields.lines || []),
        {
          id,
          code: `ITEM-${(e.fields.lines?.length || 0) + 1}`,
          section: "Works",
          cost_code: "",
          notes: "",
          drawing_reference: "",
          description: "New measured item",
          unit: "m3",
          quantity: "1",
          kind: "MEASURED",
          components: [
            {
              id: crypto.randomUUID(),
              description: "Material component",
              category: "MATERIAL",
              consumption: "1",
              unit: "m3",
              unit_price: "0",
              wastage_percent: "0",
              source_note: "",
            },
          ],
        },
      ];
    });
    setExpanded(id);
  }
  const editorProps = draft ? {draft,calc: draft.calculated,editable:!!editable,dirty,expanded,setExpanded,setPrice,update,materials,costCodes,sheets,lineChange} : undefined;
  return (
    <>
      <PageTitle
        eyebrow="ESTIMATION & QUANTITY SURVEYING"
        title="BOQ & Estimates"
        description="Measured quantities and source-backed rates, with a clear boundary between plans and authorized commitments."
        action={
          canWrite ? (
            <button
              className="button primary"
              onClick={() => setCreating(true)}
            >
              <Plus size={16} /> New estimate
            </button>
          ) : undefined
        }
      />
      {action.feedback}
      {list.error && <ErrorState error={list.error} onRetry={() => { void list.refetch(); }} />}
      {list.isPending && <Loading />}
      <div className="advanced-metrics">
        <div>
          <small>Original project budget</small>
          <strong>
            {formatMoney(control.data?.original_budget || project.budget)}
          </strong>
        </div>
        <div>
          <small>Approved estimate baseline</small>
          <strong>
            {control.data?.approved_estimate_budget
              ? formatMoney(control.data.approved_estimate_budget)
              : "Awaiting approval"}
          </strong>
        </div>
        <div>
          <small>Current estimate / budget variance</small>
          <strong className={control.data?.budget_overrun ? "negative" : ""}>
            {control.data?.forecast_vs_budget
              ? formatMoney(control.data.forecast_vs_budget)
              : "—"}
          </strong>
        </div>
        <div>
          <small>Recorded cash · {project.currency}</small>
          <strong>{formatMoney(project.balance)}</strong>
        </div>
      </div>
      <Panel
        title="Estimate versions"
        action={
          <SearchSelect
            label="Select estimate version"
            value={selected?.id || ""}
            onChange={(identity) => {
              const value = Number(identity);
              guardAction(() => {
                setSelectedId(value);
                setExpanded(undefined);
              });
            }}
            options={(list.data || []).map(e => ({ value: e.id, label: `${e.name} · r${e.revision} · ${e.status}` }))}
          />
        }
      >
        {!draft ? (
          <div className="state">
            Create an estimate from the approved BOQ, or start an empty project
            estimate.
          </div>
        ) : (
          <>
            <div className="estimate-heading">
              <div>
                <Field label="Estimate name">
                  <input
                    disabled={!editable}
                    value={draft.name}
                    onChange={(e) =>
                      update((v) => {
                        v.name = e.target.value;
                      })
                    }
                  />
                </Field>
                <p className="muted">
                  Revision {draft.revision} · Version {draft.version} ·{" "}
                  {draft.fields.estimate_type?.toLowerCase()} ·{" "}
                  {project.currency}
                </p>
              </div>
              <Status value={draft.status} />
              <div className="estimate-total">
                <small>
                  Selling / tender total {dirty ? "· save to recalculate" : ""}
                </small>
                <strong>{formatMoney(draft.total)}</strong>
                <small>
                  Cost budget:{" "}
                  {draft.cost_total
                    ? formatMoney(draft.cost_total)
                    : "Insufficient cost-basis data"}{" "}
                  {project.currency}
                </small>
              </div>
            </div>
            {dirty && (
              <div className="notice">
                Unsaved edits. Save to calculate the authoritative rate,
                estimate total and financial preview.
              </div>
            )}
            <div className="advanced-inline estimate-toolbar">
              {editable && (
                <>
                  <button
                    className="button primary"
                    disabled={action.busy || !dirty}
                    onClick={() =>
                      void action.run(save, "Estimate saved and recalculated")
                    }
                  >
                    <Save size={15} /> Save & recalculate
                  </button>
                  <button className="button light" onClick={addLine}>
                    <Plus size={15} /> Add BOQ item
                  </button>
                  <label className="button light">
                    <Upload size={15} /> Import BOQ
                    <input
                      type="file"
                      hidden
                      accept=".csv,.xlsx"
                      disabled={dirty}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file)
                          void action.run(async () => {
                            const form = new FormData();
                            form.append(
                              "expected_version",
                              String(draft.version),
                            );
                            form.append("file", file);
                            const next = await api<Estimate>(
                              `/estimates/${draft.id}/import`,
                              { method: "POST", body: form },
                            );
                            setDraft(next);
                            await reload();
                          }, "BOQ imported and calculated");
                      }}
                    />
                  </label>
                </>
              )}
              {["csv", "xlsx"].map((ext) => (
                <button
                  className="button light"
                  key={ext}
                  onClick={() =>
                    void action.run(
                      () =>
                        downloadFile(
                          `/estimates/${draft.id}/export?format=${ext}`,
                          `estimate-${draft.id}.${ext}`,
                        ),
                      "Estimate downloaded",
                    )
                  }
                >
                  <FileDown size={15} />
                  {ext.toUpperCase()}
                </button>
              ))}
              <button className="button light" onClick={() => window.print()}>
                Print estimate
              </button>
            </div>
            <EstimateBoqTable {...editorProps!} />
            <EstimateRateEditor {...editorProps!} />
            <EstimateBasisEditor draft={draft} editable={!!editable} update={update} policy={calc?.policy} />
            <div className="approval-bar">
              <Status value={draft.status} />
              {draft.status === "DRAFT" && canWrite && (
                <ConfirmButton
                  title="Submit this estimate version?"
                  description="Submission locks the quantities, selected evidence and calculation policy for independent checking."
                  disabled={dirty || action.busy}
                  onConfirm={() => transition("submit")}
                >
                  Submit for checking
                </ConfirmButton>
              )}
              {draft.status === "SUBMITTED" &&
                project.active && ["FINANCE_MANAGER", "ADMIN"].includes(user.role) &&
                !(draft.contributors || [draft.prepared_by]).includes(
                  user.id,
                ) && (
                  <ConfirmButton
                    title="Confirm independent checking?"
                    description="Confirm that quantities, sources and assumptions have been reviewed. This records checking, not final budget approval."
                    onConfirm={() => transition("check")}
                  >
                    Check estimate
                  </ConfirmButton>
                )}
              {draft.status === "CHECKED" &&
                project.active && user.role === "ADMIN" &&
                ![draft.prepared_by, draft.checked_by].includes(user.id) && (
                  <ConfirmButton
                    title="Approve this exact budget version?"
                    description="This creates a locked estimate baseline. It does not authorize procurement or payment."
                    disabled={(
                      draft.contributors || [draft.prepared_by]
                    ).includes(user.id)}
                    onConfirm={() => transition("approve")}
                  >
                    Approve estimate baseline
                  </ConfirmButton>
                )}
              {draft.status !== "DRAFT" && canWrite && (
                <button
                  className="button light"
                  onClick={() =>
                    void action.run(
                      () => transition("revise"),
                      "New editable revision created",
                    )
                  }
                >
                  Create revision
                </button>
              )}
            </div>
            {["SUBMITTED", "CHECKED"].includes(draft.status) &&
              (draft.contributors || [draft.prepared_by]).includes(user.id) && (
                <p className="muted">
                  You contributed to retained content. Another authorized person
                  must independently check or approve this estimate.
                </p>
              )}
            {draft.snapshot_hash && (
              <p className="hash-text">
                Approval evidence hash: {draft.snapshot_hash}
              </p>
            )}
            <div className="advanced-inline">
              <Field label="Compare with another revision">
                <select
                  value={otherId || ""}
                  onChange={(e) =>
                    setOtherId(Number(e.target.value) || undefined)
                  }
                >
                  <option value="">Select revision</option>
                  {list.data
                    ?.filter(
                      (e) =>
                        e.estimate_key === draft.estimate_key &&
                        e.id !== draft.id,
                    )
                    .map((e) => (
                      <option key={e.id} value={e.id}>
                        Revision {e.revision} · {e.status}
                      </option>
                    ))}
                </select>
              </Field>
              {difference.data && (
                <span>
                  Current − selected:{" "}
                  {formatMoney(difference.data.total_difference)}{" "}
                  {project.currency}
                </span>
              )}
            </div>
          </>
        )}
      </Panel>
      {forecast.data && <EstimateForecastPanel forecast={forecast.data} />}
      {draft?.snapshot_hash && (
        <div className="advanced-inline">
          <button
            className="button light"
            onClick={() =>
              void action.run(
                () =>
                  downloadFile(
                    `/estimates/${draft.id}/evidence`,
                    `estimate-${draft.id}-approval-evidence.json`,
                  ),
                "Approval evidence downloaded",
              )
            }
          >
            Download approval evidence
          </button>
        </div>
      )}
      {control.data && (
        <Panel title="Cost and commitment context">
          <Facts
            data={{
              approved_PO_line_values: control.data.po_line_commitment,
              paid_cash: control.data.paid_cash,
              actual_incurred_cost: control.data.actual_incurred_cost ?? "Insufficient accrual data",
              budget_warning: control.data.budget_overrun
                ? "Estimate exceeds the available baseline"
                : "Within current baseline",
            }}
          />
          <p className="muted">{control.data.notice}</p>
        </Panel>
      )}
      {draft && (
        <EstimateCopilot projectId={project.id} estimateId={draft.id} />
      )}
      {price && draft && (
        <PriceDrawer
          {...price}
          estimate={draft}
          onSelected={(next) => {
            setDraft(next);
            setDirty(false);
            void reload();
          }}
          onClose={() => setPrice(undefined)}
        />
      )}
      {creating && (
        <Modal
          title="Create project estimate"
          onClose={() => setCreating(false)}
        >
          <form
            className="advanced-form"
            onSubmit={(e) => {
              e.preventDefault();
              void action.run(async () => {
                const next = await post<Estimate>("/estimates", {
                  project_id: project.id,
                  name,
                  import_boq: importBoq,
                });
                setSelectedId(next.id);
                await reload();
                setCreating(false);
              });
            }}
          >
            <Field label="Estimate name">
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
            <label className="advanced-inline">
              <input
                type="checkbox"
                checked={importBoq}
                onChange={(e) => setImportBoq(e.target.checked)}
              />{" "}
              Copy approved BOQ into this estimate draft
            </label>
            <p>Approved procurement records remain unchanged.</p>
            {action.feedback}
            <button className="button primary" disabled={action.busy}>
              Create estimate
            </button>
          </form>
        </Modal>
      )}
    </>
  );
}
