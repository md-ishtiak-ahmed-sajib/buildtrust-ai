import { formatMoney, titleCase } from "../api";
export type ForecastPart = {
  line_id: string;
  component_id?: string | null;
  scope?: string | null;
  amount: string;
  cost_amount?: string | null;
  tax?: string | null;
  retention?: string | null;
  advance_recovery?: string | null;
  due_date: string | null;
  contract_link_id?: number | null;
};
export function ForecastBreakdown({ rows }: { rows: ForecastPart[] }) {
  if (!rows.length) return null;
  return (
    <div className="table-scroll">
      <table>
        <caption>
          Estimated cash requirements and distinct cost allocations
        </caption>
        <thead>
          <tr>
            {[
              "Scope",
              "Date",
              "Project cost",
              "Tax",
              "Retention withheld",
              "Advance recovery",
              "Cash requirement",
              "Review source",
            ].map((v) => (
              <th key={v}>{v}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              <td>
                {row.line_id}
                {row.component_id ? ` · ${row.component_id}` : ""} ·{" "}
                {titleCase(row.scope || "Estimate")}
              </td>
              <td>{row.due_date || "Unscheduled"}</td>
              {(
                [
                  "cost_amount",
                  "tax",
                  "retention",
                  "advance_recovery",
                  "amount",
                ] as const
              ).map((key) => (
                <td key={key}>
                  {row[key] == null
                    ? "Insufficient data"
                    : formatMoney(row[key]!)}
                </td>
              ))}
              <td>
                {row.contract_link_id
                  ? `Approved mapping #${row.contract_link_id}`
                  : "Estimate assumptions"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
