/**
 * Thin fetch wrapper. Always sends cookies (HttpOnly session) and parses JSON.
 * Throws Error with the API's `detail` message on non-2xx responses.
 */
export async function api<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })
  if (!res.ok) {
    let detail: string = res.statusText
    try {
      const body = await res.json()
      if (body?.detail) detail = body.detail
    } catch {
      // body wasn't JSON
    }
    throw new Error(detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}
