import { useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { login } from '../api/auth'
import { listEmployees } from '../api/employees'

type LoginFormProps = {
  onAuthenticated: () => void
}

export function LoginForm({ onAuthenticated }: LoginFormProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const result = await login({
        username: username.trim(),
        password,
      })
      if (result.status !== 'ok') {
        throw new ApiError(0, 'Sign-in did not complete. Try again.')
      }
      await listEmployees({ limit: 1, offset: 0 })
      setPassword('')
      onAuthenticated()
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') {
        return
      }
      const message =
        cause instanceof ApiError
          ? cause.message
          : 'Sign-in could not be completed. Try again.'
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="login" aria-labelledby="login-heading">
      <div className="login-brand">
        <span className="brand-mark" aria-hidden="true">
          A
        </span>
        <div>
          <p className="brand-name">ACME</p>
          <p className="brand-product">Salary Management</p>
        </div>
      </div>
      <h1 id="login-heading">Sign in</h1>
      <p className="login-lead">
        Use the HR Manager credentials to access employee records and compensation
        analytics.
      </p>
      <form className="login-form" onSubmit={(event) => void handleSubmit(event)}>
        {error ? (
          <p className="status-banner status-banner-error" role="alert">
            {error}
          </p>
        ) : null}
        <label className="field-label" htmlFor="username">
          Username
          <input
            className="field-control"
            id="username"
            name="username"
            type="text"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
            disabled={submitting}
          />
        </label>
        <label className="field-label" htmlFor="password">
          Password
          <input
            className="field-control"
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            disabled={submitting}
          />
        </label>
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </section>
  )
}
