
import { apiRequest } from './client'

import type {
  BackendHealth,
  ApplicationInfo,
  ProfilesResponse,
  StatisticsResponse,
} from '../types/api'

import type {
  PokerState,
} from '../types/poker'

const API_PREFIX = '/api/v1'

const ANALYSIS_TIMEOUT_MS = 600000

export const pokerApi = {
  getHealth(signal?: AbortSignal) {
    return apiRequest<BackendHealth>(
      '/health',
      {
        method: 'GET',
        timeoutMs: 5000,
        signal,
      }
    )
  },

  getInfo(signal?: AbortSignal) {
    return apiRequest<ApplicationInfo>(
      `${API_PREFIX}/info`,
      {
        method: 'GET',
        signal,
      }
    )
  },

  getProfiles(signal?: AbortSignal) {
    return apiRequest<ProfilesResponse>(
      `${API_PREFIX}/profiles`,
      {
        method: 'GET',
        signal,
      }
    )
  },

  getStatistics(signal?: AbortSignal) {
    return apiRequest<StatisticsResponse>(
      `${API_PREFIX}/statistics`,
      {
        method: 'GET',
        signal,
      }
    )
  },

  analyzeScreenshot(
    file: File,
    signal?: AbortSignal
  ) {
    const formData = new FormData()

    formData.append(
      'file',
      file,
      file.name
    )

    return apiRequest<PokerState>(
      `${API_PREFIX}/analyze/screenshot`,
      {
        method: 'POST',
        body: formData,
        timeoutMs: ANALYSIS_TIMEOUT_MS,
        signal,
      }
    )
  },
}
