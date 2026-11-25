
import {
  LoaderCircle,
  Clock,
  ArrowRight,
} from 'lucide-react'

import type {
  AnalysisState,
} from '../../types/analysis'

import {
  formatDuration,
} from '../../utils/formatters'

interface ProcessingBannerProps {
  analysis: AnalysisState
  backendBusy: boolean
  onViewAnalysis: () => void
}

export default function ProcessingBanner({
  analysis,
  backendBusy,
  onViewAnalysis,
}: ProcessingBannerProps) {

  const isProcessing =
    analysis.status === 'processing'

  if (!isProcessing && !backendBusy) {
    return null
  }

  return (
    <div
      role="status"
      className="border-b border-blue-500/20 bg-blue-500/5 px-4 py-3 md:px-6"
    >

      <div className="flex flex-wrap items-center justify-between gap-3">

        <div className="flex min-w-0 items-center gap-3">

          <LoaderCircle
            size={19}
            className="shrink-0 animate-spin text-blue-400"
          />

          <div className="min-w-0">

            <p className="truncate text-sm font-medium text-blue-400">

              {isProcessing
                ? 'Screenshot analysis in progress'
                : 'Backend is processing a request'}

            </p>

            <p className="mt-1 truncate text-xs text-slate-400">

              {isProcessing
                ? analysis.filename
                : 'Waiting for the backend to become available'}

            </p>

          </div>

        </div>

        <div className="flex items-center gap-4">

          {isProcessing && (
            <div className="flex items-center gap-2 text-xs tabular-nums text-slate-300">

              <Clock size={14} />

              {formatDuration(
                analysis.elapsedSeconds
              )}

            </div>
          )}

          <button
            onClick={onViewAnalysis}
            className="flex items-center gap-2 rounded-lg border border-blue-500/20 px-3 py-2 text-xs text-blue-400 hover:bg-blue-500/10"
          >

            View Analysis

            <ArrowRight size={14} />

          </button>

        </div>

      </div>

    </div>
  )
}
