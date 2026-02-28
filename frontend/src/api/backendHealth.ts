const API_BASE =
  typeof import.meta.env?.VITE_API_URL === "string"
    ? import.meta.env.VITE_API_URL
    : "";

/**
 * Проверяет, доступен ли бекенд (GET /api/ready).
 * Возвращает true при ответе 200, false при сетевой ошибке или не-200.
 */
export async function checkBackendReady(timeoutMs = 5000): Promise<boolean> {
  const url = `${API_BASE}/api/ready`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { method: "GET", signal: controller.signal });
    clearTimeout(timer);
    return res.ok;
  } catch {
    clearTimeout(timer);
    return false;
  }
}
