export interface BlankCheckResult {
  variant: string[];
  date: string[];
  reg_number: string[];
  answers: string[][];
  repl: string[][];
  record_id: number;
  warnings: string[];
  aligned_image_url?: string | null;
}

import { authHeaders, handleUnauthorized } from "./auth";

export type IssueCode =
  | "MINUS_NOT_LEADING"
  | "INTERNAL_EMPTY_CELL"
  | "LEADING_EMPTY_CELL"
  | "NOT_AN_INTEGER"
  | "MULTIPLE_MINUS"
  | "EMPTY_AFTER_TRIM"
  | "UNSUPPORTED_SYMBOL"
  | "REQUIRED_FIELD_EMPTY";

export interface RecognizedCell {
  index: number;
  row?: number | null;
  col?: number | null;
  symbol: string | null;
}

export interface ValidationIssue {
  field_id: string;
  cell_indices: number[];
  code: IssueCode;
  message: string;
}

export interface FieldReview {
  field_id: string;
  label: string;
  cells: RecognizedCell[];
  issues: ValidationIssue[];
  proposed_joined: string;
  parsed_integer: number | null;
  is_valid: boolean;
}

export interface CorrectionPayload {
  page: number;
  source_filename?: string | null;
  aligned_image_url?: string | null;
  fields: FieldReview[];
}

/** One saved record from multi-page processing (200 or 422 response). */
export interface SavedRecordIdItem {
  page: number;
  record_id: number;
}

/** 200 response from POST /v1/blank-check/multi when all pages saved. */
export interface MultiPageSuccessResponse {
  saved_record_ids: SavedRecordIdItem[];
}

/** 422 details when some pages have errors (REVIEW_REQUIRED from multi endpoint). */
export interface MultiPageErrorDetails {
  pages_with_errors: CorrectionPayload[];
  saved_record_ids: SavedRecordIdItem[];
}

/** One item in the list from GET /v1/blanks */
export interface BlankListItem {
  id: number;
  source_filename?: string | null;
  source_url?: string | null;
  page_num?: number | null;
  created_at: string;
  verified?: boolean;
  verified_at?: string | null;
  verified_by?: string | null;
  variant: string[];
  date: string[];
  reg_number: string[];
}

/** Response from GET /v1/blanks/:id for edit UI */
export interface BlankEditResponse extends CorrectionPayload {
  record_id: number;
  verified?: boolean;
  verified_at?: string | null;
  verified_by?: string | null;
}

export interface CorrectionFieldSubmission {
  field_id: string;
  cells: RecognizedCell[];
  joined_value?: string | null;
}

export interface CorrectionSubmission {
  page: number;
  source_filename?: string | null;
  fields: CorrectionFieldSubmission[];
  aligned_image_url?: string | null;
  record_id?: number | null;
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: Record<string, unknown> | CorrectionPayload | MultiPageErrorDetails;
}

