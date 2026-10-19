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
      <header className="directory-header">
        <h1 id="directory-heading">Employee directory</h1>
        <p>
          Browse HR employee records. Use pagination to move through the
          directory. Search and status filters apply to the employees on the
          current page.
        </p>
      </header>

      <div className="directory-controls">
        <label htmlFor="employee-search">
          Search this page
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
        <label htmlFor="employment-status">
          Employment status
          <select
            id="employment-status"
            name="employment_status"
            value={statusFilter}
            onChange={(event) =>
              setStatusFilter(event.target.value as StatusFilter)
            }
          >
            <option value="ALL">All statuses</option>
            {EMPLOYMENT_STATUSES.map((status) => (
              <option key={status} value={status}>
                {formatStatus(status)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading ? (
        <p className="directory-status" role="status">
          Loading employees…
        </p>
      ) : null}

      {error ? (
        <p className="directory-status directory-error" role="alert">
          {error.message}
        </p>
      ) : null}

      {!loading && !error && list && list.items.length === 0 ? (
        <p className="directory-status" role="status">
          No employees are available.
        </p>
      ) : null}

      {!loading &&
      !error &&
      list &&
      list.items.length > 0 &&
      visibleEmployees.length === 0 ? (
        <p className="directory-status" role="status">
          No employees on this page match the current search or status filter.
        </p>
      ) : null}

      {!loading && !error && visibleEmployees.length > 0 ? (
        <div className="table-wrap">
          <table>
            <caption className="visually-hidden">
              Employees on the current page
            </caption>
            <thead>
              <tr>
                <th scope="col">Employee code</th>
                <th scope="col">Name</th>
                <th scope="col">Country</th>
                <th scope="col">Department</th>
                <th scope="col">Job title</th>
                <th scope="col">Status</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleEmployees.map((employee) => (
                <tr key={employee.id}>
                  <td>{employee.employee_code}</td>
                  <td>{employee.full_name}</td>
                  <td>{employee.country}</td>
                  <td>{employee.department}</td>
                  <td>{employee.job_title}</td>
                  <td>{formatStatus(employee.employment_status)}</td>
                  <td>
                    <button
                      type="button"
                      className="row-action"
                      onClick={() => onSelectEmployee(employee.id)}
                      aria-label={`View details for ${employee.full_name}`}
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <nav className="pagination" aria-label="Employee list pagination">
        <p className="pagination-summary">{rangeLabel}</p>
        <div className="pagination-actions">
          <button
            type="button"
            onClick={() => setOffset(Math.max(0, currentOffset - limit))}
            disabled={loading || !hasPrevious}
          >
            Previous
          </button>
          <button
            type="button"
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
