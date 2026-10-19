import { useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { correctEmployeeSalary } from '../api/salaries'
import {
  PAY_FREQUENCIES,
  SALARY_CURRENCIES,
  type PayFrequency,
  type Salary,
  type SalaryCurrency,
} from '../types/salary'

const MAX_AMOUNT = '9999999999.99'
const AMOUNT_PATTERN = /^\d+(\.\d{1,2})?$/

type CorrectSalaryFormProps = {
  employeeId: number
  salary: Salary
  onCorrected: () => Promise<void> | void
  onCancel: () => void
}

function isAmountTooLarge(value: string): boolean {
  const [wholeRaw, fraction = ''] = value.split('.')
  const whole = wholeRaw.replace(/^0+/, '') || '0'
  if (whole.length > 10) {
    return true
  }
  if (whole.length < 10) {
    return false
  }
  if (whole > '9999999999') {
    return true
  }
  if (whole < '9999999999') {
    return false
  }
  return fraction.padEnd(2, '0') > MAX_AMOUNT.slice(-2)
}

function validateAmount(value: string): string | null {
  const amount = value.trim()
  if (!amount) {
    return 'Enter an amount.'
  }
  if (!AMOUNT_PATTERN.test(amount) || amount.startsWith('.')) {
    return 'Amount must be a positive number with at most two decimal places.'
  }
  if (/^0+(\.0+)?$/.test(amount)) {
    return 'Amount must be greater than zero.'
  }
  if (isAmountTooLarge(amount)) {
    return 'Amount cannot exceed 9999999999.99.'
  }
  return null
}

export function CorrectSalaryForm({
  employeeId,
  salary,
  onCorrected,
  onCancel,
}: CorrectSalaryFormProps) {
  const [amount, setAmount] = useState(salary.amount)
  const [currency, setCurrency] = useState<SalaryCurrency>(salary.currency)
  const [payFrequency, setPayFrequency] = useState<PayFrequency>(salary.pay_frequency)
  const [effectiveFrom, setEffectiveFrom] = useState(salary.effective_from)
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage(null)
    const amountError = validateAmount(amount)
    if (amountError) {
      setError(amountError)
      return
    }
    if (!effectiveFrom) {
      setError('Enter an effective date.')
      return
    }
    if (!reason.trim()) {
      setError('Enter a correction reason.')
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      await correctEmployeeSalary(employeeId, salary.id, {
        amount: amount.trim(),
        currency,
        pay_frequency: payFrequency,
        effective_from: effectiveFrom,
        reason,
      })
      await onCorrected()
      setReason('')
      setMessage('Salary record corrected.')
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') {
        return
      }
      setError(
        cause instanceof ApiError
          ? cause.message
          : 'The salary could not be corrected. Try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="salary-form" onSubmit={(event) => void handleSubmit(event)}>
      <h2 className="detail-subheading">Correct salary</h2>
      {message ? (
        <p className="directory-status" role="status">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="directory-status directory-error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="salary-form-grid">
        <label htmlFor="correction-amount">
          Amount
          <input
            id="correction-amount"
            name="correction_amount"
            inputMode="decimal"
            autoComplete="off"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            required
            disabled={submitting}
          />
        </label>
        <label htmlFor="correction-currency">
          Currency
          <select
            id="correction-currency"
            name="correction_currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value as SalaryCurrency)}
            disabled={submitting}
          >
            {SALARY_CURRENCIES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="correction-frequency">
          Pay frequency
          <select
            id="correction-frequency"
            name="correction_pay_frequency"
            value={payFrequency}
            onChange={(event) =>
              setPayFrequency(event.target.value as PayFrequency)
            }
            disabled={submitting}
          >
            {PAY_FREQUENCIES.map((frequency) => (
              <option key={frequency} value={frequency}>
                {frequency === 'MONTHLY' ? 'Monthly' : 'Annual'}
              </option>
            ))}
          </select>
        </label>
        <label htmlFor="correction-effective-from">
          Effective date
          <input
            id="correction-effective-from"
            name="correction_effective_from"
            type="date"
            value={effectiveFrom}
            onChange={(event) => setEffectiveFrom(event.target.value)}
            required
            disabled={submitting}
          />
        </label>
        <label htmlFor="correction-reason" className="salary-form-reason">
          Reason
          <textarea
            id="correction-reason"
            name="correction_reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            required
            disabled={submitting}
            rows={3}
          />
        </label>
      </div>
      <div className="salary-form-actions">
        <button type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : 'Save correction'}
        </button>
        <button type="button" className="row-action" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
      </div>
    </form>
  )
}
