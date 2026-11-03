const API = process.env.NEXT_PUBLIC_API_URL || '/api/v1';
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${API}${path}`, { ...init, credentials: 'include', headers, cache: 'no-store' });
  if (!response.ok) { const data = await response.json().catch(() => ({})); const detail = data.detail; const message = typeof detail === 'string' ? detail : detail?.message ? `${detail.message}${Array.isArray(detail.questions_missing_answer_key) ? ` Questions: ${detail.questions_missing_answer_key.join(', ')}` : ''}` : `Request failed (${response.status})`; throw new Error(message); }
  return response.status === 204 ? undefined as T : response.json();
}
export { API };
