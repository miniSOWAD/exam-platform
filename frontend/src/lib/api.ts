const API = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

type ApiErrorDetail = {
  loc?: Array<string | number>;
  msg?: string;
  message?: string;
  questions_missing_answer_key?: number[];
};

function getApiErrorMessage(data: unknown, status: number): string {
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
  return `Request failed (${status})`;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  // The browser must set the multipart boundary for FormData uploads.
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(`${API}${path}`, {
    ...init,
    credentials: 'include',
    headers,
    cache: 'no-store',
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(getApiErrorMessage(data, response.status));
  }
  return response.status === 204 ? undefined as T : response.json();
}

export { API };
