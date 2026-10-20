export function formatCount(value: number): string {
  return new Intl.NumberFormat('en-US').format(value)
}

export function formatMoney(value: string): string {
  const amount = Number(value)
  if (!Number.isFinite(amount)) {
    return value
  }
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)
}

export function formatIsoDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) {
    return value
  }
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

export function formatPayFrequency(value: string): string {
  return value === 'ANNUAL' ? 'Annual' : 'Monthly'
}
