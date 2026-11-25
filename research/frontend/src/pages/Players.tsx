
import {
  Users,
  Coins,
  Trophy,
  ScanLine,
  TriangleAlert,
  UserRound,
} from 'lucide-react'

import StatCard
  from '../components/dashboard/StatCard'

import PlayerTable
  from '../components/dashboard/PlayerTable'

import StackDistribution
  from '../components/players/StackDistribution'

import ConfidenceIndicator
  from '../components/players/ConfidenceIndicator'

import type {
  PokerState,
} from '../types/poker'

import {
  calculatePlayerAnalytics,
} from '../utils/playerAnalytics'

import {
  formatNumber,
  formatConfidence,
} from '../utils/formatters'

interface PlayersProps {
  result: PokerState | null
  onViewDashboard: () => void
}

export default function Players({
  result,
  onViewDashboard,
}: PlayersProps) {

  const players =
    result?.players ?? []

  const analytics =
    calculatePlayerAnalytics(players)

  return (
    <div className="space-y-6">

      {/* PAGE HEADER */}

      <div>

        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-emerald-400">
          Player Analytics
        </p>

        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
          Players
        </h1>

        <p className="mt-2 text-sm text-slate-400">
          Inspect recognized player records,
          chip stacks, bounties and OCR confidence.
        </p>

      </div>

      {/* EMPTY STATE */}

      {!result && (
        <section className="rounded-xl border border-slate-800 bg-[#111827] px-6 py-16 text-center">

          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/10">

            <Users
              size={30}
              className="text-emerald-400"
            />

          </div>

          <h2 className="text-xl font-semibold">
            No player information available
          </h2>

          <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-slate-400">

            Analyze a saved screenshot from the
            Dashboard to populate the player
            information workspace.

          </p>

          <button
            onClick={onViewDashboard}
            className="mt-6 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-emerald-500"
          >

            Go to Dashboard

          </button>

        </section>
      )}

      {/* VALIDATION WARNING */}

      {result &&
        result.status !== 'valid' && (

          <div
            role="alert"
            className="flex items-start gap-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-400"
          >

            <TriangleAlert
              size={20}
              className="shrink-0"
            />

            <p>

              This screenshot contains validation
              warnings or errors. Some player
              information may be incomplete
              or incorrect.

            </p>

          </div>

        )}

      {/* SUMMARY CARDS */}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

        <StatCard
          label="Detected Players"
          value={
            result
              ? analytics.playerCount
              : '—'
          }
          icon={Users}
          description="Recognized player records"
        />

        <StatCard
          label="Total Detected Chips"
          value={formatNumber(
            analytics.totalStack
          )}
          icon={Coins}
          description={`${analytics.knownStackCount} known stacks`}
          accent="text-amber-400"
        />

        <StatCard
          label="Largest Stack"
          value={formatNumber(
            analytics.largestStack
          )}
          icon={Trophy}
          description="Largest detected chip stack"
          accent="text-violet-400"
        />

        <StatCard
          label="Average Name Confidence"
          value={formatConfidence(
            analytics.averageNameConfidence
          )}
          icon={ScanLine}
          description="Mean reported OCR confidence"
          accent="text-blue-400"
        />

      </div>

      {/* ANALYTICS PANELS */}

      <div className="grid items-start gap-6 xl:grid-cols-2">

        <StackDistribution
          players={players}
        />

        <section className="rounded-xl border border-slate-800 bg-[#111827] p-5">

          <div className="mb-6 flex items-center gap-3">

            <div className="rounded-lg bg-blue-500/10 p-2.5">

              <ScanLine
                size={20}
                className="text-blue-400"
              />

            </div>

            <div>

              <h3 className="font-semibold">
                Recognition Summary
              </h3>

              <p className="mt-1 text-xs text-slate-400">
                Mean confidence by field
              </p>

            </div>

          </div>

          <div className="space-y-5">

            {[
              {
                label: 'Player names',
                value:
                  analytics.averageNameConfidence,
              },
              {
                label: 'Chip stacks',
                value:
                  analytics.averageStackConfidence,
              },
              {
                label: 'Bounty amounts',
                value:
                  analytics.averageBountyConfidence,
              },
            ].map((item) => (

              <div
                key={item.label}
                className="rounded-lg border border-slate-800 bg-[#0b1018] p-4"
              >

                <p className="mb-3 text-sm text-slate-300">

                  {item.label}

                </p>

                <ConfidenceIndicator
                  value={item.value}
                  label={item.label}
                />

              </div>

            ))}

          </div>

          <div className="mt-6 border-t border-slate-800 pt-5">

            <div className="mb-4 flex items-center gap-2">

              <UserRound
                size={17}
                className="text-slate-400"
              />

              <h4 className="text-sm font-medium">
                Stack Summary
              </h4>

            </div>

            <div className="space-y-4 text-sm">

              {[
                {
                  label: 'Average detected stack',
                  value: formatNumber(
                    analytics.averageStack === null
                      ? null
                      : Math.round(
                          analytics.averageStack
                        )
                  ),
                },
                {
                  label: 'Smallest detected stack',
                  value: formatNumber(
                    analytics.smallestStack
                  ),
                },
                {
                  label: 'Tournament average stack',
                  value: formatNumber(
                    result?.table.average_stack
                  ),
                },
                {
                  label: 'Known stack records',
                  value:
                    `${analytics.knownStackCount}/${analytics.playerCount}`,
                },
              ].map((item) => (

                <div
                  key={item.label}
                  className="flex items-center justify-between gap-3"
                >

                  <span className="text-slate-400">

                    {item.label}

                  </span>

                  <span className="font-medium tabular-nums">

                    {item.value}

                  </span>

                </div>

              ))}

            </div>

          </div>

          <p className="mt-5 text-xs leading-relaxed text-slate-500">

            Confidence values are reported by
            the recognition engine. They do
            not guarantee that a recognized
            value is correct.

          </p>

        </section>

      </div>

      {/* DETAILED PLAYER RECORDS */}

      <PlayerTable
        players={players}
        hasResult={result !== null}
      />

    </div>
  )
}
