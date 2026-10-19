import type { Estimate, Line, Material } from "./shared";
export type PriceRequest = {
  material: Material;
  lineId: string;
  componentId: string;
  quantity: string;
};
export type EstimateEditorProps = {
  draft: Estimate;
  calc?: Estimate["calculated"];
  editable: boolean;
  dirty: boolean;
  expanded?: string;
  setExpanded: (id: string | undefined) => void;
  setPrice: (request: PriceRequest) => void;
  update: (work: (estimate: Estimate) => void) => void;
  lineChange: (id: string, key: keyof Line, value: unknown) => void;
  materials: { data?: Material[] };
  costCodes: { data?: { id: number; code: string; name: string }[] };
  sheets: {
    data?: {
      id: number;
      status: string;
      fields: { name: string };
      result: { quantity: string; unit: string };
    }[];
  };
};
