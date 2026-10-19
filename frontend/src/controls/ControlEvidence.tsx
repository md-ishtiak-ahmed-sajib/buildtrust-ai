import { titleCase } from "../api";
import type { components } from "../types/api.generated";
type Control = components["schemas"]["ControlResponse"];

const hidden = (key: string) => key.endsWith("_minor") || key.endsWith("_hash") || key.endsWith("_json") ||
  ["kind", "policy", "source", "sources", "acceptances", "contributors", "estimate_hash", "snapshot_hash", "estimate_line_id"].includes(key);
const controlReferences = new Set(["contract_id", "policy_id", "baseline_id", "rfq_id", "selected_bid_id", "recommendation_id", "advance_assignment_id"]);

function Details({ data, names, depth = 0 }: { data: unknown; names: Map<number, string>; depth?: number }) {
  if (data == null || data === "") return <span>Not recorded</span>;
  if (typeof data === "boolean") return <span>{data ? "Confirmed" : "Not confirmed"}</span>;
  if (Array.isArray(data)) return data.length ? <ol className="evidence-items">{data.map((item, index) => <li key={index}><Details data={item} names={names} depth={depth + 1} /></li>)}</ol> : <span>None recorded</span>;
  if (typeof data !== "object") return <span>{String(data)}</span>;
  if (depth > 5) return <span>See full audit fields for this supporting detail.</span>;
  return <dl className="advanced-facts">{Object.entries(data).filter(([key, value]) => !hidden(key) && value != null && value !== "").map(([key, value]) => (
    <div key={key}><dt>{titleCase(key.replace(/_id$/, " reference").replace(/_ids$/, " references"))}</dt>
      <dd>{key.endsWith("_id") && typeof value === "number" ? (controlReferences.has(key) && names.get(value) || `${titleCase(key.slice(0, -3))} #${value}`) : <Details data={value} names={names} depth={depth + 1} />}</dd>
    </div>
  ))}</dl>;
}

export function ControlEvidence({ record, records }: { record: Control; records: Control[] }) {
  const names = new Map(records.map(row => [row.id, row.name]));
  // Human amounts remain decimal strings. Integer storage values and internal
  // fingerprints are retained separately for audit inspection.
  const business = { ...record.payload, ...record.calculated } as Record<string, unknown>;
  for (const [key, label] of [["tax_minor", "tax"], ["retention_minor", "held_retention"],
    ["advance_minor", "advance_recovered"], ["incorporated_minor", "previously_recognized_materials"]]) {
    const value = record.calculated[key];
    if (typeof value === "number" && Number.isSafeInteger(value)) {
      const amount = BigInt(value);
      business[label] = `${amount / 100n}.${String(amount % 100n).padStart(2, "0")}`;
    }
  }
  return <>
    <Details data={business} names={names} />
    <p className="muted">{record.snapshot_hash ? "Evidence is bound to the submitted review snapshot." : "Draft evidence has not yet been submitted for independent review."}</p>
    <details><summary>Full audit fields and fingerprint</summary>
      <pre className="audit-fields">{JSON.stringify({ payload: record.payload, calculated: record.calculated, snapshot_hash: record.snapshot_hash }, null, 2)}</pre>
    </details>
  </>;
}
