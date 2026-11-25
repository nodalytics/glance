
import { useEffect, useState } from 'react'

import { pokerApi } from '../api/pokerApi'

import type {
  BackendHealth,
} from '../types/api'

import type {
  ConnectionStatus,
} from '../types/navigation'

export function useBackendHealth() {
  const [status, setStatus] =
    useState<ConnectionStatus>('checking')

  const [health, setHealth] =
    useState<BackendHealth | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    let checking = false

    async function checkBackend() {
      if (
        checking ||
        controller.signal.aborted
      ) {
        return
      }

      checking = true

      try {
        const data = await pokerApi.getHealth(
          controller.signal
        )

        if (
          data.status !== 'ok' ||
          data.mode !== 'offline'
        ) {
          throw new Error(
            'Unexpected backend response'
          )
        }

        if (!controller.signal.aborted) {
          setHealth(data)
          setStatus('connected')
        }

      } catch {
        if (!controller.signal.aborted) {
          setHealth(null)
          setStatus('disconnected')
        }

      } finally {
        checking = false
      }
    }

    void checkBackend()

    const interval = window.setInterval(
      checkBackend,
      5000
    )

    return () => {
      controller.abort()
      window.clearInterval(interval)
    }
  }, [])

  return {
    status,
    health,
  }
}
