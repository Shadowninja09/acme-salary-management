import { Fragment, useEffect, useState } from 'react'
import { ApiError } from '../api/client'
import { getEmployee } from '../api/employees'
import { listEmployeeSalaries, listEmployeeSalaryCorrections } from '../api/salaries'
import { permittedCurrenciesForCountry } from '../countryCurrency'
import {
  formatIsoDate,
  formatMoney,
  formatPayFrequency,
} from '../format'
import { AddSalaryForm } from './AddSalaryForm'
import { CorrectSalaryForm } from './CorrectSalaryForm'
import type { Employee } from '../types/employee'
import type { Salary, SalaryAuditSnapshot, SalaryCorrectionAudit } from '../types/salary'

const HISTORY_REFRESH_WARNING =
  'The salary change was saved, but the history lists could not be updated. This page may be out of date.'

type EmployeeDetailProps = {
  employeeId: number
  onBack: () => void
}

type SnapshotField = {
  key: keyof SalaryAuditSnapshot
  label: string
  format: (value: string) => string
}

const SNAPSHOT_FIELDS: SnapshotField[] = [
  { key: 'amount', label: 'Amount', format: formatMoney },
  { key: 'currency', label: 'Currency', format: (value) => value },
  { key: 'pay_frequency', label: 'Pay frequency', format: formatPayFrequency },
  { key: 'effective_from', label: 'Effective date', format: formatIsoDate },
]

