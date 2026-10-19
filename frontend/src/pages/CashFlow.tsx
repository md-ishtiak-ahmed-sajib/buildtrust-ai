import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Banknote, Clock3, Info, ShieldCheck, Wallet } from "lucide-react";
import { api, formatMoney, titleCase } from "../api";
import type { Forecast } from "../types";
import { useWorkspace } from "../App";
import { CashChart, ErrorState, Loading, Metric, PageTitle, Panel, Status } from "../ui";
import { useInvoices, dateTime } from "./shared";

export function CashFlowPage() {
  const { project } = useWorkspace();
  const [delay, setDelay] = useState(15),
    [pressure, setPressure] = useState(10);
  const forecast = useQuery({
    queryKey: ["forecast", project.id, delay, pressure],
    queryFn: () =>
      api<Forecast>(
        `/cashflow/forecast?project_id=${project.id}&delay_days=${delay}&cost_pressure_percent=${pressure}`,
      ),
  });
  return (
    <>
      <PageTitle
        eyebrow="PREPARE FOR WHAT COMES NEXT"
        title="Cash-Flow Forecast"
        description="Understand your liquidity across recorded commitments and alternative assumptions."
      />
      <div className="scenario-controls">
        <label>
          Receivables delay{" "}
          <input
            type="number"
            min={0}
            max={90}
            value={delay}
            onChange={(e) =>
              setDelay(Math.min(90, Math.max(0, Number(e.target.value))))
            }
          />
          <span>days</span>
        </label>
        <label>
          Future cost pressure{" "}
          <input
            type="number"
            min={0}
            max={100}
            value={pressure}
            onChange={(e) =>
              setPressure(Math.min(100, Math.max(0, Number(e.target.value))))
            }
          />
          <span>%</span>
        </label>
        <span className="muted">
          <Info size={15} />
          Scenario assumptions, not market predictions
        </span>
      </div>
      {forecast.isPending ? (
        <Loading />
      ) : forecast.error ? (
        <ErrorState error={forecast.error} onRetry={() => { void forecast.refetch(); }} />
      ) : (
        <>
          <div className="metric-grid">
            <Metric
              label="Recorded cash balance"
              value={`৳ ${formatMoney(forecast.data.recorded_balance)}`}
              detail="Excludes unreceived future receivables"
              icon={<Wallet size={18} />}
              accent
            />
            <Metric
              label="Cash reserved"
              value={`৳ ${formatMoney(forecast.data.reserved)}`}
              detail="Held for pending and approved proposals"
              icon={<Clock3 size={18} />}
            />
            <Metric
              label="Minimum cash reserve"
              value={`৳ ${formatMoney(forecast.data.minimum_reserve)}`}
              detail="Required liquidity buffer"
              icon={<ShieldCheck size={18} />}
            />
            <Metric
              label="Available to evaluate"
              value={`৳ ${formatMoney(forecast.data.available_cash)}`}
              detail="Before additional proposed payments"
              icon={<Banknote size={18} />}
            />
          </div>
          <Panel
            title="30-day liquidity scenarios"
            subtitle="BDT · Daily projected closing cash"
          >
            <CashChart forecast={forecast.data} all />
          </Panel>
          <div className="scenario-grid">
            {forecast.data.scenarios.map((s) => (
              <Panel key={s.name} title={titleCase(s.name)}>
                <div className="scenario-body">
                  <Status
                    value={s.reserve_maintained ? "VERIFIED" : "BLOCKED"}
                  />
                  <small>Lowest projected balance</small>
                  <strong>৳ {formatMoney(s.lowest_balance)}</strong>
                  <p>Greatest pressure on {s.pressure_date}</p>
                  <div className="obligation-list">
                    {s.shortfall_obligations.slice(0, 4).map((o) => (
                      <div key={o.id}>
                        <span>{o.description}</span>
                        <b>৳ {formatMoney(o.amount, true)}</b>
                      </div>
                    ))}
                  </div>
                </div>
              </Panel>
            ))}
          </div>
          <div className="notice">
            <ShieldCheck size={20} />
            <p>
              Payment policy requires the base case and the configured{" "}
              {forecast.data.policy_receivable_delay_days}-day
              delayed-receivables case to preserve the reserve. These preview
              controls do not change approval policy. Cost-pressure shortfalls
              require attention.
            </p>
          </div>
        </>
      )}
    </>
  );
}
