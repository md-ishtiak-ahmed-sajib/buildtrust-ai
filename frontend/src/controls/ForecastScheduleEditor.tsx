type Row = { quantity: string; due_date: string | null };

export function ForecastScheduleEditor({ rows, onChange }: { rows: Row[]; onChange: (rows: Row[]) => void }) {
  return <div>
    <p className="muted">Allocate the entire mapped quantity. Blank dates remain unscheduled.</p>
    {rows.map((row, index) => <div className="advanced-grid" key={index}>
      <label>Quantity {index + 1}<input inputMode="decimal" required value={row.quantity} onChange={e => onChange(rows.map((v,i) => i===index ? {...v,quantity:e.target.value}:v))} /></label>
      <label>Payment date {index + 1}<input type="date" value={row.due_date || ''} onChange={e => onChange(rows.map((v,i) => i===index ? {...v,due_date:e.target.value || null}:v))} /></label>
      <button type="button" className="button" onClick={() => onChange(rows.filter((_,i) => i!==index))}>Remove schedule {index+1}</button>
    </div>)}
    <button type="button" className="button" onClick={() => onChange([...rows,{quantity:'',due_date:null}])}>Add scheduled quantity</button>
  </div>;
}
