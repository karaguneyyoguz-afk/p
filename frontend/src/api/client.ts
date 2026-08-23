export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
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
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  return handleResponse<T>(res)
}

/** For file uploads — no Content-Type header so the browser sets the
 * multipart boundary itself. */
export async function apiPostForm<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(path, { method: 'POST', body: formData })
  return handleResponse<T>(res)
}
