
import type { PokerState } from './poker'

export type AnalysisStatus =
  | 'idle'
  | 'processing'
  | 'success'
  | 'error'

export interface AnalysisError {
  code: string
  message: string
  status: number
  details: Record<string, unknown> | null
}

export interface AnalysisState {
  status: AnalysisStatus
  result: PokerState | null
  error: AnalysisError | null
  filename: string | null
  elapsedSeconds: number
}

export const INITIAL_ANALYSIS_STATE: AnalysisState = {
  status: 'idle',
  result: null,
  error: null,
  filename: null,
  elapsedSeconds: 0,
}
