
export interface BackendHealth {
  status: 'ok' | 'degraded'
  service: string
  version: string
  mode: 'offline'
  pipeline_initialized: boolean
  busy: boolean
}

export interface ApplicationInfo {
  name: string
  version: string
  description: string
  mode: 'offline'
  schema_version: string
  supported_image_formats: string[]
  max_upload_size_bytes: number
}

export interface RecognitionProfile {
  name: string
  description: string
  recognizer: string
  input_type: string
  available: boolean
  api_supported: boolean
  occupancy_detection_enabled: boolean
}

export interface ProfilesResponse {
  mode: 'offline'
  default_profile: string
  profiles: RecognitionProfile[]
}

export interface ServiceStatistics {
  total_requests: number
  successful_requests: number
  failed_requests: number
  rejected_requests: number
  busy_requests: number
}

export interface StatisticsResponse {
  pipeline_initialized: boolean
  busy: boolean
  statistics: ServiceStatistics
}

export interface ApiErrorDetail {
  code: string
  message: string
  details?: Record<string, unknown> | null
}

export interface ApiErrorResponse {
  success: false
  error: ApiErrorDetail
}