function todayIsoDate(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function findApplicableSalary(salaries: Salary[], asOf: string): Salary | null {
  let current: Salary | null = null
  for (const salary of salaries) {
    if (salary.effective_from > asOf) {
      continue
    }
    if (
      current === null ||
      salary.effective_from > current.effective_from
    ) {
      current = salary
    }
  }
  return current
}

function formatChangedAt(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function snapshotChanges(oldValues: SalaryAuditSnapshot, newValues: SalaryAuditSnapshot) {
  return SNAPSHOT_FIELDS.filter((field) => oldValues[field.key] !== newValues[field.key]).map(
    (field) => ({
      key: field.key,
      label: field.label,
      from: field.format(oldValues[field.key]),
      to: field.format(newValues[field.key]),
    }),
  )
}

function isLegacyCurrency(country: string, currency: Salary['currency']): boolean {
  const permitted = permittedCurrenciesForCountry(country)
  return permitted.length > 0 && !permitted.includes(currency)
}

export function EmployeeDetail({ employeeId, onBack }: EmployeeDetailProps) {
  const [employee, setEmployee] = useState<Employee | null>(null)
  const [salaries, setSalaries] = useState<Salary[] | null>(null)
  const [corrections, setCorrections] = useState<SalaryCorrectionAudit[] | null>(null)
  const [selectedSalaryId, setSelectedSalaryId] = useState<number | null>(null)
  const [addingSalary, setAddingSalary] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)
  const [historyRefreshError, setHistoryRefreshError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      setEmployee(null)
      setSalaries(null)
      setCorrections(null)
      setAddingSalary(false)
      setHistoryRefreshError(null)
      try {
        const [profile, history, correctionHistory] = await Promise.all([
          getEmployee(employeeId, controller.signal),
          listEmployeeSalaries(employeeId, controller.signal),
          listEmployeeSalaryCorrections(employeeId, controller.signal),
        ])
        if (!cancelled) {
          setEmployee(profile)
          setSalaries(history)
          setCorrections(correctionHistory)
          setSelectedSalaryId(null)
        }
      } catch (cause) {
        if (cancelled || (cause instanceof DOMException && cause.name === 'AbortError')) {
          return
        }
        setError(cause instanceof ApiError ? cause : new ApiError(0, 'Unexpected error'))
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
  }, [employeeId])

  async function refreshHistory(): Promise<boolean> {
    try {
      const [history, correctionHistory] = await Promise.all([
        listEmployeeSalaries(employeeId),
        listEmployeeSalaryCorrections(employeeId),
      ])
      setSalaries(history)
      setCorrections(correctionHistory)
      setSelectedSalaryId((currentId) =>
        currentId !== null && history.some((salary) => salary.id === currentId)
          ? currentId
          : null,
      )
      setHistoryRefreshError(null)
      return true
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') {
        return false
      }
      setHistoryRefreshError(HISTORY_REFRESH_WARNING)
      return false
    }
  }

  const asOf = todayIsoDate()
  const currentSalary = salaries ? findApplicableSalary(salaries, asOf) : null

  function startCorrection(salaryId: number) {
    setAddingSalary(false)
    setSelectedSalaryId(salaryId)
  }

  function startAddSalary() {
    setSelectedSalaryId(null)
    setAddingSalary(true)
  }

  return (
    <section className="detail" aria-labelledby="detail-heading">
      {loading ? (
        <p className="workspace-status" role="status">
          Loading employee details…
        </p>
      ) : null}

      {error ? (
        <p className="status-banner status-banner-error" role="alert">
          {error.message}
        </p>
      ) : null}

      {historyRefreshError ? (
        <p className="status-banner status-banner-error" role="alert">
          {historyRefreshError}
        </p>
      ) : null}

      {!loading && !error && employee ? (
        <>
          <header className="detail-head">
            <button type="button" className="detail-back" onClick={onBack}>
              Back to directory
            </button>
            <div className="detail-head-main">
              <div className="detail-identity">
                <h1 id="detail-heading">{employee.full_name}</h1>
                <p>
                  {employee.job_title}
                  <span aria-hidden="true"> · </span>
                  {employee.department}
                  <span aria-hidden="true"> · </span>
                  {employee.country}
                </p>
                <p className="detail-code">{employee.employee_code}</p>
              </div>
              <span
                className={
                  employee.employment_status === 'ACTIVE'
                    ? 'status-pill status-pill-active'
                    : 'status-pill status-pill-inactive'
                }
              >
                {employee.employment_status === 'ACTIVE' ? 'Active' : 'Inactive'}
              </span>
            </div>
          </header>

          {salaries && salaries.length > 0 ? (
            <section className="current-pay" aria-labelledby="current-pay-heading">
              <h2 id="current-pay-heading">Current compensation</h2>
              {currentSalary ? (
                <>
                  <p className="current-pay-amount">
                    {formatMoney(currentSalary.amount)} {currentSalary.currency}
                  </p>
                  <p className="current-pay-meta">
                    {formatPayFrequency(currentSalary.pay_frequency)}
                    <span aria-hidden="true"> · </span>
                    Effective {formatIsoDate(currentSalary.effective_from)}
                    {isLegacyCurrency(employee.country, currentSalary.currency) ? (
                      <>
                        <span aria-hidden="true"> · </span>
                        Legacy currency
                      </>
                    ) : null}
                  </p>
                </>
              ) : (
                <p className="current-pay-empty">No salary is in effect today.</p>
              )}
            </section>
          ) : null}

          <section className="workspace-section" aria-labelledby="salary-history-heading">
            <div className="section-toolbar">
              <div className="section-copy">
                <h2 id="salary-history-heading">Salary history</h2>
                <p>Newest effective date first. Corrections update the same record.</p>
              </div>
              {addingSalary ? null : (
                <button type="button" className="btn btn-secondary" onClick={startAddSalary}>
                  Add salary
                </button>
              )}
            </div>

            {addingSalary ? (
              <AddSalaryForm
                key={employee.id}
                employeeId={employee.id}
                country={employee.country}
                onCreated={() => refreshHistory()}
                onCancel={() => setAddingSalary(false)}
              />
            ) : null}

            {salaries && salaries.length === 0 ? (
              <p className="empty-note" role="status">
                No salary records.
              </p>
            ) : null}

            {salaries && salaries.length > 0 ? (
              <div className="salary-history">
                <table>
                  <caption className="visually-hidden">
                    Salary history, newest effective date first
                  </caption>
                  <thead>
                    <tr>
                      <th>Pay</th>
                      <th>Frequency</th>
                      <th>Effective date</th>
                      <th>
                        <span className="visually-hidden">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {salaries.map((salary) => {
                      const isCurrent = currentSalary?.id === salary.id
                      const legacy = isLegacyCurrency(employee.country, salary.currency)
                      const isSelected = selectedSalaryId === salary.id
                      return (
                        <Fragment key={salary.id}>
                          <tr className={isSelected ? 'is-selected' : undefined}>
                            <td data-label="Pay">
                              <span className="salary-pay">
                                {formatMoney(salary.amount)} {salary.currency}
                              </span>
                              {isCurrent || legacy ? (
                                <span className="salary-flags">
                                  {isCurrent ? <span className="record-flag">Current</span> : null}
                                  {legacy ? (
                                    <span className="record-flag record-flag-muted">
                                      Legacy currency
                                    </span>
                                  ) : null}
                                </span>
                              ) : null}
                            </td>
                            <td data-label="Frequency">
                              {formatPayFrequency(salary.pay_frequency)}
                            </td>
                            <td data-label="Effective date">
                              {formatIsoDate(salary.effective_from)}
                            </td>
                            <td>
                              <button
                                type="button"
                                className="btn btn-ghost"
                                onClick={() => startCorrection(salary.id)}
                                aria-pressed={isSelected}
                              >
                                Edit salary
                              </button>
                            </td>
                          </tr>
                          {isSelected ? (
                            <tr className="salary-correct-row">
                              <td colSpan={4}>
                                <CorrectSalaryForm
                                  key={salary.id}
                                  employeeId={employee.id}
                                  country={employee.country}
                                  salary={salary}
                                  onCorrected={async () => {
                                    await refreshHistory()
                                    setSelectedSalaryId(null)
                                  }}
                                  onCancel={() => setSelectedSalaryId(null)}
                                />
                              </td>
                            </tr>
                          ) : null}
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>

          <section className="workspace-section" aria-labelledby="correction-history-heading">
            <div className="section-copy">
              <h2 id="correction-history-heading">Correction history</h2>
              <p>Newest first. Only values that changed are listed.</p>
            </div>
            {corrections && corrections.length === 0 ? (
              <p className="empty-note" role="status">
                No correction records.
              </p>
            ) : null}
            {corrections && corrections.length > 0 ? (
              <ul className="audit-list">
                {corrections.map((correction) => {
                  const changes = snapshotChanges(
                    correction.old_values,
                    correction.new_values,
                  )
                  return (
                    <li
                      key={`${correction.salary_record_id}-${correction.changed_at}-${correction.reason}`}
                    >
                      <article className="audit-card">
                        <header>
                          <time dateTime={correction.changed_at}>
                            {formatChangedAt(correction.changed_at)}
                          </time>
                          {correction.changed_by ? <p>{correction.changed_by}</p> : null}
                        </header>
                        {changes.length > 0 ? (
                          <ul className="change-log">
                            {changes.map((change) => (
                              <li key={change.key}>
                                <span className="change-field">{change.label}</span>
                                <span>
                                  {change.from}
                                  <span aria-hidden="true"> → </span>
                                  <span className="visually-hidden">changed to </span>
                                  {change.to}
                                </span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="empty-note">No field values changed.</p>
                        )}
                        {correction.reason ? (
                          <p className="audit-reason">
                            <span>Reason</span>
                            {correction.reason}
                          </p>
                        ) : null}
                      </article>
                    </li>
                  )
                })}
              </ul>
            ) : null}
          </section>
        </>
      ) : null}
    </section>
  )
}
