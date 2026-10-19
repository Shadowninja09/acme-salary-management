export const EMPLOYMENT_STATUSES = ['ACTIVE', 'INACTIVE'] as const

export type EmploymentStatus = (typeof EMPLOYMENT_STATUSES)[number]

export type Employee = {
  id: number
  employee_code: string
  full_name: string
  country: string
  department: string
  job_title: string
  employment_status: EmploymentStatus
  created_at: string
  updated_at: string
}

export type EmployeeList = {
  items: Employee[]
  total: number
  limit: number
  offset: number
}

export type EmployeeListQuery = {
  limit: number
  offset: number
}
