import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { Invoice } from "../types";
import { useWorkspace } from "../App";

export function useInvoices() {
  const { project } = useWorkspace();
  return useQuery({
    queryKey: ["invoices", project.id],
    queryFn: () => api<Invoice[]>(`/invoices?project_id=${project.id}`),
  });
}

export function dateTime(value: string) {
  return new Date(value).toLocaleString("en-GB", {
    timeZone: "Asia/Dhaka",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
