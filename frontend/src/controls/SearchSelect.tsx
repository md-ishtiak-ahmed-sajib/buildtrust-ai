import { useState } from "react";

type Option = { value: string | number; label: string };
export function SearchSelect({ label, value, options, onChange, emptyLabel }: {
  label: string; value: string | number; options: Option[];
  onChange: (value: string) => void; emptyLabel?: string;
}) {
  const [query, setQuery] = useState("");
  const filtered = options.filter(option => String(option.value) === String(value) || option.label.toLowerCase().includes(query.trim().toLowerCase()));
  return <div className="search-select">
    <input type="search" aria-label={`Filter ${label.replace(/^(Select|Linked) /i, "").toLowerCase()} options`} placeholder="Type to filter options" value={query} onChange={event => setQuery(event.target.value)} />
    <select aria-label={label} value={value} onChange={event => onChange(event.target.value)}>
      {emptyLabel && <option value="">{emptyLabel}</option>}
      {filtered.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
      {!filtered.length && <option disabled value="">No matching recorded options</option>}
    </select>
  </div>;
}
