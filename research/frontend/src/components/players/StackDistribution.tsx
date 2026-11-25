
import {
  BarChart3,
} from 'lucide-react'

import type {
  PokerPlayer,
} from '../../types/poker'

import {
  formatNumber,
  formatSeat,
} from '../../utils/formatters'

interface StackDistributionProps {
  players: PokerPlayer[]
}

export default function StackDistribution({
  players,
}: StackDistributionProps) {

  const knownPlayers = players.filter(
    (
      player
    ): player is PokerPlayer & {
      stack: number
    } =>
      typeof player.stack === 'number' &&
      Number.isFinite(player.stack) &&
      player.stack >= 0
  )

  const sortedPlayers =
    [...knownPlayers].sort(
      (a, b) => b.stack - a.stack
    )

  const largestStack =
    sortedPlayers[0]?.stack ?? 0

  const totalStack =
    sortedPlayers.reduce(
      (total, player) =>
        total + player.stack,
      0
    )

  return (
    <section className="rounded-xl border border-slate-800 bg-[#111827] p-5">

      <div className="mb-6 flex items-center gap-3">

        <div className="rounded-lg bg-emerald-500/10 p-2.5">

          <BarChart3
            size={20}
            className="text-emerald-400"
          />

        </div>

        <div>

          <h3 className="font-semibold">
            Stack Distribution
          </h3>

          <p className="mt-1 text-xs text-slate-400">
            Recognized chip stacks by player
          </p>

        </div>

      </div>

      {sortedPlayers.length === 0 ? (

        <div className="py-12 text-center text-sm text-slate-500">

          No recognized stack information.

        </div>

      ) : (

        <div className="space-y-5">

          {sortedPlayers.map(
            (player, index) => {

              const barPercentage =
                largestStack > 0
                  ? (
                      player.stack /
                      largestStack
                    ) * 100
                  : 0

              const chipShare =
                totalStack > 0
                  ? (
                      player.stack /
                      totalStack
                    ) * 100
                  : null

              return (
                <div
                  key={`${player.seat}-${index}`}
                  className="space-y-2"
                >

                  <div className="flex items-center justify-between gap-3">

                    <div className="min-w-0">

                      <p className="truncate text-sm font-medium text-slate-200">

                        {player.name ??
                          formatSeat(player.seat)}

                      </p>

                      <p className="mt-0.5 text-xs text-slate-500">

                        {formatSeat(player.seat)}

                      </p>

                    </div>

                    <div className="shrink-0 text-right">

                      <p className="text-sm font-semibold tabular-nums text-emerald-400">

                        {formatNumber(player.stack)}

                      </p>

                      <p className="mt-0.5 text-xs text-slate-500">

                        {chipShare === null
                          ? '—'
                          : `${chipShare.toFixed(1)}%`}

                      </p>

                    </div>

                  </div>

                  <div className="h-2.5 overflow-hidden rounded-full bg-slate-800">

                    <div
                      title={`${formatNumber(player.stack)} chips`}
                      className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                      style={{
                        width: `${barPercentage}%`,
                      }}
                    />

                  </div>

                </div>
              )
            }
          )}

        </div>

      )}

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 pt-4">

        <div>

          <p className="text-xs text-slate-500">
            Total detected chips
          </p>

          <p className="mt-1 text-xl font-semibold tabular-nums">

            {formatNumber(
              knownPlayers.length > 0
                ? totalStack
                : null
            )}

          </p>

        </div>

        <p className="text-xs text-slate-500">

          {knownPlayers.length} of {
            players.length
          } known stacks

        </p>

      </div>

      <p className="mt-3 text-xs leading-relaxed text-slate-500">

        Bar lengths are relative to the largest
        detected stack. Percentages represent
        shares of detected chips, excluding
        unknown stacks.

      </p>

    </section>
  )
}
