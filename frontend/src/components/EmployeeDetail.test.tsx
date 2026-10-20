import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { jsonResponse } from '../test/http'
import { EmployeeDetail } from './EmployeeDetail'

const EMPLOYEE_ID = 41
const fetchMock = vi.fn()

const employee = {
  id: EMPLOYEE_ID,
  employee_code: 'EMP-0041',
  full_name: 'Priya Shah',
  country: 'United Kingdom',
  department: 'Engineering',
  job_title: 'Engineer',
  employment_status: 'ACTIVE',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const existingSalary = {
  id: 9,
  employee_id: EMPLOYEE_ID,
  amount: '3000.00',
  currency: 'GBP',
  pay_frequency: 'MONTHLY',
  effective_from: '2026-01-01',
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

test('create POST success then refresh failure does not report a failed save', async () => {
  let posted = false
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url === `/api/v1/employees/${EMPLOYEE_ID}` && method === 'GET') {
      return Promise.resolve(jsonResponse(200, employee))
    }
    if (url.includes('/salary-corrections') && method === 'GET') {
      return Promise.resolve(jsonResponse(200, []))
    }
    if (url === `/api/v1/employees/${EMPLOYEE_ID}/salaries` && method === 'POST') {
      posted = true
      return Promise.resolve(
        jsonResponse(201, {
          id: 10,
          employee_id: EMPLOYEE_ID,
          amount: '4000.00',
          currency: 'GBP',
          pay_frequency: 'MONTHLY',
          effective_from: '2026-06-01',
        }),
      )
    }
    if (url === `/api/v1/employees/${EMPLOYEE_ID}/salaries` && method === 'GET') {
      if (posted) {
        return Promise.resolve(jsonResponse(500, { detail: 'Lists unavailable' }))
      }
      return Promise.resolve(jsonResponse(200, []))
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  const user = userEvent.setup()
  render(<EmployeeDetail employeeId={EMPLOYEE_ID} onBack={() => undefined} />)

  expect(await screen.findByRole('heading', { name: 'Priya Shah' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Add salary' }))
  await user.type(screen.getByLabelText('Amount'), '4000.00')
  fireEvent.change(screen.getByLabelText('Effective date'), {
    target: { value: '2026-06-01' },
  })
  await user.click(screen.getByRole('button', { name: 'Save salary' }))

  expect(await screen.findByText('Salary record added.')).toBeInTheDocument()
  expect(
    screen.getByText(
      'The salary was saved, but the history lists could not be updated. This page may be out of date.',
    ),
  ).toBeInTheDocument()
  expect(screen.queryByText('The salary could not be saved. Try again.')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Amount')).toHaveValue('')
  expect(screen.getByLabelText('Effective date')).toHaveValue('')

  const postCalls = fetchMock.mock.calls.filter(([input, init]) => {
    const { url, method } = requestParts(input as RequestInfo, init as RequestInit)
    return method === 'POST' && url.includes('/salaries')
  })
  expect(postCalls).toHaveLength(1)
})

test('create POST failure still shows a write error and does not claim success', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url === `/api/v1/employees/${EMPLOYEE_ID}` && method === 'GET') {
      return Promise.resolve(jsonResponse(200, employee))
    }
    if (url.includes('/salary-corrections') && method === 'GET') {
      return Promise.resolve(jsonResponse(200, []))
    }
    if (url === `/api/v1/employees/${EMPLOYEE_ID}/salaries` && method === 'POST') {
      return Promise.resolve(jsonResponse(409, { detail: 'Duplicate' }))
    }
    if (url === `/api/v1/employees/${EMPLOYEE_ID}/salaries` && method === 'GET') {
      return Promise.resolve(jsonResponse(200, []))
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  const user = userEvent.setup()
  render(<EmployeeDetail employeeId={EMPLOYEE_ID} onBack={() => undefined} />)

  expect(await screen.findByRole('heading', { name: 'Priya Shah' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Add salary' }))
  await user.type(screen.getByLabelText('Amount'), '4000.00')
  fireEvent.change(screen.getByLabelText('Effective date'), {
    target: { value: '2026-06-01' },
  })
  await user.click(screen.getByRole('button', { name: 'Save salary' }))

  expect(
    await screen.findByText('A salary record already exists for that effective date.'),
  ).toBeInTheDocument()
  expect(screen.queryByText('Salary record added.')).not.toBeInTheDocument()
  expect(screen.getByLabelText('Amount')).toHaveValue('4000.00')
})

test('correction PATCH success then refresh failure does not report a failed correction', async () => {
  let patched = false
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url === `/api/v1/employees/${EMPLOYEE_ID}` && method === 'GET') {
      return Promise.resolve(jsonResponse(200, employee))
    }
    if (url.includes('/salary-corrections') && method === 'GET') {
      if (patched) {
        return Promise.resolve(jsonResponse(500, { detail: 'Lists unavailable' }))
      }
      return Promise.resolve(jsonResponse(200, []))
    }
    if (url.includes(`/salaries/${existingSalary.id}`) && method === 'PATCH') {
      patched = true
      return Promise.resolve(
        jsonResponse(200, { ...existingSalary, amount: '3200.00' }),
      )
    }
    if (url === `/api/v1/employees/${EMPLOYEE_ID}/salaries` && method === 'GET') {
      return Promise.resolve(jsonResponse(200, [existingSalary]))
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  const user = userEvent.setup()
  render(<EmployeeDetail employeeId={EMPLOYEE_ID} onBack={() => undefined} />)

  expect(await screen.findByRole('heading', { name: 'Priya Shah' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Correct' }))
  await user.type(screen.getByLabelText('Reason'), 'Payroll adjustment')
  await user.click(screen.getByRole('button', { name: 'Save correction' }))

  expect(
    await screen.findByText(
      'The salary change was saved, but the history lists could not be updated. This page may be out of date.',
    ),
  ).toBeInTheDocument()
  expect(screen.queryByText('The salary could not be corrected. Try again.')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Save correction' })).not.toBeInTheDocument()

  const patchCalls = fetchMock.mock.calls.filter(([input, init]) => {
    const { method } = requestParts(input as RequestInfo, init as RequestInit)
    return method === 'PATCH'
  })
  expect(patchCalls).toHaveLength(1)
})

test('correction PATCH failure still shows a write error and does not claim success', async () => {
  fetchMock.mockImplementation((input: RequestInfo, init?: RequestInit) => {
    const { url, method } = requestParts(input, init)
    if (url === `/api/v1/employees/${EMPLOYEE_ID}` && method === 'GET') {
      return Promise.resolve(jsonResponse(200, employee))
    }
    if (url.includes('/salary-corrections') && method === 'GET') {
      return Promise.resolve(jsonResponse(200, []))
    }
    if (url.includes(`/salaries/${existingSalary.id}`) && method === 'PATCH') {
      return Promise.resolve(jsonResponse(422, { detail: 'Invalid' }))
    }
    if (url === `/api/v1/employees/${EMPLOYEE_ID}/salaries` && method === 'GET') {
      return Promise.resolve(jsonResponse(200, [existingSalary]))
    }
    return Promise.resolve(jsonResponse(404, { detail: 'Not found' }))
  })

  const user = userEvent.setup()
  render(<EmployeeDetail employeeId={EMPLOYEE_ID} onBack={() => undefined} />)

  expect(await screen.findByRole('heading', { name: 'Priya Shah' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Correct' }))
  await user.type(screen.getByLabelText('Reason'), 'Payroll adjustment')
  await user.click(screen.getByRole('button', { name: 'Save correction' }))

  expect(
    await screen.findByText(
      'The correction is invalid. Check the amount, currency, pay frequency, date, and required reason.',
    ),
  ).toBeInTheDocument()
  expect(
    screen.queryByText(
      'The salary change was saved, but the history lists could not be updated. This page may be out of date.',
    ),
  ).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save correction' })).toBeEnabled()
})
