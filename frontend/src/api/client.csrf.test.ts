import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { jsonResponse } from '../test/http'
import { createEmployeeSalary } from './salaries'
import { login } from './auth'

const fetchMock = vi.fn()
const CSRF_TOKEN = 'csrf-test-token'

function headerValue(init: RequestInit | undefined, name: string): string | null {
  return new Headers(init?.headers).get(name)
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
  document.cookie = 'acme_csrf='
  document.cookie = `acme_csrf=${encodeURIComponent(CSRF_TOKEN)}`
})

afterEach(() => {
  document.cookie = 'acme_csrf='
  vi.unstubAllGlobals()
})

test('state-changing salary POST sends the CSRF cookie as X-CSRF-Token', async () => {
  fetchMock.mockResolvedValueOnce(
    jsonResponse(201, {
      id: 12,
      employee_id: 4,
      amount: '100000.00',
      currency: 'INR',
      pay_frequency: 'MONTHLY',
      effective_from: '2026-04-01',
    }),
  )

  await createEmployeeSalary(4, {
    amount: '100000.00',
    currency: 'INR',
    pay_frequency: 'MONTHLY',
    effective_from: '2026-04-01',
  })

  expect(fetchMock).toHaveBeenCalledTimes(1)
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(url).toBe('/api/v1/employees/4/salaries')
  expect(init.method).toBe('POST')
  expect(init.credentials).toBe('include')
  expect(headerValue(init, 'X-CSRF-Token')).toBe(CSRF_TOKEN)
})

test('login POST does not attach a CSRF header', async () => {
  fetchMock.mockResolvedValueOnce(jsonResponse(200, { status: 'ok' }))

  await login({ username: 'hr.manager', password: 'secret' })

  expect(fetchMock).toHaveBeenCalledTimes(1)
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(url).toBe('/api/v1/auth/login')
  expect(init.method).toBe('POST')
  expect(headerValue(init, 'X-CSRF-Token')).toBeNull()
})
