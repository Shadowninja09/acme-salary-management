import { ApiError, apiGet, apiPost } from './client'
import type { Salary, SalaryCreateRequest } from '../types/salary'

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
