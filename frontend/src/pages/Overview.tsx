import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ArrowUpRight, CheckCheck, CircleDollarSign, FileCheck2, Info, Plus, ShieldCheck, ShieldX, Sparkles, Wallet } from "lucide-react";
import { api, formatMoney, titleCase } from "../api";
import type { Summary } from "../types";
import { useWorkspace } from "../App";
import { EstimateOverview } from "../advanced/Overview";
import { CashChart, ErrorState, InvoiceTable, Loading, Metric, PageTitle, Panel } from "../ui";
import { useInvoices, dateTime } from "./shared";

export function OverviewPage() {
  const { project } = useWorkspace();
  const { data, error, isPending } = useQuery({
    queryKey: ["summary", project.id],
    queryFn: () => api<Summary>(`/dashboard/summary?project_id=${project.id}`),
  });
  if (isPending) return <Loading />;
  if (error) return <ErrorState message={error.message} />;
  return (
    <>
      <PageTitle
        eyebrow="YOUR PROJECT, AT A GLANCE"
        title="Financial overview"
        description="Know what’s available, what’s owed, and what needs your attention."
        action={
          <Link className="button primary" to="/documents">
            <Plus size={17} />
            Upload document
          </Link>
        }
      />
      <div className="metric-grid">
        <Metric
          label="Available liquidity"
          value={`৳ ${formatMoney(data.available_cash)}`}
          detail="Recorded cash less active reservations"
          icon={<Wallet size={18} />}
          accent
        />
        <Metric
          label="Pending supplier payables"
          value={`৳ ${formatMoney(data.outstanding_obligations)}`}
          detail={`${data.awaiting_approval} awaiting approval · ${data.approved_payments} approved`}
          icon={<ArrowUpRight size={18} />}
        />
        <Metric
          label="Invoices at risk"
          value={String(data.blocked_invoices).padStart(2, "0")}
          detail="Held by financial verification controls"
          icon={<ShieldX size={18} />}
        />
        <Metric
          label="Simulated payments"
          value={`৳ ${formatMoney(data.total_paid)}`}
          detail={`${data.settled_payments} settled transaction${data.settled_payments !== 1 ? "s" : ""}`}
          icon={<CircleDollarSign size={18} />}
        />
      </div>
      <EstimateOverview />
      <div className="dashboard-grid">
        <Panel
          title="Cash-flow outlook"
          subtitle="Your next 30 days, based on recorded commitments"
          action={
            <Link className="text-link" to="/cashflow">
              Explore scenarios <ArrowUpRight size={14} />
            </Link>
          }
        >
          <div className="chart-summary">
            <div>
              <small>Projected closing balance</small>
              <strong>
                ৳ {formatMoney(data.cashflow.scenarios[0].days.at(-1)!.closing)}
              </strong>
            </div>
            <span className="chart-legend">
              <span />
              Base-case projection
            </span>
          </div>
          <CashChart forecast={data.cashflow} />
          <div className="chart-note">
            <Info size={14} />
            Reserve threshold: BDT {formatMoney(
              data.cashflow.minimum_reserve,
            )}{" "}
            · Scheduled inflows are assumptions
          </div>
        </Panel>
        <section className="attention-panel">
          <div className="attention-icon">
            <ShieldCheck size={24} />
          </div>
          <span className="eyebrow">FINANCIAL GUARDRAILS</span>
          <h2>
            Review with evidence.
            <br />
            Pay with confidence.
          </h2>
          <p>
            {data.blocked_invoices} invoice
            {data.blocked_invoices !== 1 ? "s" : ""} held for review. Compare
            every claim against scope, orders, and accepted delivery.
          </p>
          <Link className="button light" to="/invoices">
            Review invoices <ArrowRight size={17} />
          </Link>
          <div className="attention-footer">
            <CheckCheck size={17} />
            Human approval always required
          </div>
        </section>
      </div>
      <div className="dashboard-bottom">
        <Panel
          title="Invoice review queue"
          subtitle="Prioritize discrepancies before they become payments"
          action={
            <Link className="text-link" to="/invoices">
              View all <ArrowRight size={14} />
            </Link>
          }
        >
          <InvoiceTable invoices={data.invoices} limit={5} />
        </Panel>
        <Panel
          title="Recent agent activity"
          subtitle="A clear record of what happened"
        >
          <div className="activity-list">
            {data.activity.slice(0, 5).map((a, i) => (
              <div className="activity" key={a.id}>
                <span className={`activity-icon ${i === 0 ? "teal" : ""}`}>
                  <FileCheck2 size={15} />
                </span>
                <div>
                  <strong>{titleCase(a.type)}</strong>
                  <small>{a.actor}</small>
                </div>
                <time>{dateTime(a.created_at)}</time>
              </div>
            ))}
          </div>
          <Link className="panel-bottom-link" to="/audit">
            Open audit trail <ArrowRight size={15} />
          </Link>
        </Panel>
      </div>
      <div className="workflow-strip">
        <span>
          <Sparkles size={18} />A connected financial workflow
        </span>
        {[
          "Document intake",
          "Four-way verification",
          "Liquidity assessment",
          "Human approval",
          "Sandbox settlement",
        ].map((s, i) => (
          <span key={s}>
            <b>{String(i + 1).padStart(2, "0")}</b>
            {s}
            {i < 4 && <ArrowRight size={13} />}
          </span>
        ))}
      </div>
    </>
  );
}
