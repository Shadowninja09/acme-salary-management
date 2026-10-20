import { useEffect, useId, useMemo, useState } from 'react'
import { getCompensationAnalytics } from '../api/analytics'
import { ApiError } from '../api/client'
import {
  formatCount,
  formatIsoDate,
  formatMoney,
  formatPayFrequency,
} from '../format'
import type {
  CompensationAnalytics as CompensationAnalyticsResult,
  CompensationCountryGroup,
  CompensationDepartmentGroup,
  CompensationSalaryGroup,
} from '../types/analytics'

function localIsoDate(value: Date = new Date()): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function parseAmount(value: string): number {
  const amount = Number(value)
  return Number.isFinite(amount) && amount > 0 ? amount : 0
}

function headcountBy<T extends { employee_count: number }>(
  rows: T[],
  nameOf: (row: T) => string,
): { label: string; value: number }[] {
  const totals = new Map<string, number>()
  for (const row of rows) {
    const name = nameOf(row)
    totals.set(name, (totals.get(name) ?? 0) + row.employee_count)
  }
  return [...totals.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((left, right) => right.value - left.value || left.label.localeCompare(right.label))
}

function groupKey(group: CompensationSalaryGroup): string {
  return `${group.currency}-${group.pay_frequency}`
}

export function CompensationAnalyticsView() {
  const [reportingDate, setReportingDate] = useState(localIsoDate)
  const [refreshToken, setRefreshToken] = useState(0)
  const [result, setResult] = useState<CompensationAnalyticsResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    if (!reportingDate) {
      return
    }

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
  }, [reportingDate, refreshToken])

  const departmentCounts = useMemo(
    () => (result ? headcountBy(result.by_department, (row) => row.department) : []),
    [result],
  )
  const countryCounts = useMemo(
    () => (result ? headcountBy(result.by_country, (row) => row.country) : []),
    [result],
  )

  const showResult = Boolean(result && reportingDate && !error)
  const snapshotLabel = reportingDate
    ? loading && result
      ? `Updating snapshot for ${formatIsoDate(reportingDate)}…`
      : `Compensation snapshot for ${formatIsoDate(reportingDate)}`
    : 'Select a reporting date.'
  const displayedDate = result ? formatIsoDate(result.reporting_date) : null
  const showingPreviousSnapshot =
    loading && result !== null && result.reporting_date !== reportingDate

  return (
    <section className="analytics">
      <header className="page-head">
        <div>
          <h1>Compensation Analytics</h1>
          <p>{snapshotLabel}</p>
        </div>
        <div className="page-head-controls">
          <label className="field-label" htmlFor="reporting-date">
            Reporting date
            <input
              className="field-control"
              id="reporting-date"
              name="reporting_date"
              type="date"
              value={reportingDate}
              onChange={(event) => {
                const nextDate = event.target.value
                setReportingDate(nextDate)
                if (!nextDate) {
                  setResult(null)
                  setError(new ApiError(422, 'Select a reporting date.'))
                  setLoading(false)
                }
              }}
            />
          </label>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setRefreshToken((current) => current + 1)}
            disabled={loading || !reportingDate}
          >
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </header>

      {loading && reportingDate && !result ? (
        <p className="workspace-status" role="status">
          Loading compensation analytics…
        </p>
      ) : null}

      {error ? (
        <p className="status-banner status-banner-error" role="alert">
          {error.message}
        </p>
      ) : null}

      {showResult && result ? (
        <div
          className={loading ? 'analytics-body is-updating' : 'analytics-body'}
          aria-busy={loading}
        >
          {showingPreviousSnapshot && displayedDate ? (
            <p className="workspace-status" role="status">
              Showing {displayedDate} until the new snapshot arrives.
            </p>
          ) : null}

          <div className="kpi-coverage">
            <div className="kpi-row">
              <article className="kpi-card">
                <p className="kpi-label">Active Employees</p>
                <p className="kpi-value">{formatCount(result.active_employee_count)}</p>
              </article>
              <article className="kpi-card">
                <p className="kpi-label">With Salary</p>
                <p className="kpi-value">{formatCount(result.active_employees_with_salary)}</p>
              </article>
              <article className="kpi-card">
                <p className="kpi-label">Without Salary</p>
                <p className="kpi-value">{formatCount(result.active_employees_without_salary)}</p>
              </article>
            </div>
            <SalaryCoverageChart
              active={result.active_employee_count}
              withSalary={result.active_employees_with_salary}
              withoutSalary={result.active_employees_without_salary}
            />
          </div>

          <div className="chart-grid">
            <CountBarChart
              title="Employees with salary by department"
              description="Headcount of active employees with an applicable salary, grouped by department."
              items={departmentCounts}
              emptyLabel="No department salary groups on this reporting date."
            />
            <CountBarChart
              title="Employees with salary by country"
              description="Headcount of active employees with an applicable salary, grouped by country."
              items={countryCounts}
              emptyLabel="No country salary groups on this reporting date."
            />
          </div>

          <section className="chart-block" aria-labelledby="salary-charts-heading">
            <h2 id="salary-charts-heading">Salary by currency and pay frequency</h2>
            {result.salary_summary.length === 0 ? (
              <p className="empty-note" role="status">
                No applicable salaries on this reporting date.
              </p>
            ) : (
              <div className="salary-charts">
                {result.salary_summary.map((group) => (
                  <SalaryRangeChart key={groupKey(group)} group={group} />
                ))}
              </div>
            )}
          </section>

          <SalaryFigures
            salarySummary={result.salary_summary}
            departments={result.by_department}
            countries={result.by_country}
          />
        </div>
      ) : null}
    </section>
  )
}

