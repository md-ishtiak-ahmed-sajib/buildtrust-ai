import { Children, cloneElement, isValidElement, useId, useState, type ReactNode } from "react";
import { ApiError } from "../api";
import type { components } from "../types/api.generated";
export type Estimate = components["schemas"]["EstimateResponse"];
export type Line = components["schemas"]["EstimateLine"];
export type Component = components["schemas"]["RateComponent"];
export type Search = components["schemas"]["SearchResponse"];
export type Comparison = components["schemas"]["PriceComparison"];
export type Offer = components["schemas"]["PriceFinding"];
type QuoteContract = components["schemas"]["QuotationInput"];
export type QuoteFields = Pick<
  QuoteContract,
  "material_id" | "supplier" | "title"
> &
  Partial<Omit<QuoteContract, "material_id" | "supplier" | "title">>;
export type Material = {
  id: number;
  project_id: number;
  name: string;
  category: string;
  unit: string;
  specification: Record<string, string>;
  version: number;
  active: boolean;
};
export type Quotation = {
  id: number;
  project_id: number;
  material_id: number;
  fields: QuoteFields;
  version: number;
  status: string;
  prepared_by: number;
  contributors?: number[];
  verified_by: number | null;
  filename: string | null;
  attachment_hash: string | null;
  evidence_revisions?: { id: number; version: number; evidence: Record<string, unknown>; snapshot_hash: string; actor_id: number; created_at: string }[];
};
export type Profile = {
  id: number;
  code: string;
  name: string;
  edition: string;
  source_url: string;
  verification_status: string;
  rules: Record<string, unknown>;
};
export const units = [
  "tonne",
  "kg",
  "bag",
  "m3",
  "m2",
  "m",
  "each",
  "thousand",
  "ft3",
  "hour",
  "day",
  "sum",
];
export const currencies = ["BDT", "USD", "EUR", "GBP", "INR", "CNY"] as const;
export const text = (value: unknown) => (value == null ? "—" : String(value));
export function useAction() {
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState<Error>();
  async function run(work: () => Promise<unknown>, success = "Saved") {
    setBusy(true);
    setError(undefined);
    setMessage("");
    try {
      await work();
      setMessage(success);
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Request failed"));
    } finally {
      setBusy(false);
    }
  }
  return {
    busy,
    run,
    feedback: (
      <>
        {error && (
          <div className="notice error" role="alert">
            <div>
              <p>{error.message}</p>
              {error instanceof ApiError && !!error.fields.length && (
                <ul>
                  {error.fields.map((field, index) => (
                    <li key={index}>
                      {field.location.join(" › ")}: {field.message}
                    </li>
                  ))}
                </ul>
              )}
              {error instanceof ApiError && error.requestId && (
                <small>Request reference: {error.requestId}</small>
              )}
            </div>
          </div>
        )}
        {message && (
          <div className="notice success" role="status">
            {message}
          </div>
        )}
      </>
    ),
  };
}
export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  const labelId = useId();
  return (
    <div className="advanced-field">
      <span id={labelId}>{label}</span>
      {Children.map(children, child => {
        if (isValidElement<{ "aria-label"?: string; "aria-labelledby"?: string }>(child)
          && typeof child.type === "string" && ["input", "select", "textarea"].includes(child.type)
          && !child.props["aria-label"] && !child.props["aria-labelledby"])
          return cloneElement(child, { "aria-labelledby": labelId });
        return child;
      })}
    </div>
  );
}
export function Facts({ data }: { data: Record<string, unknown> }) {
  return (
    <dl className="advanced-facts">
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <dt>{key.replaceAll("_", " ")}</dt>
          <dd>
            {typeof value === "object" && value !== null
              ? JSON.stringify(value)
              : text(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}
export function SpecEditor({
  value,
  onChange,
}: {
  value: Record<string, string>;
  onChange: (v: Record<string, string>) => void;
}) {
  const [newKey, setNewKey] = useState("");
  return (
    <div className="spec-editor">
      {Object.entries(value).map(([key, val]) => (
        <div className="advanced-inline" key={key}>
          <Field label={key}>
            <input
              value={val}
              onChange={(e) => onChange({ ...value, [key]: e.target.value })}
            />
          </Field>
          <button
            type="button"
            className="button light"
            aria-label={`Remove ${key}`}
            onClick={() => {
              const next = { ...value };
              delete next[key];
              onChange(next);
            }}
          >
            ×
          </button>
        </div>
      ))}
      <div className="advanced-inline">
        <input
          aria-label="New specification attribute"
          placeholder="Attribute, e.g. grade"
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
        />
        <button
          type="button"
          className="button light"
          disabled={!newKey.trim()}
          onClick={() => {
            onChange({ ...value, [newKey.trim()]: "" });
            setNewKey("");
          }}
        >
          Add attribute
        </button>
      </div>
    </div>
  );
}
/** Exact decimal multiplication for display/search parameters; backend recalculates decisions. */
export function multiplyExact(left: string, right: string): string {
  const parse = (v: string) => {
    if (!/^\d*(?:\.\d*)?$/.test(v) || !v.replaceAll(".", ""))
      return [0n, 0] as const;
    const [whole, fraction = ""] = v.split(".");
    return [BigInt((whole || "0") + fraction), fraction.length] as const;
  };
  const [a, ap] = parse(left),
    [b, bp] = parse(right);
  const places = ap + bp,
    raw = (a * b).toString().padStart(places + 1, "0");
  return places
    ? (raw.slice(0, -places) + "." + raw.slice(-places)).replace(
        /\.?0+$/,
        "",
      ) || "0"
    : raw;
}
