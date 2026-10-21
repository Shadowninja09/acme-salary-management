import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { jsonResponse } from '../test/http'
import { EmployeeDirectory } from './EmployeeDirectory'

const fetchMock = vi.fn()

const firstPageEmployee = {
  id: 1,
  employee_code: 'EMP-000001',
  full_name: 'Ada Lovelace',
  country: 'United Kingdom',
  department: 'Engineering',
  job_title: 'Analyst',
  employment_status: 'ACTIVE',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const searchedEmployee = {
  id: 5000,
  employee_code: 'EMP-005000',
  full_name: 'Seed Employee 005000',
  country: 'India',
  department: 'Finance',
  job_title: 'Manager',
  employment_status: 'ACTIVE',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

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

test('entering a search query requests employees with q and uses API results', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url === '/api/v1/employees?limit=50&offset=0' && method === 'GET') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [firstPageEmployee],
          total: 10000,
          limit: 50,
          offset: 0,
        }),
      )
    }
    if (
      url === '/api/v1/employees?limit=50&offset=0&q=EMP-005000' &&
      method === 'GET'
    ) {
      return Promise.resolve(
        jsonResponse(200, {
          items: [searchedEmployee],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      )
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  render(<EmployeeDirectory onSelectEmployee={() => undefined} />)

  expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument()
  expect(screen.queryByText('Seed Employee 005000')).not.toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Search employees'), {
    target: { value: 'EMP-005000' },
  })

  expect(await screen.findByText('Seed Employee 005000')).toBeInTheDocument()
  expect(screen.queryByText('Ada Lovelace')).not.toBeInTheDocument()
  expect(screen.getByText('Showing 1–1 of 1')).toBeInTheDocument()

  const searchCalls = fetchMock.mock.calls.filter(([input, init]) => {
    const { url, method } = requestParts(input as RequestInfo, init as RequestInit)
    return method === 'GET' && String(url).includes('q=EMP-005000')
  })
  expect(searchCalls.length).toBeGreaterThan(0)
})

test('search resets pagination to the first page', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (method !== 'GET' || !url.startsWith('/api/v1/employees')) {
      return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
    }
    if (url === '/api/v1/employees?limit=50&offset=0') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [firstPageEmployee],
          total: 100,
          limit: 50,
          offset: 0,
        }),
      )
    }
    if (url === '/api/v1/employees?limit=50&offset=50') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [
            {
              ...firstPageEmployee,
              id: 51,
              employee_code: 'EMP-000051',
              full_name: 'Page Two Person',
            },
          ],
          total: 100,
          limit: 50,
          offset: 50,
        }),
      )
    }
    if (url === '/api/v1/employees?limit=50&offset=0&q=Hopper') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [
            {
              ...searchedEmployee,
              full_name: 'Grace Hopper',
              employee_code: 'EMP-000080',
            },
          ],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      )
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  render(<EmployeeDirectory onSelectEmployee={() => undefined} />)
  expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(await screen.findByText('Page Two Person')).toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Search employees'), {
    target: { value: 'Hopper' },
  })
  expect(await screen.findByText('Grace Hopper')).toBeInTheDocument()

  const urls = fetchMock.mock.calls.map(([input, init]) => {
    const { url, method } = requestParts(input as RequestInfo, init as RequestInit)
    return method === 'GET' ? url : null
  })
  expect(urls).toContain('/api/v1/employees?limit=50&offset=50')
  expect(urls).toContain('/api/v1/employees?limit=50&offset=0&q=Hopper')
  expect(urls).not.toContain('/api/v1/employees?limit=50&offset=50&q=Hopper')
})

