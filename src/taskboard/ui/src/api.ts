// Thin fetch wrappers. All requests are same-origin and rely on the
// httpOnly tb_session cookie (set by the BFF) for auth.

export interface Me {
  sub: string;
  email: string;
  name: string;
}

export interface Task {
  id: string;
  title: string;
  done: boolean;
  created_at: string;
  updated_at: string;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (resp.status === 401) {
    // Send the user through the OIDC flow and bring them back here.
    window.location.href = "/auth/login?return=" + encodeURIComponent(window.location.pathname);
    throw new Error("redirecting to login");
  }
  if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`);
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export const api = {
  me: () => req<Me>("/api/me"),
  list: () => req<Task[]>("/api/tasks"),
  create: (title: string) => req<Task>("/api/tasks", { method: "POST", body: JSON.stringify({ title }) }),
  patch: (id: string, body: Partial<Pick<Task, "title" | "done">>) =>
    req<Task>(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (id: string) => req<void>(`/api/tasks/${id}`, { method: "DELETE" }),
  logout: () => req<void>("/auth/logout", { method: "POST" }),
};
