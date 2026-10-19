import { Panel, CashChart } from "../ui";

import { ForecastBreakdown, type ForecastPart } from "./ForecastBreakdown";

import { formatMoney } from "../api";

import type { Forecast } from "../types";

export type EstimatePreview = {
  recorded_cash: string;
  unscheduled_estimated_cost: string;
  notice: string;
  estimated_overlay?: ForecastPart[];
  unscheduled_commitments?: Record<string, string | number>[];
  warnings: string[];
  base: Forecast;
  scenarios: Forecast["scenarios"];
};

export function EstimateForecastPanel({
  forecast,
}: {
  forecast: EstimatePreview;
}) {
  return (
    <Panel
      title="Estimate cash-flow impact"

      subtitle="The overlay schedules uncommitted work only. It does not change recorded cash or payment policy."
    >
      <div className="advanced-metrics">
        <div>
          <small>Recorded cash</small>

          <strong>{formatMoney(forecast.recorded_cash)}</strong>
        </div>

        <div>
          <small>Base minimum, 30 days</small>

          <strong>
            {formatMoney(forecast.base.scenarios[0].lowest_balance)}
          </strong>
        </div>

        <div>
          <small>With scheduled estimate</small>

          <strong>{formatMoney(forecast.scenarios[0].lowest_balance)}</strong>
        </div>

        <div>
          <small>Unscheduled estimated costs</small>

          <strong>{formatMoney(forecast.unscheduled_estimated_cost)}</strong>
        </div>
      </div>

      <CashChart
        forecast={{
          ...forecast.base,

          scenarios: forecast.scenarios,
        }}
      />

      {!!forecast.unscheduled_commitments?.length && (
        <details>
          <summary>Unscheduled commitments and held retention</summary>
          <ul>
            {forecast.unscheduled_commitments.map((v, i) => (
              <li key={i}>
                {v.source_type} #{v.source_id}: {formatMoney(String(v.amount))}{" "}
                · payment date required
              </li>
            ))}
          </ul>
        </details>
      )}

      <ForecastBreakdown rows={forecast.estimated_overlay || []} />

      {forecast.warnings.map((w) => (
        <div className="notice" key={w}>
          {w}
        </div>
      ))}

      <p className="muted">{forecast.notice}</p>
    </Panel>
  );
}
