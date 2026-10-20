import { useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { createEmployeeSalary } from '../api/salaries'
import { permittedCurrenciesForCountry } from '../countryCurrency'
import {
  PAY_FREQUENCIES,
  type PayFrequency,
  type SalaryCurrency,
} from '../types/salary'

const MAX_AMOUNT = '9999999999.99'
const AMOUNT_PATTERN = /^\d+(\.\d{1,2})?$/

type AddSalaryFormProps = {
  employeeId: number
  country: string
  onCreated: () => Promise<boolean | void> | boolean | void
  onCancel?: () => void
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

export function AddSalaryForm({
  employeeId,
  country,
  onCreated,
  onCancel,
}: AddSalaryFormProps) {
  const permittedCurrencies = permittedCurrenciesForCountry(country)
  const [amount, setAmount] = useState('')
  const [currency, setCurrency] = useState<SalaryCurrency | null>(null)
  const selectedCurrency =
    currency !== null && permittedCurrencies.includes(currency)
      ? currency
      : (permittedCurrencies[0] ?? null)
  const [payFrequency, setPayFrequency] = useState<PayFrequency>('MONTHLY')
  const [effectiveFrom, setEffectiveFrom] = useState('')
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
    if (selectedCurrency === null) {
      setError(
        "No salary currency policy is configured for this employee's country.",
      )
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      try {
        await createEmployeeSalary(employeeId, {
          amount: amount.trim(),
          currency: selectedCurrency,
          pay_frequency: payFrequency,
          effective_from: effectiveFrom,
        })
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === 'AbortError') {
          return
        }
        setError(
          cause instanceof ApiError
            ? cause.message
            : 'The salary could not be saved. Try again.',
        )
        return
      }

      setAmount('')
      setEffectiveFrom('')
      setMessage('Salary record added.')

      try {
        const refreshed = await onCreated()
        if (refreshed === false) {
          setError(
            'The salary was saved, but the history lists could not be updated. This page may be out of date.',
          )
        }
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === 'AbortError') {
          return
        }
        setError(
          'The salary was saved, but the history lists could not be updated. This page may be out of date.',
        )
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="salary-form" onSubmit={(event) => void handleSubmit(event)}>
      <h2 className="detail-subheading">Add salary</h2>
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
      <div className="salary-form-grid">
        <label htmlFor="salary-amount">
          Amount
          <input
            id="salary-amount"
            name="amount"
            inputMode="decimal"
            autoComplete="off"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            required
            disabled={submitting}
          />
        </label>
        <label htmlFor="salary-currency">
          Currency
          <select
            id="salary-currency"
            name="currency"
            value={selectedCurrency ?? ''}
            onChange={(event) => setCurrency(event.target.value as SalaryCurrency)}
            disabled={submitting || permittedCurrencies.length === 0}
          >
            {permittedCurrencies.length === 0 ? (
              <option value="">No permitted currency</option>
            ) : (
              permittedCurrencies.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))
            )}
          </select>
        </label>
        <label htmlFor="salary-frequency">
          Pay frequency
          <select
            id="salary-frequency"
            name="pay_frequency"
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
        <label htmlFor="salary-effective-from">
          Effective date
          <input
            id="salary-effective-from"
            name="effective_from"
            type="date"
            value={effectiveFrom}
            onChange={(event) => setEffectiveFrom(event.target.value)}
            required
            disabled={submitting}
          />
        </label>
      </div>
      <div className="salary-form-actions">
        <button
          className="btn btn-primary"
          type="submit"
          disabled={submitting || permittedCurrencies.length === 0}
        >
          {submitting ? 'Saving…' : 'Save salary'}
        </button>
        {onCancel ? (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onCancel}
            disabled={submitting}
          >
            Cancel
          </button>
        ) : null}
      </div>
    </form>
  )
}
