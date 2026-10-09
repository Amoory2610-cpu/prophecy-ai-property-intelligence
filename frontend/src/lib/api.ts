/**
 * Thin client for the FastAPI backend. Requests go to same-origin `/api/*`, which
 * Next.js rewrites to the backend, so the httpOnly session cookie is sent automatically.
 */

export type FieldError = { field: string; message: string };

export class ApiError extends Error {
  status: number;
  fieldErrors: FieldError[];

  constructor(status: number, message: string, fieldErrors: FieldError[] = []) {
    super(message);
    this.status = status;
    this.fieldErrors = fieldErrors;
  }

  /** One readable sentence for a toast or inline alert. */
  get summary(): string {
    if (this.fieldErrors.length) {
      return this.fieldErrors
        .map((e) => (e.field ? `${humanise(e.field)}: ${e.message}` : e.message))
        .join(". ");
    }
    return this.message;
  }
}

export function humanise(field: string): string {
  const last = field.split(".").pop() ?? field;
  const words = last.replace(/_pct$/, " %").replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

type Options = Omit<RequestInit, "body"> & { body?: unknown; form?: FormData };

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const { body, form, headers, ...rest } = options;
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      credentials: "same-origin",
      ...rest,
      headers: form ? headers : { "Content-Type": "application/json", ...headers },
      body: form ?? (body === undefined ? undefined : JSON.stringify(body)),
    });
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) {
    const detail =
      (data && typeof data.detail === "string" && data.detail) ||
      (res.status === 401 ? "Your session has ended. Sign in again." : `Request failed (${res.status})`);
    throw new ApiError(res.status, detail, Array.isArray(data?.errors) ? data.errors : []);
  }
  return data as T;
}

function safeJson(text: string) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** Trigger a browser download from an authenticated endpoint. */
export async function download(path: string, fallbackName: string) {
  const res = await fetch(`/api${path}`, { credentials: "same-origin" });
  if (!res.ok) throw new ApiError(res.status, "Download failed");
  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
