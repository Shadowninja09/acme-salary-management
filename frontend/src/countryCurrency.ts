import { SALARY_CURRENCIES, type SalaryCurrency } from './types/salary'

const COUNTRY_CURRENCY_POLICY: Record<string, readonly SalaryCurrency[]> = {
  india: ['INR'],
  'united states': ['USD'],
  'united kingdom': ['GBP'],
  canada: ['CAD'],
  australia: ['AUD'],
  germany: ['EUR'],
}

export function normalizeCountry(country: string): string {
  return country.trim().split(/\s+/).join(' ').toLowerCase()
}

export function permittedCurrenciesForCountry(
  country: string,
): SalaryCurrency[] {
  const permitted = COUNTRY_CURRENCY_POLICY[normalizeCountry(country)]
  if (!permitted) {
    return []
  }
  return SALARY_CURRENCIES.filter((code) => permitted.includes(code))
}

export function defaultCurrencyForCountry(
  country: string,
): SalaryCurrency | null {
  return permittedCurrenciesForCountry(country)[0] ?? null
}

export function currencyOptionsForCorrection(
  country: string,
  recordedCurrency: SalaryCurrency,
): SalaryCurrency[] {
  const permitted = permittedCurrenciesForCountry(country)
  if (permitted.includes(recordedCurrency)) {
    return [...permitted]
  }
  return [recordedCurrency, ...permitted]
}
