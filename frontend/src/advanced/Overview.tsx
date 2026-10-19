import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useWorkspace } from "../App";
import { api, formatMoney } from "../api";
import { Panel, Status } from "../ui";
export function EstimateOverview() {
  const { project } = useWorkspace();
  const { data } = useQuery({
    queryKey: ["estimate-overview", project.id],
    queryFn: () =>
      api<{
        estimate_id: number | null;
        estimate_status: string;
        current_estimate: string;
        approved_estimate_budget: string | null;
        forecast_vs_budget: string;
        budget_overrun: boolean;
      }>(`/finance/cost-control?project_id=${project.id}`),
  });
  if (!data?.estimate_id) return null;
  return (
    <Panel
      title="Estimate & budget outlook"
      subtitle="Current persisted estimate; procurement and payment permissions remain separate."
      action={
        <Link className="text-link" to="/estimates">
          Review BOQ & sources →
        </Link>
      }
    >
      <div className="advanced-metrics">
        <div>
          <small>Current estimate · {project.currency}</small>
          <strong>{formatMoney(data.current_estimate)}</strong>
        </div>
        <div>
          <small>Approved estimate baseline</small>
          <strong>
            {data.approved_estimate_budget
              ? formatMoney(data.approved_estimate_budget)
              : "Awaiting approval"}
          </strong>
        </div>
        <div>
          <small>Estimate against budget</small>
          <strong className={data.budget_overrun ? "negative" : ""}>
            {formatMoney(data.forecast_vs_budget)}
          </strong>
        </div>
        <div>
          <small>Version status</small>
          <Status value={data.estimate_status} />
        </div>
      </div>
    </Panel>
  );
}
