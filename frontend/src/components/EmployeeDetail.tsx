import { useEffect, useState } from 'react'
import { ApiError } from '../api/client'
import { getEmployee } from '../api/employees'
import { listEmployeeSalaries, listEmployeeSalaryCorrections } from '../api/salaries'
import { AddSalaryForm } from './AddSalaryForm'
import { CorrectSalaryForm } from './CorrectSalaryForm'
import type { Employee } from '../types/employee'
import type { PayFrequency, Salary, SalaryAuditSnapshot, SalaryCorrectionAudit } from '../types/salary'

type EmployeeDetailProps = {
  employeeId: number
  onBack: () => void
}

function formatPayFrequency(frequency: PayFrequency): string {
  return frequency === 'MONTHLY' ? 'Monthly' : 'Annual'
}

function formatChangedAt(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString()
}

function SalarySnapshotValues({ snapshot }: { snapshot: SalaryAuditSnapshot }) {
  return (
    <dl className="correction-values">
      <div>
        <dt>Amount</dt>
        <dd>{snapshot.amount}</dd>
      </div>
      <div>
        <dt>Currency</dt>
        <dd>{snapshot.currency}</dd>
      </div>
      <div>
        <dt>Pay frequency</dt>
        <dd>{formatPayFrequency(snapshot.pay_frequency)}</dd>
      </div>
      <div>
        <dt>Effective date</dt>
        <dd>{snapshot.effective_from}</dd>
      </div>
    </dl>
  )
}

export function EmployeeDetail({ employeeId, onBack }: EmployeeDetailProps) {
  const [employee, setEmployee] = useState<Employee | null>(null)
  const [salaries, setSalaries] = useState<Salary[] | null>(null)
  const [corrections, setCorrections] = useState<SalaryCorrectionAudit[] | null>(null)
  const [selectedSalaryId, setSelectedSalaryId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      setEmployee(null)
      setSalaries(null)
      setCorrections(null)
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

  async function refreshHistory() {
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
  }

  const selectedSalary =
    salaries?.find((salary) => salary.id === selectedSalaryId) ?? null

  return (
    <section className="detail" aria-labelledby="detail-heading">
      <div className="detail-toolbar">
        <button type="button" onClick={onBack}>
          Back to directory
        </button>
      </div>

      {loading ? (
        <p className="directory-status" role="status">
          Loading employee details…
        </p>
      ) : null}

      {error ? (
        <p className="directory-status directory-error" role="alert">
          {error.message}
        </p>
      ) : null}

      {!loading && !error && employee ? (
        <>
          <header className="directory-header">
            <h1 id="detail-heading">{employee.full_name}</h1>
            <p>Employee details and salary history.</p>
          </header>
          <dl className="detail-fields">
            <div>
              <dt>Employee code</dt>
              <dd>{employee.employee_code}</dd>
            </div>
            <div>
              <dt>Country</dt>
              <dd>{employee.country}</dd>
            </div>
            <div>
              <dt>Department</dt>
              <dd>{employee.department}</dd>
            </div>
            <div>
              <dt>Job title</dt>
              <dd>{employee.job_title}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{employee.employment_status === 'ACTIVE' ? 'Active' : 'Inactive'}</dd>
            </div>
          </dl>

          <AddSalaryForm employeeId={employee.id} onCreated={refreshHistory} />

          {selectedSalary ? (
            <CorrectSalaryForm
              key={selectedSalary.id}
              employeeId={employee.id}
              salary={selectedSalary}
              onCorrected={async () => {
                await refreshHistory()
                setSelectedSalaryId(null)
              }}
              onCancel={() => setSelectedSalaryId(null)}
            />
          ) : null}

          <h2 className="detail-subheading">Salary history</h2>
          {salaries && salaries.length === 0 ? (
            <p className="directory-status" role="status">
              No salary records.
            </p>
          ) : null}
          {salaries && salaries.length > 0 ? (
            <div className="table-wrap">
              <table>
                <caption className="visually-hidden">
                  Salary history, newest effective date first
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Effective date</th>
                    <th scope="col">Amount</th>
                    <th scope="col">Currency</th>
                    <th scope="col">Pay frequency</th>
                    <th scope="col">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {salaries.map((salary) => (
                    <tr key={salary.id}>
                      <td>{salary.effective_from}</td>
                      <td>{salary.amount}</td>
                      <td>{salary.currency}</td>
                      <td>{formatPayFrequency(salary.pay_frequency)}</td>
                      <td>
                        <button
                          type="button"
                          className="row-action"
                          onClick={() => setSelectedSalaryId(salary.id)}
                          aria-pressed={selectedSalaryId === salary.id}
                        >
                          Correct
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          <h2 className="detail-subheading">Correction history</h2>
          {corrections && corrections.length === 0 ? (
            <p className="directory-status" role="status">
              No correction records.
            </p>
          ) : null}
          {corrections && corrections.length > 0 ? (
            <div className="table-wrap">
              <table>
                <caption className="visually-hidden">
                  Salary correction history, newest correction first
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Correction date/time</th>
                    <th scope="col">Salary record ID</th>
                    <th scope="col">Previous values</th>
                    <th scope="col">New values</th>
                    <th scope="col">Reason</th>
                    <th scope="col">Changed by</th>
                  </tr>
                </thead>
                <tbody>
                  {corrections.map((correction) => (
                    <tr
                      key={`${correction.salary_record_id}-${correction.changed_at}-${correction.reason}`}
                    >
                      <td>
                        <time dateTime={correction.changed_at}>
                          {formatChangedAt(correction.changed_at)}
                        </time>
                      </td>
                      <td>{correction.salary_record_id}</td>
                      <td>
                        <SalarySnapshotValues snapshot={correction.old_values} />
                      </td>
                      <td>
                        <SalarySnapshotValues snapshot={correction.new_values} />
                      </td>
                      <td className="correction-reason">{correction.reason}</td>
                      <td>{correction.changed_by}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