function SalaryCoverageChart({
  active,
  withSalary,
  withoutSalary,
}: {
  active: number
  withSalary: number
  withoutSalary: number
}) {
  const titleId = useId()
  const size = 168
  const stroke = 16
  const center = size / 2
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const withShare = active > 0 ? Math.min(withSalary, active) / active : 0
  const withLength = withShare * circumference
  const percent = active > 0 ? Math.round(withShare * 100) : null
  const description =
    active <= 0
      ? 'No active employees on this reporting date.'
      : `${formatCount(withSalary)} of ${formatCount(active)} active employees have an applicable salary (${percent}%).`

  return (
    <section className="chart-block coverage-card" aria-labelledby={titleId}>
      <h2 id={titleId}>Salary coverage</h2>
      <div className="coverage-layout">
        <div className="coverage-donut">
          <svg
            className="chart-svg"
            viewBox={`0 0 ${size} ${size}`}
            role="img"
            aria-label={description}
          >
            <g transform={`rotate(-90 ${center} ${center})`}>
              <circle
                className="coverage-track"
                cx={center}
                cy={center}
                r={radius}
                fill="none"
                strokeWidth={stroke}
              />
              {withLength > 0 ? (
                <circle
                  className="coverage-arc"
                  cx={center}
                  cy={center}
                  r={radius}
                  fill="none"
                  strokeWidth={stroke}
                  strokeDasharray={`${withLength} ${circumference - withLength}`}
                />
              ) : null}
            </g>
          </svg>
          <div className="coverage-center" aria-hidden="true">
            <p className="coverage-percent">{percent === null ? '—' : `${percent}%`}</p>
            <p className="coverage-center-label">with salary</p>
          </div>
        </div>
        <ul className="coverage-legend">
          <li>
            <span className="coverage-swatch coverage-swatch-with" aria-hidden="true" />
            <span>With salary</span>
            <span className="coverage-legend-count">{formatCount(withSalary)}</span>
          </li>
          <li>
            <span className="coverage-swatch coverage-swatch-without" aria-hidden="true" />
            <span>Without salary</span>
            <span className="coverage-legend-count">{formatCount(withoutSalary)}</span>
          </li>
        </ul>
      </div>
    </section>
  )
}

function CountBarChart({
  title,
  description,
  items,
  emptyLabel,
}: {
  title: string
  description: string
  items: { label: string; value: number }[]
  emptyLabel: string
}) {
  const titleId = useId()
  const descId = useId()
  const maximum = items.reduce((highest, item) => Math.max(highest, item.value), 0)

  return (
    <section className="chart-block" aria-labelledby={titleId}>
      <h2 id={titleId}>{title}</h2>
      <p id={descId} className="visually-hidden">
        {description}
      </p>
      {items.length === 0 ? (
        <p className="empty-note" role="status">
          {emptyLabel}
        </p>
      ) : (
        <figure className="chart-figure">
          <ul className="count-bars" aria-labelledby={`${titleId} ${descId}`}>
            {items.map((item) => {
              const widthPercent = maximum > 0 ? (item.value / maximum) * 100 : 0
              return (
                <li key={item.label} className="count-bar-row">
                  <span className="count-bar-label">{item.label}</span>
                  <span className="count-bar-track">
                    <span
                      className="count-bar-fill"
                      style={{
                        width: `${widthPercent}%`,
                        minWidth: item.value > 0 ? '2px' : 0,
                      }}
                    />
                  </span>
                  <span className="count-bar-value">{formatCount(item.value)}</span>
                </li>
              )
            })}
          </ul>
        </figure>
      )}
    </section>
  )
}

