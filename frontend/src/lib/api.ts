const API = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
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
    const contentType = response.headers.get('content-type') || '';
    let message = `Request failed (${response.status})`;
    if (contentType.includes('application/json')) {
      const data = await response.json().catch(() => ({}));
      const detail = data?.detail;
      if (typeof detail === 'string') message = detail;
      else if (detail?.message) {
        message = `${detail.message}${Array.isArray(detail.questions_missing_answer_key) ? ` Questions: ${detail.questions_missing_answer_key.join(', ')}` : ''}`;
      } else if (typeof data?.message === 'string') message = data.message;
    } else {
      const text = await response.text().catch(() => '');
      if (text.trim()) message = text.trim().slice(0, 500);
    }
    throw new Error(message);
  }

  return response.status === 204 ? undefined as T : response.json();
}

export { API };
