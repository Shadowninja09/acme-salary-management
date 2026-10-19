import { apiGet } from './client'
import type { Employee, EmployeeList, EmployeeListQuery } from '../types/employee'

const EMPLOYEES_PATH = '/api/v1/employees'

export function listEmployees(
  query: EmployeeListQuery,
  signal?: AbortSignal,
): Promise<EmployeeList> {
  return apiGet<EmployeeList>(
    EMPLOYEES_PATH,
    {
      limit: String(query.limit),
      offset: String(query.offset),
    },
    signal,
  )
}

export function getEmployee(
  employeeId: number,
  signal?: AbortSignal,
): Promise<Employee> {
  return apiGet<Employee>(`${EMPLOYEES_PATH}/${employeeId}`, undefined, signal)
}
