import { apiGet } from './client'
import type { CompensationAnalytics } from '../types/analytics'

const ANALYTICS_PATH = '/api/v1/analytics/compensation'

export function getCompensationAnalytics(
  reportingDate: string,
  signal?: AbortSignal,
): Promise<CompensationAnalytics> {
  return apiGet<CompensationAnalytics>(
    ANALYTICS_PATH,
    { date: reportingDate },
    signal,
  )
}
