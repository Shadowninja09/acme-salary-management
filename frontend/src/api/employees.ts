import { apiGet } from './client'
import type { Employee, EmployeeList, EmployeeListQuery } from '../types/employee'

const EMPLOYEES_PATH = '/api/v1/employees'

export function listEmployees(
  query: EmployeeListQuery,
  signal?: AbortSignal,
): Promise<EmployeeList> {
  const params: Record<string, string> = {
    limit: String(query.limit),
    offset: String(query.offset),
  }
  const search = query.q?.trim()
  if (search) {
    params.q = search
  }
  if (query.status) {
    params.status = query.status
  }
  return apiGet<EmployeeList>(EMPLOYEES_PATH, params, signal)
}

export function getEmployee(
  employeeId: number,
  signal?: AbortSignal,
): Promise<Employee> {
  return apiGet<Employee>(`${EMPLOYEES_PATH}/${employeeId}`, undefined, signal)
}
