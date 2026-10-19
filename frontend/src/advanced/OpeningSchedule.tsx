import { Field } from "./shared";
export type Opening = { width: string; height: string; count: string; reference: string };
export function OpeningSchedule({ rows, onChange }: { rows: Opening[]; onChange: (rows: Opening[]) => void }) {
  return <fieldset><legend>Individual opening measurements</legend>
    <p>Use the selected dimension unit. Counts cover the entire sheet; sheet count is not applied again. Keep aggregate opening area and manual deduction at zero.</p>
    {rows.map((row, index) => <div key={index} className="advanced-grid">
      {(["width", "height", "count", "reference"] as const).map(key => <Field key={key} label={`Opening ${key} ${index + 1}`}>
        <input required value={row[key]} onChange={event => onChange(rows.map((r, i) => i === index ? { ...r, [key]: event.target.value } : r))} />
      </Field>)}
      <button className="button" type="button" onClick={() => onChange(rows.filter((_, i) => i !== index))}>Remove opening {index + 1}</button>
    </div>)}
    <button className="button" type="button" disabled={rows.length >= 200} onClick={() => onChange([...rows, { width: "1", height: "1", count: "1", reference: "" }])}>Add opening</button>
  </fieldset>;
}
