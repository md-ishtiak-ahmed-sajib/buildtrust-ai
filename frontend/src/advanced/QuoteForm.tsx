import { useState } from "react";
import { api, titleCase } from "../api";
import { Field, SpecEditor, useAction, units, currencies, text, type Material, type QuoteFields, type Quotation } from "./shared";

export function QuoteForm({
  material,
  existing,
  onSaved,
}: {
  material: Material;
  existing?: Quotation;
  onSaved: () => void;
}) {
  const action = useAction();
  const [value, setValue] = useState<QuoteFields>(
    existing?.fields || {
      material_id: material.id,
      supplier: "",
      title: material.name,
      currency: "BDT",
      unit: material.unit,
      quoted_quantity: "1",
      specification: material.specification,
      city: "Dhaka",
      country: "BD",
      freight_basis: "UNKNOWN",
      tax_basis: "UNKNOWN",
      source_type: "SUPPLIER_QUOTE",
    },
  );
  const change = (key: keyof QuoteFields, v: unknown) =>
    setValue((old) => ({ ...old, [key]: v }));
  return (
    <form
      className="advanced-form"
      onSubmit={(e) => {
        e.preventDefault();
        void action.run(async () => {
          await api(existing ? `/quotations/${existing.id}` : "/quotations", {
            method: existing ? "PATCH" : "POST",
            body: JSON.stringify({
              ...value,
              expected_version: existing?.version,
            }),
          });
          onSaved();
        }, "Quotation saved for independent review");
      }}
    >
      <div className="notice">
        Uploading or entering a quotation does not verify it. Explicit unknown
        charges remain unknown.
      </div>
      <div className="advanced-grid">
        {(
          [
            ["supplier", "Supplier"],
            ["number", "Quotation number"],
            ["title", "Product title"],
            ["price", "Unit price"],
            ["quoted_quantity", "Quoted order quantity"],
            ["minimum_quantity", "Minimum quantity"],
            ["city", "Delivery city"],
            ["country", "Country code"],
            ["delivery_days", "Delivery days"],
            ["package_weight_kg", "Package weight (kg)"],
            ["source_url", "Source HTTPS URL"],
            ["density_kg_m3", "Material bulk density (kg/m³), if converting"],
            ["density_assumption", "Density / moisture source assumption"],
          ] as const
        ).map(([key, label]) => (
          <Field key={key} label={label}>
            <input
              required={["supplier", "title"].includes(key)}
              value={text(value[key]) === "—" ? "" : text(value[key])}
              onChange={(e) =>
                change(
                  key,
                  key === "delivery_days"
                    ? e.target.value
                      ? Number(e.target.value)
                      : null
                    : e.target.value || null,
                )
              }
            />
          </Field>
        ))}
        <Field label="Unit">
          <select
            value={value.unit || material.unit}
            onChange={(e) => change("unit", e.target.value)}
          >
            {units.map((u) => (
              <option key={u}>{u}</option>
            ))}
          </select>
        </Field>
        <Field label="Currency">
          <select
            value={value.currency || "BDT"}
            onChange={(e) => change("currency", e.target.value)}
          >
            {currencies.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </Field>
        <Field label="Source category">
          <select
            value={value.source_type}
            onChange={(e) => change("source_type", e.target.value)}
          >
            <option value="SUPPLIER_QUOTE">Supplier quotation</option>
            <option value="OFFICIAL_REFERENCE">
              Official schedule reference
            </option>
          </select>
        </Field>
        <Field label="Delivery confirmed">
          <select
            value={value.can_deliver == null ? "" : String(value.can_deliver)}
            onChange={(e) =>
              change(
                "can_deliver",
                e.target.value === "" ? null : e.target.value === "true",
              )
            }
          >
            <option value="">Unknown</option>
            <option value="true">Yes, evidence reviewed</option>
            <option value="false">No</option>
          </select>
        </Field>
        <Field label="Quotation date">
          <input
            type="date"
            value={value.quotation_date || ""}
            onChange={(e) => change("quotation_date", e.target.value || null)}
          />
        </Field>
        <Field label="Valid until">
          <input
            type="date"
            value={value.valid_until || ""}
            onChange={(e) => change("valid_until", e.target.value || null)}
          />
        </Field>
      </div>
      <h3>Technical specification</h3>
      <SpecEditor
        value={value.specification || {}}
        onChange={(v) => change("specification", v)}
      />
      <h3>Charges for the quoted order</h3>
      <div className="advanced-grid">
        {(["freight", "tax"] as const).map((key) => (
          <div key={key}>
            <Field label={`${titleCase(key)} basis`}>
              <select
                value={value[`${key}_basis`] || "UNKNOWN"}
                onChange={(e) => change(`${key}_basis`, e.target.value)}
              >
                <option value="UNKNOWN">Unknown</option>
                <option value="INCLUDED">Included in product price</option>
                <option value="EXCLUDED">Additional charge</option>
              </select>
            </Field>
            <Field label={`${titleCase(key)} amount (blank = unknown)`}>
              <input
                inputMode="decimal"
                value={value[key] || ""}
                onChange={(e) => change(key, e.target.value || null)}
              />
            </Field>
          </div>
        ))}
        {(["handling", "other_cost"] as const).map((key) => (
          <Field
            key={key}
            label={`${titleCase(key)} (enter 0 if confirmed zero)`}
          >
            <input
              inputMode="decimal"
              value={value[key] || ""}
              onChange={(e) => change(key, e.target.value || null)}
            />
          </Field>
        ))}
        <Field label="Tax treatment">
          <select
            value={String(value.tax_recoverable || false)}
            onChange={(e) =>
              change("tax_recoverable", e.target.value === "true")
            }
          >
            <option value="false">Nonrecoverable</option>
            <option value="true">Recoverable; amount recorded</option>
          </select>
        </Field>
      </div>
      {value.source_type === "OFFICIAL_REFERENCE" && (
        <>
          <h3>Official schedule metadata</h3>
          <div className="advanced-grid">
            {(["edition", "chapter", "item_code", "locality"] as const).map(
              (key) => (
                <Field label={titleCase(key)} key={key}>
                  <input
                    value={value[key] || ""}
                    onChange={(e) => change(key, e.target.value)}
                  />
                </Field>
              ),
            )}
            <Field label="Effective date">
              <input
                type="date"
                value={value.effective_date || ""}
                onChange={(e) =>
                  change("effective_date", e.target.value || null)
                }
              />
            </Field>
            <Field label="Rate category">
              <select
                value={value.rate_category || "MATERIAL"}
                onChange={(e) => change("rate_category", e.target.value)}
              >
                <option value="MATERIAL">Material only</option>
                <option value="WORK_ITEM">Work item</option>
                <option value="COMPOSITE">Composite work rate</option>
              </select>
            </Field>
          </div>
        </>
      )}
      <Field label="Evidence and assumptions">
        <textarea
          value={value.notes || ""}
          onChange={(e) => change("notes", e.target.value)}
        />
      </Field>
      {action.feedback}
      <button className="button primary" disabled={action.busy}>
        Save quotation draft
      </button>
    </form>
  );
}
