export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// Set by useAuth after login/`/api/auth/me` -- echoed back as the
// X-CSRF-Token header on every mutating request (see app.py's
// before_request CSRF check). null before login / after logout, which is
// fine: /api/auth/login itself is exempt from the check.
let csrfToken: string | null = null

export function setCsrfToken(token: string | null) {
  csrfToken = token
}

function mutatingHeaders(hasJsonBody: boolean): HeadersInit {
  const headers: Record<string, string> = {}
  if (hasJsonBody) headers['Content-Type'] = 'application/json'
  if (csrfToken) headers['X-CSRF-Token'] = csrfToken
  return headers
}

async function handleResponse<T>(res: Response): Promise<T> {
  const text = await res.text()
  const data = text ? JSON.parse(text) : null

  if (!res.ok) {
    const message =
      (data && (data.error || data.message)) || `İstek başarısız oldu (${res.status})`
    throw new ApiError(message, res.status)
  }

  return data as T
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path)
  return handleResponse<T>(res)
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: mutatingHeaders(Boolean(body)),
    body: body ? JSON.stringify(body) : undefined,
  })
  return handleResponse<T>(res)
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'PUT',
    headers: mutatingHeaders(Boolean(body)),
    body: body ? JSON.stringify(body) : undefined,
  })
  return handleResponse<T>(res)
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'PATCH',
    headers: mutatingHeaders(Boolean(body)),
    body: body ? JSON.stringify(body) : undefined,
  })
  return handleResponse<T>(res)
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(path, { method: 'DELETE', headers: mutatingHeaders(false) })
  return handleResponse<T>(res)
}

/** For file uploads — no Content-Type header so the browser sets the
 * multipart boundary itself. */
export async function apiPostForm<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(path, { method: 'POST', headers: mutatingHeaders(false), body: formData })
  return handleResponse<T>(res)
}
