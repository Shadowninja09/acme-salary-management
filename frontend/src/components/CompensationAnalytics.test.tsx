import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { jsonResponse } from '../test/http'
import { CompensationAnalyticsView } from './CompensationAnalytics'
import type { CompensationAnalytics } from '../types/analytics'

const fetchMock = vi.fn()

function emptyAnalytics(reportingDate: string): CompensationAnalytics {
  return {
    reporting_date: reportingDate,
    active_employee_count: 0,
    active_employees_with_salary: 0,
    active_employees_without_salary: 0,
    salary_summary: [],
    by_department: [],
    by_country: [],
  }
}

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

test('renders empty-data copy from a valid empty analytics response', async () => {
  fetchMock.mockImplementation((input: RequestInfo) => {
    const url = String(input)
    const date = new URL(url, 'http://frontend.test').searchParams.get('date') ?? ''
    return Promise.resolve(jsonResponse(200, emptyAnalytics(date)))
  })

  render(<CompensationAnalyticsView />)

  const dateInput = screen.getByLabelText('Reporting date') as HTMLInputElement
  expect(dateInput).toHaveValue()
  expect(dateInput.value).toMatch(/^\d{4}-\d{2}-\d{2}$/)

  expect(
    await screen.findByText('No applicable salaries on this reporting date.'),
  ).toBeInTheDocument()
  expect(
    screen.getByText('No department salary groups on this reporting date.'),
  ).toBeInTheDocument()
  expect(
    screen.getByText('No country salary groups on this reporting date.'),
  ).toBeInTheDocument()
  expect(screen.getByText('Active Employees').parentElement).toHaveTextContent('0')
  expect(
    screen.getByRole('img', { name: 'No active employees on this reporting date.' }),
  ).toBeInTheDocument()

  expect(fetchMock).toHaveBeenCalled()
  const requestedUrl = String(fetchMock.mock.calls[0]?.[0])
  expect(requestedUrl).toBe(
    `/api/v1/analytics/compensation?date=${encodeURIComponent(dateInput.value)}`,
  )
  const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
  expect(init.method).toBe('GET')
})

test('shows an error when the analytics request fails', async () => {
  fetchMock.mockResolvedValue(
    jsonResponse(500, { detail: 'Compensation analytics could not be loaded.' }),
  )

  render(<CompensationAnalyticsView />)

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Compensation analytics could not be loaded.',
  )
  expect(
    screen.queryByText('No applicable salaries on this reporting date.'),
  ).not.toBeInTheDocument()
  expect(screen.getByLabelText('Reporting date')).toBeInTheDocument()
})
