import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, FileSearch, Fingerprint, LoaderCircle, Send, ShieldCheck, Sparkles, AlertTriangle, ExternalLink } from "lucide-react";
import { api, post, formatMoney, titleCase } from "../api";
import type { Verification, Workflow } from "../types";
import { useWorkspace } from "../App";
import { Empty, ErrorState, Loading, PageTitle, Panel, Status } from "../ui";
import { useInvoices, dateTime } from "./shared";

export function InvoicesPage() {
  const { user, project, refresh } = useWorkspace(),
    invoices = useInvoices();
  const [params, setParams] = useSearchParams(),
    [filter, setFilter] = useState("ALL"),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [runId, setRunId] = useState<number | null>(null);
  const selected =
    invoices.data?.find((i) => i.id === Number(params.get("invoice"))) ||
    invoices.data?.[0];
  const verification = useQuery({
    queryKey: ["verification", selected?.id],
    queryFn: () => api<Verification>(`/invoices/${selected!.id}/verification`),
    enabled: !!selected,
  });
  const run = useQuery({
    queryKey: ["workflow", runId],
    queryFn: () => api<Workflow>(`/agent/workflows/${runId}`),
    enabled: !!runId,
    refetchInterval: (q) =>
      ["QUEUED", "RUNNING"].includes(q.state.data?.status || "QUEUED")
        ? 700
        : false,
  });
  const history = useQuery({
    queryKey: ["workflow-history", selected?.id],
    queryFn: () => api<Workflow[]>(`/invoices/${selected!.id}/workflows`),
    enabled: !!selected,
  });
  const currentRun = run.data || history.data?.[0];
  useEffect(() => {
    if (run.data && !["QUEUED", "RUNNING"].includes(run.data.status))
      void refresh();
  }, [run.data?.status]);
  const [question, setQuestion] = useState("Why was this invoice blocked?"),
    [answer, setAnswer] = useState<{
      answer: string;
      explanation_source: string;
      document_ids: number[];
    } | null>(null),
    [asking, setAsking] = useState(false);
  async function analyze() {
    setBusy(true);
    setError("");
    try {
      const r = await post<{ workflow_id: number }>("/agent/analyze", {
        invoice_id: selected!.id,
      });
      setRunId(r.workflow_id);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (invoices.isPending) return <Loading />;
  if (invoices.error) return <ErrorState error={invoices.error} onRetry={() => { void invoices.refetch(); }} />;
  const report = verification.data;
  return (
    <>
      <PageTitle
        eyebrow="EVIDENCE BEFORE AUTHORIZATION"
        title="Invoice Intelligence"
        description="Match every supplier claim to approved scope, contracted supply, and accepted delivery."
        action={
          (project.active && user.role !== "AUDITOR") &&
          selected && (
            <button
              className="button primary"
              onClick={analyze}
              disabled={busy || currentRun?.status === "RUNNING"}
            >
              {busy ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <Sparkles size={17} />
              )}
              Run financial workflow
            </button>
          )
        }
      />
      {error && <ErrorState message={error} />}
      <div className="invoice-layout">
        <Panel
          className="invoice-list"
          title="Supplier invoices"
          action={
            <select
              aria-label="Filter invoice status"
              className="small-select"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="ALL">All</option>
              <option>BLOCKED</option>
              <option>VERIFIED</option>
              <option>SETTLED</option>
            </select>
          }
        >
          {invoices.data
            .filter((i) => filter === "ALL" || i.status === filter)
            .map((i) => (
              <button
                className={`invoice-choice ${selected?.id === i.id ? "selected" : ""}`}
                key={i.id}
                onClick={() => {
                  setParams({ invoice: String(i.id) });
                  setRunId(null);
                  setAnswer(null);
                }}
              >
                <div>
                  <strong>{i.invoice_number}</strong>
                  <Status value={i.status} />
                </div>
                <p>{i.supplier}</p>
                <b>৳ {formatMoney(i.grand_total)}</b>
                <small>{i.invoice_date}</small>
              </button>
            ))}
          {!invoices.data.length && (
            <Empty>Upload an invoice to start verification.</Empty>
          )}
        </Panel>
        <div className="invoice-detail">
          {selected && (
            <>
              <div className="invoice-detail-head">
                <div className="document-icon">
                  <FileSearch size={24} />
                </div>
                <div>
                  <h2>{selected.invoice_number}</h2>
                  <p>
                    {selected.supplier} <span>·</span> {selected.invoice_date}
                  </p>
                </div>
                <Status value={selected.status} />
              </div>
              {verification.isPending ? (
                <Loading />
              ) : verification.error ? (
                <ErrorState error={verification.error} onRetry={() => { void verification.refetch(); }} />
              ) : (
                report && (
                  <>
                    <div className="comparison-metrics">
                      <div>
                        <small>Supplier claim</small>
                        <strong>৳ {formatMoney(report.claimed_amount)}</strong>
                      </div>
                      <div>
                        <small>Supported by evidence</small>
                        <strong>৳ {formatMoney(report.verified_amount)}</strong>
                      </div>
                      <div
                        className={Number(report.difference) > 0 ? "red" : ""}
                      >
                        <small>Unsupported amount</small>
                        <strong>৳ {formatMoney(report.difference)}</strong>
                      </div>
                    </div>
                    <Panel
                      title="Four-way financial verification"
                      subtitle="Canonical units · Exact item codes and specifications"
                    >
                      <div className="table-scroll">
                        <table className="comparison-table">
                          <thead>
                            <tr>
                              <th>Item / unit</th>
                              <th>BOQ</th>
                              <th>PO</th>
                              <th>Accepted</th>
                              <th>Prior use</th>
                              <th>Invoiced</th>
                              <th>Contract / claim rate</th>
                            </tr>
                          </thead>
                          <tbody>
                            {report.comparisons.map((c) => (
                              <tr
                                className={
                                  c.severity === "BLOCK" ? "mismatch-row" : ""
                                }
                                key={c.item_code}
                              >
                                <td>
                                  <strong>{c.item_code}</strong>
                                  <small>{c.unit}</small>
                                </td>
                                <td>{formatMoney(c.boq_quantity)}</td>
                                <td>{formatMoney(c.po_quantity)}</td>
                                <td>{formatMoney(c.accepted_quantity)}</td>
                                <td>{formatMoney(c.previously_allocated)}</td>
                                <td>
                                  <strong>
                                    {formatMoney(c.invoice_quantity)}
                                  </strong>
                                  {c.quantity_variance_percent &&
                                    Number(c.quantity_variance_percent) > 0 && (
                                      <small className="red">
                                        +{c.quantity_variance_percent}%
                                      </small>
                                    )}
                                </td>
                                <td>
                                  {formatMoney(c.contract_rate)} /{" "}
                                  {formatMoney(c.invoice_rate)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div className="evidence-bar">
                        <span>
                          <Fingerprint size={15} />
                          Source evidence
                        </span>
                        {[
                          ...new Map(
                            report.comparisons
                              .flatMap((c) => c.evidence)
                              .map((e) => [e.document_id, e]),
                          ).values(),
                        ].map((e) => (
                          <Link
                            key={e.document_id}
                            to={`/documents?id=${e.document_id}`}
                          >
                            {e.record_type} #{e.document_id}
                            <ExternalLink size={12} />
                          </Link>
                        ))}
                      </div>
                    </Panel>
                    <Panel
                      title={
                        report.payment_eligible
                          ? "Verification complete"
                          : "Why was this blocked?"
                      }
                      subtitle="Deterministic financial controls · Each blocking finding prevents payment"
                    >
                      <div className="finding-list">
                        {report.findings.length ? (
                          report.findings.map((f, i) => (
                            <div
                              className={`finding ${f.severity === "BLOCK" ? "blocking" : "warning"}`}
                              key={i}
                            >
                              <AlertTriangle size={18} />
                              <div>
                                <strong>{titleCase(f.code)}</strong>
                                <p>{f.message}</p>
                              </div>
                              <Status value={f.severity} />
                            </div>
                          ))
                        ) : (
                          <div className="notice success">
                            <ShieldCheck size={20} />
                            All checks passed. A different authorized account
                            must approve the exact proposal.
                          </div>
                        )}
                      </div>
                    </Panel>
                    <Panel
                      title="Financial workflow"
                      subtitle={
                        currentRun
                          ? titleCase(currentRun.status)
                          : "Run the workflow to persist every analysis step"
                      }
                    >
                      <div className="timeline">
                        {currentRun?.steps.map((s) => (
                          <div key={s.id}>
                            <span className="timeline-dot">
                              <Check size={12} />
                            </span>
                            <strong>{s.name}</strong>
                            <small>{titleCase(s.status)}</small>
                          </div>
                        )) ||
                          [
                            "Document intake",
                            "Extraction review",
                            "Reconciliation",
                            "Risk assessment",
                            "Cash-flow assessment",
                            "Human authorization",
                          ].map((s) => (
                            <div key={s}>
                              <span className="timeline-dot neutral" />
                              <strong>{s}</strong>
                              <small>Ready</small>
                            </div>
                          ))}
                      </div>
                      {currentRun?.result.proposal_id && (
                        <Link className="button primary" to="/payments">
                          Open prepared payment <ArrowRight size={16} />
                        </Link>
                      )}
                      {currentRun?.error && (
                        <ErrorState message={currentRun.error} />
                      )}
                    </Panel>
                    <Panel
                      title="Ask your finance copilot"
                      subtitle="Answers grounded in saved evidence and deterministic calculations"
                    >
                      <div className="question-examples">
                        {[
                          "Why was this invoice blocked?",
                          "How much does the claim exceed verified delivery?",
                          "Can we safely pay this invoice today?",
                          "What happens if receivables are delayed by 15 days?",
                        ].map((q) => (
                          <button key={q} onClick={() => setQuestion(q)}>
                            {q}
                          </button>
                        ))}
                      </div>
                      <form
                        className="ask-form"
                        onSubmit={async (e) => {
                          e.preventDefault();
                          setAsking(true);
                          try {
                            setAnswer(
                              await post("/agent/ask", {
                                question,
                                project_id: project.id,
                                invoice_id: selected.id,
                              }),
                            );
                          } catch (e) {
                            setError((e as Error).message);
                          } finally {
                            setAsking(false);
                          }
                        }}
                      >
                        <input
                          aria-label="Ask finance copilot"
                          value={question}
                          onChange={(e) => setQuestion(e.target.value)}
                          required
                        />
                        <button className="button primary" disabled={asking}>
                          <Send size={16} />
                          {asking ? "Checking…" : "Ask"}
                        </button>
                      </form>
                      {answer && (
                        <div className="copilot-answer">
                          <span>
                            <Sparkles size={15} />
                            {titleCase(answer.explanation_source)} explanation
                          </span>
                          <p>{answer.answer}</p>
                          <div>
                            {answer.document_ids.map((id) => (
                              <Link key={id} to={`/documents?id=${id}`}>
                                Source #{id}
                              </Link>
                            ))}
                          </div>
                        </div>
                      )}
                    </Panel>
                  </>
                )
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