export interface ApiErrorResponse {
  error: ApiErrorPayload;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: Record<string, unknown> | CorrectionPayload | MultiPageErrorDetails;

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

export function isCorrectionPayload(
  value: unknown,
): value is CorrectionPayload {
  if (!value || typeof value !== "object") return false;
  const maybe = value as Partial<CorrectionPayload>;
  return (
    typeof maybe.page === "number" &&
    Array.isArray(maybe.fields)
  );
}

export function isMultiPageErrorDetails(
  value: unknown,
): value is MultiPageErrorDetails {
  if (!value || typeof value !== "object") return false;
  const maybe = value as Partial<MultiPageErrorDetails>;
  return (
    Array.isArray(maybe.pages_with_errors) &&
    Array.isArray(maybe.saved_record_ids)
  );
}

const API_BASE =
  typeof import.meta.env?.VITE_API_URL === "string"
    ? import.meta.env.VITE_API_URL
    : "";

export async function submitCorrections(
  submission: CorrectionSubmission,
  timeoutMs = 60000,
): Promise<BlankCheckResult> {
  const url = `${API_BASE}/api/v1/blank-check/corrections`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(submission),
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
    if (res.status === 401) handleUnauthorized();
    try {
      const body = JSON.parse(text) as Record<string, unknown>;
      const rawDetail = body.detail;
      const nestedError =
        typeof rawDetail === "object" && rawDetail !== null && "error" in rawDetail
          ? (rawDetail as { error: ApiErrorPayload }).error
          : undefined;
      const errorPayload =
        (body.error as ApiErrorPayload) ??
        nestedError ??
        (rawDetail as ApiErrorPayload);
      if (
        errorPayload &&
        typeof errorPayload.code === "string" &&
        typeof errorPayload.message === "string"
      ) {
        throw new ApiError(res.status, errorPayload);
      }
    } catch (e) {
      if (e instanceof ApiError) throw e;
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

export async function fetchBlanksList(
  search?: string,
  uncheckedOnly?: boolean,
  timeoutMs = 15000,
): Promise<BlankListItem[]> {
  const params = new URLSearchParams();
  if (search != null && search.trim() !== "") {
    params.set("search", search.trim());
  }
  if (uncheckedOnly === true) {
    params.set("unchecked_only", "true");
  }
  const query = params.toString();
  const url = `${API_BASE}/api/v1/blanks${query ? `?${query}` : ""}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(url, { method: "GET", headers: authHeaders(), signal: controller.signal });
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
    if (res.status === 401) handleUnauthorized();
    try {
      const body = JSON.parse(text) as Record<string, unknown>;
      const rawDetail = body.detail;
      const nestedError =
        typeof rawDetail === "object" && rawDetail !== null && "error" in rawDetail
          ? (rawDetail as { error: ApiErrorPayload }).error
          : undefined;
      const errorPayload =
        (body.error as ApiErrorPayload) ??
        nestedError ??
        (rawDetail as ApiErrorPayload);
      if (
        errorPayload &&
        typeof errorPayload.code === "string" &&
        typeof errorPayload.message === "string"
      ) {
        throw new ApiError(res.status, errorPayload);
      }
    } catch (e) {
      if (e instanceof ApiError) throw e;
    }
    throw new ApiError(res.status, {
      code: "HTTP_ERROR",
      message: text || `HTTP ${res.status}`,
      details: undefined,
    });
  }

  try {
    return JSON.parse(text) as BlankListItem[];
  } catch {
    throw new ApiError(res.status, {
      code: "INVALID_RESPONSE",
      message: "Сервер вернул некорректный ответ",
      details: undefined,
    });
  }
}

export async function fetchBlankById(
  id: number,
  timeoutMs = 15000,
): Promise<BlankEditResponse> {
  const url = `${API_BASE}/api/v1/blanks/${id}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(url, { method: "GET", headers: authHeaders(), signal: controller.signal });
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
    if (res.status === 401) handleUnauthorized();
    try {
      const body = JSON.parse(text) as Record<string, unknown>;
      const rawDetail = body.detail;
      const nestedError =
        typeof rawDetail === "object" && rawDetail !== null && "error" in rawDetail
          ? (rawDetail as { error: ApiErrorPayload }).error
          : undefined;
      const errorPayload =
        (body.error as ApiErrorPayload) ??
        nestedError ??
        (rawDetail as ApiErrorPayload);
      if (
        errorPayload &&
        typeof errorPayload.code === "string" &&
        typeof errorPayload.message === "string"
      ) {
        throw new ApiError(res.status, errorPayload);
      }
    } catch (e) {
      if (e instanceof ApiError) throw e;
    }
    throw new ApiError(res.status, {
      code: "HTTP_ERROR",
      message: text || `HTTP ${res.status}`,
      details: undefined,
    });
  }

  try {
    return JSON.parse(text) as BlankEditResponse;
  } catch {
    throw new ApiError(res.status, {
      code: "INVALID_RESPONSE",
      message: "Сервер вернул некорректный ответ",
      details: undefined,
    });
  }
}

export async function deleteBlankApi(
  id: number,
  timeoutMs = 15000,
): Promise<void> {
  const url = `${API_BASE}/api/v1/blanks/${id}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const res = await fetch(url, {
    method: "DELETE",
    headers: authHeaders(),
    signal: controller.signal,
  });
  clearTimeout(timer);
  if (!res.ok) {
    if (res.status === 401) handleUnauthorized();
    const text = await res.text();
    try {
      const body = text ? (JSON.parse(text) as Record<string, unknown>) : {};
      const detail = body.detail;
      const msg = typeof detail === "string" ? detail : text || `HTTP ${res.status}`;
      throw new ApiError(res.status, { code: "HTTP_ERROR", message: msg, details: undefined });
    } catch (e) {
      if (e instanceof ApiError) throw e;
      throw new ApiError(res.status, {
        code: "HTTP_ERROR",
        message: text || `HTTP ${res.status}`,
        details: undefined,
      });
    }
  }
}

export async function setBlankVerifiedApi(
  id: number,
  verified: boolean,
  timeoutMs = 15000,
): Promise<void> {
  const url = `${API_BASE}/api/v1/blanks/${id}/verified`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const res = await fetch(url, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ verified }),
    signal: controller.signal,
  });
  clearTimeout(timer);
  if (!res.ok) {
    if (res.status === 401) handleUnauthorized();
    const text = await res.text();
    try {
      const body = text ? (JSON.parse(text) as Record<string, unknown>) : {};
      const detail = body.detail;
      const msg = typeof detail === "string" ? detail : text || `HTTP ${res.status}`;
      throw new ApiError(res.status, { code: "HTTP_ERROR", message: msg, details: undefined });
    } catch (e) {
      if (e instanceof ApiError) throw e;
      throw new ApiError(res.status, {
        code: "HTTP_ERROR",
        message: text || `HTTP ${res.status}`,
        details: undefined,
      });
    }
  }
}

export async function uploadPdfAndPredict(
  file: File,
  page: number = 0,
  timeoutMs = 60000
): Promise<BlankCheckResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("filename", file.name);
  formData.append("page", String(page));

  const url = `${API_BASE}/api/v1/blank-check`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      body: formData,
      headers: authHeaders(),
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
    if (res.status === 401) handleUnauthorized();
    try {
      const body = JSON.parse(text) as Record<string, unknown>;
      const rawDetail = body.detail;
      const nestedError =
        typeof rawDetail === "object" && rawDetail !== null && "error" in rawDetail
          ? (rawDetail as { error: ApiErrorPayload }).error
          : undefined;
      const errorPayload =
        (body.error as ApiErrorPayload) ??
        nestedError ??
        (rawDetail as ApiErrorPayload);
      if (
        errorPayload &&
        typeof errorPayload.code === "string" &&
        typeof errorPayload.message === "string"
      ) {
        throw new ApiError(res.status, errorPayload);
      }
    } catch (e) {
      if (e instanceof ApiError) throw e;
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

export async function uploadPdfAndPredictMulti(
  file: File,
  timeoutMs = 180000,
): Promise<MultiPageSuccessResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("filename", file.name);

  const url = `${API_BASE}/api/v1/blank-check/multi`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      body: formData,
      headers: authHeaders(),
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
    if (res.status === 401) handleUnauthorized();
    try {
      const body = JSON.parse(text) as Record<string, unknown>;
      const rawDetail = body.detail;
      const nestedError =
        typeof rawDetail === "object" && rawDetail !== null && "error" in rawDetail
          ? (rawDetail as { error: ApiErrorPayload }).error
          : undefined;
      const errorPayload =
        (body.error as ApiErrorPayload) ??
        nestedError ??
        (rawDetail as ApiErrorPayload);
      if (
        errorPayload &&
        typeof errorPayload.code === "string" &&
        typeof errorPayload.message === "string"
      ) {
        throw new ApiError(res.status, errorPayload);
      }
    } catch (e) {
      if (e instanceof ApiError) throw e;
    }
    throw new ApiError(res.status, {
      code: "HTTP_ERROR",
      message: text || `HTTP ${res.status}`,
      details: undefined,
    });
  }

  try {
    return JSON.parse(text) as MultiPageSuccessResponse;
  } catch {
    throw new ApiError(res.status, {
      code: "INVALID_RESPONSE",
      message: "Сервер вернул некорректный ответ",
      details: undefined,
    });
  }
}

export async function downloadBlanksTable(
  timeoutMs = 60000,
  filename = "blanks.xlsx",
): Promise<void> {
  const url = `${API_BASE}/api/v1/export`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let res: Response;
  try {
    res = await fetch(url, { method: "GET", headers: authHeaders(), signal: controller.signal });
  } catch (err) {
    clearTimeout(timer);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new NetworkError("Превышено время ожидания ответа от сервера");
    }
    throw new NetworkError();
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    if (res.status === 401) handleUnauthorized();
    const text = await res.text();
    try {
      const body = JSON.parse(text) as Record<string, unknown>;
      const rawDetail = body.detail;
      const nestedError =
        typeof rawDetail === "object" && rawDetail !== null && "error" in rawDetail
          ? (rawDetail as { error: ApiErrorPayload }).error
          : undefined;
      const errorPayload =
        (body.error as ApiErrorPayload) ??
        nestedError ??
        (rawDetail as ApiErrorPayload);
      if (
        errorPayload &&
        typeof errorPayload.code === "string" &&
        typeof errorPayload.message === "string"
      ) {
        throw new ApiError(res.status, errorPayload);
      }
    } catch (e) {
      if (e instanceof ApiError) throw e;
    }
    throw new ApiError(res.status, {
      code: "HTTP_ERROR",
      message: text || `HTTP ${res.status}`,
      details: undefined,
    });
  }

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition");
  const match = disposition?.match(/filename="?([^";\n]+)"?/);
  const name = match?.[1]?.trim() || filename;

  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}