test('pagination uses the filtered API total', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url === '/api/v1/employees?limit=50&offset=0' && method === 'GET') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [firstPageEmployee],
          total: 10000,
          limit: 50,
          offset: 0,
        }),
      )
    }
    if (url === '/api/v1/employees?limit=50&offset=0&q=Ada' && method === 'GET') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [firstPageEmployee],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      )
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  render(<EmployeeDirectory onSelectEmployee={() => undefined} />)
  expect(await screen.findByText('Showing 1–1 of 10000')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Next' })).toBeEnabled()

  fireEvent.change(screen.getByLabelText('Search employees'), {
    target: { value: 'Ada' },
  })

  expect(await screen.findByText('Showing 1–1 of 1')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
})

const inactiveOne = {
  ...firstPageEmployee,
  id: 2,
  employee_code: 'EMP-000010',
  full_name: 'Inactive One',
  employment_status: 'INACTIVE',
}

const inactiveTwo = {
  ...firstPageEmployee,
  id: 3,
  employee_code: 'EMP-000020',
  full_name: 'Inactive Two',
  employment_status: 'INACTIVE',
}

const inactiveThree = {
  ...firstPageEmployee,
  id: 4,
  employee_code: 'EMP-000030',
  full_name: 'Inactive Three',
  employment_status: 'INACTIVE',
}

test('selecting INACTIVE requests status=INACTIVE and uses API results', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url === '/api/v1/employees?limit=50&offset=0' && method === 'GET') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [firstPageEmployee, inactiveOne],
          total: 10000,
          limit: 50,
          offset: 0,
        }),
      )
    }
    if (
      url === '/api/v1/employees?limit=50&offset=0&status=INACTIVE' &&
      method === 'GET'
    ) {
      return Promise.resolve(
        jsonResponse(200, {
          items: [inactiveOne, inactiveTwo, inactiveThree],
          total: 3,
          limit: 50,
          offset: 0,
        }),
      )
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  render(<EmployeeDirectory onSelectEmployee={() => undefined} />)
  expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Inactive' }))

  expect(await screen.findByText('Inactive One')).toBeInTheDocument()
  expect(screen.getByText('Inactive Two')).toBeInTheDocument()
  expect(screen.getByText('Inactive Three')).toBeInTheDocument()
  expect(screen.queryByText('Ada Lovelace')).not.toBeInTheDocument()
  expect(screen.getByText('Showing 1–3 of 3')).toBeInTheDocument()
  expect(screen.queryByText('Showing 1–50 of 10000')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
})

test('selecting ACTIVE requests status=ACTIVE', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url === '/api/v1/employees?limit=50&offset=0' && method === 'GET') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [firstPageEmployee],
          total: 2,
          limit: 50,
          offset: 0,
        }),
      )
    }
    if (
      url === '/api/v1/employees?limit=50&offset=0&status=ACTIVE' &&
      method === 'GET'
    ) {
      return Promise.resolve(
        jsonResponse(200, {
          items: [firstPageEmployee],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      )
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  render(<EmployeeDirectory onSelectEmployee={() => undefined} />)
  expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Active' }))
  expect(await screen.findByText('Showing 1–1 of 1')).toBeInTheDocument()

  const urls = fetchMock.mock.calls.map(([input, init]) => {
    const { url, method } = requestParts(input as RequestInfo, init as RequestInit)
    return method === 'GET' ? url : null
  })
  expect(urls).toContain('/api/v1/employees?limit=50&offset=0&status=ACTIVE')
})

test('changing status resets pagination to the first page', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (method !== 'GET' || !url.startsWith('/api/v1/employees')) {
      return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
    }
    if (url === '/api/v1/employees?limit=50&offset=0') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [firstPageEmployee],
          total: 100,
          limit: 50,
          offset: 0,
        }),
      )
    }
    if (url === '/api/v1/employees?limit=50&offset=50') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [
            {
              ...firstPageEmployee,
              id: 51,
              employee_code: 'EMP-000051',
              full_name: 'Page Two Person',
            },
          ],
          total: 100,
          limit: 50,
          offset: 50,
        }),
      )
    }
    if (url === '/api/v1/employees?limit=50&offset=0&status=INACTIVE') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [inactiveOne],
          total: 3,
          limit: 50,
          offset: 0,
        }),
      )
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  render(<EmployeeDirectory onSelectEmployee={() => undefined} />)
  expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(await screen.findByText('Page Two Person')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Inactive' }))
  expect(await screen.findByText('Inactive One')).toBeInTheDocument()

  const urls = fetchMock.mock.calls.map(([input, init]) => {
    const { url, method } = requestParts(input as RequestInfo, init as RequestInit)
    return method === 'GET' ? url : null
  })
  expect(urls).toContain('/api/v1/employees?limit=50&offset=50')
  expect(urls).toContain('/api/v1/employees?limit=50&offset=0&status=INACTIVE')
  expect(urls).not.toContain(
    '/api/v1/employees?limit=50&offset=50&status=INACTIVE',
  )
})

