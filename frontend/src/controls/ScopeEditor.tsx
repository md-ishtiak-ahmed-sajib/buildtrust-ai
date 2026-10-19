import { Field } from "../advanced/shared";

type Row = Record<string, string | number | null>;
type Option = { id: number; label: string };
export function ScopeEditor({ certificate, rows, onChange, codes, boq }: {
  certificate: boolean; rows: Row[]; onChange: (rows: Row[]) => void;
  codes: Option[]; boq: Option[];
}) {
  const fields = certificate ? ["item_code", "cumulative_quantity"] : ["code", "description", "quantity", "unit", "rate", "cost_code_id", "boq_item_id"];
  return <div className="scope-editor">
    {rows.map((row, index) => <fieldset key={index} className="advanced-grid">
      <legend>Scope line {index + 1}</legend>
      {fields.map(key => <Field key={key} label={`${key.replaceAll("_", " ")} · row ${index + 1}`}>
        {key.endsWith("_id") ? <select required={key === "cost_code_id"} value={String(row[key] || "")}
          onChange={event => onChange(rows.map((r, i) => i === index ? { ...r, [key]: event.target.value ? Number(event.target.value) : null } : r))}>
          <option value="">{key === "boq_item_id" ? "Optional approved procurement BOQ" : "Select cost code"}</option>
          {(key === "cost_code_id" ? codes : boq).map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
        </select> : <input required aria-label={`${key} row ${index + 1}`} value={String(row[key] ?? "")}
          onChange={event => onChange(rows.map((r, i) => i === index ? { ...r, [key]: event.target.value } : r))} />}
      </Field>)}
      <button className="button" type="button" disabled={rows.length < 2} onClick={() => onChange(rows.filter((_, i) => i !== index))}>Remove line {index + 1}</button>
    </fieldset>)}
    <button className="button" type="button" onClick={() => onChange([...rows, certificate ? { item_code: "", cumulative_quantity: "0" } : { code: "", description: "", quantity: "1", unit: "m3", rate: "0", cost_code_id: "", boq_item_id: null }])}>Add scope line</button>
  </div>;
}
