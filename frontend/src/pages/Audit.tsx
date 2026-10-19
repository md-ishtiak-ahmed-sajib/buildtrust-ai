import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Fingerprint, RefreshCw, ShieldCheck } from "lucide-react";
import { api, post, titleCase } from "../api";
import type { AuditEvent, Integrity } from "../types";
import { useWorkspace } from "../App";
import { ConfirmButton, ErrorState, Loading, Modal, PageTitle, Panel } from "../ui";
import { useInvoices, dateTime } from "./shared";

export function AuditPage() {
  const { user, project, refresh } = useWorkspace();
  const [integrity, setIntegrity] = useState<Integrity | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [selected, setSelected] = useState<AuditEvent | null>(null);
  const events = useQuery({
    queryKey: ["audit", project.id],
    queryFn: () => api<AuditEvent[]>(`/audit/events?project_id=${project.id}`),
  });
  return (
    <>
      <PageTitle
        eyebrow="EVERY ACTION HAS A RECORD"
        title="Audit & Security"
        description="Inspect financial actions and verify the integrity of the persisted audit chain."
        action={
          <button
            className="button primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                setIntegrity(await api<Integrity>("/audit/verify"));
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <Fingerprint size={17} />
            {busy ? "Verifying…" : "Verify audit chain"}
          </button>
        }
      />
      {error && <ErrorState message={error} />}
      <div className="security-overview">
        <div>
          <span className="security-icon">
            <ShieldCheck size={24} />
          </span>
          <div>
            <strong>Deterministic financial controls</strong>
            <p>
              Permissions, approval limits, and separation of duties enforced by
              the backend.
            </p>
          </div>
        </div>
        <div>
          <span className="security-icon">
            <Fingerprint size={24} />
          </span>
          <div>
            <strong>SHA-256 audit chain</strong>
            <p>
              Tamper evidence within a local database. No independent external
              anchoring.
            </p>
          </div>
        </div>
      </div>
      {integrity && (
        <div className={`notice ${integrity.valid ? "success" : "error"}`}>
          <ShieldCheck size={22} />
          <div>
            <strong>
              {integrity.valid
                ? "Chain verified"
                : `Integrity failure at event #${integrity.failed_event_id}`}
            </strong>
            <p>
              {integrity.checked_events} events checked. {integrity.limitation}
            </p>
            <code className="small-hash">{integrity.head_hash}</code>
          </div>
        </div>
      )}
      <Panel
        title="Financial audit trail"
        subtitle="Event timestamps stored in UTC · Displayed in Dhaka time"
      >
        {events.isPending ? (
          <Loading />
        ) : events.error ? (
          <ErrorState error={events.error} onRetry={() => { void events.refetch(); }} />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Time / event</th>
                  <th>Actor</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {events.data.map((e) => (
                  <tr key={e.id}>
                    <td>
                      <strong>{dateTime(e.created_at)}</strong>
                      <small>Event #{e.id}</small>
                    </td>
                    <td>
                      {e.actor_name}
                      <small>{titleCase(e.role)}</small>
                    </td>
                    <td>
                      <span className="audit-action">
                        {titleCase(e.event_type)}
                      </span>
                    </td>
                    <td>
                      {e.entity_type} #{e.entity_id}
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={`View audit event ${e.id}`}
                        onClick={() => setSelected(e)}
                      >
                        <ArrowUpRight size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      {project.active && user.role === "ADMIN" && (
        <div className="reset-row">
          <div>
            <strong>Start a fresh demonstration</strong>
            <p>
              Archives the current run and seeds new fictional records. Audit
              history is preserved.
            </p>
          </div>
          <ConfirmButton
            title="Reset demonstration"
            description="Archive this run and create new fictional project records? Prior audit events and settled payment evidence remain available."
            className="button danger-outline"
            onConfirm={async () => {
              await post("/demo/reset");
              await refresh();
            }}
          >
            <RefreshCw size={15} />
            Reset demo
          </ConfirmButton>
        </div>
      )}
      {selected && (
        <Modal
          title={`Audit event #${selected.id}`}
          onClose={() => setSelected(null)}
        >
          <dl className="detail-list">
            <div>
              <dt>Actor</dt>
              <dd>{selected.actor_name}</dd>
            </div>
            <div>
              <dt>Action</dt>
              <dd>{titleCase(selected.event_type)}</dd>
            </div>
            <div>
              <dt>Timestamp (UTC)</dt>
              <dd>{selected.created_at}</dd>
            </div>
          </dl>
          <label className="hash-label">
            Previous event hash<code>{selected.previous_hash}</code>
          </label>
          <label className="hash-label">
            Current event hash<code>{selected.event_hash}</code>
          </label>
          <pre className="json-preview">
            {JSON.stringify(selected.details, null, 2)}
          </pre>
        </Modal>
      )}
    </>
  );
}
