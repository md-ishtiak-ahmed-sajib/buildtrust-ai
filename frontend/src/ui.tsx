import { useState, useEffect, useRef, type ReactNode, lazy, Suspense } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  LoaderCircle,
  X,
  ChevronRight,
} from "lucide-react";
import { Link } from "react-router-dom";
import { ApiError, formatMoney, titleCase } from "./api";
import type { Invoice, Forecast } from "./types";


export function Status({ value }: { value: string }) {
  const good = [
    "VERIFIED",
    "APPROVED",
    "SETTLED",
    "CONFIRMED",
    "COMPLETED",
    "EXTRACTED",
  ].includes(value);
  const bad = ["BLOCKED", "BLOCK", "FAILED", "DUPLICATE", "REJECTED"].includes(
    value,
  );
  return (
    <span className={`status ${good ? "good" : bad ? "bad" : "pending"}`}>
      <span />
      {titleCase(value)}
    </span>
  );
}
export function Loading() {
  return (
    <div className="state">
      <LoaderCircle className="spin" size={22} />
      Loading financial records…
    </div>
  );
}
export function ErrorState({ message, error, onRetry }: { message?: string; error?: Error; onRetry?: () => void }) {
  return (
    <div className="notice error" role="alert">
      <AlertCircle size={18} />
      <div><p>{error?.message || message || 'Unable to load this record.'}</p>
      {error instanceof ApiError && !!error.fields.length && <ul>{error.fields.map((field,index)=><li key={index}>{field.location.join(' / ')}: {field.message}</li>)}</ul>}
      {error instanceof ApiError && error.retryAfter && <p>Try again after {error.retryAfter} seconds.</p>}
      {error instanceof ApiError && error.requestId && <small>Request reference: {error.requestId}</small>}
      {onRetry && <button className="button light" type="button" onClick={onRetry}>Retry loading</button>}</div>
    </div>
  );
}
export function Empty({ children }: { children: ReactNode }) {
  return <div className="state">{children}</div>;
}
export function PageTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Panel({
  title,
  subtitle,
  action,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="panel-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function Metric({
  label,
  value,
  detail,
  icon,
  accent = false,
}: {
  label: string;
  value: string;
  detail: string;
  icon: ReactNode;
  accent?: boolean;
}) {
  return (
    <div className={`metric ${accent ? "accent" : ""}`}>
      <div className="metric-top">
        <span>{label}</span>
        <span className="metric-icon">{icon}</span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
    </div>
  );
}
export function InvoiceTable({
  invoices,
  limit,
}: {
  invoices: Invoice[];
  limit?: number;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Invoice / supplier</th>
            <th>Amount</th>
            <th>Status</th>
            <th aria-label="Open invoice" />
          </tr>
        </thead>
        <tbody>
          {invoices.slice(0, limit).map((i) => (
            <tr key={i.id}>
              <td>
                <Link className="strong" to={`/invoices?invoice=${i.id}`}>
                  {i.invoice_number}
                </Link>
                <small>{i.supplier}</small>
              </td>
              <td className="numeric">৳ {formatMoney(i.grand_total)}</td>
              <td>
                <Status value={i.status} />
              </td>
              <td>
                <Link
                  className="icon-button"
                  aria-label={`Review ${i.invoice_number}`}
                  to={`/invoices?invoice=${i.id}`}
                >
                  <ArrowUpRight size={17} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!invoices.length && (
        <Empty>
          No invoices in this project. Upload a supplier invoice to begin.
        </Empty>
      )}
    </div>
  );
}
const LazyCashChart = lazy(() => import("./CashChart"));
export function CashChart(props: { forecast: Forecast; all?: boolean }) {
  return <Suspense fallback={<Loading />}><LazyCashChart {...props} /></Suspense>;
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialogRef.current
      ?.querySelector<HTMLElement>(
        'button,input,select,textarea,[tabindex="0"]',
      )
      ?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      previous?.focus();
    };
  }, []);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        ref={dialogRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
          if (e.key === "Tab") {
            const nodes = [
              ...(dialogRef.current?.querySelectorAll<HTMLElement>(
                'button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]',
              ) || []),
            ];
            const first = nodes[0],
              last = nodes.at(-1);
            if (e.shiftKey && document.activeElement === first) {
              e.preventDefault();
              last?.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
              e.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <div className="panel-head">
          <h2>{title}</h2>
          <button
            autoFocus
            className="icon-button"
            aria-label="Close dialog"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
export function ConfirmButton({
  children,
  title,
  description,
  onConfirm,
  disabled = false,
  className = "button primary",
}: {
  children: ReactNode;
  title: string;
  description: string;
  onConfirm: () => Promise<unknown>;
  disabled?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <>
      <button
        className={className}
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        {children}
      </button>
      {open && (
        <Modal title={title} onClose={() => !busy && setOpen(false)}>
          <p className="modal-description">{description}</p>
          {error && <ErrorState message={error} />}
          <div className="modal-actions">
            <button
              className="button"
              disabled={busy}
              onClick={() => setOpen(false)}
            >
              Cancel
            </button>
            <button
              className="button primary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  await onConfirm();
                  setOpen(false);
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <ChevronRight size={16} />
              )}
              Confirm
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
