
import {
  FileJson,
  Database,
  HardDrive,
  ShieldCheck,
  Clock,
  Braces,
} from 'lucide-react'

import StatCard
  from '../components/dashboard/StatCard'

import JsonViewer
  from '../components/json/JsonViewer'

import type {
  PokerState,
} from '../types/poker'

import {
  serializeJson,
  getJsonSize,
} from '../utils/jsonUtils'

import {
  formatFileSize,
  formatDuration,
  formatSeat,
} from '../utils/formatters'

interface JsonDataProps {
  result: PokerState | null
  onViewDashboard: () => void
}

export default function JsonData({
  result,
  onViewDashboard,
}: JsonDataProps) {

  const formattedJson =
    result
      ? serializeJson(result)
      : null

  const responseSize =
    formattedJson !== null
      ? formatFileSize(
          getJsonSize(formattedJson)
        )
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

  const timestamp =
    result
      ? new Date(result.timestamp_utc)
      : null

  const formattedTimestamp =
    timestamp &&
    !Number.isNaN(timestamp.getTime())
      ? timestamp.toISOString()
      : '—'

  return (
    <div className="space-y-6">

      {/* PAGE HEADER */}

      <div>

        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-emerald-400">
          Structured Data Workspace
        </p>

        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
          JSON Data
        </h1>

        <p className="mt-2 text-sm text-slate-400">

          Inspect, copy and export the structured
          poker state returned by the analysis API.

        </p>

      </div>

      {/* SUMMARY CARDS */}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

        <StatCard
          label="Schema Version"
          value={
            result?.schema_version ?? '—'
          }
          icon={Braces}
          description="API response schema"
        />

        <StatCard
          label="JSON Data Size"
          value={responseSize}
          icon={HardDrive}
          description="Formatted UTF-8 JSON"
          accent="text-blue-400"
        />

        <StatCard
          label="State Status"
          value={validationStatus}
          icon={ShieldCheck}
          description="Backend validation result"
          accent={validationColor}
        />

        <StatCard
          label="Data Source"
          value={
            result
              ? formatSeat(result.source)
              : '—'
          }
          icon={Database}
          description="Analysis input source"
          accent="text-violet-400"
        />

      </div>

      {/* EMPTY STATE */}

      {!result ? (

        <section className="rounded-xl border border-slate-800 bg-[#111827] px-6 py-20 text-center">

          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/10">

            <FileJson
              size={32}
              className="text-emerald-400"
            />

          </div>

          <h2 className="text-xl font-semibold">

            No JSON response available

          </h2>

          <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-slate-400">

            Analyze a saved screenshot from the
            Dashboard to inspect and export
            its structured response.

          </p>

          <button
            type="button"
            onClick={onViewDashboard}
            className="mt-6 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-emerald-500"
          >

            Go to Dashboard

          </button>

        </section>

      ) : (

        <>

          {/* RESPONSE METADATA */}

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
                  Response Metadata
                </h3>

                <p className="mt-1 text-xs text-slate-400">
                  Analysis identification and timing
                </p>

              </div>

            </div>

            <div className="grid gap-4 md:grid-cols-2">

              {[
                {
                  label: 'Timestamp (UTC)',
                  value: formattedTimestamp,
                },
                {
                  label: 'Screenshot filename',
                  value:
                    result.metadata.screenshot
                      ?.filename ?? '—',
                },
                {
                  label: 'Recognition profile',
                  value:
                    result.metadata
                      .recognition_profile ?? '—',
                },
                {
                  label: 'Processing duration',
                  value: formatDuration(
                    result.metadata
                      .processing_time_seconds
                  ),
                },
                {
                  label: 'Player records',
                  value: result.players.length,
                },
                {
                  label: 'Recognized cards',
                  value:
                    result.game
                      .recognized_card_count,
                },
              ].map((item) => (

                <div
                  key={item.label}
                  className="min-w-0 rounded-lg bg-[#0b1018] p-4"
                >

                  <p className="text-xs text-slate-500">

                    {item.label}

                  </p>

                  <p className="mt-2 break-all text-sm font-medium text-slate-200">

                    {item.value}

                  </p>

                </div>

              ))}

            </div>

          </section>

          {/* JSON VIEWER */}

          <JsonViewer
            key={result.timestamp_utc}
            result={result}
          />

          <p className="text-xs leading-relaxed text-slate-500">

            Exported JSON contains the structured
            analysis response, including recognized
            player information and processing metadata.
            It does not include the original screenshot
            image. Handle exported data appropriately.

          </p>

        </>

      )}

    </div>
  )
}
