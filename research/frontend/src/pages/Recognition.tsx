
import {
  ScanLine,
  ShieldCheck,
  CircleAlert,
  TriangleAlert,
  Clock,
} from 'lucide-react'

import StatCard
  from '../components/dashboard/StatCard'

import CardRecognitionTable
  from '../components/recognition/CardRecognitionTable'

import ValidationPanel
  from '../components/recognition/ValidationPanel'

import ProcessingTimings
  from '../components/recognition/ProcessingTimings'

import RecognitionProfile
  from '../components/recognition/RecognitionProfile'

import type {
  PokerState,
} from '../types/poker'

import {
  formatDuration,
} from '../utils/formatters'

interface RecognitionProps {
  result: PokerState | null
  onViewDashboard: () => void
}

export default function Recognition({
  result,
  onViewDashboard,
}: RecognitionProps) {

  const validation =
    result?.validation

  const recognizedCards =
    result
      ? `${result.game.recognized_card_count}/${result.game.occupied_count}`
      : '—'

  const validationStatus =
    !result
      ? 'Pending'
      : !result.validation.valid ||
          result.status === 'invalid'
        ? 'Invalid'
        : result.status === 'partial'
          ? 'Partial'
          : 'Valid'

  const validationColor =
    validationStatus === 'Valid'
      ? 'text-emerald-400'
      : validationStatus === 'Invalid'
        ? 'text-red-400'
        : 'text-amber-400'

  return (
    <div className="space-y-6">

      <div>

        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-emerald-400">

          Recognition Diagnostics

        </p>

        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">

          Recognition

        </h1>

        <p className="mt-2 text-sm text-slate-400">

          Inspect card recognition, confidence
          scores, validation results and backend
          processing performance.

        </p>

      </div>

      {!result && (

        <section className="rounded-xl border border-slate-800 bg-[#111827] px-6 py-16 text-center">

          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/10">

            <ScanLine
              size={30}
              className="text-emerald-400"
            />

          </div>

          <h2 className="text-xl font-semibold">

            No recognition results available

          </h2>

          <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-slate-400">

            Analyze a saved screenshot to inspect
            detailed recognition diagnostics.

          </p>

          <button
            onClick={onViewDashboard}
            className="mt-6 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-emerald-500"
          >

            Go to Dashboard

          </button>

        </section>

      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

        <StatCard
          label="Recognized Cards"
          value={recognizedCards}
          icon={ScanLine}
          description="Recognized / occupied cards"
        />

        <StatCard
          label="Validation Status"
          value={validationStatus}
          icon={ShieldCheck}
          description="Backend consistency checks"
          accent={validationColor}
        />

        <StatCard
          label="Validation Errors"
          value={validation?.error_count ?? '—'}
          icon={CircleAlert}
          description="Detected state errors"
          accent={
            (validation?.error_count ?? 0) > 0
              ? 'text-red-400'
              : 'text-emerald-400'
          }
        />

        <StatCard
          label="Validation Warnings"
          value={validation?.warning_count ?? '—'}
          icon={TriangleAlert}
          description="Detected state warnings"
          accent={
            (validation?.warning_count ?? 0) > 0
              ? 'text-amber-400'
              : 'text-emerald-400'
          }
        />

      </div>

      {result && (

        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-[#111827] p-4">

          <div className="flex items-center gap-3">

            <Clock
              size={20}
              className="text-blue-400"
            />

            <div>

              <p className="text-sm font-medium">

                Backend Processing Duration

              </p>

              <p className="mt-1 text-xs text-slate-500">

                Reported by the analysis pipeline

              </p>

            </div>

          </div>

          <p className="text-xl font-semibold tabular-nums text-blue-400">

            {formatDuration(
              result.metadata.processing_time_seconds
            )}

          </p>

        </div>

      )}

      <CardRecognitionTable
        result={result}
      />

      <div className="grid items-start gap-6 xl:grid-cols-2">

        <ValidationPanel
          result={result}
        />

        <ProcessingTimings
          result={result}
        />

      </div>

      <RecognitionProfile
        result={result}
      />

    </div>
  )
}
