
import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'

import { pokerApi } from '../api/pokerApi'

import { ApiError } from '../api/client'

import {
  INITIAL_ANALYSIS_STATE,
} from '../types/analysis'

import type {
  AnalysisState,
  AnalysisError,
} from '../types/analysis'

import type {
  PokerState,
} from '../types/poker'

export function useScreenshotAnalysis() {
  const [state, setState] =
    useState<AnalysisState>(
      INITIAL_ANALYSIS_STATE
    )

  const controllerRef =
    useRef<AbortController | null>(null)

  const processingRef =
    useRef(false)

  const startedAtRef =
    useRef<number | null>(null)

  const mountedRef =
    useRef(true)

  useEffect(() => {
    mountedRef.current = true

    return () => {
      mountedRef.current = false

      controllerRef.current?.abort()
    }
  }, [])

  const isProcessing =
    state.status === 'processing'

  // ----------------------------------------------
  // ELAPSED PROCESSING TIMER
  // ----------------------------------------------

  useEffect(() => {
    if (!isProcessing) {
      return
    }

    const interval = window.setInterval(() => {
      if (startedAtRef.current === null) {
        return
      }

      const elapsedSeconds =
        (
          performance.now() -
          startedAtRef.current
        ) / 1000

      setState((previous) => ({
        ...previous,
        elapsedSeconds,
      }))
    }, 1000)

    return () => {
      window.clearInterval(interval)
    }
  }, [isProcessing])

  // ----------------------------------------------
  // RESET ANALYSIS
  // ----------------------------------------------

  const reset = useCallback(() => {
    if (processingRef.current) {
      return
    }

    setState({
      ...INITIAL_ANALYSIS_STATE,
    })
  }, [])

  // ----------------------------------------------
  // ANALYZE SCREENSHOT
  // ----------------------------------------------

  const analyze = useCallback(
    async (
      file: File
    ): Promise<PokerState | null> => {
      if (processingRef.current) {
        return null
      }

      processingRef.current = true

      const controller =
        new AbortController()

      controllerRef.current = controller

      const startedAt =
        performance.now()

      startedAtRef.current = startedAt

      setState({
        status: 'processing',
        result: null,
        error: null,
        filename: file.name,
        elapsedSeconds: 0,
      })

      try {
        const result =
          await pokerApi.analyzeScreenshot(
            file,
            controller.signal
          )

        // Basic response compatibility checks.

        if (
          !result ||
          result.schema_version !== '1.0.0' ||
          result.source !== 'offline_screenshot' ||
          !result.table ||
          !result.game ||
          !result.cards ||
          !Array.isArray(result.players) ||
          !result.validation ||
          !result.metadata ||
          ![
            'valid',
            'partial',
            'invalid',
          ].includes(result.status)
        ) {
          throw new ApiError(
            'The backend returned an incompatible poker state.',
            200,
            'INVALID_POKER_STATE'
          )
        }

        const elapsedSeconds =
          (
            performance.now() -
            startedAt
          ) / 1000

        if (
          mountedRef.current &&
          !controller.signal.aborted
        ) {
          setState({
            status: 'success',
            result,
            error: null,
            filename: file.name,
            elapsedSeconds,
          })
        }

        return result

      } catch (error) {
        const analysisError: AnalysisError =
          error instanceof ApiError
            ? {
                code: error.code,
                message: error.message,
                status: error.status,
                details: error.details,
              }
            : {
                code: 'UNEXPECTED_ERROR',
                message:
                  'An unexpected analysis error occurred.',
                status: 0,
                details: null,
              }

        if (mountedRef.current) {
          setState({
            status: 'error',
            result: null,
            error: analysisError,
            filename: file.name,
            elapsedSeconds:
              (
                performance.now() -
                startedAt
              ) / 1000,
          })
        }

        return null

      } finally {
        processingRef.current = false

        controllerRef.current = null

        startedAtRef.current = null
      }
    },
    []
  )

  return {
    state,
    analyze,
    reset,
    isProcessing,
  }
}
