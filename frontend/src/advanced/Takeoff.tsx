import { useEffect, useState, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, Save } from "lucide-react";
import { useWorkspace } from "../App";
import { api, post } from "../api";
import { PageTitle, Panel, Status, ErrorState } from "../ui";
import type { components } from "../types/api.generated";
import { Field, Facts, useAction, type Profile } from "./shared";
import { OpeningSchedule, type Opening } from "./OpeningSchedule";
type Calculation = NonNullable<
  components["schemas"]["TakeoffInput"]["calculation"]
>;
type Result = {
  quantity: string;
  unit: string;
  gross_quantity: string;
  formula: string;
  warnings: string[];
  profile_applied_rules?: Record<string, unknown>[];
};
type Sheet = {
  id: number;
  version: number;
  status: string;
  prepared_by: number;
  checked_by: number | null;
  fields: components["schemas"]["TakeoffInput"];
  result: Result;
  created_at: string;
};
const formulas: Record<
  Calculation,
  { label: string; dimensions: Record<string, string> }
> = {
  RECTANGULAR_VOLUME: {
    label: "Concrete / rectangular volume",
    dimensions: { length: "0.4", width: "0.4", height: "3", count: "20" },
  },
  CIRCULAR_VOLUME: {
    label: "Circular column volume",
    dimensions: { diameter: "0.4", height: "3", count: "20" },
  },
  REBAR: {
    label: "Reinforcement mass",
    dimensions: { diameter_mm: "16", length: "12", count: "10" },
  },
  FORMWORK_COLUMN: {
    label: "Column formwork — four sides",
    dimensions: { length: "0.4", width: "0.4", height: "3", count: "20" },
  },
  FORMWORK_FOOTING: {
    label: "Footing formwork — four sides",
    dimensions: { length: "2", width: "2", height: "0.5", count: "1" },
  },
  FORMWORK_BEAM: {
    label: "Beam formwork — sides and soffit",
    dimensions: { length: "5", width: "0.3", height: "0.6", count: "1" },
  },
  FORMWORK_SLAB: {
    label: "Slab soffit formwork",
    dimensions: { length: "5", width: "4", count: "1" },
  },
  AREA: {
    label: "Generic area / finishes",
    dimensions: { length: "5", width: "4", count: "1" },
  },
  LENGTH: {
    label: "Generic length / pipes / cables",
    dimensions: { length: "12", count: "1" },
  },
  COUNT: { label: "Generic item count", dimensions: { count: "1" } },
  EARTHWORK: {
    label: "Earthworks / supplied top and bottom extents",
    dimensions: {
      top_length: "6",
      top_width: "5",
      bottom_length: "4",
      bottom_width: "3",
      depth: "2",
      count: "1",
    },
  },
  BACKFILL: {
    label: "Backfill / explicit compaction volume factor",
    dimensions: {
      excavated_volume: "20",
      excluded_volume: "5",
      volume_factor: "1",
      count: "1",
    },
  },
  DISPOSAL: {
    label: "Disposal / explicit bulking factor",
    dimensions: {
      excavated_volume: "20",
      excluded_volume: "5",
      volume_factor: "1.2",
      count: "1",
    },
  },
  COMPACTION: { label: "Compaction / supplied volume factor", dimensions: { loose_volume: "20", compaction_factor: "0.9", count: "1" } },
  MASONRY: {
    label: "Masonry / explicit openings",
    dimensions: {
      length: "10",
      height: "3",
      thickness: "0.2",
      opening_area: "6",
      count: "1",
    },
  },
  FINISHES: {
    label: "Finishes / selected faces",
    dimensions: {
      length: "10",
      height: "3",
      opening_area: "6",
      faces: "2",
      count: "1",
    },
  },
  DOORS_WINDOWS: {
    label: "Doors and windows / measured area",
    dimensions: { length: "1.2", height: "1.5", count: "4" },
  },
  ROOFING: {
    label: "Roofing / explicit slope factor",
    dimensions: { length: "10", width: "8", slope_factor: "1.1", count: "1" },
  },
  PAVEMENT: {
    label: "Pavement volume",
    dimensions: { length: "10", width: "8", height: "0.15", count: "1" },
  },
  TRIANGULAR_PRISM: {
    label: "Triangular prism concrete",
    dimensions: { length: "4", width: "3", height: "2", count: "1" },
  },
  FRUSTUM: {
    label: "Frustum concrete",
    dimensions: {
      top_length: "2",
      top_width: "2",
      bottom_length: "4",
      bottom_width: "4",
      height: "1.5",
      count: "1",
    },
  },
  ANNULAR_VOLUME: {
    label: "Annular concrete volume",
    dimensions: {
      outer_diameter: "2",
      inner_diameter: "1",
      height: "3",
      count: "1",
    },
  },
  REBAR_SCHEDULE: {
    label: "Supplied reinforcement schedule",
    dimensions: { count: "1" },
  },
};
export function TakeoffPage() {
  const { project, user } = useWorkspace(),
    client = useQueryClient(),
    action = useAction();
  const profiles = useQuery({
    queryKey: ["measurement-profiles", project.id],
    queryFn: () => api<Profile[]>(`/measurement/profiles?project_id=${project.id}`),
  });
  const sheets = useQuery({
    queryKey: ["takeoff-sheets", project.id],
    queryFn: () => api<Sheet[]>(`/takeoff/sheets?project_id=${project.id}`),
  });
  const [kind, setKind] = useState<Calculation>("RECTANGULAR_VOLUME"),
    [dims, setDims] = useState<Record<string, string>>({
      ...formulas.RECTANGULAR_VOLUME.dimensions,
    }),
    [name, setName] = useState("Column quantity sheet"),
    [profileId, setProfileId] = useState(0),
    [dimensionUnit, setDimensionUnit] = useState("m"),
    [deduction, setDeduction] = useState("0"),
    [deductionReason, setDeductionReason] = useState(""),
    [assumptions, setAssumptions] = useState(""),
    [drawing, setDrawing] = useState(""),
    [revision, setRevision] = useState("1"),
    [element, setElement] = useState(""),
    [location, setLocation] = useState(""),
    [massMethod, setMassMethod] = useState("APPROXIMATION"),
    [massSource, setMassSource] = useState(""),
    [result, setResult] = useState<Result>();
  const [schedule, setSchedule] = useState("12,10,1.58");
  const [openings, setOpenings] = useState<Opening[]>([]);
  useEffect(() => { setProfileId(0); setOpenings([]); setResult(undefined); }, [project.id]);
  useEffect(() => {
    if (profiles.data && !profileId)
      setProfileId(
        profiles.data.find((p) => p.code === "NRM2")?.id ||
          profiles.data[0]?.id ||
          0,
      );
  }, [profiles.data, profileId]);
  useEffect(() => {
    setResult(undefined);
  }, [
    project.id,
    kind,
    dims,
    name,
    profileId,
    dimensionUnit,
    deduction,
    deductionReason,
    assumptions,
    drawing,
    revision,
    element,
    location,
    massMethod,
    massSource,
    schedule,
    openings,
  ]);
  const selected = profiles.data?.find((p) => p.id === profileId);
  const payload = () => ({
    project_id: project.id,
    profile_id: profileId,
    name,
    calculation: kind,
    dimensions: dims,
    dimension_unit: dimensionUnit,
    deduction,
    deduction_reason: deductionReason,
    assumptions,
    drawing_reference: drawing,
    revision,
    element,
    location,
    openings,
    mass_method: massMethod,
    nominal_mass_source: massSource,
    reinforcement_schedule:
      kind === "REBAR_SCHEDULE"
        ? schedule
            .trim()
            .split("\n")
            .map((row) => {
              const [length, count, unit_mass_kg_m] = row
                .split(",")
                .map((value) => value.trim());
              return { length, count, unit_mass_kg_m };
            })
        : [],
  });
  const currentInput = JSON.stringify(payload());
  const latestInput = useRef(currentInput);
  latestInput.current = currentInput;
  return (
    <>
      <PageTitle
        eyebrow="MEASUREMENT WORKSPACE"
        title="Quantity Takeoff"
        description="Dimension-aware calculations with recorded drawings, assumptions, measurement profiles and independent checking."
      />
      {action.feedback}
      <div className="takeoff-layout">
        <Panel title="Measurement sheet">
          <form
            className="advanced-form"
            onSubmit={(e) => {
              e.preventDefault();
              void action.run(async () => {
                const inputs = payload();
                const response = await post<Result>(
                  "/takeoff/calculate",
                  inputs,
                );
                // Fields remain editable while the request runs. Do not publish
                // a result against newer input values (handled by the input key).
                if (latestInput.current === JSON.stringify(inputs))
                  setResult(response);
              }, "Calculation complete");
            }}
          >
            <Field label="Sheet name">
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
            <div className="advanced-grid">
              <Field label="Calculation">
                <select
                  value={kind}
                  onChange={(e) => {
                    const value = e.target.value as Calculation;
                    setKind(value);
                    setDims({ ...formulas[value].dimensions });
                    setOpenings([]);
                    setResult(undefined);
                  }}
                >
                  {Object.entries(formulas).map(([key, v]) => (
                    <option key={key} value={key}>
                      {v.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Measurement profile">
                <select
                  value={profileId}
                  onChange={(e) => { setProfileId(Number(e.target.value)); setOpenings([]); }}
                >
                  {profiles.data
                    ?.filter((p) => p.code !== "ICMS3")
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} · {p.edition}
                      </option>
                    ))}
                </select>
              </Field>
              <Field label="Length dimension unit">
                <select
                  value={dimensionUnit}
                  onChange={(e) => setDimensionUnit(e.target.value)}
                >
                  {["m", "mm", "cm", "ft"].map((u) => (
                    <option key={u}>{u}</option>
                  ))}
                </select>
              </Field>
              {Object.entries(dims).map(([key, value]) => (
                <Field
                  label={
                    key === "diameter_mm"
                      ? "Bar diameter (mm)"
                      : key === "count"
                        ? "Count (whole number)"
                        : key.replaceAll("_", " ")
                  }
                  key={key}
                >
                  <input
                    required
                    inputMode="decimal"
                    value={value}
                    onChange={(e) =>
                      setDims((old) => ({ ...old, [key]: e.target.value }))
                    }
                  />
                </Field>
              ))}
            </div>
            {kind === "REBAR_SCHEDULE" && (
              <>
                <Field label="Supplied reinforcement rows (length, count, kg per metre)">
                  <textarea
                    value={schedule}
                    onChange={(e) => setSchedule(e.target.value)}
                  />
                </Field>
                <Field label="Nominal mass source">
                  <input
                    required
                    value={massSource}
                    onChange={(e) => setMassSource(e.target.value)}
                  />
                </Field>
              </>
            )}
            {kind === "REBAR" && (
              <>
                <Field label="Mass method">
                  <select
                    value={massMethod}
                    onChange={(e) => {
                      const method = e.target.value;
                      setMassMethod(method);
                      setDims((old) => {
                        const next = {
                          diameter_mm: old.diameter_mm || "16",
                          length: old.length || "12",
                          count: old.count || "10",
                        } as Record<string, string>;
                        if (method === "SPECIFIED")
                          next.unit_mass_kg_m = "1.58";
                        if (method === "DENSITY") next.density_kg_m3 = "7850";
                        return next;
                      });
                    }}
                  >
                    <option value="APPROXIMATION">D²/162 approximation</option>
                    <option value="SPECIFIED">
                      Specified nominal mass table
                    </option>
                    <option value="DENSITY">Explicit steel density</option>
                  </select>
                </Field>
                {massMethod === "SPECIFIED" && (
                  <Field label="Nominal mass source">
                    <input
                      required
                      value={massSource}
                      onChange={(e) => setMassSource(e.target.value)}
                    />
                  </Field>
                )}
              </>
            )}
            <div className="advanced-grid">
              <Field label="Drawing reference">
                <input
                  value={drawing}
                  onChange={(e) => setDrawing(e.target.value)}
                />
              </Field>
              <Field label="Drawing revision">
                <input
                  value={revision}
                  onChange={(e) => setRevision(e.target.value)}
                />
              </Field>
              <Field label="Element">
                <input
                  value={element}
                  onChange={(e) => setElement(e.target.value)}
                />
              </Field>
              <Field label="Location">
                <input
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
              </Field>
              <Field label="Explicit deduction (result units)">
                <input
                  value={deduction}
                  onChange={(e) => setDeduction(e.target.value)}
                />
              </Field>
              <Field label="Deduction reason">
                <input
                  value={deductionReason}
                  onChange={(e) => setDeductionReason(e.target.value)}
                />
              </Field>
            </div>
            <Field label="Design inputs and measurement assumptions">
              <textarea
                value={assumptions}
                onChange={(e) => setAssumptions(e.target.value)}
              />
            </Field>
            {Array.isArray(selected?.rules.opening_rules) && selected.rules.opening_rules.some(rule => rule.calculation === kind) &&
              <OpeningSchedule rows={openings} onChange={setOpenings} />}
            <div className="advanced-inline">
              <button className="button primary" disabled={action.busy}>
                <Calculator size={16} /> Calculate quantity
              </button>
              {project.active && user.role !== "AUDITOR" && (
                <button
                  type="button"
                  className="button light"
                  disabled={action.busy}
                  onClick={() =>
                    void action.run(async () => {
                      const saved = await post<{ result: Result }>(
                        "/takeoff/sheets",
                        payload(),
                      );
                      setResult(saved.result);
                      await client.invalidateQueries({
                        queryKey: ["takeoff-sheets"],
                      });
                    }, "Measurement saved for independent checking")
                  }
                >
                  <Save size={16} /> Save measurement sheet
                </button>
              )}
            </div>
          </form>
        </Panel>
        <div>
          <Panel title="Calculation result">
            {result ? (
              <>
                <div className="takeoff-answer">
                  <small>Net measured quantity</small>
                  <strong>
                    {result.quantity} <span>{result.unit}</span>
                  </strong>
                  <p>{result.formula}</p>
                </div>
                <Facts
                  data={{
                    gross_quantity: result.gross_quantity,
                    profile: selected?.name,
                    drawing_reference: drawing,
                    revision,
                  }}
                />
                {result.warnings.map((w) => (
                  <div className="notice" key={w}>
                    {w}
                  </div>
                ))}
                {!!result.profile_applied_rules?.length && <details><summary>Applied opening-rule decisions</summary>
                  {result.profile_applied_rules.map((rule, index) => <Facts key={index} data={rule} />)}
                </details>}
              </>
            ) : (
              <div className="state">
                Enter dimensions and calculate to see the formula and result.
              </div>
            )}
          </Panel>
          <Panel title="Profile integrity">
            <p>
              {selected?.name} · {selected?.edition}
            </p>
            <div className="notice">
              {selected?.verification_status.replaceAll("_", " ").toLowerCase()}
              . Geometry templates do not establish full compliance with the
              selected standard.
            </div>
            {selected && (
              <>
                <Facts data={selected.rules} />
                {selected.source_url && (
                  <a
                    href={selected.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    View standard reference
                  </a>
                )}
              </>
            )}
          </Panel>
        </div>
      </div>
      <Panel
        title="Saved measurement register"
        subtitle="Checked sheets can supply quantities to estimate BOQ lines."
      >
        {sheets.error && <ErrorState error={sheets.error} onRetry={() => { void sheets.refetch(); }} />}
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Sheet / drawing</th>
                <th>Quantity</th>
                <th>Calculation</th>
                <th>Status</th>
                <th>Check</th>
              </tr>
            </thead>
            <tbody>
              {sheets.data?.map((s) => (
                <tr key={s.id}>
                  <td>
                    <strong>
                      #{s.id} {s.fields.name}
                    </strong>
                    <br />
                    {s.fields.drawing_reference} · rev {s.fields.revision}
                  </td>
                  <td>
                    {s.result.quantity} {s.result.unit}
                  </td>
                  <td>
                    <details>
                      <summary>{s.result.formula}</summary>
                      <Facts
                        data={s.fields as unknown as Record<string, unknown>}
                      />
                    </details>
                  </td>
                  <td>
                    <Status value={s.status} />
                  </td>
                  <td>
                    {s.status === "DRAFT" &&
                      project.active && ["ADMIN", "FINANCE_MANAGER"].includes(user.role) &&
                      s.prepared_by !== user.id && (
                        <button
                          className="button light"
                          onClick={() =>
                            void action.run(async () => {
                              await post(`/takeoff/sheets/${s.id}/check`, {
                                expected_version: s.version,
                                reason:
                                  "Geometry and recorded assumptions reviewed",
                              });
                              await client.invalidateQueries({
                                queryKey: ["takeoff-sheets"],
                              });
                            }, "Measurement independently checked")
                          }
                        >
                          Check geometry
                        </button>
                      )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}