function SalaryRangeChart({ group }: { group: CompensationSalaryGroup }) {
  const titleId = useId()
  const min = parseAmount(group.minimum_salary)
  const average = parseAmount(group.average_salary)
  const max = parseAmount(group.maximum_salary)
  const scale = Math.max(min, average, max)
  const width = 560
  const left = 16
  const right = 16
  const plotWidth = width - left - right
  const height = 40
  const trackY = 20
  const frequency = formatPayFrequency(group.pay_frequency)
  const title = `${group.currency} · ${frequency}`

  function xOf(amount: number): number {
    if (scale <= 0) {
      return left
    }
    return left + (amount / scale) * plotWidth
  }

  const minX = xOf(min)
  const avgX = xOf(average)
  const maxX = xOf(max)
  const rangeStart = Math.min(minX, maxX)
  const rangeWidth = Math.max(Math.abs(maxX - minX), scale > 0 ? 2 : 0)

  return (
    <figure className="chart-figure salary-figure" aria-labelledby={titleId}>
      <figcaption id={titleId} className="salary-figure-caption">
        <span>{title}</span>
        <span>
          {formatCount(group.employee_count)}{' '}
          {group.employee_count === 1 ? 'employee' : 'employees'}
        </span>
      </figcaption>
      <dl className="salary-legend">
        <div>
          <dt>Min</dt>
          <dd>
            {formatMoney(group.minimum_salary)} {group.currency}
          </dd>
        </div>
        <div>
          <dt>Average</dt>
          <dd>
            {formatMoney(group.average_salary)} {group.currency}
          </dd>
        </div>
        <div>
          <dt>Max</dt>
          <dd>
            {formatMoney(group.maximum_salary)} {group.currency}
          </dd>
        </div>
      </dl>
      {scale <= 0 ? (
        <p className="empty-note" role="status">
          No salary amounts in this group.
        </p>
      ) : (
        <svg
          className="chart-svg salary-range-svg"
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`${title}: minimum ${formatMoney(group.minimum_salary)} ${group.currency}, average ${formatMoney(group.average_salary)} ${group.currency}, maximum ${formatMoney(group.maximum_salary)} ${group.currency}.`}
        >
          <line className="chart-axis" x1={left} y1={trackY} x2={left + plotWidth} y2={trackY} />
          <rect
            className="chart-range"
            x={rangeStart}
            y={trackY - 6}
            width={rangeWidth}
            height={12}
            rx={6}
          />
          <circle className="chart-marker" cx={avgX} cy={trackY} r={6} />
        </svg>
      )}
    </figure>
  )
}

function SalaryFigures({
  salarySummary,
  departments,
  countries,
}: {
  salarySummary: CompensationSalaryGroup[]
  departments: CompensationDepartmentGroup[]
  countries: CompensationCountryGroup[]
}) {
  return (
    <div className="figure-details">
      <details>
        <summary>Salary figures</summary>
        {salarySummary.length === 0 ? (
          <p className="empty-note" role="status">
            No salary groups to list.
          </p>
        ) : (
          <div className="table-wrap">
            <table>
              <caption className="visually-hidden">
                Average, minimum, and maximum salary for each currency and pay frequency.
              </caption>
              <thead>
                <tr>
                  <th>Currency</th>
                  <th>Pay frequency</th>
                  <th className="num">Employees</th>
                  <th className="num">Average</th>
                  <th className="num">Minimum</th>
                  <th className="num">Maximum</th>
                </tr>
              </thead>
              <tbody>
                {salarySummary.map((group) => (
                  <tr key={groupKey(group)}>
                    <td>{group.currency}</td>
                    <td>{formatPayFrequency(group.pay_frequency)}</td>
                    <td className="num">{formatCount(group.employee_count)}</td>
                    <td className="num">{formatMoney(group.average_salary)}</td>
                    <td className="num">{formatMoney(group.minimum_salary)}</td>
                    <td className="num">{formatMoney(group.maximum_salary)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>
      <details>
        <summary>Department figures</summary>
        <DimensionTable
          caption="Salary statistics by department, currency, and pay frequency."
          rows={departments}
          nameHeader="Department"
          nameOf={(row) => row.department}
          emptyLabel="No department salary groups to list."
        />
      </details>
      <details>
        <summary>Country figures</summary>
        <DimensionTable
          caption="Salary statistics by country, currency, and pay frequency."
          rows={countries}
          nameHeader="Country"
          nameOf={(row) => row.country}
          emptyLabel="No country salary groups to list."
        />
      </details>
    </div>
  )
}

function DimensionTable<T extends CompensationSalaryGroup>({
  caption,
  rows,
  nameHeader,
  nameOf,
  emptyLabel,
}: {
  caption: string
  rows: T[]
  nameHeader: string
  nameOf: (row: T) => string
  emptyLabel: string
}) {
  if (rows.length === 0) {
    return (
      <p className="empty-note" role="status">
        {emptyLabel}
      </p>
    )
  }

  return (
    <div className="table-wrap">
      <table>
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            <th>{nameHeader}</th>
            <th>Currency</th>
            <th>Pay frequency</th>
            <th className="num">Employees</th>
            <th className="num">Average</th>
            <th className="num">Minimum</th>
            <th className="num">Maximum</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${nameOf(row)}-${groupKey(row)}`}>
              <td>{nameOf(row)}</td>
              <td>{row.currency}</td>
              <td>{formatPayFrequency(row.pay_frequency)}</td>
              <td className="num">{formatCount(row.employee_count)}</td>
              <td className="num">{formatMoney(row.average_salary)}</td>
              <td className="num">{formatMoney(row.minimum_salary)}</td>
              <td className="num">{formatMoney(row.maximum_salary)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
