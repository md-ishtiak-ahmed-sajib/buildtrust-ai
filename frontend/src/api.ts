let accessToken = "";
export const setToken = (token: string) => {
  accessToken = token;
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
    public fields: { location: (string | number)[]; message: string }[] = [],
    public requestId: string | null = null,
    public retryAfter: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
async function checkResponse(response: Response, path: string) {
  if (response.ok) return;
  const body = await response.json().catch(() => ({}));
  if (response.status === 401 && !path.includes("/auth/login"))
    window.dispatchEvent(new Event("session-expired"));
  throw new ApiError(
    body.error?.message || `Request failed (${response.status})`,
    response.status,
    body.error?.code || "REQUEST_FAILED",
    body.error?.fields || [],
    response.headers.get("X-Request-ID"),
    response.headers.get("Retry-After"),
  );
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api/v1${path}`, { ...options, headers }).catch(() => {
    throw new ApiError('Cannot reach the local application. Check that it is running, then try again.', 0, 'NETWORK_ERROR');
  });
  await checkResponse(response, path);
  return response.json();
}
export async function previewBlob(id: number) {
  const response = await fetch(`/api/v1/documents/${id}/preview`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  await checkResponse(response, `/documents/${id}/preview`);
  return response.blob();
}
export async function downloadFile(path: string, filename: string) {
  const response = await fetch(`/api/v1${path}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  await checkResponse(response, path);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const post = <T>(path: string, body?: unknown, headers?: HeadersInit) =>
  api<T>(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
    headers,
  });
export function formatMoney(value: string | number, compact = false) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: compact ? 1 : 2,
    minimumFractionDigits: compact ? 0 : 2,
    notation: compact ? "compact" : "standard",
  }).format(number);
}
export const titleCase = (text: string) =>
  text
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
