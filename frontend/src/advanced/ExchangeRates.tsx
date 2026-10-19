import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useWorkspace } from "../App";
import { api, post } from "../api";
import { Panel, ErrorState } from "../ui";
import { Field, useAction, currencies } from "./shared";

export function ExchangeRates() {
  const { project, user } = useWorkspace(),
    action = useAction(),
    client = useQueryClient();
  const [base, setBase] = useState("USD"),
    [factor, setFactor] = useState(""),
    [source, setSource] = useState(""),
    [observedDate, setObservedDate] = useState(
      new Intl.DateTimeFormat("en-CA", {
        timeZone: "Asia/Dhaka",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }).format(new Date()),
    );
  const rates = useQuery({
    queryKey: ["exchange-rates", project.id],
    queryFn: () =>
      api<
        {
          id: number;
          base: string;
          quote: string;
          factor: string;
          source: string;
          date: string;
        }[]
      >(`/prices/exchange-rates?project_id=${project.id}`),
  });
  const allowed = ["ADMIN", "FINANCE_MANAGER"].includes(user.role);
  const reload = async () => {
    await client.invalidateQueries({ queryKey: ["exchange-rates"] });
    await client.invalidateQueries({ queryKey: ["material-prices"] });
  };
  return (
    <Panel
      title="Recorded exchange rates"
      subtitle="Estimate conversions preserve the observation date and source. Payment currency controls stay unchanged."
    >
      {allowed && (
        <form
          className="advanced-form"
          onSubmit={(e) => {
            e.preventDefault();
            void action.run(async () => {
              await post("/prices/exchange-rates", {
                project_id: project.id,
                base,
                quote: project.currency,
                factor,
                source,
                observed_date: observedDate,
              });
              await reload();
            }, "Sourced exchange rate recorded");
          }}
        >
          <div className="advanced-grid">
            <Field label="Source currency">
              <select value={base} onChange={(e) => setBase(e.target.value)}>
                {currencies
                  .filter((c) => c !== project.currency)
                  .map((c) => (
                    <option key={c}>{c}</option>
                  ))}
              </select>
            </Field>
            <Field label={`${project.currency} per source currency unit`}>
              <input
                required
                value={factor}
                onChange={(e) => setFactor(e.target.value)}
              />
            </Field>
            <Field label="Observation date">
              <input
                required
                type="date"
                value={observedDate}
                onChange={(e) => setObservedDate(e.target.value)}
              />
            </Field>
            <Field label="Rate source / reference">
              <input
                required
                minLength={5}
                value={source}
                onChange={(e) => setSource(e.target.value)}
              />
            </Field>
          </div>
          <div className="advanced-inline">
            <button className="button primary" disabled={action.busy}>
              Save sourced manual rate
            </button>
            <button
              type="button"
              className="button light"
              disabled={action.busy}
              onClick={() =>
                void action.run(async () => {
                  await post("/prices/exchange-rates/fetch", {
                    project_id: project.id,
                    base,
                    quote: project.currency,
                  });
                  await reload();
                }, "Frankfurter rate retrieved and recorded")
              }
            >
              Fetch available Frankfurter rate
            </button>
          </div>
          {action.feedback}
        </form>
      )}
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Pair</th>
              <th>Factor</th>
              <th>Rate date</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {rates.data?.map((r) => (
              <tr key={r.id}>
                <td>
                  {r.base} → {r.quote}
                </td>
                <td>{r.factor}</td>
                <td>{r.date}</td>
                <td>{r.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rates.error && <ErrorState error={rates.error} onRetry={() => { void rates.refetch(); }} />}
    </Panel>
  );
}
