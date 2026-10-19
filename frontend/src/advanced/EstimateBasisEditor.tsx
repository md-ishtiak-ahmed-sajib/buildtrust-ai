import { Field, type Estimate } from "./shared";
import { titleCase } from "../api";
export function EstimateBasisEditor({
  draft,
  editable,
  update,
  policy,
}: {
  draft: Estimate;
  editable: boolean;
  update: (work: (e: Estimate) => void) => void;
  policy?: string;
}) {
  return (
    <details className="basis-editor" open>
      <summary>Basis of Estimate & build-up policy</summary>
      <fieldset disabled={!editable}>
        <Field label="Basis of Estimate">
          <textarea
            value={draft.fields.basis || ""}
            onChange={(e) =>
              update((v) => {
                v.fields.basis = e.target.value;
              })
            }
          />
        </Field>
        <div className="advanced-grid">
          {(["inclusions", "exclusions", "uncertainty"] as const).map((key) => (
            <Field label={titleCase(key)} key={key}>
              <textarea
                value={draft.fields[key] || ""}
                onChange={(e) =>
                  update((v) => {
                    v.fields[key] = e.target.value;
                  })
                }
              />
            </Field>
          ))}
          {(
            [
              "site_overhead_percent",
              "general_overhead_percent",
              "profit_percent",
              "tax_percent",
              "contingency_percent",
            ] as const
          ).map((key) => (
            <Field label={titleCase(key)} key={key}>
              <input
                value={draft.fields[key] || "0"}
                onChange={(e) =>
                  update((v) => {
                    v.fields[key] = e.target.value;
                  })
                }
              />
            </Field>
          ))}
          <Field label="Tax treatment">
            <select
              value={draft.fields.tax_treatment || "UNKNOWN"}
              onChange={(e) =>
                update((v) => {
                  v.fields.tax_treatment = e.target
                    .value as typeof v.fields.tax_treatment;
                })
              }
            >
              <option value="UNKNOWN">
                Unknown: cost budget unavailable if tax applies
              </option>
              <option value="NONRECOVERABLE_COST">
                Nonrecoverable project cost
              </option>
              <option value="RECOVERABLE">Recoverable tax</option>
              <option value="OUTPUT">Output tax on selling value</option>
            </select>
          </Field>
        </div>
      </fieldset>
      <p className="muted">{policy}</p>
    </details>
  );
}
