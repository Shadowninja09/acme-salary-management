import { ApiError, apiGet, apiPatch, apiPost } from './client'
import type {
  Salary,
  SalaryCorrectionAudit,
  SalaryCorrectionRequest,
  SalaryCreateRequest,
} from '../types/salary'

export function listEmployeeSalaries(
  employeeId: number,
  signal?: AbortSignal,
): Promise<Salary[]> {
  return apiGet<Salary[]>(
    `/api/v1/employees/${employeeId}/salaries`,
    undefined,
    signal,
  )
}

export function listEmployeeSalaryCorrections(
  employeeId: number,
  signal?: AbortSignal,
): Promise<SalaryCorrectionAudit[]> {
  return apiGet<SalaryCorrectionAudit[]>(
    `/api/v1/employees/${employeeId}/salary-corrections`,
    undefined,
    signal,
  )
}

export async function createEmployeeSalary(
  employeeId: number,
  payload: SalaryCreateRequest,
  signal?: AbortSignal,
): Promise<Salary> {
  try {
    return await apiPost<Salary>(
      `/api/v1/employees/${employeeId}/salaries`,
      payload,
      signal,
    )
  } catch (cause) {
    if (cause instanceof ApiError) {
      if (cause.status === 409) {
        throw new ApiError(
          409,
          'A salary record already exists for that effective date.',
        )
      }
      if (cause.status === 422) {
        throw new ApiError(
          422,
          'The salary details are invalid. Check the amount, currency, pay frequency, and date.',
        )
      }
      if (cause.status === 404) {
        throw new ApiError(404, 'Employee not found.')
      }
    }
    throw cause
  }
}

export async function correctEmployeeSalary(
  employeeId: number,
  salaryId: number,
  payload: SalaryCorrectionRequest,
  signal?: AbortSignal,
): Promise<Salary> {
  try {
    return await apiPatch<Salary>(
      `/api/v1/employees/${employeeId}/salaries/${salaryId}`,
      payload,
      signal,
    )
  } catch (cause) {
    if (cause instanceof ApiError) {
      if (cause.status === 401) {
        throw new ApiError(401, 'You are not signed in.')
      }
      if (cause.status === 409) {
        throw new ApiError(
          409,
          'A salary record already exists for that effective date.',
        )
      }
      if (cause.status === 422) {
        throw new ApiError(
          422,
          'The correction is invalid. Check the amount, currency, pay frequency, date, and required reason.',
        )
      }
      if (cause.status === 404) {
        const detail = cause.message.toLowerCase()
        if (detail.includes('employee')) {
          throw new ApiError(404, 'Employee not found.')
        }
        throw new ApiError(404, 'Salary record not found.')
      }
    }
    throw cause
  }
}
