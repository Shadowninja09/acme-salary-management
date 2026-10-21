import { useMemo, useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { correctEmployeeSalary } from '../api/salaries'
import {
  currencyOptionsForCorrection,
  permittedCurrenciesForCountry,
} from '../countryCurrency'
import { formatIsoDate } from '../format'
import {
  PAY_FREQUENCIES,
  type PayFrequency,
  type Salary,
  type SalaryCurrency,
} from '../types/salary'

const MAX_AMOUNT = '9999999999.99'
const AMOUNT_PATTERN = /^\d+(\.\d{1,2})?$/

type CorrectSalaryFormProps = {
  employeeId: number
  country: string
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
  country,
  salary,
  onCorrected,
  onCancel,
}: CorrectSalaryFormProps) {
  const currencyOptions = useMemo(
    () => currencyOptionsForCorrection(country, salary.currency),
    [country, salary.currency],
  )
  const permittedCurrencies = permittedCurrenciesForCountry(country)
  const recordedCurrencyOutsidePolicy = !permittedCurrencies.includes(salary.currency)
  const [amount, setAmount] = useState(salary.amount)
  const [currency, setCurrency] = useState<SalaryCurrency>(salary.currency)
  const [payFrequency, setPayFrequency] = useState<PayFrequency>(salary.pay_frequency)
  const [effectiveFrom, setEffectiveFrom] = useState(salary.effective_from)
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [writeSucceeded, setWriteSucceeded] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const selectedCurrency = currencyOptions.includes(currency)
    ? currency
    : salary.currency

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
    const currencyAllowed =
      permittedCurrencies.includes(selectedCurrency) ||
      selectedCurrency === salary.currency
    if (!currencyAllowed) {
      setError("Select a currency permitted for this employee's country.")
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      try {
        await correctEmployeeSalary(employeeId, salary.id, {
          amount: amount.trim(),
          currency: selectedCurrency,
          pay_frequency: payFrequency,
          effective_from: effectiveFrom,
          reason,
        })
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === 'AbortError') {
          return
        }
        setError(
          cause instanceof ApiError
            ? cause.message
            : 'The salary could not be corrected. Try again.',
        )
        return
      }

      setWriteSucceeded(true)
      setReason('')
      setMessage('Salary record corrected.')

      try {
        await onCorrected()
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === 'AbortError') {
          return
        }
        setError(
          'The correction was saved, but the history lists could not be updated. This page may be out of date.',
        )
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="salary-form" onSubmit={(event) => void handleSubmit(event)}>
      <h2 className="detail-subheading">Correct salary</h2>
      <p className="salary-form-context">
        Effective {formatIsoDate(salary.effective_from)}
      </p>
      {message ? (
        <p className="status-banner status-banner-ok" role="status">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="status-banner status-banner-error" role="alert">
          {error}
        </p>
      ) : null}
      {recordedCurrencyOutsidePolicy ? (
        <p className="status-banner" role="status">
          This record uses {salary.currency}, which is outside the current
          country currency policy. Historical values are unchanged until you
          save a permitted currency.
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
            disabled={submitting || writeSucceeded}
          />
        </label>
        <label htmlFor="correction-currency">
          Currency
          <select
            id="correction-currency"
            name="correction_currency"
            value={selectedCurrency}
            onChange={(event) => setCurrency(event.target.value as SalaryCurrency)}
            disabled={submitting || writeSucceeded}
          >
            {currencyOptions.map((code) => (
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
            disabled={submitting || writeSucceeded}
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
            disabled={submitting || writeSucceeded}
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
            disabled={submitting || writeSucceeded}
            rows={3}
          />
        </label>
      </div>
      <div className="salary-form-actions">
        <button
          className="btn btn-primary"
          type="submit"
          disabled={submitting || writeSucceeded}
        >
          {submitting ? 'Saving…' : 'Save changes'}
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onCancel}
          disabled={submitting}
        >
          Cancel
        </button>
      </div>
    </form>
  )
}
