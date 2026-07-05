// Same-origin fetch (Next proxies /api -> FastAPI). Cookies flow automatically.
export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function handle(res: Response) {
  if (res.ok) return res.status === 204 ? null : res.json();
  let detail: unknown = res.statusText;
  try {
    const body = await res.json();
    detail = body.detail ?? body;
  } catch {}
  throw new ApiError(res.status, detail);
}

export const api = {
  get: (path: string) => fetch(`/api/v1${path}`, { credentials: "include" }).then(handle),
  post: (path: string, body?: unknown, headers: Record<string, string> = {}) =>
    fetch(`/api/v1${path}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    }).then(handle),
  patch: (path: string, body: unknown) =>
    fetch(`/api/v1${path}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(handle),
  del: (path: string) =>
    fetch(`/api/v1${path}`, { method: "DELETE", credentials: "include" }).then(handle),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`/api/v1/media/upload`, { method: "POST", credentials: "include", body: fd }).then(handle);
  },
};

export function errText(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.detail === "string") return e.detail;
    return JSON.stringify(e.detail);
  }
  return e instanceof Error ? e.message : "unexpected error";
}
