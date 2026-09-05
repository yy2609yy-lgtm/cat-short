import type { AppSettings, CropParams, Job, SyncStatus } from "./types";

const TOKEN_KEY = "catshort.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers });
  if (res.status === 401) {
    setToken(null);
    if (!path.includes("/auth/login")) window.location.href = "/login";
    throw new Error("未登录");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.headers.get("content-type")?.includes("application/json")) {
    return (await res.json()) as T;
  }
  return undefined as T;
}

export const api = {
  login: (username: string, password: string) =>
    req<{ access_token: string; username: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => req<{ username: string }>("/api/auth/me"),
  settings: () => req<AppSettings>("/api/settings"),
  jobs: () => req<Job[]>("/api/jobs"),
  job: (id: string) => req<Job>(`/api/jobs/${id}`),
  confirm: (id: string, crop: CropParams) =>
    req<Job>(`/api/jobs/${id}/confirm`, { method: "POST", body: JSON.stringify(crop) }),
  retry: (id: string) => req<Job>(`/api/jobs/${id}/retry`, { method: "POST" }),
  publish: (id: string) => req<Job>(`/api/jobs/${id}/publish`, { method: "POST" }),
  syncNow: () =>
    req<{ mode: string; ingested: number; skipped: number; errors: string[] }>("/api/sync/drive", {
      method: "POST",
    }),
  syncStatus: () => req<SyncStatus>("/api/sync/status"),
  upload: async (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return req<Job>("/api/assets/upload", { method: "POST", body });
  },
};

export function sourceUrl(jobId: string) {
  return `/api/jobs/${jobId}/media/source?token=${encodeURIComponent(getToken() || "")}`;
}

export function renderUrl(jobId: string) {
  return `/api/jobs/${jobId}/media/render?token=${encodeURIComponent(getToken() || "")}`;
}
