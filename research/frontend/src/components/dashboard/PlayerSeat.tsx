
import { UserRound } from 'lucide-react'

import type {
  PokerPlayer,
} from '../../types/poker'

import {
  formatNumber,
  formatSeat,
  formatConfidence,
} from '../../utils/formatters'

interface PlayerSeatProps {
  player?: PokerPlayer | null
  label: string
  x: number
  y: number
}

export default function PlayerSeat({
  player,
  label,
  x,
  y,
}: PlayerSeatProps) {

  const tooltip = player
    ? [
        `Seat: ${formatSeat(player.seat)}`,
        `Player: ${player.name ?? 'Unknown'}`,
        `Stack: ${formatNumber(player.stack)}`,
        `Bounty: ${player.bounty_display ?? '—'}`,
        `Name confidence: ${
          formatConfidence(
            player.name_confidence
          )
        }`,
        `Stack confidence: ${
          formatConfidence(
            player.stack_confidence
          )
        }`,
      ].join('\n')
    : label

  return (
    <div
      title={tooltip}
      style={{
        left: `${x}%`,
        top: `${y}%`,
      }}
      className={`
        absolute z-10
        flex w-[22%] max-w-32
        -translate-x-1/2
        -translate-y-1/2
        flex-col items-center
        rounded-lg border
        px-1 py-1.5 shadow-lg
        sm:px-2 sm:py-2
        ${
          player
            ? 'border-slate-600 bg-[#1e293b]'
            : 'border-slate-700 bg-[#17212f]'
        }
      `}
    >

      <div className="flex w-full min-w-0 items-center justify-center gap-1">

        <UserRound
          size={11}
          className="hidden shrink-0 text-slate-400 sm:block"
        />

        <p className="truncate text-[9px] font-medium text-slate-200 sm:text-xs">
          {player?.name ?? label}
        </p>

      </div>

      <p className="mt-1 text-[10px] font-semibold tabular-nums text-emerald-400 sm:text-sm">
        {formatNumber(player?.stack)}
      </p>

      {player?.bounty_display && (
        <p className="mt-0.5 text-[8px] text-amber-400 sm:text-[10px]">
          {player.bounty_display}
        </p>
      )}

    </div>
  )
}
