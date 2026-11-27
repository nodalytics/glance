
import {
  Clock,
  Timer,
} from 'lucide-react'

import type {
  PokerState,
} from '../../types/poker'

import {
  formatDuration,
} from '../../utils/formatters'

interface ProcessingTimingsProps {
  result: PokerState | null
}

function isValidTiming(
  value: unknown
): value is number {
  return (
    typeof value === 'number' &&
    Number.isFinite(value) &&
    value >= 0
  )
}

export default function ProcessingTimings({
  result,
}: ProcessingTimingsProps) {

  const metadata =
    result?.metadata

  const timings =
    metadata?.timings

  const stages = [
    {
      label: 'Screenshot loading',
      value: timings?.screenshot_loading_seconds,
    },
    {
      label: 'Table OCR extraction',
      value: timings?.table_extraction_seconds,
    },
    {
      label: 'Card cropping',
      value: timings?.card_cropping_seconds,
    },
    {
      label: 'Recognizer initialization',
      value: timings?.initialization_seconds,
    },
    {
      label: 'Card recognition',
      value: timings?.recognition_seconds,
    },
    {
      label: 'State building',
      value: timings?.state_building_seconds,
    },
    {
      label: 'Image loading',
      value: timings?.image_loading_seconds,
    },
  ].filter(
    (
      stage
    ): stage is {
      label: string
      value: number
    } => isValidTiming(stage.value)
  )

  const longestStage =
    [...stages].sort(
      (a, b) => b.value - a.value
    )[0]

  const maxTime =
    longestStage?.value ?? 0

  const totals = [
    {
      label: 'Recognition pipeline total',
      value: timings?.total_seconds,
    },
    {
      label: 'Screenshot pipeline total',
      value: timings?.screenshot_total_seconds,
    },
    {
      label: 'Directory pipeline total',
      value: timings?.directory_total_seconds,
    },
    {
      label: 'Processing service total',
      value: metadata?.service_processing_seconds,
    },
    {
      label: 'Reported processing time',
      value: metadata?.processing_time_seconds,
    },
  ].filter(
    (
      item
    ): item is {
      label: string
      value: number
    } => isValidTiming(item.value)
  )

  return (
    <section className="rounded-xl border border-slate-800 bg-[#111827] p-5">

      <div className="mb-5 flex items-center gap-3">

        <div className="rounded-lg bg-blue-500/10 p-2.5">

          <Clock
            size={20}
            className="text-blue-400"
          />

        </div>

        <div>

          <h3 className="font-semibold">
            Processing Timings
          </h3>

          <p className="mt-1 text-xs text-slate-400">
            Backend execution time by stage
          </p>

        </div>

      </div>

      {stages.length === 0 ? (

        <p className="py-12 text-center text-sm text-slate-500">

          No detailed processing timings available.

        </p>

      ) : (

        <div className="space-y-5">

          {stages.map((stage) => (

            <div
              key={stage.label}
              className="space-y-2"
            >

              <div className="flex items-center justify-between gap-3">

                <span className="text-sm text-slate-300">
                  {stage.label}
                </span>

                <span className="shrink-0 text-xs font-medium tabular-nums text-blue-400">
                  {formatDuration(stage.value)}
                </span>

              </div>

              <div className="h-2 overflow-hidden rounded-full bg-slate-800">

                <div
                  className="h-full rounded-full bg-blue-500"
                  style={{
                    width: `${
                      maxTime > 0
                        ? stage.value / maxTime * 100
                        : 0
                    }%`,
                  }}
                />

              </div>

            </div>

          ))}

        </div>

      )}

      {longestStage && (

        <div className="mt-6 rounded-lg border border-amber-500/20 bg-amber-500/5 p-4">

          <div className="flex items-center gap-2 text-amber-400">

            <Timer size={17} />

            <p className="text-sm font-semibold">
              Slowest reported stage
            </p>

          </div>

          <p className="mt-2 text-sm text-slate-300">

            {longestStage.label}

          </p>

          <p className="mt-1 text-xl font-semibold tabular-nums text-amber-400">

            {formatDuration(
              longestStage.value
            )}

          </p>

        </div>

      )}

      {totals.length > 0 && (

        <div className="mt-6 border-t border-slate-800 pt-5">

          <h4 className="mb-4 text-sm font-semibold">
            Pipeline Totals
          </h4>

          <div className="space-y-4">

            {totals.map((item) => (

              <div
                key={item.label}
                className="flex items-center justify-between gap-3 text-sm"
              >

                <span className="text-slate-400">

                  {item.label}

                </span>

                <span className="shrink-0 font-medium tabular-nums">

                  {formatDuration(item.value)}

                </span>

              </div>

            ))}

          </div>

        </div>

      )}

      <p className="mt-5 text-xs leading-relaxed text-slate-500">

        Bars are relative to the longest reported
        stage. Pipeline totals may include other
        stages and must not be added together.
        These timings are backend measurements,
        not the complete browser request duration.

      </p>

    </section>
  )
}