test('search and status are requested together and reset pagination', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (method !== 'GET' || !url.startsWith('/api/v1/employees')) {
      return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
    }
    if (url === '/api/v1/employees?limit=50&offset=0') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [firstPageEmployee],
          total: 100,
          limit: 50,
          offset: 0,
        }),
      )
    }
    if (url === '/api/v1/employees?limit=50&offset=50') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [
            {
              ...firstPageEmployee,
              id: 51,
              employee_code: 'EMP-000051',
              full_name: 'Page Two Person',
            },
          ],
          total: 100,
          limit: 50,
          offset: 50,
        }),
      )
    }
    if (url === '/api/v1/employees?limit=50&offset=0&q=1000') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [
            {
              ...firstPageEmployee,
              id: 80,
              employee_code: 'EMP-010000',
              full_name: 'Seed Employee 010000',
            },
          ],
          total: 2,
          limit: 50,
          offset: 0,
        }),
      )
    }
    if (url === '/api/v1/employees?limit=50&offset=0&q=1000&status=INACTIVE') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [
            {
              ...inactiveOne,
              employee_code: 'EMP-001000',
              full_name: 'Seed Employee 001000',
            },
          ],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      )
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  render(<EmployeeDirectory onSelectEmployee={() => undefined} />)
  expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(await screen.findByText('Page Two Person')).toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Search employees'), {
    target: { value: '1000' },
  })
  expect(await screen.findByText('Seed Employee 010000')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: 'Inactive' }))

  expect(await screen.findByText('Seed Employee 001000')).toBeInTheDocument()
  expect(screen.getByText('Showing 1–1 of 1')).toBeInTheDocument()

  const urls = fetchMock.mock.calls.map(([input, init]) => {
    const { url, method } = requestParts(input as RequestInfo, init as RequestInit)
    return method === 'GET' ? url : null
  })
  expect(urls).toContain(
    '/api/v1/employees?limit=50&offset=0&q=1000&status=INACTIVE',
  )
  expect(urls).not.toContain(
    '/api/v1/employees?limit=50&offset=50&q=1000&status=INACTIVE',
  )
})

test('search encodes percent, underscore, and backslash in q', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (method !== 'GET' || !url.startsWith('/api/v1/employees')) {
      return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
    }
    if (url === '/api/v1/employees?limit=50&offset=0') {
      return Promise.resolve(
        jsonResponse(200, {
          items: [firstPageEmployee],
          total: 1,
          limit: 50,
          offset: 0,
        }),
      )
    }
    return Promise.resolve(
      jsonResponse(200, {
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      }),
    )
  })

  render(<EmployeeDirectory onSelectEmployee={() => undefined} />)
  expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Search employees'), {
    target: { value: '%_\\' },
  })
  expect(await screen.findByText('No employees match the current filters.')).toBeInTheDocument()

  const urls = fetchMock.mock.calls.map(([input, init]) => {
    const { url, method } = requestParts(input as RequestInfo, init as RequestInit)
    return method === 'GET' ? url : null
  })
  expect(urls).toContain('/api/v1/employees?limit=50&offset=0&q=%25_%5C')
})
