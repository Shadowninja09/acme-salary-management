import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from './App'
import { jsonResponse } from './test/http'

const fetchMock = vi.fn()

const EMPTY_PROBE = { items: [], total: 0, limit: 1, offset: 0 }
const EMPTY_DIRECTORY = { items: [], total: 0, limit: 50, offset: 0 }

function requestParts(input: RequestInfo, init?: RequestInit) {
  return {
    url: String(input),
    method: (init?.method ?? 'GET').toUpperCase(),
  }
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('protected 401 after a valid session probe returns to login', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url === '/api/v1/employees?limit=1&offset=0' && method === 'GET') {
      return Promise.resolve(jsonResponse(200, EMPTY_PROBE))
    }
    if (url === '/api/v1/employees?limit=50&offset=0' && method === 'GET') {
      return Promise.resolve(jsonResponse(401, { detail: 'Unauthorized' }))
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  render(<App />)

  expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument()
  expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Employees' })).not.toBeInTheDocument()
})

test('login 401 shows invalid credentials and stays on the login screen', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url === '/api/v1/employees?limit=1&offset=0' && method === 'GET') {
      return Promise.resolve(jsonResponse(401, { detail: 'Unauthorized' }))
    }
    if (url === '/api/v1/auth/login' && method === 'POST') {
      return Promise.resolve(jsonResponse(401, { detail: 'Unauthorized' }))
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  const user = userEvent.setup()
  render(<App />)

  expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  await user.type(screen.getByLabelText('Username'), 'hr.manager')
  await user.type(screen.getByLabelText('Password'), 'wrong-password')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Invalid username or password.',
  )
  expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument()
})

test('protected 403 does not return to login', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url === '/api/v1/employees?limit=1&offset=0' && method === 'GET') {
      return Promise.resolve(jsonResponse(200, EMPTY_PROBE))
    }
    if (url === '/api/v1/employees?limit=50&offset=0' && method === 'GET') {
      return Promise.resolve(jsonResponse(403, { detail: 'Forbidden' }))
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  render(<App />)

  expect(await screen.findByRole('heading', { name: 'Employees' })).toBeInTheDocument()
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'This request failed a session security check. Sign in again, then retry.',
  )
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Sign in' })).not.toBeInTheDocument()
})

test('protected network failure does not return to login', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url === '/api/v1/employees?limit=1&offset=0' && method === 'GET') {
      return Promise.resolve(jsonResponse(200, EMPTY_PROBE))
    }
    if (url === '/api/v1/employees?limit=50&offset=0' && method === 'GET') {
      return Promise.reject(new TypeError('Failed to fetch'))
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  render(<App />)

  expect(await screen.findByRole('heading', { name: 'Employees' })).toBeInTheDocument()
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Could not reach the API. Confirm the backend is running and that this app is served through the Vite development proxy.',
  )
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Sign in' })).not.toBeInTheDocument()
})

test('logout 401 returns to the login screen', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url.startsWith('/api/v1/employees') && method === 'GET') {
      const empty = url.includes('limit=1') ? EMPTY_PROBE : EMPTY_DIRECTORY
      return Promise.resolve(jsonResponse(200, empty))
    }
    if (url === '/api/v1/auth/logout' && method === 'POST') {
      return Promise.resolve(jsonResponse(401, { detail: 'Unauthorized' }))
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  const user = userEvent.setup()
  render(<App />)

  expect(await screen.findByRole('heading', { name: 'Employees' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Sign out' }))

  expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument()
  expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument()
})
