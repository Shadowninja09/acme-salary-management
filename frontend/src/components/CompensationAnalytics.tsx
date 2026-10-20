import { useEffect, useState } from 'react'
import { getCompensationAnalytics } from '../api/analytics'
import { ApiError } from '../api/client'
import type {
  CompensationAnalytics as CompensationAnalyticsResult,
  CompensationSalaryGroup,
} from '../types/analytics'

function localIsoDate(value: Date = new Date()): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatPayFrequency(value: string): string {
  return value === 'ANNUAL' ? 'Annual' : 'Monthly'
}

type CompensationAnalyticsProps = {
  onOpenDirectory: () => void
}

export function CompensationAnalyticsView({ onOpenDirectory }: CompensationAnalyticsProps) {
  const [reportingDate, setReportingDate] = useState(localIsoDate)
  const [result, setResult] = useState<CompensationAnalyticsResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const payload = await getCompensationAnalytics(reportingDate, controller.signal)
        if (!cancelled) {
          setResult(payload)
        }
      } catch (cause) {
        if (cancelled || (cause instanceof DOMException && cause.name === 'AbortError')) {
          return
        }
        if (!cancelled) {
          setResult(null)
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
  }, [reportingDate])

  return (
    <section className="analytics">
      <div className="directory-header">
        <h1>Compensation analytics</h1>
        <p>
          Salary statistics for active employees as of the reporting date. Amounts stay in
          their original currency and pay frequency; groups are never combined.
        </p>
      </div>

      <div className="directory-controls">
        <label>
          Reporting date
          <input
            type="date"
            value={reportingDate}
            onChange={(event) => setReportingDate(event.target.value)}
          />
        </label>
        <button type="button" className="row-action" onClick={onOpenDirectory}>
          Employee directory
        </button>
      </div>

      {loading ? (
        <p className="directory-status" role="status">
          Loading compensation analytics…
        </p>
      ) : null}

      {error ? (
        <p className="directory-status directory-error" role="alert">
          {error.message}
        </p>
      ) : null}

      {!loading && !error && result ? (
        <>
          <dl className="detail-fields analytics-counts">
            <div>
              <dt>Reporting date</dt>
              <dd>{result.reporting_date}</dd>
            </div>
            <div>
              <dt>Active employees</dt>
              <dd>{result.active_employee_count}</dd>
            </div>
            <div>
              <dt>With applicable salary</dt>
              <dd>{result.active_employees_with_salary}</dd>
            </div>
            <div>
              <dt>Without applicable salary</dt>
              <dd>{result.active_employees_without_salary}</dd>
            </div>
          </dl>

          <h2 className="detail-subheading">Overall salary summary</h2>
          <SalaryGroupTable
            rows={result.salary_summary.map((group) => ({
              key: `${group.currency}-${group.pay_frequency}`,
              group,
            }))}
            emptyLabel="No applicable salaries on this reporting date."
          />

          <h2 className="detail-subheading">By department</h2>
          <SalaryGroupTable
            dimensionLabel="Department"
            rows={result.by_department.map((group) => ({
              key: `${group.department}-${group.currency}-${group.pay_frequency}`,
              dimension: group.department,
              group,
            }))}
            emptyLabel="No department salary groups on this reporting date."
          />

          <h2 className="detail-subheading">By country</h2>
          <SalaryGroupTable
            dimensionLabel="Country"
            rows={result.by_country.map((group) => ({
              key: `${group.country}-${group.currency}-${group.pay_frequency}`,
              dimension: group.country,
              group,
            }))}
            emptyLabel="No country salary groups on this reporting date."
          />
        </>
      ) : null}
    </section>
  )
}

type SalaryGroupRow = {
  key: string
  dimension?: string
  group: CompensationSalaryGroup
}

function SalaryGroupTable({
  rows,
  emptyLabel,
  dimensionLabel,
}: {
  rows: SalaryGroupRow[]
  emptyLabel: string
  dimensionLabel?: string
}) {
  if (rows.length === 0) {
    return (
      <p className="directory-status" role="status">
        {emptyLabel}
      </p>
    )
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {dimensionLabel ? <th>{dimensionLabel}</th> : null}
            <th>Currency</th>
            <th>Pay frequency</th>
            <th>Employees</th>
            <th>Average</th>
            <th>Minimum</th>
            <th>Maximum</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ key, dimension, group }) => (
            <tr key={key}>
              {dimensionLabel ? <td>{dimension}</td> : null}
              <td>{group.currency}</td>
              <td>{formatPayFrequency(group.pay_frequency)}</td>
              <td>{group.employee_count}</td>
              <td>{group.average_salary}</td>
              <td>{group.minimum_salary}</td>
              <td>{group.maximum_salary}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
