
import { apiRequest } from './client'

import type {
  PerformanceReport,
} from '../types/performance'

const API_PREFIX = '/api/v1'

export const performanceApi = {

  getReport(signal?: AbortSignal) {

    return apiRequest<PerformanceReport>(
      `${API_PREFIX}/performance/report`,
      {
        method: 'GET',
        timeoutMs: 15000,
        signal,
      }
    )
  },
}
