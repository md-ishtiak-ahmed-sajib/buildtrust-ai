import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useWorkspace } from "./App";
import { api } from "./api";
import { Panel, PageTitle, Status, Loading, ErrorState } from "./ui";
import { Field } from "./advanced/shared";
import { useStoredFilter } from "./controls/useStoredFilter";
type Item = {
  kind: string;
  id: number;
  title: string;
  status: string;
  actionable: boolean;
  explanation: string;
  url: string;
  expires_at: string | null;
  expiry_state: string | null;
};
type Register = {
  total: number;
  offset: number;
  limit: number;
  items: { id: number; label: string; status: string; created_at: string }[];
};
export function OperationsPage() {
  const { project, user } = useWorkspace();
  const [kind, setKind] = useStoredFilter(`${user.id}.${project.id}.register`, "documents");
  const [q, setQ] = useStoredFilter(`${user.id}.${project.id}.query`, "");
  const [order, setOrder] = useStoredFilter(`${user.id}.${project.id}.order`, "desc");
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const work = useQuery({
    queryKey: ["work-items", project.id],
    queryFn: () => api<Item[]>(`/work-items?project_id=${project.id}`),
    refetchInterval: 30000,
  });
  const register = useQuery({
    queryKey: ["register", project.id, kind, q, status, offset, order],
    queryFn: () =>
      api<Register>(
        `/registers/${kind}?project_id=${project.id}&q=${encodeURIComponent(q)}&status=${encodeURIComponent(status)}&offset=${offset}&order=${order}`,
      ),
  });
  return (
    <>
      <PageTitle
        eyebrow="WORKFLOW & EVIDENCE"
        title="Review Inbox"
        description="Current review and expiry information comes directly from authoritative records."
      />
      <Panel
        title={`Next steps for ${user.role.toLowerCase().replaceAll("_", " ")}`}
      >
        <p>
          {user.role === "OPERATOR"
            ? "Prepare evidence and submit complete drafts for independent review."
            : user.role === "AUDITOR"
              ? "Read sources, calculations and audit events; approval actions require another role."
              : "Review independent work. Contributors cannot check or approve their retained content."}
        </p>
        <details>
          <summary>First-run guide</summary>
          <ol>
            <li>
              Find locally generated credentials in your private data directory.
              Sign in as each role to demonstrate independence.
            </li>
            <li>
              Upload documented files, review extraction, and ask an authorized
              reviewer to confirm procurement evidence.
            </li>
            <li>
              Use Materials &amp; Prices to create the fictional upgrade
              project. Demonstration, live, reference and historical offers
              remain separately labeled.
            </li>
            <li>
              Prepare estimates and payments; use different people for review
              and approval. Every settlement is simulated.
            </li>
            <li>
              Archived runs are listed in the project selector and remain read
              only.
            </li>
          </ol>
        </details>
      </Panel>
      <Panel title="Review and expiry notifications">
        {work.isPending ? (
          <Loading />
        ) : work.error ? (
          <ErrorState error={work.error} onRetry={() => { void work.refetch(); }} />
        ) : !work.data?.length ? (
          <p>No pending review in this project.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Work item</th>
                  <th>Status</th>
                  <th>Next step</th>
                  <th>Expiry</th>
                </tr>
              </thead>
              <tbody>
                {work.data.map((item) => (
                  <tr key={`${item.kind}-${item.id}`}>
                    <td>
                      <Link to={item.url}>{item.title}</Link>
                    </td>
                    <td>
                      <Status value={item.status} />
                    </td>
                    <td>{item.explanation}</td>
                    <td>{item.expiry_state && item.expiry_state !== "VALID" && <strong>{item.expiry_state === "EXPIRED" ? "Expired · " : "Expires soon · "}</strong>}{item.expires_at || "No expiry recorded"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <Panel title="Search persisted registers">
        <div className="advanced-grid">
          <Field label="Register">
            <select
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
                setOffset(0);
              }}
            >
              {[
                "documents",
                "quotations",
                "estimates",
                "payments",
                "audit", "invoices", "purchase-orders", "receipts", "controls", "contracts", "certificates", "amendments", "corrections", "measurements", "materials", "prices", "journals", "cost-codes",
              ].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </Field>
          <Field label="Search register">
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setOffset(0);
              }}
              maxLength={120}
            />
          </Field>
          <Field label="Status filter"><input value={status} placeholder="All statuses" maxLength={40} onChange={e => {setStatus(e.target.value.toUpperCase()); setOffset(0);}} /></Field>
          <Field label="Sort">
            <select value={order} onChange={(e) => setOrder(e.target.value)}>
              <option value="desc">Newest first</option>
              <option value="asc">Oldest first</option>
            </select>
          </Field>
        </div>
        {register.error ? (
          <ErrorState error={register.error} onRetry={() => { void register.refetch(); }} />
        ) : register.isPending ? (
          <Loading />
        ) : (
          <>
            <p role="status">{register.data.total} matching records</p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Record</th>
                    <th>Status</th>
                    <th>Recorded</th>
                  </tr>
                </thead>
                <tbody>
                  {register.data.items.map((r) => (
                    <tr key={r.id}>
                      <td>{r.id}</td>
                      <td className="register-label">{r.label}</td>
                      <td>{r.status}</td>
                      <td>{r.created_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!register.data.items.length && (
              <p>
                No records match these filters. Try another register or search.
              </p>
            )}
            <div className="modal-actions">
              <button
                className="button"
                disabled={!offset}
                onClick={() => setOffset(offset - 25)}
              >
                Previous
              </button>
              <button
                className="button"
                disabled={offset + 25 >= register.data.total}
                onClick={() => setOffset(offset + 25)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </Panel>
    </>
  );
}
