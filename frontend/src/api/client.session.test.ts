import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { login } from './auth'
import { apiGet, setUnauthorizedHandler } from './client'
import { jsonResponse } from '../test/http'

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  setUnauthorizedHandler(null)
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  setUnauthorizedHandler(null)
  vi.unstubAllGlobals()
})

test('login 401 does not invoke the unauthorized handler', async () => {
  const onUnauthorized = vi.fn()
  setUnauthorizedHandler(onUnauthorized)
  fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: 'Unauthorized' }))

  await expect(login({ username: 'hr.manager', password: 'wrong' })).rejects.toMatchObject({
    status: 401,
    message: 'Invalid username or password.',
  })

  expect(onUnauthorized).not.toHaveBeenCalled()
})

test('protected GET 401 invokes the unauthorized handler', async () => {
  const onUnauthorized = vi.fn()
  setUnauthorizedHandler(onUnauthorized)
  fetchMock.mockResolvedValueOnce(jsonResponse(401, { detail: 'Unauthorized' }))

  await expect(apiGet('/api/v1/employees')).rejects.toMatchObject({
    status: 401,
  })

  expect(onUnauthorized).toHaveBeenCalledTimes(1)
})
