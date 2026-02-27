export interface BlankCheckResult {
  variant: string[];
  date: string[];
  reg_number: string[];
  answers: string[][];
  repl: string[][];
  record_id: number;
  warnings: string[];
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiErrorResponse {
  error: ApiErrorPayload;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, unknown>;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message);
    this.status = status;
    this.code = payload.code;
    this.details = payload.details;
  }
}

export class NetworkError extends Error {
  constructor(message = "Не удалось подключиться к серверу") {
    super(message);
  }
}

const API_BASE =
  typeof import.meta.env?.VITE_API_URL === "string"
    ? import.meta.env.VITE_API_URL
    : "";

export async function uploadPdfAndPredict(
  file: File,
  page: number = 0,
  timeoutMs = 60000
): Promise<BlankCheckResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("page", String(page));

  const url = `${API_BASE}/api/v1/blank-check`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new NetworkError("Превышено время ожидания ответа от сервера");
    }
    throw new NetworkError();
  } finally {
    clearTimeout(timer);
  }

  const text = await res.text();

  if (!res.ok) {
    try {
      const json = JSON.parse(text) as ApiErrorResponse;
      if (json && json.error && typeof json.error.code === "string") {
        throw new ApiError(res.status, json.error);
      }
    } catch {
      // fall through to generic error below
    }
    throw new ApiError(res.status, {
      code: "HTTP_ERROR",
      message: text || `HTTP ${res.status}`,
      details: undefined,
    });
  }

  try {
    return JSON.parse(text) as BlankCheckResult;
  } catch {
    throw new ApiError(res.status, {
      code: "INVALID_RESPONSE",
      message: "Сервер вернул некорректный ответ",
      details: undefined,
    });
  }
}
