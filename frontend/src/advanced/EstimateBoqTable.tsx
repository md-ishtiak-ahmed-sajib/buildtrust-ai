import { ChevronDown, Search, Trash2 } from "lucide-react";
import { formatMoney } from "../api";
import { multiplyExact } from "./shared";
import type { EstimateEditorProps } from "./estimateEditorTypes";
export function EstimateBoqTable({
  draft,
  calc,
  editable,
  dirty,
  expanded,
  setExpanded,
  setPrice,
  update,
  materials,
}: EstimateEditorProps) {
  return (
    <div className="table-scroll boq-table">
      <table>
        <thead>
          <tr>
            <th>Section / code</th>
            <th>Description / material pricing</th>
            <th>Quantity</th>
            <th>Unit</th>
            <th>Analyzed rate</th>
            <th>Amount</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {draft.fields.lines?.map((line) => (
            <tr key={line.id}>
              <td>
                <small>{line.section}</small>
                <br />
                <strong>{line.code}</strong>
              </td>
              <td>
                <button
                  className="boq-item-link"
                  onClick={() =>
                    setExpanded(expanded === line.id ? undefined : line.id)
                  }
                >
                  {line.description}
                  <ChevronDown size={15} />
                </button>
                <div className="boq-material-links">
                  {line.components
                    ?.filter((c) => c.material_id)
                    .map((c) => (
                      <button
                        key={c.id}
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
                        <Search size={12} /> {c.description}
                      </button>
                    ))}
                </div>
              </td>
              <td>{line.quantity}</td>
              <td>{line.unit}</td>
              <td>
                {formatMoney(
                  calc?.lines.find((c) => c.id === line.id)?.unit_rate || "0",
                )}
              </td>
              <td>
                <strong>
                  {formatMoney(
                    calc?.lines.find((c) => c.id === line.id)?.amount || "0",
                  )}
                </strong>
              </td>
              <td>
                {editable && (
                  <button
                    className="icon-button"
                    aria-label={`Delete ${line.code}`}
                    onClick={() =>
                      update((e) => {
                        e.fields.lines = e.fields.lines?.filter(
                          (l) => l.id !== line.id,
                        );
                      })
                    }
                  >
                    <Trash2 size={15} />
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
