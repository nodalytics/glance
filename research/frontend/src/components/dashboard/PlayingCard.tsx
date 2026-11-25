
import {
  Spade,
  HelpCircle,
} from 'lucide-react'

import type {
  PokerCard,
} from '../../types/poker'

import {
  getSuitSymbol,
  isRedSuit,
  formatConfidence,
} from '../../utils/formatters'

interface PlayingCardProps {
  card?: PokerCard | null
  hero?: boolean
}

export default function PlayingCard({
  card,
  hero = false,
}: PlayingCardProps) {

  const baseClass = `
    relative flex aspect-[0.72] w-full
    select-none flex-col items-center
    justify-center rounded-md
    sm:rounded-lg
  `

  // Empty slot or no analysis available.

  if (!card || card.occupied === false) {
    return (
      <div
        aria-label="Empty card slot"
        className={`${baseClass}
          border border-dashed
          border-emerald-300/25
          bg-black/15
        `}
      >
        <Spade
          size={18}
          className="text-emerald-200/20"
        />
      </div>
    )
  }

  // Occupied or uncertain slot,
  // but recognition was unsuccessful.

  if (
    !card.recognized ||
    !card.rank ||
    !card.suit
  ) {
    return (
      <div
        title="Card recognition uncertain"
        aria-label="Unrecognized card"
        className={`${baseClass}
          border border-amber-500/50
          bg-amber-500/10
          text-amber-400
        `}
      >
        <HelpCircle size={22} />

        <span className="mt-1 text-[8px]">
          Unknown
        </span>
      </div>
    )
  }

  const symbol =
    getSuitSymbol(card.suit)

  const red =
    isRedSuit(card.suit)

  const tooltip = [
    `${card.rank} of ${card.suit}`,
    `Rank confidence: ${
      formatConfidence(
        card.rank_confidence
      )
    }`,
    `Suit confidence: ${
      formatConfidence(
        card.suit_confidence
      )
    }`,
  ].join('\n')

  return (
    <div
      title={tooltip}
      aria-label={`${card.rank} of ${card.suit}`}
      className={`${baseClass}
        border bg-slate-50 shadow-lg
        transition-transform duration-150
        hover:-translate-y-1
        ${
          hero
            ? 'border-emerald-400'
            : 'border-slate-300'
        }
        ${
          red
            ? 'text-red-600'
            : 'text-slate-900'
        }
      `}
    >

      <div className="absolute left-1 top-1 flex flex-col items-center leading-none sm:left-1.5 sm:top-1.5">

        <span className="text-[9px] font-bold sm:text-xs">
          {card.rank}
        </span>

        <span className="text-[10px] sm:text-sm">
          {symbol}
        </span>

      </div>

      <span className="text-lg font-bold leading-none sm:text-3xl">
        {card.rank}
      </span>

      <span className="mt-1 text-xl leading-none sm:text-3xl">
        {symbol}
      </span>

      <div className="absolute bottom-1 right-1 rotate-180 text-[10px] leading-none sm:bottom-1.5 sm:right-1.5 sm:text-sm">
        {symbol}
      </div>

    </div>
  )
}
