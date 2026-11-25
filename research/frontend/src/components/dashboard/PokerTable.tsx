
import {
  Layers,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-react'

import PlayingCard from './PlayingCard'

import PlayerSeat from './PlayerSeat'

import type {
  PokerState,
} from '../../types/poker'

import {
  formatNumber,
  formatStreet,
} from '../../utils/formatters'

interface PokerTableProps {
  result: PokerState | null
}

const BOARD_SLOTS = [
  'board_1',
  'board_2',
  'board_3',
  'board_4',
  'board_5',
]

const HERO_SLOTS = [
  'hero_card_1',
  'hero_card_2',
]

// Generic display positions.
// Exact seat mapping can be calibrated later.

const SEAT_POSITIONS = [
  { x: 50, y: 6 },
  { x: 17, y: 19 },
  { x: 12, y: 50 },
  { x: 20, y: 83 },
  { x: 80, y: 83 },
  { x: 88, y: 50 },
  { x: 83, y: 19 },
]

export default function PokerTable({
  result,
}: PokerTableProps) {

  const boardCards =
    BOARD_SLOTS.map((slot) =>
      result?.cards.board_slots.find(
        (card) => card.slot === slot
      ) ?? null
    )

  const heroCards =
    HERO_SLOTS.map((slot) =>
      result?.cards.hero_slots.find(
        (card) => card.slot === slot
      ) ?? null
    )

  const players =
    result?.players ?? []

  const valid =
    result?.status === 'valid' &&
    result.validation.valid

  const statusClass = !result
    ? 'border-slate-700 text-slate-400'
    : valid
      ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400'
      : 'border-amber-500/20 bg-amber-500/10 text-amber-400'

  return (
    <section className="min-w-0 rounded-xl border border-slate-800 bg-[#111827] p-4 sm:p-5">

      {/* TABLE HEADER */}

      <div className="mb-6 flex items-center justify-between gap-3">

        <div className="flex items-center gap-3">

          <div className="rounded-lg bg-emerald-500/10 p-2.5">

            <Layers
              size={20}
              className="text-emerald-400"
            />

          </div>

          <div>

            <h3 className="font-semibold">
              Poker Table
            </h3>

            <p className="mt-1 text-xs text-slate-400">
              Recognized screenshot state
            </p>

          </div>

        </div>

        <span className={`rounded-full border px-3 py-1 text-xs ${statusClass}`}>

          {result
            ? formatStreet(
                result.game.street
              )
            : 'No data'}

        </span>

      </div>

      {/* TABLE VISUALIZATION */}

      <div className="relative mx-auto aspect-[1.2] w-full max-w-2xl">

        <div className="absolute inset-x-[6%] inset-y-[7%] rounded-[44%] border-[8px] border-[#293a31] bg-[#174632] shadow-2xl sm:border-[12px]">

          <div className="pointer-events-none absolute inset-2 rounded-[44%] border border-[#a18a54]/40" />

          {/* POT */}

          <div className="absolute left-1/2 top-[13%] w-[65%] -translate-x-1/2 text-center">

            <p className="text-[8px] font-semibold uppercase tracking-widest text-emerald-100/60 sm:text-xs">
              Total Pot
            </p>

            <p className="mt-1 text-lg font-bold tabular-nums text-white sm:text-3xl">

              {formatNumber(
                result?.table.pot
              )}

            </p>

          </div>

          {/* COMMUNITY CARDS */}

          <div className="absolute left-1/2 top-[31%] w-[65%] -translate-x-1/2">

            <div className="grid grid-cols-5 gap-1 sm:gap-2">

              {boardCards.map(
                (card, index) => (
                  <PlayingCard
                    key={BOARD_SLOTS[index]}
                    card={card}
                  />
                )
              )}

            </div>

            <p className="mt-2 text-center text-[8px] uppercase tracking-wider text-emerald-100/50 sm:text-[10px]">
              Community Cards
            </p>

          </div>

          {/* BLINDS */}

          <div className="absolute left-1/2 top-[60%] w-[70%] -translate-x-1/2 text-center">

            <p className="text-[8px] text-emerald-100/60 sm:text-xs">

              Blinds: {
                formatNumber(
                  result?.table.small_blind
                )
              }

              {' / '}

              {formatNumber(
                result?.table.big_blind
              )}

            </p>

          </div>

          {/* HERO CARDS */}

          <div className="absolute bottom-[5%] left-1/2 w-[25%] -translate-x-1/2">

            <div className="grid grid-cols-2 gap-1 sm:gap-2">

              {heroCards.map(
                (card, index) => (
                  <PlayingCard
                    key={HERO_SLOTS[index]}
                    card={card}
                    hero
                  />
                )
              )}

            </div>

            <p className="mt-2 text-center text-[8px] font-semibold uppercase tracking-wider text-emerald-300 sm:text-[10px]">
              Hero Cards
            </p>

          </div>

        </div>

        {/* PLAYER SEATS */}

        {SEAT_POSITIONS.map(
          (position, index) => (
            <PlayerSeat
              key={index}
              player={
                players[index] ?? null
              }
              label={`Seat ${index + 1}`}
              x={position.x}
              y={position.y}
            />
          )
        )}

      </div>

      {/* TABLE SUMMARY */}

      <div className="mt-5 grid grid-cols-3 gap-2 border-t border-slate-800 pt-4">

        <div className="rounded-lg bg-[#0b1018] p-3 text-center">

          <p className="text-[10px] text-slate-500 sm:text-xs">
            Recognized Cards
          </p>

          <p className="mt-2 text-lg font-semibold text-emerald-400">

            {result
              ? `${result.game.recognized_card_count}/${result.game.occupied_count}`
              : '—'}

          </p>

        </div>

        <div className="rounded-lg bg-[#0b1018] p-3 text-center">

          <p className="text-[10px] text-slate-500 sm:text-xs">
            Players
          </p>

          <p className="mt-2 text-lg font-semibold">

            {result
              ? players.length
              : '—'}

          </p>

        </div>

        <div className="rounded-lg bg-[#0b1018] p-3 text-center">

          <p className="text-[10px] text-slate-500 sm:text-xs">
            Validation
          </p>

          <p className={`mt-2 text-sm font-semibold sm:text-lg ${
            !result
              ? 'text-slate-500'
              : valid
                ? 'text-emerald-400'
                : 'text-amber-400'
          }`}>

            {!result
              ? 'Pending'
              : valid
                ? 'Valid'
                : result.status === 'invalid'
                  ? 'Invalid'
                  : 'Partial'}

          </p>

        </div>

      </div>

      {/* VALIDATION MESSAGE */}

      {result ? (
        <div className={`mt-4 flex items-center justify-center gap-2 text-xs ${
          valid
            ? 'text-emerald-400'
            : 'text-amber-400'
        }`}>

          {valid ? (
            <ShieldCheck size={15} />
          ) : (
            <TriangleAlert size={15} />
          )}

          {result.validation.error_count}
          {' errors · '}
          {result.validation.warning_count}
          {' warnings'}

        </div>
      ) : (
        <p className="mt-4 text-center text-xs text-slate-500">
          Analyze a saved screenshot to populate the table.
        </p>
      )}

      {result && (
        <p className="mt-3 text-center text-[10px] text-slate-500">
          Player positions are illustrative.
        </p>
      )}

    </section>
  )
}
