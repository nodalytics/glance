
import type {
  ApiErrorResponse,
} from '../types/api'

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  readonly details:
    | Record<string, unknown>
    | null

  constructor(
    message: string,
    status: number,
    code: string,
    details: Record<string, unknown> | null = null
  ) {
    super(message)

    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

interface RequestOptions extends RequestInit {
  timeoutMs?: number
}

function isApiErrorResponse(
  value: unknown
): value is ApiErrorResponse {
  if (
    typeof value !== 'object' ||
    value === null
  ) {
    return false
  }

  const candidate =
    value as Partial<ApiErrorResponse>

  return (
    candidate.success === false &&
    typeof candidate.error === 'object' &&
    candidate.error !== null &&
    typeof candidate.error.code === 'string' &&
    typeof candidate.error.message === 'string'
  )
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    timeoutMs = 15000,
    signal: externalSignal,
    ...requestOptions
  } = options

  const controller = new AbortController()

  let timedOut = false

  const timeout = window.setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  function abortRequest() {
    controller.abort()
  }

  if (externalSignal?.aborted) {
    controller.abort()
  } else {
    externalSignal?.addEventListener(
      'abort',
      abortRequest,
      { once: true }
    )
  }

  try {
    const headers = new Headers(
      requestOptions.headers
    )

    headers.set(
      'Accept',
      'application/json'
    )

    const response = await fetch(path, {
      ...requestOptions,
      headers,
      signal: controller.signal,
      cache: 'no-store',
    })

    const contentType =
      response.headers.get('content-type') ?? ''

    let data: unknown = null

    if (
      contentType.includes('application/json')
    ) {
      try {
        data = await response.json()
      } catch (error) {
        if (controller.signal.aborted) {
          throw error
        }

        throw new ApiError(
          'The server returned invalid JSON.',
          response.status,
          'INVALID_JSON_RESPONSE'
        )
      }
    }

    if (!response.ok) {
      if (isApiErrorResponse(data)) {
        throw new ApiError(
          data.error.message,
          response.status,
          data.error.code,
          data.error.details ?? null
        )
      }

      throw new ApiError(
        `Request failed with HTTP ${response.status}.`,
        response.status,
        'HTTP_ERROR'
      )
    }

    if (data === null) {
      throw new ApiError(
        'The server returned an unexpected response.',
        response.status,
        'INVALID_RESPONSE'
      )
    }

    return data as T

  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }

    if (timedOut) {
      throw new ApiError(
        'The request exceeded its time limit.',
        0,
        'REQUEST_TIMEOUT'
      )
    }

    if (controller.signal.aborted) {
      throw new ApiError(
        'The request was cancelled.',
        0,
        'REQUEST_CANCELLED'
      )
    }

    throw new ApiError(
      'Unable to communicate with the backend.',
      0,
      'NETWORK_ERROR'
    )

  } finally {
    window.clearTimeout(timeout)

    externalSignal?.removeEventListener(
      'abort',
      abortRequest
    )
  }
}
