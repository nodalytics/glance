
import {
  LoaderCircle,
  CircleCheck,
  AlertCircle,
  TriangleAlert,
  Clock,
} from 'lucide-react'

import type {
  AnalysisState,
} from '../../types/analysis'

import {
  formatDuration,
} from '../../utils/formatters'

interface AnalysisFeedbackProps {
  analysis: AnalysisState
}

export default function AnalysisFeedback({
  analysis,
}: AnalysisFeedbackProps) {
  if (analysis.status === 'idle') {
    return null
  }

  // ----------------------------------------------
  // PROCESSING
  // ----------------------------------------------

  if (analysis.status === 'processing') {
    return (
      <div
        role="status"
        className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4"
      >

        <div className="flex items-center gap-3">

          <LoaderCircle
            size={22}
            className="shrink-0 animate-spin text-blue-400"
          />

          <div className="flex-1">

            <p className="text-sm font-semibold text-blue-400">
              Analyzing screenshot...
            </p>

            <p className="mt-1 text-xs leading-relaxed text-slate-400">
              The backend is processing the saved
              screenshot and validating the
              recognized table state.
            </p>

          </div>
        </div>

        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-800">
          <div className="h-full w-full animate-pulse rounded-full bg-blue-500/60" />
        </div>

        <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">

          <Clock size={14} />

          Elapsed time: {
            formatDuration(
              analysis.elapsedSeconds
            )
          }

        </div>

        <p className="mt-3 text-xs text-slate-500">
          Processing may take several minutes.
          Please keep the backend running.
        </p>

      </div>
    )
  }

  // ----------------------------------------------
  // REQUEST ERROR
  // ----------------------------------------------

  if (analysis.status === 'error') {
    return (
      <div
        role="alert"
        className="rounded-xl border border-red-500/20 bg-red-500/5 p-4"
      >

        <div className="flex items-start gap-3">

          <AlertCircle
            size={22}
            className="shrink-0 text-red-400"
          />

          <div className="min-w-0">

            <p className="text-sm font-semibold text-red-400">
              Analysis failed
            </p>

            <p className="mt-2 text-sm text-slate-300">
              {analysis.error?.message ??
                'Unable to analyze screenshot.'}
            </p>

            <p className="mt-2 break-all font-mono text-xs text-red-400/70">
              {analysis.error?.code}
            </p>

            {analysis.error?.status === 503 && (
              <p className="mt-3 text-xs text-slate-400">
                The backend is busy. Wait until
                processing finishes before trying again.
              </p>
            )}

            {analysis.error?.code ===
              'REQUEST_TIMEOUT' && (
              <p className="mt-3 text-xs text-slate-400">
                The browser stopped waiting.
                The backend may still be processing.
                Check its status before retrying.
              </p>
            )}

          </div>
        </div>

      </div>
    )
  }

  // ----------------------------------------------
  // COMPLETED ANALYSIS
  // ----------------------------------------------

  const result = analysis.result

  if (!result) {
    return null
  }

  const valid =
    result.status === 'valid' &&
    result.validation.valid

  const invalid =
    result.status === 'invalid' ||
    !result.validation.valid

  const Icon =
    valid ? CircleCheck : TriangleAlert

  const containerClass = valid
    ? 'border-emerald-500/20 bg-emerald-500/5'
    : invalid
      ? 'border-red-500/20 bg-red-500/5'
      : 'border-amber-500/20 bg-amber-500/5'

  const textClass = valid
    ? 'text-emerald-400'
    : invalid
      ? 'text-red-400'
      : 'text-amber-400'

  return (
    <div
      role="status"
      className={`rounded-xl border p-4 ${containerClass}`}
    >

      <div className="flex items-start gap-3">

        <Icon
          size={22}
          className={`shrink-0 ${textClass}`}
        />

        <div className="flex-1">

          <p className={`text-sm font-semibold ${textClass}`}>
            {valid
              ? 'Analysis completed successfully'
              : invalid
                ? 'Analysis completed with validation errors'
                : 'Analysis completed with warnings'}
          </p>

          <p className="mt-2 text-xs text-slate-400">
            {result.game.recognized_card_count}
            {' cards recognized · '}
            {result.players.length}
            {' players detected'}
          </p>

          <p className="mt-2 text-xs text-slate-400">
            {result.validation.error_count}
            {' errors · '}
            {result.validation.warning_count}
            {' warnings'}
          </p>

          <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">

            <Clock size={14} />

            Request duration: {
              formatDuration(
                analysis.elapsedSeconds
              )
            }

          </div>

        </div>
      </div>

    </div>
  )
}
