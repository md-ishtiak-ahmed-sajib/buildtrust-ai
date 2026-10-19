import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ArrowUpRight, Check, CheckCheck, FileCheck2, Play, Plus, ShieldCheck, Download } from "lucide-react";
import { api, post, formatMoney } from "../api";
import type { Proposal, Receipt } from "../types";
import { useWorkspace } from "../App";
import { ConfirmButton, Empty, ErrorState, Loading, Modal, PageTitle, Panel, Status } from "../ui";
import { useInvoices, dateTime } from "./shared";

export function PaymentsPage() {
  const { user, project, refresh } = useWorkspace(),
    invoices = useInvoices();
  const proposals = useQuery({
    queryKey: ["payments", project.id],
    queryFn: () => api<Proposal[]>(`/payments?project_id=${project.id}`),
  });
  const [selectedId, setSelectedId] = useState<number | null>(null),
    [showPrepare, setShowPrepare] = useState(false),
    [invoiceId, setInvoiceId] = useState(0),
    [error, setError] = useState(""),
    [receipt, setReceipt] = useState<Receipt | null>(null);
  const keys = useRef(new Map<number, string>());
  const selected =
    proposals.data?.find((p) => p.id === selectedId) || proposals.data?.[0];
  const financeRole = project.active && ["ADMIN", "FINANCE_MANAGER"].includes(user.role),
    withinLimit =
      selected && Number(selected.amount) <= Number(user.approval_limit);
  const canApprove =
    financeRole && withinLimit && selected?.requested_by !== user.id;
  const validInvoices =
    invoices.data?.filter((i) => i.status === "VERIFIED") || [];
  async function action(path: string) {
    await post(path);
    await refresh();
  }
  return (
    <>
      <PageTitle
        eyebrow="CONTROLLED, APPROVED, TRACEABLE"
        title="Payment Center"
        description="Prepare and authorize exact payment instructions. Every settlement here is simulated."
        action={
          (project.active && user.role !== "AUDITOR") && (
            <button
              className="button primary"
              onClick={() => setShowPrepare(true)}
            >
              <Plus size={17} />
              Prepare payment
            </button>
          )
        }
      />
      <div className="notice simulation-notice">
        <ShieldCheck size={19} />
        <p>
          <strong>Sandbox settlement only.</strong> No real bank connection or
          money transfer. Approval is bound to an exact payment snapshot.
        </p>
      </div>
      {error && <ErrorState message={error} />}
      <Panel
        title="Payment proposals"
        subtitle="A separate authorized person must approve each proposal"
      >
        {proposals.isPending ? (
          <Loading />
        ) : proposals.error ? (
          <ErrorState error={proposals.error} onRetry={() => { void proposals.refetch(); }} />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Invoice / supplier</th>
                  <th>Amount</th>
                  <th>State</th>
                  <th>Approval expires</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {proposals.data.map((p) => (
                  <tr
                    className={selected?.id === p.id ? "selected-row" : ""}
                    key={p.id}
                  >
                    <td>
                      <button
                        className="text-link strong"
                        onClick={() => setSelectedId(p.id)}
                      >
                        {p.invoice_number}
                      </button>
                      <small>{p.supplier}</small>
                    </td>
                    <td className="numeric">৳ {formatMoney(p.amount)}</td>
                    <td>
                      <Status value={p.status} />
                    </td>
                    <td>{dateTime(p.expires_at)}</td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={`View proposal ${p.id}`}
                        onClick={() => setSelectedId(p.id)}
                      >
                        <ArrowUpRight size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!proposals.data.length && (
              <Empty>
                No proposals yet. Run the valid invoice workflow or prepare a
                verified invoice.
              </Empty>
            )}
          </div>
        )}
      </Panel>
      {selected && (
        <div className="payment-detail-grid">
          <Panel
            title={`Proposal #${selected.id}`}
            subtitle={selected.invoice_number}
          >
            <dl className="detail-list">
              <div>
                <dt>Supplier</dt>
                <dd>{selected.supplier}</dd>
              </div>
              <div>
                <dt>Proposed amount</dt>
                <dd className="large">৳ {formatMoney(selected.amount)}</dd>
              </div>
              <div>
                <dt>Currency</dt>
                <dd>{selected.currency}</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>
                  <Status value={selected.status} />
                </dd>
              </div>
              <div>
                <dt>Independent approvals</dt>
                <dd>
                  {
                    selected.approvals.filter((a) => a.decision === "APPROVED")
                      .length
                  }
                </dd>
              </div>
            </dl>
            <div className="payment-actions">
              {selected.status === "PENDING_APPROVAL" && canApprove && (
                <ConfirmButton
                  title="Approve sandbox payment"
                  description={`Approve ${selected.currency} ${formatMoney(selected.amount)} to ${selected.supplier}? The exact beneficiary, evidence, amount, and expiry will be checked again.`}
                  onConfirm={() => action(`/payments/${selected.id}/approve`)}
                >
                  <ShieldCheck size={16} />
                  Approve payment
                </ConfirmButton>
              )}
              {selected.status === "APPROVED" && financeRole && withinLimit && (
                <ConfirmButton
                  title="Execute simulated settlement"
                  description={`Simulate a settlement of BDT ${formatMoney(selected.amount)}? This updates the local sandbox cash balance and ledger once.`}
                  onConfirm={async () => {
                    if (!keys.current.has(selected.id))
                      keys.current.set(selected.id, crypto.randomUUID());
                    setReceipt(
                      await post<Receipt>(
                        `/payments/${selected.id}/execute`,
                        undefined,
                        { "Idempotency-Key": keys.current.get(selected.id)! },
                      ),
                    );
                    await refresh();
                  }}
                >
                  <Play size={16} />
                  Execute simulation
                </ConfirmButton>
              )}
              {["PENDING_APPROVAL", "APPROVED"].includes(selected.status) &&
                financeRole &&
                withinLimit && (
                  <ConfirmButton
                    className="button danger-outline"
                    title="Reject proposal"
                    description="Reject this proposal and release its cash and delivery reservations?"
                    onConfirm={() => action(`/payments/${selected.id}/reject`)}
                  >
                    Reject
                  </ConfirmButton>
                )}
              {selected.status === "SETTLED" && (
                <button
                  className="button primary"
                  onClick={async () => {
                    try {
                      setReceipt(
                        await api<Receipt>(`/payments/${selected.id}/receipt`),
                      );
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  <FileCheck2 size={16} />
                  View mock receipt
                </button>
              )}
              {selected.status === "PENDING_APPROVAL" && !canApprove && (
                <p className="muted">
                  <LockMessage />
                  Approval requires a different authorized Finance Manager or
                  Admin within their limit.
                </p>
              )}
            </div>
          </Panel>
          <Panel
            title="Approval protection"
            subtitle="The approved instructions must remain unchanged"
          >
            <div className="protection-list">
              <div>
                <Check size={16} />
                <span>
                  Invoice, supplier, amount, and currency bound to approval
                </span>
              </div>
              <div>
                <Check size={16} />
                <span>Delivery entitlement and available cash reserved</span>
              </div>
              <div>
                <Check size={16} />
                <span>
                  Current risk and cash-flow checks repeated at settlement
                </span>
              </div>
              <div>
                <Check size={16} />
                <span>Retries return the original transaction result</span>
              </div>
            </div>
            <label className="hash-label">
              Approved beneficiary fingerprint
              <code>{selected.beneficiary_fingerprint}</code>
            </label>
            <label className="hash-label">
              Payment snapshot SHA-256<code>{selected.snapshot_hash}</code>
            </label>
          </Panel>
        </div>
      )}
      {showPrepare && (
        <Modal
          title="Prepare a sandbox payment"
          onClose={() => setShowPrepare(false)}
        >
          <p className="modal-description">
            Select a verified invoice. Financial and liquidity controls are
            checked again before reserving cash.
          </p>
          <label>
            Verified invoice
            <select
              value={invoiceId || validInvoices[0]?.id || ""}
              onChange={(e) => setInvoiceId(Number(e.target.value))}
            >
              {validInvoices.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.invoice_number} · BDT {formatMoney(i.grand_total)}
                </option>
              ))}
            </select>
          </label>
          {!validInvoices.length && (
            <Empty>No verified invoices are available.</Empty>
          )}
          <div className="modal-actions">
            <button
              className="button primary"
              disabled={!validInvoices.length}
              onClick={async () => {
                try {
                  const p = await post<Proposal>("/payments/proposals", {
                    invoice_id: invoiceId || validInvoices[0].id,
                  });
                  setSelectedId(p.id);
                  setShowPrepare(false);
                  await refresh();
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Prepare proposal <ArrowRight size={16} />
            </button>
          </div>
        </Modal>
      )}
      {receipt && (
        <Modal
          title="Simulated payment receipt"
          onClose={() => setReceipt(null)}
        >
          <div className="receipt">
            <div className="receipt-check">
              <CheckCheck size={28} />
            </div>
            <span className="simulation">SIMULATION · NO REAL TRANSFER</span>
            <h3>Sandbox settlement complete</h3>
            <strong>৳ {formatMoney(receipt.amount)}</strong>
            <p>{receipt.supplier}</p>
            <dl className="detail-list">
              <div>
                <dt>Invoice</dt>
                <dd>{receipt.invoice_number}</dd>
              </div>
              <div>
                <dt>Provider</dt>
                <dd>{receipt.provider}</dd>
              </div>
              <div>
                <dt>Settled at</dt>
                <dd>{dateTime(receipt.executed_at)} Dhaka</dd>
              </div>
              <div>
                <dt>Cash after settlement</dt>
                <dd>৳ {formatMoney(receipt.balance_after)}</dd>
              </div>
            </dl>
            <label className="hash-label">
              Mock transaction ID<code>{receipt.mock_transaction_id}</code>
            </label>
            <button className="button" onClick={() => window.print()}>
              <Download size={16} />
              Print receipt
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

export function LockMessage() {
  return <ShieldCheck size={15} />;
}
