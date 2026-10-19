export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const CSRF_COOKIE_NAME = 'acme_csrf'
const CSRF_HEADER_NAME = 'X-CSRF-Token'
const LOGIN_PATH = '/api/v1/auth/login'
const SESSION_SECURITY_MESSAGE =
  'This request failed a session security check. Sign in again, then retry.'
const NETWORK_ERROR_MESSAGE =
  'Could not reach the API. Confirm the backend is running and that this app is served through the Vite development proxy.'

function readCookie(name: string): string | undefined {
  if (typeof document === 'undefined') {
    return undefined
  }
  const prefix = `${name}=`
  for (const part of document.cookie.split(';')) {
    const trimmed = part.trim()
    if (trimmed.startsWith(prefix)) {
      const raw = trimmed.slice(prefix.length)
      if (!raw) {
        return undefined
      }
      try {
        return decodeURIComponent(raw)
      } catch {
        return raw
      }
    }
  }
  return undefined
}

function headerIsPresent(headers: Record<string, string>, name: string): boolean {
  const expected = name.toLowerCase()
  return Object.keys(headers).some((key) => key.toLowerCase() === expected)
}

function detailFromBody(body: unknown): string | undefined {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = body.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
  }
  return undefined
}

async function parseErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body: unknown = await response.json()
    return detailFromBody(body) ?? fallback
  } catch {
    return fallback
  }
}

type RequestOptions = {
  method: 'GET' | 'POST'
  query?: Record<string, string>
  json?: unknown
  signal?: AbortSignal
  unauthorizedMessage?: string
}

export async function apiRequest<T>(path: string, options: RequestOptions): Promise<T> {
  const url = options.query
    ? `${path}?${new URLSearchParams(options.query).toString()}`
    : path
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  if (
    options.method === 'POST' &&
    path !== LOGIN_PATH &&
    !headerIsPresent(headers, CSRF_HEADER_NAME)
  ) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME)
    if (csrfToken) {
      headers[CSRF_HEADER_NAME] = csrfToken
    }
  }

  let response: Response
  try {
    response = await fetch(url, {
      method: options.method,
      credentials: 'include',
      headers,
      body: options.json === undefined ? undefined : JSON.stringify(options.json),
      signal: options.signal,
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') {
      throw cause
    }
    throw new ApiError(0, NETWORK_ERROR_MESSAGE)
  }

  if (response.status === 401) {
    throw new ApiError(
      401,
      options.unauthorizedMessage ??
        (await parseErrorMessage(response, 'You are not signed in.')),
    )
  }

  if (response.status === 403) {
    throw new ApiError(403, SESSION_SECURITY_MESSAGE)
  }

  if (!response.ok) {
    throw new ApiError(
      response.status,
      await parseErrorMessage(response, 'The request could not be completed.'),
    )
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export function apiGet<T>(
  path: string,
  query?: Record<string, string>,
  signal?: AbortSignal,
): Promise<T> {
  return apiRequest<T>(path, {
    method: 'GET',
    query,
    signal,
    unauthorizedMessage:
      'You are not signed in. Log in as the HR Manager, then try again.',
  })
}

export function apiPost<T>(path: string, json: unknown, signal?: AbortSignal): Promise<T> {
  return apiRequest<T>(path, { method: 'POST', json, signal })
}
