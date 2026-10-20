import { useEffect, useState } from 'react'
import { logout } from './api/auth'
import { ApiError, setUnauthorizedHandler } from './api/client'
import { listEmployees } from './api/employees'
import { CompensationAnalyticsView } from './components/CompensationAnalytics'
import { EmployeeDetail } from './components/EmployeeDetail'
import { EmployeeDirectory } from './components/EmployeeDirectory'
import { LoginForm } from './components/LoginForm'
import './App.css'

type SessionState = 'checking' | 'anonymous' | 'authenticated'
type AuthenticatedView = 'directory' | 'analytics'

function App() {
  const [session, setSession] = useState<SessionState>('checking')
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [logoutError, setLogoutError] = useState<string | null>(null)
  const [loggingOut, setLoggingOut] = useState(false)
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | null>(null)
  const [view, setView] = useState<AuthenticatedView>('directory')

  function returnToAnonymousSession() {
    setSelectedEmployeeId(null)
    setView('directory')
    setLogoutError(null)
    setSessionError(null)
    setSession('anonymous')
  }

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setSelectedEmployeeId(null)
      setView('directory')
      setLogoutError(null)
      setSessionError(null)
      setSession('anonymous')
    })
    return () => {
      setUnauthorizedHandler(null)
    }
  }, [])

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
      returnToAnonymousSession()
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') {
        return
      }
      if (cause instanceof ApiError && cause.status === 401) {
        returnToAnonymousSession()
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

  if (session === 'checking') {
    return (
      <div className="login-page">
        <p className="status-banner" role="status">
          Checking session…
        </p>
      </div>
    )
  }

  if (session === 'anonymous') {
    return (
      <div className="login-page">
        <div>
          {sessionError ? (
            <p className="status-banner status-banner-error" role="alert">
              {sessionError}
            </p>
          ) : null}
          <LoginForm onAuthenticated={() => setSession('authenticated')} />
        </div>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            A
          </span>
          <div>
            <p className="brand-name">ACME</p>
            <p className="brand-product">Salary Management</p>
          </div>
        </div>
        <nav className="app-nav" aria-label="Primary">
          <button
            type="button"
            className={view === 'directory' ? 'nav-link is-active' : 'nav-link'}
            aria-current={view === 'directory' ? 'page' : undefined}
            onClick={() => {
              setSelectedEmployeeId(null)
              setView('directory')
            }}
          >
            Employees
          </button>
          <button
            type="button"
            className={view === 'analytics' ? 'nav-link is-active' : 'nav-link'}
            aria-current={view === 'analytics' ? 'page' : undefined}
            onClick={() => {
              setSelectedEmployeeId(null)
              setView('analytics')
            }}
          >
            Analytics
          </button>
        </nav>
        <div className="session-bar">
          <p className="session-role">HR Manager</p>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => void handleLogout()}
            disabled={loggingOut}
          >
            {loggingOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </aside>
      <div className="app-content">
        <main className="app-main">
          {logoutError ? (
            <p className="status-banner status-banner-error" role="alert">
              {logoutError}
            </p>
          ) : null}
          {view === 'directory' ? (
            <>
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
          ) : (
            <CompensationAnalyticsView />
          )}
        </main>
      </div>
    </div>
  )
}

export default App
