export const SALARY_CURRENCIES = ['INR', 'USD', 'GBP', 'EUR', 'CAD', 'AUD'] as const
export const PAY_FREQUENCIES = ['MONTHLY', 'ANNUAL'] as const

export type SalaryCurrency = (typeof SALARY_CURRENCIES)[number]
export type PayFrequency = (typeof PAY_FREQUENCIES)[number]

export type Salary = {
  id: number
  employee_id: number
  amount: string
  currency: SalaryCurrency
  pay_frequency: PayFrequency
  effective_from: string
}

export type SalaryCreateRequest = {
  amount: string
  currency: SalaryCurrency
  pay_frequency: PayFrequency
  effective_from: string
}
