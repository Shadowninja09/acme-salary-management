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
      <h1 id="login-heading">ACME Salary Management</h1>
      <p className="login-lead">
        Sign in as the HR Manager to view employee records.
      </p>
      <form className="login-form" onSubmit={(event) => void handleSubmit(event)}>
        {error ? (
          <p className="directory-status directory-error" role="alert">
            {error}
          </p>
        ) : null}
        <label htmlFor="username">
          Username
          <input
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
        <label htmlFor="password">
          Password
          <input
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
        <button type="submit" disabled={submitting}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </section>
  )
}
