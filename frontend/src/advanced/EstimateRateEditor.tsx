import { SearchSelect } from "../controls/SearchSelect";
import { titleCase } from "../api";
import { Field, Facts, multiplyExact, units } from "./shared";
import type { EstimateEditorProps } from "./estimateEditorTypes";
export function EstimateRateEditor({
  draft,
  calc,
  editable,
  dirty,
  expanded,
  setPrice,
  update,
  materials,
  costCodes,
  sheets,
  lineChange,
}: EstimateEditorProps) {
  return (
    <>
      {" "}
      {draft.fields.lines
        ?.filter((l) => l.id === expanded)
        .map((line) => (
          <section className="line-editor" key={line.id}>
            <h3>{line.code} · Measurement & rate analysis</h3>
            <fieldset disabled={!editable}>
              <div className="advanced-grid">
                {(
                  [
                    "section",
                    "code",
                    "description",
                    "quantity",
                    "cost_code",
                    "drawing_reference",
                  ] as const
                ).map((key) => (
                  <Field key={key} label={titleCase(key)}>
                    {key === "cost_code" ? (
                      <SearchSelect
                        label="Cost code"
                        value={line.cost_code || ""}
                        emptyLabel="Unassigned (shown as a mapping gap)"
                        options={(costCodes.data || []).map((code) => ({
                          value: code.code,
                          label: `${code.code} · ${code.name}`,
                        }))}
                        onChange={(value) => lineChange(line.id, key, value)}
                      />
                    ) : (
                      <input
                        value={line[key] || ""}
                        onChange={(e) =>
                          lineChange(line.id, key, e.target.value)
                        }
                      />
                    )}
                  </Field>
                ))}
                <Field label="BOQ unit">
                  <select
                    value={line.unit}
                    onChange={(e) =>
                      lineChange(line.id, "unit", e.target.value)
                    }
                  >
                    {units.map((u) => (
                      <option key={u}>{u}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Item type">
                  <select
                    value={line.kind}
                    onChange={(e) =>
                      lineChange(line.id, "kind", e.target.value)
                    }
                  >
                    {["MEASURED", "PROVISIONAL_SUM", "PRIME_COST"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Planned payment date (uncommitted quantity)">
                  <input
                    type="date"
                    value={line.due_date || ""}
                    onChange={(e) =>
                      lineChange(line.id, "due_date", e.target.value || null)
                    }
                  />
                </Field>
                <Field label="Measured quantity source">
                  <select
                    value={line.takeoff_sheet_id || ""}
                    onChange={(e) => {
                      const sheet = sheets.data?.find(
                        (s) => s.id === Number(e.target.value),
                      );
                      update((est) => {
                        const target = est.fields.lines!.find(
                          (l) => l.id === line.id,
                        )!;
                        target.takeoff_sheet_id = sheet?.id || null;
                        if (sheet) {
                          target.quantity = sheet.result.quantity;
                          target.unit = sheet.result.unit;
                        }
                      });
                    }}
                  >
                    <option value="">Manual / documented quantity</option>
                    {sheets.data?.map((s) => (
                      <option key={s.id} value={s.id}>
                        #{s.id} {s.fields.name} · {s.result.quantity}{" "}
                        {s.result.unit} · {s.status}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
              <Field label="Item notes">
                <textarea
                  value={line.notes || ""}
                  onChange={(e) => lineChange(line.id, "notes", e.target.value)}
                />
              </Field>
            </fieldset>
            <h4>Unit-rate components</h4>
            <p className="muted">
              Consumption is per one BOQ work unit. Material wastage applies
              here once. Markups follow the saved build-up policy.
            </p>
            {line.components?.map((c) => (
              <div className="rate-component" key={c.id}>
                <fieldset disabled={!editable}>
                  <div className="advanced-grid">
                    <Field label="Cost category">
                      <select
                        value={c.category}
                        onChange={(e) =>
                          update((est) => {
                            Object.assign(
                              est.fields
                                .lines!.find((l) => l.id === line.id)!
                                .components!.find((v) => v.id === c.id)!,
                              { category: e.target.value },
                            );
                          })
                        }
                      >
                        {[
                          "MATERIAL",
                          "LABOUR",
                          "EQUIPMENT",
                          "SUBCONTRACT",
                          "TRANSPORT",
                          "OTHER",
                        ].map((v) => (
                          <option key={v}>{v}</option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Description">
                      <input
                        value={c.description}
                        onChange={(e) =>
                          update((est) => {
                            est.fields
                              .lines!.find((l) => l.id === line.id)!
                              .components!.find(
                                (v) => v.id === c.id,
                              )!.description = e.target.value;
                          })
                        }
                      />
                    </Field>
                    <Field label="Linked material">
                      <SearchSelect
                        label="Linked material"
                        value={c.material_id || ""}
                        onChange={(identity) =>
                          update((est) => {
                            const comp = est.fields
                              .lines!.find((l) => l.id === line.id)!
                              .components!.find((v) => v.id === c.id)!;
                            const mat = materials.data?.find(
                              (m) => m.id === Number(identity),
                            );
                            comp.material_id = mat?.id || null;
                            comp.selection_id = null;
                            if (mat) {
                              comp.unit = mat.unit;
                              comp.description = mat.name;
                            }
                          })
                        }
                        emptyLabel="Manual component rate"
                        options={(materials.data || []).map((m) => ({
                          value: m.id,
                          label: `${m.name} / ${m.unit}`,
                        }))}
                      />
                    </Field>
                    {(
                      ["consumption", "unit_price", "wastage_percent"] as const
                    ).map((key) => (
                      <Field label={titleCase(key)} key={key}>
                        <input
                          value={c[key] || "0"}
                          onChange={(e) =>
                            update((est) => {
                              const comp = est.fields
                                .lines!.find((l) => l.id === line.id)!
                                .components!.find((v) => v.id === c.id)!;
                              comp[key] = e.target.value;
                              if (key === "unit_price")
                                comp.selection_id = null;
                            })
                          }
                        />
                      </Field>
                    ))}
                    <Field label="Component unit">
                      <select
                        value={c.unit}
                        onChange={(e) =>
                          update((est) => {
                            const comp = est.fields
                              .lines!.find((l) => l.id === line.id)!
                              .components!.find((v) => v.id === c.id)!;
                            comp.unit = e.target.value;
                            comp.selection_id = null;
                          })
                        }
                      >
                        {units.map((u) => (
                          <option key={u}>{u}</option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Manual source / assumptions">
                      <input
                        value={c.source_note || ""}
                        onChange={(e) =>
                          update((est) => {
                            est.fields
                              .lines!.find((l) => l.id === line.id)!
                              .components!.find(
                                (v) => v.id === c.id,
                              )!.source_note = e.target.value;
                          })
                        }
                      />
                    </Field>
                  </div>
                </fieldset>
                <div className="advanced-inline">
                  {c.selection_id && (
                    <span className="status good">
                      Evidence selection #{c.selection_id}
                    </span>
                  )}
                  {c.material_id && (
                    <button
                      className="button primary"
                      disabled={dirty}
                      onClick={() => {
                        const mat = materials.data?.find(
                          (m) => m.id === c.material_id,
                        );
                        if (mat)
                          setPrice({
                            material: mat,
                            lineId: line.id,
                            componentId: c.id,
                            quantity: multiplyExact(
                              line.quantity || "0",
                              c.consumption || "1",
                            ),
                          });
                      }}
                    >
                      Compare source prices
                    </button>
                  )}
                  {editable && (line.components?.length || 0) > 1 && (
                    <button
                      className="button light"
                      onClick={() =>
                        update((est) => {
                          const target = est.fields.lines!.find(
                            (l) => l.id === line.id,
                          )!;
                          target.components = target.components?.filter(
                            (v) => v.id !== c.id,
                          );
                        })
                      }
                    >
                      Remove component
                    </button>
                  )}
                </div>
              </div>
            ))}
            {editable && (
              <button
                className="button light"
                onClick={() =>
                  update((est) => {
                    est.fields
                      .lines!.find((l) => l.id === line.id)!
                      .components!.push({
                        id: crypto.randomUUID(),
                        category: "LABOUR",
                        description: "Labour",
                        consumption: "1",
                        unit: "hour",
                        unit_price: "0",
                        wastage_percent: "0",
                        source_note: "",
                      });
                  })
                }
              >
                Add cost component
              </button>
            )}
            <details>
              <summary>Authoritative saved rate calculation</summary>
              <Facts
                data={
                  (calc?.lines.find(
                    (r) => r.id === line.id,
                  ) as unknown as Record<string, unknown>) || {}
                }
              />
            </details>
          </section>
        ))}
    </>
  );
}
