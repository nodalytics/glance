
import {
  useCallback,
  useEffect,
  useState,
} from 'react'

import {
  performanceApi,
} from '../api/performanceApi'

import type {
  PerformanceReport,
} from '../types/performance'

export function usePerformanceReport() {

  const [report, setReport] =
    useState<PerformanceReport | null>(null)

  const [loading, setLoading] =
    useState(true)

  const [error, setError] =
    useState<string | null>(null)

  const [revision, setRevision] =
    useState(0)

  const refresh = useCallback(() => {

    setLoading(true)
    setError(null)
    setRevision(value => value + 1)

  }, [])

  useEffect(() => {

    const controller = new AbortController()

    async function loadReport() {

      try {

        const result =
          await performanceApi.getReport(
            controller.signal
          )

        if (controller.signal.aborted) {
          return
        }

        if (
          !result.success ||
          result.mode !== 'offline' ||
          result.measurement_type !==
            'recorded_research_benchmarks' ||
          !result.summary ||
          !result.preprocessing ||
          !Array.isArray(
            result.preprocessing.ranking
          ) ||
          !Array.isArray(
            result.neural_runtimes
          ) ||
          !Array.isArray(
            result.accuracy_analysis
          )
        ) {

          throw new Error(
            'Invalid performance report response.'
          )
        }

        setReport(result)
        setError(null)

      } catch (exception) {

        if (controller.signal.aborted) {
          return
        }

        setError(
          exception instanceof Error
            ? exception.message
            : 'Unable to load performance report.'
        )

      } finally {

        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    void loadReport()

    return () => {
      controller.abort()
    }

  }, [revision])

  return {
    report,
    loading,
    error,
    refresh,
  }
}
