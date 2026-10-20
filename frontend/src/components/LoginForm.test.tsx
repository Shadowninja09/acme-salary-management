import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { jsonResponse } from '../test/http'
import { LoginForm } from './LoginForm'

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('successful login signs in and confirms the session', async () => {
  const onAuthenticated = vi.fn()
  fetchMock
    .mockResolvedValueOnce(jsonResponse(200, { status: 'ok' }))
    .mockResolvedValueOnce(
      jsonResponse(200, { items: [], total: 0, limit: 1, offset: 0 }),
    )

  const user = userEvent.setup()
  render(<LoginForm onAuthenticated={onAuthenticated} />)

  await user.type(screen.getByLabelText('Username'), 'hr.manager')
  await user.type(screen.getByLabelText('Password'), 'correct-horse')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))

  await vi.waitFor(() => {
    expect(onAuthenticated).toHaveBeenCalledTimes(1)
  })

  expect(fetchMock).toHaveBeenCalledTimes(2)

  const [loginUrl, loginInit] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(loginUrl).toBe('/api/v1/auth/login')
  expect(loginInit.method).toBe('POST')
  expect(loginInit.credentials).toBe('include')
  expect(JSON.parse(String(loginInit.body))).toEqual({
    username: 'hr.manager',
    password: 'correct-horse',
  })

  const [employeesUrl, employeesInit] = fetchMock.mock.calls[1] as [string, RequestInit]
  expect(employeesUrl).toBe('/api/v1/employees?limit=1&offset=0')
  expect(employeesInit.method).toBe('GET')
  expect(employeesInit.credentials).toBe('include')
})

test('failed login shows an error and does not continue', async () => {
  const onAuthenticated = vi.fn()
  fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: 'Unauthorized' }))

  const user = userEvent.setup()
  render(<LoginForm onAuthenticated={onAuthenticated} />)

  await user.type(screen.getByLabelText('Username'), 'hr.manager')
  await user.type(screen.getByLabelText('Password'), 'wrong-password')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Invalid username or password.',
  )
  expect(onAuthenticated).not.toHaveBeenCalled()
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/auth/login')
})
