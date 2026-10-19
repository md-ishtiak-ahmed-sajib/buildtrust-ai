import { useState } from "react";
import { api } from "../api";
import { Modal } from "../ui";
import { Field, SpecEditor, useAction, units, type Material } from "./shared";

export function MaterialEditor({
  initial,
  projectId,
  onClose,
  onSaved,
}: {
  initial?: Material;
  projectId: number;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const action = useAction(),
    [name, setName] = useState(initial?.name || ""),
    [category, setCategory] = useState(initial?.category || "Materials"),
    [unit, setUnit] = useState(initial?.unit || "tonne"),
    [spec, setSpec] = useState(
      initial?.specification || { grade: "", standard: "" },
    );
  return (
    <Modal
      title={initial ? "Edit material specification" : "Add project material"}
      onClose={onClose}
    >
      <form
        className="advanced-form"
        onSubmit={(e) => {
          e.preventDefault();
          void action.run(async () => {
            await api(initial ? `/materials/${initial.id}` : "/materials", {
              method: initial ? "PATCH" : "POST",
              body: JSON.stringify({
                project_id: projectId,
                name,
                category,
                unit,
                specification: spec,
                expected_version: initial?.version,
              }),
            });
            await onSaved();
          });
        }}
      >
        <Field label="Material name">
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <div className="advanced-grid">
          <Field label="Category">
            <input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            />
          </Field>
          <Field label="Canonical unit">
            <select
              disabled={!!initial}
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
            >
              {units.map((u) => (
                <option key={u}>{u}</option>
              ))}
            </select>
          </Field>
        </div>
        <h3>Project technical requirements</h3>
        <SpecEditor value={spec} onChange={setSpec} />
        <p className="muted">
          Unspecified requirements remain unverified. Name similarity cannot
          establish engineering equivalence.
        </p>
        {action.feedback}
        <button className="button primary" disabled={action.busy}>
          Save material
        </button>
      </form>
    </Modal>
  );
}
