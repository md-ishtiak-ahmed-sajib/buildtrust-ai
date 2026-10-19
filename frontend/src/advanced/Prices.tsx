import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Upload } from "lucide-react";
import { useWorkspace } from "../App";
import { api, post, downloadFile, titleCase } from "../api";
import { Panel, PageTitle, Modal, ErrorState, Status } from "../ui";
import { Facts, useAction, type Material, type Quotation } from "./shared";
import { QuoteForm } from "./QuoteForm";
import { ExchangeRates } from "./ExchangeRates";
import { MaterialEditor } from "./MaterialEditor";
import { PriceDrawer } from "./PriceDrawer";
export { PriceDrawer } from "./PriceDrawer";

export function MaterialsPage() {
  const { project, user, refresh } = useWorkspace(),
    client = useQueryClient(),
    action = useAction();
  const [active, setActive] = useState<Material>(),
    [edit, setEdit] = useState<Material | "NEW">(),
    [editingQuote, setEditingQuote] = useState<Quotation | number>(),
    [filter, setFilter] = useState("");
  const materials = useQuery({
    queryKey: ["materials", project.id],
    queryFn: () => api<Material[]>(`/materials?project_id=${project.id}`),
  });
  const quotes = useQuery({
    queryKey: ["quotations", project.id],
    queryFn: () => api<Quotation[]>(`/quotations?project_id=${project.id}`),
  });
  const providers = useQuery({
    queryKey: ["price-providers"],
    queryFn: () => api<{ id: string; enabled: boolean }[]>("/prices/providers"),
  });
  const history = useQuery({
    queryKey: ["selected-rates", project.id],
    queryFn: () =>
      api<
        {
          id: number;
          reason: string;
          created_at: string;
          snapshot_hash: string;
          snapshot: Record<string, unknown>;
        }[]
      >(`/prices/history?project_id=${project.id}`),
  });
  useEffect(() => {
    setActive(undefined);
    setEdit(undefined);
    setEditingQuote(undefined);
  }, [project.id]);
  const canWrite = project.active && user.role !== "AUDITOR",
    canCheck = project.active && ["ADMIN", "FINANCE_MANAGER"].includes(user.role);
  async function reload() {
    await client.invalidateQueries({ queryKey: ["materials"] });
    await client.invalidateQueries({ queryKey: ["quotations"] });
  }
  const quoteMaterial =
    typeof editingQuote === "number"
      ? materials.data?.find((m) => m.id === editingQuote)
      : materials.data?.find((m) => m.id === editingQuote?.material_id);
  return (
    <>
      <PageTitle
        eyebrow="MARKET INTELLIGENCE"
        title="Materials & Prices"
        description="Technical specifications, attributable sources and evidence that stays with your estimate."
        action={
          canWrite ? (
            <button className="button primary" onClick={() => setEdit("NEW")}>
              <Plus size={16} /> Add material
            </button>
          ) : undefined
        }
      />
      {action.feedback}
      <div className="provider-strip">
        {providers.data?.map((p) => (
          <span key={p.id} className={p.enabled ? "enabled" : ""}>
            {p.id}: {p.enabled ? "Available" : "Credentials missing"}
          </span>
        ))}
      </div>
      {materials.error && <ErrorState error={materials.error} onRetry={() => { void materials.refetch(); }} />}
      <Panel
        title="Project material catalogue"
        subtitle="A price match is only as strong as the recorded engineering requirements."
      >
        <input
          className="advanced-search"
          aria-label="Search materials"
          placeholder="Search material, grade or specification"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <div className="material-grid">
          {materials.data
            ?.filter((m) =>
              `${m.name} ${Object.values(m.specification).join(" ")}`
                .toLowerCase()
                .includes(filter.toLowerCase()),
            )
            .map((m) => (
              <article className="material-card" key={m.id}>
                <span className="eyebrow">
                  {m.category} · {m.unit}
                </span>
                <h3>{m.name}</h3>
                <Facts data={m.specification} />
                <div className="advanced-inline">
                  <button
                    className="button primary"
                    onClick={() => setActive(m)}
                  >
                    Compare prices
                  </button>
                  {canWrite && (
                    <>
                      <button
                        className="button light"
                        onClick={() => setEdit(m)}
                      >
                        Edit
                      </button>
                      <button
                        className="button light"
                        onClick={() => setEditingQuote(m.id)}
                      >
                        Add quotation
                      </button>
                    </>
                  )}
                </div>
                {canWrite && (
                  <label className="button light">
                    <Upload size={14} /> Import quotation / schedule
                    <input
                      type="file"
                      hidden
                      accept=".csv,.xlsx,.pdf"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file)
                          void action.run(async () => {
                            const form = new FormData();
                            form.append("material_id", String(m.id));
                            form.append("file", file);
                            await api("/quotations/import", {
                              method: "POST",
                              body: form,
                            });
                            await reload();
                          }, "Imported as draft quotations; review and verify separately");
                      }}
                    />
                  </label>
                )}
              </article>
            ))}
        </div>
        {!materials.data?.length && (
          <div className="state">
            Add a material with explicit specifications, or open the separate
            upgrade demo below.
          </div>
        )}
      </Panel>
      <Panel
        title="Supplier quotations & official references"
        subtitle="Uploaded evidence needs independent confirmation before becoming a usable source."
      >
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Supplier / product</th>
                <th>Source</th>
                <th>Price</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {quotes.data?.map((q) => (
                <tr key={q.id}>
                  <td>
                    <strong>{q.fields.supplier}</strong>
                    <br />
                    {q.fields.title}
                  </td>
                  <td>{titleCase(q.fields.source_type || "SUPPLIER_QUOTE")}</td>
                  <td>
                    {q.fields.currency} {q.fields.price || "Needs review"} /{" "}
                    {q.fields.unit || "?"}
                  </td>
                  <td>
                    <Status value={q.status} />
                  </td>
                  <td>
                    <div className="advanced-inline">
                      <details><summary>Extraction and correction history</summary>
                        {q.evidence_revisions?.length ? q.evidence_revisions.map(revision => <section key={revision.id}>
                          <h4>Revision {revision.version} · {new Date(revision.created_at).toLocaleString()}</h4>
                          <Facts data={{ reviewer_id: revision.actor_id, evidence_hash: revision.snapshot_hash, ...revision.evidence }} />
                        </section>) : <p>No extraction revisions recorded for this quotation.</p>}
                      </details>
                      {q.status === "DRAFT" && canWrite && (
                        <button
                          className="button light"
                          onClick={() => setEditingQuote(q)}
                        >
                          Review / correct
                        </button>
                      )}
                      {q.filename && (
                        <button
                          className="button light"
                          onClick={() =>
                            void action.run(
                              () =>
                                downloadFile(
                                  `/quotations/${q.id}/attachment`,
                                  q.filename!,
                                ),
                              "Attachment downloaded",
                            )
                          }
                        >
                          Attachment
                        </button>
                      )}
                      {q.status === "DRAFT" &&
                        canCheck &&
                        q.prepared_by !== user.id &&
                        !q.contributors?.includes(user.id) && (
                          <button
                            className="button"
                            onClick={() =>
                              void action.run(async () => {
                                await post(`/quotations/${q.id}/verify`, {
                                  expected_version: q.version,
                                });
                                await reload();
                              }, "Quotation independently verified")
                            }
                          >
                            Verify
                          </button>
                        )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel
        title="Selected rate history"
        subtitle="Immutable snapshots preserve the source, assumptions and user decision."
      >
        {history.data?.length ? (
          <div className="history-list">
            {history.data.map((r) => (
              <details key={r.id}>
                <summary>
                  Selection #{r.id} · {new Date(r.created_at).toLocaleString()}{" "}
                  · {r.reason}
                </summary>
                <Facts
                  data={{ snapshot_hash: r.snapshot_hash, ...r.snapshot }}
                />
              </details>
            ))}
          </div>
        ) : (
          <p className="muted">
            Select a price from a BOQ component to start the evidence history.
          </p>
        )}
      </Panel>
      <ExchangeRates />
      {user.role === "ADMIN" && (
        <Panel title="Separate upgrade demonstration">
          <p>
            Create a fictional project with BDT 2,000,000 cash and a 20-tonne
            uncommitted steel estimate. Existing projects and accounts are
            preserved.
          </p>
          <button
            className="button light"
            onClick={() =>
              void action.run(async () => {
                await post("/advanced/demo-project");
                await refresh();
              }, "Demo project available in the project selector")
            }
          >
            Create / locate upgrade demo
          </button>
        </Panel>
      )}
      {active && (
        <PriceDrawer material={active} onClose={() => setActive(undefined)} />
      )}{" "}
      {edit && (
        <MaterialEditor
          initial={edit === "NEW" ? undefined : edit}
          projectId={project.id}
          onClose={() => setEdit(undefined)}
          onSaved={async () => {
            setEdit(undefined);
            await reload();
          }}
        />
      )}
      {quoteMaterial && editingQuote && (
        <Modal
          title="Review quotation evidence"
          onClose={() => setEditingQuote(undefined)}
        >
          <QuoteForm
            material={quoteMaterial}
            existing={
              typeof editingQuote === "number" ? undefined : editingQuote
            }
            onSaved={() => {
              setEditingQuote(undefined);
              void reload();
            }}
          />
        </Modal>
      )}
    </>
  );
}
