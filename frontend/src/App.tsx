import { useEffect, useState } from 'react'
import { logout } from './api/auth'
import { ApiError } from './api/client'
import { listEmployees } from './api/employees'
import { EmployeeDetail } from './components/EmployeeDetail'
import { EmployeeDirectory } from './components/EmployeeDirectory'
import { LoginForm } from './components/LoginForm'
import './App.css'

type SessionState = 'checking' | 'anonymous' | 'authenticated'

function App() {
  const [session, setSession] = useState<SessionState>('checking')
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [logoutError, setLogoutError] = useState<string | null>(null)
  const [loggingOut, setLoggingOut] = useState(false)
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false

    async function verifyExistingSession() {
      try {
        await listEmployees({ limit: 1, offset: 0 }, controller.signal)
        if (!cancelled) {
          setSession('authenticated')
        }
      } catch (cause) {
        if (cancelled || (cause instanceof DOMException && cause.name === 'AbortError')) {
          return
        }
        if (cause instanceof ApiError && cause.status === 401) {
          setSession('anonymous')
          return
        }
        setSessionError(
          cause instanceof ApiError
            ? cause.message
            : 'Could not verify the current session.',
        )
        setSession('anonymous')
      }
    }

    void verifyExistingSession()
    return () => {
      cancelled = true
      controller.abort()
    }
  }, [])

  async function handleLogout() {
    setLoggingOut(true)
    setLogoutError(null)
    try {
      const result = await logout()
      if (result.status !== 'ok') {
        throw new ApiError(0, 'Sign-out did not complete. Try again.')
      }
      setSelectedEmployeeId(null)
      setSessionError(null)
      setSession('anonymous')
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') {
        return
      }
      setLogoutError(
        cause instanceof ApiError
          ? cause.message
          : 'Sign-out could not be completed. Try again.',
      )
    } finally {
      setLoggingOut(false)
    }
  }

  return (
    <main className="page">
      {session === 'checking' ? (
        <p className="directory-status" role="status">
          Checking session…
        </p>
      ) : null}
      {session === 'anonymous' ? (
        <>
          {sessionError ? (
            <p className="directory-status directory-error" role="alert">
              {sessionError}
            </p>
          ) : null}
          <LoginForm onAuthenticated={() => setSession('authenticated')} />
        </>
      ) : null}
      {session === 'authenticated' ? (
        <>
          <header className="app-header">
            <p className="app-header-title">ACME Salary Management</p>
            <button type="button" onClick={() => void handleLogout()} disabled={loggingOut}>
              {loggingOut ? 'Signing out…' : 'Logout'}
            </button>
          </header>
          {logoutError ? (
            <p className="directory-status directory-error" role="alert">
              {logoutError}
            </p>
          ) : null}
          <div hidden={selectedEmployeeId !== null}>
            <EmployeeDirectory onSelectEmployee={setSelectedEmployeeId} />
          </div>
          {selectedEmployeeId !== null ? (
            <EmployeeDetail
              employeeId={selectedEmployeeId}
              onBack={() => setSelectedEmployeeId(null)}
            />
          ) : null}
        </>
      ) : null}
    </main>
  )
}

export default App
