
import {
  ScanLine,
  CircleCheck,
  CircleHelp,
  CircleMinus,
} from 'lucide-react'

import PlayingCard
  from '../dashboard/PlayingCard'

import ConfidenceIndicator
  from '../players/ConfidenceIndicator'

import type {
  PokerState,
  PokerCard,
} from '../../types/poker'

import {
  formatSeat,
  formatConfidence,
} from '../../utils/formatters'

interface CardRecognitionTableProps {
  result: PokerState | null
}

function CardStatus({
  card,
}: {
  card: PokerCard
}) {
  if (card.occupied === false) {
    return (
      <span className="flex items-center gap-2 text-xs text-slate-500">
        <CircleMinus size={15} />
        Empty
      </span>
    )
  }

  if (
    card.recognized &&
    card.rank &&
    card.suit
  ) {
    return (
      <span className="flex items-center gap-2 text-xs text-emerald-400">
        <CircleCheck size={15} />
        Recognized
      </span>
    )
  }

  return (
    <span className="flex items-center gap-2 text-xs text-amber-400">
      <CircleHelp size={15} />
      Uncertain
    </span>
  )
}

export default function CardRecognitionTable({
  result,
}: CardRecognitionTableProps) {

  const cards = result
    ? [
        ...result.cards.board_slots,
        ...result.cards.hero_slots,
      ]
    : []

  return (
    <section className="min-w-0 overflow-hidden rounded-xl border border-slate-800 bg-[#111827]">

      <div className="flex items-center gap-3 border-b border-slate-800 p-5">

        <div className="rounded-lg bg-emerald-500/10 p-2.5">

          <ScanLine
            size={20}
            className="text-emerald-400"
          />

        </div>

        <div>

          <h3 className="font-semibold">
            Card Recognition Details
          </h3>

          <p className="mt-1 text-xs text-slate-400">
            Individual card results and confidence scores
          </p>

        </div>

      </div>

      <div className="overflow-x-auto">

        <table className="w-full whitespace-nowrap text-left text-sm">

          <thead className="bg-[#0b1018] text-xs uppercase tracking-wider text-slate-500">

            <tr>

              {[
                'Slot',
                'Card',
                'Status',
                'Occupancy',
                'Rank OCR',
                'Suit Score',
                'Suit Margin',
                'OCR Skipped',
              ].map((column) => (

                <th
                  key={column}
                  scope="col"
                  className="px-4 py-4 font-medium"
                >
                  {column}
                </th>

              ))}

            </tr>

          </thead>

          <tbody className="divide-y divide-slate-800/70">

            {cards.map((card) => (

              <tr
                key={card.slot}
                className="hover:bg-slate-800/30"
              >

                <td className="px-4 py-4 font-medium">

                  {formatSeat(card.slot)}

                </td>

                <td className="px-4 py-4">

                  <div className="w-12">

                    <PlayingCard
                      card={card}
                      hero={
                        card.slot.startsWith(
                          'hero_'
                        )
                      }
                    />

                  </div>

                </td>

                <td className="px-4 py-4">

                  <CardStatus card={card} />

                </td>

                <td className="px-4 py-4 text-xs text-slate-400">

                  {card.occupancy_state
                    ? formatSeat(
                        card.occupancy_state
                      )
                    : card.occupied === true
                      ? 'Occupied'
                      : card.occupied === false
                        ? 'Empty'
                        : 'Unknown'}

                </td>

                <td className="px-4 py-4">

                  <ConfidenceIndicator
                    value={card.rank_confidence}
                    label="Rank OCR confidence"
                  />

                </td>

                <td className="px-4 py-4">

                  <ConfidenceIndicator
                    value={card.suit_confidence}
                    label="Suit similarity score"
                  />

                </td>

                <td className="px-4 py-4 text-xs tabular-nums text-slate-300">

                  {formatConfidence(
                    card.suit_margin
                  )}

                </td>

                <td className="px-4 py-4 text-xs">

                  {card.ocr_skipped === true ? (

                    <span className="text-emerald-400">
                      Yes
                    </span>

                  ) : card.ocr_skipped === false ? (

                    <span className="text-slate-400">
                      No
                    </span>

                  ) : (

                    <span className="text-slate-500">
                      —
                    </span>

                  )}

                </td>

              </tr>

            ))}

            {cards.length === 0 && (

              <tr>

                <td
                  colSpan={8}
                  className="px-5 py-14 text-center text-slate-500"
                >

                  No card recognition results available.

                </td>

              </tr>

            )}

          </tbody>

        </table>

      </div>

      <div className="border-t border-slate-800 px-5 py-4 text-xs leading-relaxed text-slate-500">

        Rank confidence is reported by OCR.
        Suit scores represent template similarity.
        Suit margin represents the separation
        between competing suit scores.
        These values are not calibrated
        probabilities of correctness.

      </div>

    </section>
  )
}
