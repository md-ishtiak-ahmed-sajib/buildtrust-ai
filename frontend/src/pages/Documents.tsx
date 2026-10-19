import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Check, Fingerprint, Info, Plus, ShieldCheck, Upload } from "lucide-react";
import { api, post, previewBlob, titleCase } from "../api";
import type { Doc, DocumentData } from "../types";
import { useWorkspace } from "../App";
import { ConfirmButton, ErrorState, Loading, PageTitle, Panel, Status } from "../ui";
import { useInvoices, dateTime } from "./shared";

export type Extraction = {
  document: Doc;
  data: DocumentData;
  revisions: {
    version: number;
    created_at: string;
    fields: {
      path: string;
      value: string;
      source_document_id: number;
      page: number | null;
      row: number | null;
      extraction_method: string;
      human_reviewed: boolean;
    }[];
  }[];
};

export function DocumentsPage() {
  const { user, project, refresh } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const docs = useQuery({
    queryKey: ["documents", project.id],
    queryFn: () => api<Doc[]>(`/documents?project_id=${project.id}`),
  });
  const selected =
    docs.data?.find((d) => d.id === Number(params.get("id"))) || docs.data?.[0];
  const extraction = useQuery({
    queryKey: ["extraction", selected?.id],
    queryFn: () => api<Extraction>(`/documents/${selected!.id}/extraction`),
    enabled: !!selected,
  });
  const [edit, setEdit] = useState<DocumentData | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [preview, setPreview] = useState<{ url?: string; text?: string } | null>(
      null,
    ),
    [tab, setTab] = useState("fields");
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    setEdit(
      extraction.data
        ? {
            supplier_code: "",
            po_number: "",
            invoice_number: "",
            invoice_date: "",
            beneficiary_fingerprint: "",
            currency: "BDT",
            subtotal: "0",
            tax: "0",
            retention: "0",
            discount: "0",
            grand_total: "0",
            ...structuredClone(extraction.data.data),
            document_type: extraction.data.data.document_type || "INVOICE",
            items: extraction.data.data.items || [],
          }
        : null,
    );
  }, [extraction.data]);
  useEffect(() => {
    setPreview(null);
    setTab("fields");
  }, [selected?.id]);
  useEffect(
    () => () => {
      if (preview?.url) URL.revokeObjectURL(preview.url);
    },
    [preview],
  );
  const editable =
    (project.active && user.role !== "AUDITOR") &&
    !selected?.confirmed_by &&
    selected?.extraction_status !== "DUPLICATE";
  async function uploadFile(file: File) {
    setBusy(true);
    setError("");
    setNotice("");
    const data = new FormData();
    data.append("file", file);
    data.append("project_id", String(project.id));
    try {
      const doc = await api<Doc & { validation_errors: unknown }>(
        "/documents/upload",
        { method: "POST", body: data },
      );
      setParams({ id: String(doc.id) });
      setNotice(
        doc.extraction_status === "DUPLICATE"
          ? "Duplicate document detected and held. No additional payable invoice was created."
          : doc.extraction_status === "NEEDS_REVIEW"
            ? "Document received. Review extracted fields before continuing."
            : "Document contents extracted successfully. Procurement evidence still requires authorized confirmation.",
      );
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="THE FOUNDATION OF EVERY DECISION"
        title="Document workspace"
        description="Import source records, review extracted fields, and follow every value back to its evidence."
        action={
          (project.active && user.role !== "AUDITOR") && (
            <>
              <input
                className="sr-only"
                ref={fileRef}
                type="file"
                accept=".pdf,.csv,.json"
                aria-label="Upload financial document"
                onChange={(e) => {
                  if (e.target.files?.[0]) void uploadFile(e.target.files[0]);
                  e.target.value = "";
                }}
              />
              <button
                className="button primary"
                disabled={busy}
                onClick={() => fileRef.current?.click()}
              >
                <Upload size={17} />
                {busy ? "Processing…" : "Upload document"}
              </button>
            </>
          )
        }
      />
      {error && <ErrorState message={error} />}
      <div className="notice">
        <Info size={18} />
        <p>
          PDF, CSV, or JSON · Up to 10 MB · Scanned PDFs require manual entry
          when OCR is unavailable. Uploaded “approved” labels do not grant
          authority.
        </p>
      </div>
      {notice && (
        <div role="status" className="notice success">
          <Check size={18} />
          {notice}
        </div>
      )}
      <div className="documents-layout">
        <Panel
          title="Project documents"
          subtitle={`${docs.data?.length || 0} source records`}
        >
          {docs.isPending ? (
            <Loading />
          ) : docs.error ? (
            <ErrorState error={docs.error} onRetry={() => { void docs.refetch(); }} />
          ) : (
            <div className="document-list">
              {docs.data.map((d) => (
                <button
                  key={d.id}
                  className={selected?.id === d.id ? "selected" : ""}
                  onClick={() => setParams({ id: String(d.id) })}
                >
                  <span className="file-type">
                    {d.document_type.slice(0, 3)}
                  </span>
                  <div>
                    <strong>{d.original_filename}</strong>
                    <small>
                      {d.document_type} · Version {d.version}
                    </small>
                    <Status value={d.extraction_status} />
                  </div>
                  <ArrowUpRight size={16} />
                </button>
              ))}
            </div>
          )}
        </Panel>
        <Panel
          title={selected?.original_filename || "Document details"}
          subtitle={
            selected
              ? `Source #${selected.id} · ${selected.document_type}`
              : "Select a source record"
          }
        >
          {extraction.isPending ? (
            <Loading />
          ) : extraction.error ? (
            <ErrorState error={extraction.error} onRetry={() => { void extraction.refetch(); }} />
          ) : (
            edit &&
            selected && (
              <>
                <div className="tabs">
                  <button
                    className={tab === "fields" ? "active" : ""}
                    onClick={() => setTab("fields")}
                  >
                    Extracted fields
                  </button>
                  <button
                    className={tab === "evidence" ? "active" : ""}
                    onClick={() => setTab("evidence")}
                  >
                    Field provenance
                  </button>
                  <button
                    className={tab === "preview" ? "active" : ""}
                    onClick={async () => {
                      setTab("preview");
                      if (!preview) {
                        try {
                          const blob = await previewBlob(selected.id);
                          setPreview(
                            blob.type.includes("image")
                              ? { url: URL.createObjectURL(blob) }
                              : { text: await blob.text() },
                          );
                        } catch (e) {
                          setError((e as Error).message);
                        }
                      }
                    }}
                  >
                    Source preview
                  </button>
                </div>
                {tab === "fields" && (
                  <div className="extraction-editor">
                    <div className="field-grid">
                      {Object.entries(edit)
                        .filter(
                          ([key, value]) =>
                            key !== "items" && typeof value !== "object",
                        )
                        .map(([key, value]) => (
                          <label key={key}>
                            {titleCase(key)}
                            <input
                              value={String(value ?? "")}
                              disabled={!editable}
                              onChange={(e) =>
                                setEdit({ ...edit, [key]: e.target.value })
                              }
                            />
                          </label>
                        ))}
                    </div>
                    <h3>Document line items</h3>
                    {(edit.items || []).map((item, index) => (
                      <div className="item-editor" key={index}>
                        {Object.entries(item).map(([key, value]) => (
                          <label key={key}>
                            {titleCase(key)}
                            <input
                              value={value || ""}
                              disabled={!editable}
                              onChange={(e) =>
                                setEdit({
                                  ...edit,
                                  items: edit.items.map((it, i) =>
                                    i === index
                                      ? { ...it, [key]: e.target.value }
                                      : it,
                                  ),
                                })
                              }
                            />
                          </label>
                        ))}
                      </div>
                    ))}
                    {editable && !edit.items?.length && (
                      <button
                        className="button"
                        onClick={() =>
                          setEdit({
                            ...edit,
                            items: [
                              {
                                item_code: "",
                                description: "",
                                quantity: "1",
                                unit: "each",
                                unit_rate: "0",
                                amount: "0",
                              },
                            ],
                          })
                        }
                      >
                        <Plus size={15} />
                        Add item for manual review
                      </button>
                    )}
                    <div className="payment-actions">
                      {editable && (
                        <button
                          className="button primary"
                          disabled={busy}
                          onClick={async () => {
                            setBusy(true);
                            setError("");
                            try {
                              await api(
                                `/documents/${selected.id}/extraction`,
                                {
                                  method: "PATCH",
                                  body: JSON.stringify({
                                    version: selected.version,
                                    data: edit,
                                  }),
                                },
                              );
                              setNotice(
                                "Reviewed fields saved with a new provenance revision.",
                              );
                              await refresh();
                            } catch (e) {
                              setError((e as Error).message);
                            } finally {
                              setBusy(false);
                            }
                          }}
                        >
                          <Check size={16} />
                          Save reviewed fields
                        </button>
                      )}
                      {!selected.confirmed_by &&
                        selected.document_type !== "INVOICE" &&
                        (["ADMIN"].includes(user.role) ||
                          (user.role === "FINANCE_MANAGER" &&
                            ["PO", "GRN"].includes(
                              selected.document_type,
                            ))) && (
                          <ConfirmButton
                            title="Confirm procurement evidence"
                            description="Publish this source as approved project evidence? Confirm that the scope, supplier, quantities, and contract terms are correct."
                            onConfirm={async () => {
                              await post(`/documents/${selected.id}/confirm`);
                              setNotice(
                                "Procurement evidence confirmed by an authorized account.",
                              );
                              await refresh();
                            }}
                          >
                            <ShieldCheck size={16} />
                            Confirm evidence
                          </ConfirmButton>
                        )}
                    </div>
                    {selected.confirmed_by && (
                      <div className="notice success">
                        <ShieldCheck size={18} />
                        Confirmed source evidence. Its original contents and
                        approval history are preserved.
                      </div>
                    )}
                  </div>
                )}
                {tab === "evidence" && (
                  <div className="provenance">
                    <div className="notice">
                      <Fingerprint size={18} />
                      {extraction.data?.revisions.length} extraction
                      revision(s). Confidence is not fabricated for
                      deterministic parsers.
                    </div>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Field</th>
                            <th>Value</th>
                            <th>Source</th>
                            <th>Method / review</th>
                          </tr>
                        </thead>
                        <tbody>
                          {extraction.data?.revisions
                            .at(-1)
                            ?.fields.map((f) => (
                              <tr key={f.path}>
                                <td>{f.path}</td>
                                <td className="provenance-value">{f.value}</td>
                                <td>
                                  #{f.source_document_id}
                                  {f.page ? ` · p${f.page}` : ""}
                                  {f.row ? ` · row ${f.row}` : ""}
                                </td>
                                <td>
                                  {titleCase(f.extraction_method)}
                                  <small>
                                    {f.human_reviewed
                                      ? "Human reviewed"
                                      : "Original extraction"}
                                  </small>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                {tab === "preview" && (
                  <div className="source-preview">
                    {preview?.url ? (
                      <img
                        src={preview.url}
                        alt={`Raster preview of ${selected.original_filename}`}
                      />
                    ) : preview?.text ? (
                      <pre>{preview.text}</pre>
                    ) : (
                      <Loading />
                    )}
                  </div>
                )}
              </>
            )
          )}
        </Panel>
      </div>
    </>
  );
}
