const TOKEN_KEY = "auth_token";

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

/** Для URL вида /api/files/... добавляет query-параметр token. Ссылка всегда только путь (без хоста/порта), чтобы запрос шёл на тот же origin (nginx на 80). */
export function fileUrlWithAuth(url: string | null | undefined): string {
  if (!url) return "";
  let resolved = url.trim();
  if (resolved.startsWith("api/files/") && !resolved.startsWith("/"))
    resolved = "/" + resolved;
  const token = getToken();
  if (!token) return resolved;
  if (!resolved.includes("/api/files/")) return resolved;
  const sep = resolved.includes("?") ? "&" : "?";
  return `${resolved}${sep}token=${encodeURIComponent(token)}`;
}

function redirectToLogin(): void {
  clearToken();
  window.location.href = "/auth";
}

const API_BASE =
  typeof import.meta.env?.VITE_API_URL === "string"
    ? import.meta.env.VITE_API_URL
    : "";

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface UserMeResponse {
  login: string;
  is_admin: boolean;
}

export async function login(
  loginName: string,
  password: string,
  timeoutMs = 10000,
): Promise<LoginResponse> {
  const url = `${API_BASE}/api/auth/login`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login: loginName, password }),
      signal: controller.signal,
    });
    const text = await res.text();
    if (!res.ok) {
      if (res.status === 401) {
        throw new Error("Неверный логин или пароль");
      }
      throw new Error(text || `HTTP ${res.status}`);
    }
    return JSON.parse(text) as LoginResponse;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchMe(timeoutMs = 10000): Promise<UserMeResponse> {
  const token = getToken();
  if (!token) throw new Error("Not authenticated");
  const url = `${API_BASE}/api/auth/me`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    });
    const text = await res.text();
    if (!res.ok) {
      if (res.status === 401) redirectToLogin();
      throw new Error(text || `HTTP ${res.status}`);
    }
    return JSON.parse(text) as UserMeResponse;
  } finally {
    clearTimeout(timer);
  }
}

/** Call this when any API returns 401 to logout and redirect to login. */
export function handleUnauthorized(): void {
  redirectToLogin();
}

/** Build headers with Bearer token for authenticated requests. */
export function authHeaders(extra: HeadersInit = {}): HeadersInit {
  const token = getToken();
  const record: Record<string, string> =
    typeof extra === "object" && extra !== null && !(extra instanceof Headers)
      ? (extra as Record<string, string>)
      : {};
  return {
    ...record,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export interface UserListItem {
  id: number;
  login: string;
  created_at: string;
}

/** Response from create user: includes password so main admin can see it */
export interface UserCreateResponse extends UserListItem {
  password: string;
}

export async function fetchUsersList(
  timeoutMs = 15000,
): Promise<UserListItem[]> {
  const token = getToken();
  if (!token) throw new Error("Not authenticated");
  const url = `${API_BASE}/api/v1/users`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    });
    const text = await res.text();
    if (!res.ok) {
      if (res.status === 401) redirectToLogin();
      if (res.status === 403) throw new Error("Доступ запрещён");
      throw new Error(text || `HTTP ${res.status}`);
    }
    return JSON.parse(text) as UserListItem[];
  } finally {
    clearTimeout(timer);
  }
}

export async function createUserApi(
  loginName: string,
  password: string,
  timeoutMs = 15000,
): Promise<UserCreateResponse> {
  const token = getToken();
  if (!token) throw new Error("Not authenticated");
  const url = `${API_BASE}/api/v1/users`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ login: loginName, password }),
      signal: controller.signal,
    });
    const text = await res.text();
    if (!res.ok) {
      if (res.status === 401) redirectToLogin();
      if (res.status === 403) throw new Error("Доступ запрещён");
      if (res.status === 409) throw new Error("Пользователь с таким логином уже существует");
      throw new Error(text || `HTTP ${res.status}`);
    }
    return JSON.parse(text) as UserCreateResponse;
  } finally {
    clearTimeout(timer);
  }
}

export async function deleteUserApi(
  userId: number,
  timeoutMs = 15000,
): Promise<void> {
  const token = getToken();
  if (!token) throw new Error("Not authenticated");
  const url = `${API_BASE}/api/v1/users/${userId}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const res = await fetch(url, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
    signal: controller.signal,
  });
  clearTimeout(timer);
  if (!res.ok) {
    if (res.status === 401) redirectToLogin();
    if (res.status === 403) throw new Error("Доступ запрещён");
    if (res.status === 404) throw new Error("Пользователь не найден");
    throw new Error(await res.text().catch(() => `HTTP ${res.status}`));
  }
}
