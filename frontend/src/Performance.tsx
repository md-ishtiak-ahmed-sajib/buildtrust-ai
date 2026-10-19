import { ForecastBreakdown, type ForecastPart } from './advanced/ForecastBreakdown';
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useWorkspace } from "./App";
import { api, post, formatMoney, titleCase } from "./api";
import { PageTitle, Panel, CashChart, ErrorState, Loading } from "./ui";
import { Field, Facts, useAction } from "./advanced/shared";
import type { Forecast } from "./types";
type Report = {
  recorded_cash: string;
  incurred_cost: string | null;
  recognized_revenue: string | null;
  project_margin_percent: string | null;
  project_profit: string | null;
  working_capital: string | null;
  current_ratio: string | null;
  budget_utilization_percent: string | null;
  accounting_completeness: string;
  evm: Record<string, unknown>;
  ap_aging: Record<string, string>;
  ar_aging: Record<string, string>;
  reporting_currency: Record<string, unknown>;
  forecast_snapshot: Record<string, unknown> | null;
};
type Projection = Forecast & {
  horizon_days: number;
  estimated_overlay: ForecastPart[];
  warnings: string[];
  unscheduled_commitments: Record<string,unknown>[];
  unscheduled_obligations: Record<string, unknown>[];
  notice: string;
};
export function PerformancePage() {
  const { project } = useWorkspace(),
    action = useAction();
  const [horizon, setHorizon] = useState("90"),
    [scenario, setScenario] = useState("BASE"),
    [estimateId, setEstimateId] = useState(""),
    [contractLinks, setContractLinks] = useState(true),
    [currency, setCurrency] = useState(project.currency),
    [end, setEnd] = useState(""),
    [percent, setPercent] = useState("10"),
    [question, setQuestion] = useState(
      "Explain cost performance and project margin",
    ),
    [answer, setAnswer] = useState<{ answer: string; sources: unknown[] }>();
  const report = useQuery({
    queryKey: ["performance", project.id, currency],
    queryFn: () =>
      api<Report>(
        `/finance/performance?project_id=${project.id}&reporting_currency=${currency}`,
      ),
  });
  const estimates = useQuery({
    queryKey: ["estimates", project.id],
    queryFn: () =>
      api<{ id: number; name: string }[]>(
        `/estimates?project_id=${project.id}`,
      ),
  });
  const forecast = useQuery({
    queryKey: [
      "extended-forecast",
      project.id,
      horizon,
      scenario,
      estimateId,
      contractLinks,
      end,
      percent,
    ],
    queryFn: () =>
      api<Projection>(
        `/finance/extended-forecast?project_id=${project.id}&horizon=${horizon === "PROJECT" ? "30&use_project_schedule=true" : horizon}&scenario=${scenario}${estimateId ? `&estimate_id=${estimateId}` : ""}${end ? `&project_end=${end}` : ""}&material_percent=${encodeURIComponent(percent)}&use_contract_links=${contractLinks}`,
      ),
  });
  return (
    <>
      <PageTitle
        eyebrow="SOURCED COST PERFORMANCE"
        title="Performance & Scenarios"
        description="Recognized costs and independently checked progress drive performance. Scenarios do not move cash or authorize payments."
      />
      <Panel title="Accounting and project measures">
        <Field label="Reporting currency">
          <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
          >
            {[
              ...new Set([project.currency, "BDT", "USD", "EUR", "GBP", "INR"]),
            ].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </Field>
        {report.error ? (
          <ErrorState error={report.error} onRetry={() => { void report.refetch(); }} />
        ) : report.data ? (
          <>
            <div className="advanced-facts">
              {(
                [
                  "recorded_cash",
                  "incurred_cost",
                  "recognized_revenue",
                  "project_profit",
                  "project_margin_percent",
                  "working_capital",
                  "current_ratio",
                  "budget_utilization_percent",
                ] as const
              ).map((key) => (
                <div key={key}>
                  <span>{titleCase(key)}</span>
                  <strong>
                    {report.data[key] === null
                      ? "Insufficient data"
                      : report.data[key]}
                  </strong>
                </div>
              ))}
            </div>
            <p className="muted">{report.data.accounting_completeness}</p>
            <Facts data={report.data.reporting_currency} />
            <h3>Earned value management</h3>
            <Facts data={report.data.evm} />
            <h3>Approved forecast margin snapshot</h3>
            {report.data.forecast_snapshot ? <Facts data={report.data.forecast_snapshot} /> : <p>Insufficient data. Independently approve a financial forecast with complete customer contract scope and a sourced cost method.</p>}
            <h3>AR aging</h3>
            <Facts data={report.data.ar_aging} />
            <h3>AP aging</h3>
            <Facts data={report.data.ap_aging} />
          </>
        ) : (
          <Loading />
        )}
        <Link to="/controls">
          Prepare reviewed baselines, progress and recognition evidence
        </Link>
      </Panel>
      <Panel title="Dated forecast and scenarios">
        <div className="advanced-grid">
          <Field label="Forecast horizon">
            <select
              value={horizon}
              onChange={(e) => setHorizon(e.target.value)}
            >
              {[7, 30, 90].map((d) => (
                <option value={d} key={d}>
                  {d} days
                </option>
              ))}
              <option value="PROJECT">Approved project duration</option>
            </select>
          </Field>
          <Field label="Custom scenario end (optional)">
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </Field>
          <Field label="Scenario">
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
            >
              {[
                "BASE",
                "SUPPLIER_ACCELERATION",
                "PROJECT_DELAY",
                "MATERIAL_ESCALATION",
                "COMBINED",
              ].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
          <Field label="Uncommitted estimate overlay">
            <select
              value={estimateId}
              onChange={(e) => setEstimateId(e.target.value)}
            >
              <option value="">Recorded obligations only</option>
              {estimates.data?.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Material escalation percent">
            <input
              inputMode="decimal"
              value={percent}
              onChange={(e) => setPercent(e.target.value)}
            />
          </Field>
          <label><input type="checkbox" checked={contractLinks} onChange={e => setContractLinks(e.target.checked)} /> Apply independently reviewed contract mappings</label>
        </div>
        {forecast.error ? (
          <ErrorState error={forecast.error} onRetry={() => { void forecast.refetch(); }} />
        ) : forecast.data ? (
          <>
            <p>{forecast.data.notice}</p>
            {forecast.data.warnings.map((w) => (
              <p key={w} className="notice">
                {w}
              </p>
            ))}
            <CashChart forecast={forecast.data} all />
            <ForecastBreakdown rows={forecast.data.estimated_overlay || []} />
            <h3>Unscheduled contractual commitments and retention</h3>
            {forecast.data.unscheduled_commitments?.map((row,i)=><Facts data={row} key={i} />)}
            <h3>Unscheduled costs and receipts</h3>
            {forecast.data.unscheduled_obligations.length ? (
              forecast.data.unscheduled_obligations.map((row, i) => (
                <Facts data={row} key={i} />
              ))
            ) : (
              <p>No unscheduled obligations in the recorded scope.</p>
            )}
          </>
        ) : (
          <Loading />
        )}
      </Panel>
      <Panel title="Deterministic finance copilot">
        <form
          className="advanced-form"
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(
              async () =>
                setAnswer(
                  await post("/advanced/ask", {
                    project_id: project.id,
                    question,
                  }),
                ),
              "Evidence retrieved",
            );
          }}
        >
          <Field label="Finance question">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
          </Field>
          <button className="button" disabled={action.busy}>
            Explain recorded evidence
          </button>
          {action.feedback}
          {answer && (
            <div className="copilot-answer" role="status">
              <p>{answer.answer}</p>
              <details>
                <summary>Source references</summary>
                <pre>{JSON.stringify(answer.sources, null, 2)}</pre>
              </details>
            </div>
          )}
        </form>
      </Panel>
    </>
  );
}
