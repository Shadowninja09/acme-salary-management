import { ApiError, apiPost } from './client'
import type { LoginRequest, LoginResponse } from '../types/auth'

const LOGIN_PATH = '/api/v1/auth/login'
const LOGOUT_PATH = '/api/v1/auth/logout'

const INVALID_CREDENTIALS_MESSAGE = 'Invalid username or password.'
const UNTRUSTED_ORIGIN_MESSAGE =
  'Sign-in was blocked because this page’s origin is not trusted. Add this application’s origin to the backend trusted-origin list, then restart the API.'
const VALIDATION_MESSAGE = 'Enter a username and password.'

export async function login(
  credentials: LoginRequest,
  signal?: AbortSignal,
): Promise<LoginResponse> {
  try {
    return await apiPost<LoginResponse>(LOGIN_PATH, credentials, signal)
  } catch (cause) {
    if (cause instanceof ApiError) {
      if (cause.status === 401) {
        throw new ApiError(401, INVALID_CREDENTIALS_MESSAGE)
      }
      if (cause.status === 403) {
        throw new ApiError(403, UNTRUSTED_ORIGIN_MESSAGE)
      }
      if (cause.status === 422) {
        throw new ApiError(422, VALIDATION_MESSAGE)
      }
    }
    throw cause
  }
}

export async function logout(signal?: AbortSignal): Promise<LoginResponse> {
  try {
    return await apiPost<LoginResponse>(LOGOUT_PATH, undefined, signal)
  } catch (cause) {
    if (cause instanceof ApiError && cause.status === 401) {
      throw new ApiError(
        401,
        'You are not signed in, or the session has expired. Sign in again.',
      )
    }
    throw cause
  }
}
