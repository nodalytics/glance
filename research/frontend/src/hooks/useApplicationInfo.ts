
import {
  useCallback,
  useEffect,
  useState,
} from 'react'

import { pokerApi } from '../api/pokerApi'

import { ApiError } from '../api/client'

import type {
  ApplicationInfo,
  ProfilesResponse,
  StatisticsResponse,
} from '../types/api'

interface ApplicationData {
  info: ApplicationInfo
  profiles: ProfilesResponse
  statistics: StatisticsResponse
}

export function useApplicationInfo() {
  const [data, setData] =
    useState<ApplicationData | null>(null)

  const [loading, setLoading] =
    useState(true)

  const [error, setError] =
    useState<string | null>(null)

  const [revision, setRevision] =
    useState(0)

  const refresh = useCallback(() => {
    setLoading(true)
    setError(null)

    setRevision(
      (previous) => previous + 1
    )
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    async function loadInformation() {
      try {
        const [
          info,
          profiles,
          statistics,
        ] = await Promise.all([
          pokerApi.getInfo(
            controller.signal
          ),

          pokerApi.getProfiles(
            controller.signal
          ),

          pokerApi.getStatistics(
            controller.signal
          ),
        ])

        if (!controller.signal.aborted) {
          setData({
            info,
            profiles,
            statistics,
          })

          setError(null)
        }

      } catch (error) {
        if (!controller.signal.aborted) {
          setData(null)

          setError(
            error instanceof ApiError
              ? error.message
              : 'Unable to load application information.'
          )
        }

      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    void loadInformation()

    return () => {
      controller.abort()
    }
  }, [revision])

  return {
    data,
    loading,
    error,
    refresh,
  }
}
