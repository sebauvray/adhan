/**
 * Thin fetch wrapper. Always sends cookies (HttpOnly session) and parses JSON.
 * Throws Error with the API's `detail` message on non-2xx responses.
 *
 * If `body` is a FormData instance, Content-Type is left for the browser to
 * set (it needs to include the multipart boundary).
 */
export async function api<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = options.body instanceof FormData
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...((options.headers as Record<string, string>) || {}),
  }
  const res = await fetch(`/api${path}`, {
    credentials: 'include',
    ...options,
    headers,
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
