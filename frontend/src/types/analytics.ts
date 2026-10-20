import type { PayFrequency, SalaryCurrency } from './salary'

export type CompensationSalaryGroup = {
  currency: SalaryCurrency
  pay_frequency: PayFrequency
  employee_count: number
  average_salary: string
  minimum_salary: string
  maximum_salary: string
}

export type CompensationDepartmentGroup = CompensationSalaryGroup & {
  department: string
}

export type CompensationCountryGroup = CompensationSalaryGroup & {
  country: string
}

export type CompensationAnalytics = {
  reporting_date: string
  active_employee_count: number
  active_employees_with_salary: number
  active_employees_without_salary: number
  salary_summary: CompensationSalaryGroup[]
  by_department: CompensationDepartmentGroup[]
  by_country: CompensationCountryGroup[]
}
