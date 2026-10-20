import { useEffect, useMemo, useState } from 'react'
import { ApiError } from '../api/client'
import { listEmployees } from '../api/employees'
import {
  EMPLOYMENT_STATUSES,
  type Employee,
  type EmployeeList,
  type EmploymentStatus,
} from '../types/employee'

const PAGE_SIZE = 50

type StatusFilter = 'ALL' | EmploymentStatus

function matchesSearch(employee: Employee, query: string): boolean {
  if (!query) {
    return true
  }
  const haystack = [
    employee.employee_code,
    employee.full_name,
    employee.country,
    employee.department,
    employee.job_title,
  ]
    .join(' ')
    .toLowerCase()
  return haystack.includes(query)
}

function formatStatus(status: EmploymentStatus): string {
  return status === 'ACTIVE' ? 'Active' : 'Inactive'
}

function isNestedInteractive(target: EventTarget | null): boolean {
  return (
    target instanceof Element &&
    target.closest('a, button, input, select, textarea, label') !== null
  )
}

type EmployeeDirectoryProps = {
  onSelectEmployee: (employeeId: number) => void
}

export function EmployeeDirectory({ onSelectEmployee }: EmployeeDirectoryProps) {
  const [offset, setOffset] = useState(0)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL')
  const [list, setList] = useState<EmployeeList | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const result = await listEmployees(
          { limit: PAGE_SIZE, offset },
          controller.signal,
        )
        if (!cancelled) {
          setList(result)
        }
      } catch (cause) {
        if (cancelled || (cause instanceof DOMException && cause.name === 'AbortError')) {
          return
        }
        if (!cancelled) {
          setList(null)
          setError(cause instanceof ApiError ? cause : new ApiError(0, 'Unexpected error'))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [offset])

  const visibleEmployees = useMemo(() => {
    const items = list?.items ?? []
    const query = search.trim().toLowerCase()
    return items.filter((employee) => {
      const statusOk =
        statusFilter === 'ALL' || employee.employment_status === statusFilter
      return statusOk && matchesSearch(employee, query)
    })
  }, [list, search, statusFilter])

  const total = list?.total ?? 0
  const limit = list?.limit ?? PAGE_SIZE
  const currentOffset = list?.offset ?? offset
  const from = total === 0 ? 0 : currentOffset + 1
  const to = Math.min(currentOffset + (list?.items.length ?? 0), total)
  const hasPrevious = currentOffset > 0
  const hasNext = currentOffset + limit < total
  const rangeLabel =
    total === 0 ? 'No employees' : `Showing ${from}–${to} of ${total}`

  return (
    <section className="directory" aria-labelledby="directory-heading">
      <header className="page-head">
        <div>
          <h1 id="directory-heading">Employees</h1>
          <p>
            Paginated directory of HR records. Search and status filters apply to
            the current page only.
          </p>
        </div>
      </header>

      <div className="directory-tools">
        <label className="search-field" htmlFor="employee-search">
          <span>Search this page</span>
          <input
            id="employee-search"
            name="search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            autoComplete="off"
            placeholder="Name, code, country, department, or title"
          />
        </label>
        <div className="segmented" role="group" aria-label="Employment status">
          <button
            type="button"
            className={statusFilter === 'ALL' ? 'is-active' : undefined}
            aria-pressed={statusFilter === 'ALL'}
            onClick={() => setStatusFilter('ALL')}
          >
            All
          </button>
          {EMPLOYMENT_STATUSES.map((status) => (
            <button
              key={status}
              type="button"
              className={statusFilter === status ? 'is-active' : undefined}
              aria-pressed={statusFilter === status}
              onClick={() => setStatusFilter(status)}
            >
              {formatStatus(status)}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="workspace-status" role="status">
          Loading employees…
        </p>
      ) : null}

      {error ? (
        <p className="status-banner status-banner-error" role="alert">
          {error.message}
        </p>
      ) : null}

      {!loading && !error && list && list.items.length === 0 ? (
        <p className="empty-note" role="status">
          No employees are available.
        </p>
      ) : null}

      {!loading &&
      !error &&
      list &&
      list.items.length > 0 &&
      visibleEmployees.length === 0 ? (
        <p className="empty-note" role="status">
          No employees on this page match the current search or status filter.
        </p>
      ) : null}

      {!loading && !error && visibleEmployees.length > 0 ? (
        <ul className="people-list">
          {visibleEmployees.map((employee) => (
            <li key={employee.id}>
              <article
                className="people-row"
                role="button"
                tabIndex={0}
                aria-label={`View details for ${employee.full_name}`}
                onClick={(event) => {
                  if (isNestedInteractive(event.target)) {
                    return
                  }
                  onSelectEmployee(employee.id)
                }}
                onKeyDown={(event) => {
                  if (event.key !== 'Enter' && event.key !== ' ') {
                    return
                  }
                  if (isNestedInteractive(event.target)) {
                    return
                  }
                  event.preventDefault()
                  onSelectEmployee(employee.id)
                }}
              >
                <div className="people-identity">
                  <p className="people-name">{employee.full_name}</p>
                  <p>
                    {employee.employee_code}
                    <span aria-hidden="true"> · </span>
                    {employee.job_title}
                    <span aria-hidden="true"> · </span>
                    {employee.department}
                    <span aria-hidden="true"> · </span>
                    {employee.country}
                  </p>
                </div>
                <span
                  className={
                    employee.employment_status === 'ACTIVE'
                      ? 'status-pill status-pill-active'
                      : 'status-pill status-pill-inactive'
                  }
                >
                  {formatStatus(employee.employment_status)}
                </span>
              </article>
            </li>
          ))}
        </ul>
      ) : null}

      <nav className="pagination" aria-label="Employee list pagination">
        <p className="pagination-summary">{rangeLabel}</p>
        <div className="pagination-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setOffset(Math.max(0, currentOffset - limit))}
            disabled={loading || !hasPrevious}
          >
            Previous
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setOffset(currentOffset + limit)}
            disabled={loading || !hasNext}
          >
            Next
          </button>
        </div>
      </nav>
    </section>
  )
}
