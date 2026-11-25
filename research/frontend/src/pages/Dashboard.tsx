
import {
  Coins,
  Layers,
  Users,
  TrendingUp,
  ShieldCheck,
  ScanLine,
  Clock,
  } from 'lucide-react'

import StatCard from '../components/dashboard/StatCard'

import ScreenshotUpload from '../components/dashboard/ScreenshotUpload'

import PlayerTable from '../components/dashboard/PlayerTable'

import PokerTable from '../components/dashboard/PokerTable'

import type {
  AnalysisState,
} from '../types/analysis'

import type {
  ConnectionStatus,
} from '../types/navigation'

import {
  formatNumber,
  formatStreet,
  formatDuration,
} from '../utils/formatters'

interface DashboardProps {
  file: File | null

  onFileChange:
    (file: File | null) => void

  onAnalyze: () => void

  analysis: AnalysisState

  connectionStatus: ConnectionStatus

  backendBusy: boolean
}

export default function Dashboard({
  file,
  onFileChange,
  onAnalyze,
  analysis,
  connectionStatus,
  backendBusy,
}: DashboardProps) {
  const result = analysis.result

  const validationStatus =
    analysis.status === 'processing'
      ? 'Processing'
      : analysis.status === 'error'
        ? 'Failed'
        : result
          ? result.status === 'valid'
            ? 'Valid'
            : result.status === 'partial'
              ? 'Partial'
              : 'Invalid'
          : 'Pending'

  const validationAccent =
    validationStatus === 'Valid'
      ? 'text-emerald-400'
      : validationStatus === 'Invalid' ||
          validationStatus === 'Failed'
        ? 'text-red-400'
        : 'text-amber-400'

  const recognizedCards =
    result
      ? `${result.game.recognized_card_count}/${result.game.occupied_count}`
      : '—'

  return (
    <div className="space-y-6">

      <div>

        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-emerald-400">
          Overview
        </p>

        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
          Analysis Dashboard
        </h1>

        <p className="mt-2 text-sm text-slate-400">
          Analyze saved screenshots and inspect
          structured poker table information.
        </p>

      </div>

      {result &&
        result.status !== 'valid' && (
          <div
            role="alert"
            className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-400"
          >
            This result contains incomplete or
            invalid information. Review the
            validation details before relying
            on the recognized data.
          </div>
        )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

        <StatCard
          label="Total Pot"
          value={formatNumber(
            result?.table.pot
          )}
          icon={Coins}
          description="Detected chip amount"
          accent="text-amber-400"
        />

        <StatCard
          label="Game Street"
          value={formatStreet(
            result?.game.street
          )}
          icon={Layers}
          description="Recognized board stage"
          accent="text-blue-400"
        />

        <StatCard
          label="Detected Players"
          value={
            result
              ? result.players.length
              : '—'
          }
          icon={Users}
          description="Recognized player seats"
          accent="text-violet-400"
        />

        <StatCard
          label="Average Stack"
          value={formatNumber(
            result?.table.average_stack
          )}
          icon={TrendingUp}
          description="Tournament average"
        />

      </div>

      <div className="grid items-start gap-6 2xl:grid-cols-2">

        <ScreenshotUpload
          file={file}
          onFileChange={onFileChange}
          onAnalyze={onAnalyze}
          analysis={analysis}
          connectionStatus={connectionStatus}
          backendBusy={backendBusy}
        />

<PokerTable result={result} />
      </div>

      <div className="grid gap-4 md:grid-cols-3">

        <StatCard
          label="Recognized Cards"
          value={recognizedCards}
          icon={ScanLine}
          description="Recognized / occupied cards"
        />

        <StatCard
          label="Processing Time"
          value={formatDuration(
            result?.metadata
              .processing_time_seconds
          )}
          icon={Clock}
          description="Backend analysis duration"
          accent="text-blue-400"
        />

        <StatCard
          label="State Validation"
          value={validationStatus}
          icon={ShieldCheck}
          description={
            result
              ? `${result.validation.error_count} errors · ${result.validation.warning_count} warnings`
              : 'Awaiting analysis result'
          }
          accent={validationAccent}
        />

      </div>

      {result && (
        <section className="rounded-xl border border-slate-800 bg-[#111827] p-5">

          <h3 className="mb-5 font-semibold">
            Tournament Information
          </h3>

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

            {[
              {
                label: 'Small Blind',
                value: formatNumber(
                  result.table.small_blind
                ),
              },
              {
                label: 'Big Blind',
                value: formatNumber(
                  result.table.big_blind
                ),
              },
              {
                label: 'Tournament Position',
                value:
                  result.table
                    .tournament_position ?? '—',
              },
              {
                label: 'Prize Pool',
                value:
                  result.table
                    .prize_pool_display ?? '—',
              },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-lg border border-slate-800 bg-[#0b1018] p-4"
              >

                <p className="text-xs text-slate-400">
                  {item.label}
                </p>

                <p className="mt-2 text-lg font-semibold">
                  {item.value}
                </p>

              </div>
            ))}

          </div>

        </section>
      )}

      <PlayerTable
  players={result?.players ?? []}
  hasResult={result !== null}
  compact
/>

    </div>
  )
}
