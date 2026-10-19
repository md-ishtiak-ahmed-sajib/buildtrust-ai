import { Field } from "../advanced/shared";
type Rule = { calculation: string; threshold_m2: string; comparison: string; multiply_selected_faces: boolean };
export function OpeningRulesEditor({ rows, onChange }: { rows: Rule[]; onChange: (rows: Rule[]) => void }) {
  return <div>
    <p>Record only the threshold and comparison supported by the cited edition and reviewed clause. Each calculation may have one rule. Opening counts cover the complete sheet.</p>
    {rows.map((row, index) => <fieldset className="advanced-grid" key={index}><legend>Opening rule {index + 1}</legend>
      <Field label={`Rule calculation ${index + 1}`}><select value={row.calculation} onChange={event => onChange(rows.map((r, i) => i === index ? { ...r, calculation: event.target.value } : r))}>
        {["MASONRY", "FINISHES", "AREA", "DOORS_WINDOWS", "FORMWORK_SLAB"].map(value => <option key={value}>{value}</option>)}
      </select></Field>
      <Field label={`Sourced opening threshold m² ${index + 1}`}><input required value={row.threshold_m2} onChange={event => onChange(rows.map((r, i) => i === index ? { ...r, threshold_m2: event.target.value } : r))} /></Field>
      <Field label={`Threshold comparison ${index + 1}`}><select value={row.comparison} onChange={event => onChange(rows.map((r, i) => i === index ? { ...r, comparison: event.target.value } : r))}>
        <option value="GT">Deduct strictly above threshold</option><option value="GE">Deduct at or above threshold</option>
      </select></Field>
      <Field label={`Multiply selected finish faces ${index + 1}`}><input type="checkbox" checked={row.multiply_selected_faces} disabled={row.calculation !== "FINISHES"} onChange={event => onChange(rows.map((r, i) => i === index ? { ...r, multiply_selected_faces: event.target.checked } : r))} /></Field>
      <button type="button" className="button" onClick={() => onChange(rows.filter((_, i) => i !== index))}>Remove rule {index + 1}</button>
    </fieldset>)}
    <button type="button" className="button" disabled={rows.length >= 5} onClick={() => onChange([...rows, { calculation: "MASONRY", threshold_m2: "0", comparison: "GT", multiply_selected_faces: false }])}>Add sourced opening rule</button>
  </div>;
}
