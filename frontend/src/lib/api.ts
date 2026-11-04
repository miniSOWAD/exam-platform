/**
 * All browser API calls must use the same-origin Next.js proxy.
 * Do not point the browser directly at FastAPI: its HttpOnly auth cookie is
 * SameSite=Lax and would not be sent on cross-site fetch requests.
 */
const API = '/api/v1';

type ApiErrorDetail = {
  loc?: Array<string | number>;
  msg?: string;
  message?: string;
  questions_missing_answer_key?: number[];
};

export class ApiError extends Error {
  readonly status: number;
  readonly data: unknown;

  constructor(message: string, status: number, data: unknown = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export function isUnauthorizedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}

function getApiErrorMessage(data: unknown, status: number): string {
  if (typeof data === 'string' && data.trim()) return data.trim();
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail?: unknown }).detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (!item || typeof item !== 'object') return '';
          const error = item as ApiErrorDetail;
          const field = Array.isArray(error.loc) ? error.loc.filter((part) => part !== 'body').join('.') : '';
          return [field, error.msg].filter(Boolean).join(': ');
        })
        .filter(Boolean);
      if (messages.length) return messages.join(' | ');
    }
    if (detail && typeof detail === 'object') {
      const error = detail as ApiErrorDetail;
      if (error.message) {
        const missing = Array.isArray(error.questions_missing_answer_key)
          ? ` Questions: ${error.questions_missing_answer_key.join(', ')}`
          : '';
        return `${error.message}${missing}`;
      }
    }
  }
  if (data && typeof data === 'object' && 'message' in data) {
    const message = (data as { message?: unknown }).message;
    if (typeof message === 'string' && message.trim()) return message;
  }
  if (status === 500) {
    return 'The ExamFlow server encountered an internal error. The administrator should check the backend logs and database migration status.';
  }
  if (status === 502 || status === 503 || status === 504) {
    return 'The ExamFlow API is temporarily unavailable. Please try again shortly.';
  }
  return `Request failed (${status})`;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  // The browser must set the multipart boundary for FormData uploads.
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers,
      cache: 'no-store',
    });
  } catch {
    throw new ApiError(
      'Could not connect to the ExamFlow API. Check the frontend API proxy configuration and try again.',
      0,
    );
  }

  if (!response.ok) {
    const rawBody = await response.text().catch(() => "");
    let data: unknown = null;
    if (rawBody) {
      try { data = JSON.parse(rawBody); }
      catch { data = rawBody; }
    }
    throw new ApiError(getApiErrorMessage(data, response.status), response.status, data);
  }
  return response.status === 204 ? undefined as T : response.json();
}

export { API };
