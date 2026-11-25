
import { useState } from 'react'

import {
  Users,
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  UserRound,
} from 'lucide-react'

import type {
  PokerPlayer,
} from '../../types/poker'

import {
  formatNumber,
  formatSeat,
} from '../../utils/formatters'

import ConfidenceIndicator
  from '../players/ConfidenceIndicator'

interface PlayerTableProps {
  players: PokerPlayer[]
  hasResult?: boolean
  compact?: boolean
}

type SortField =
  | 'seat'
  | 'name'
  | 'stack'
  | 'name_confidence'
  | 'stack_confidence'
  | 'bounty_confidence'

type SortDirection =
  | 'asc'
  | 'desc'

export default function PlayerTable({
  players,
  hasResult = false,
  compact = false,
}: PlayerTableProps) {

  const [search, setSearch] =
    useState('')

  const [sortField, setSortField] =
    useState<SortField>('stack')

  const [sortDirection, setSortDirection] =
    useState<SortDirection>('desc')

  // ----------------------------------------------
  // SEARCH
  // ----------------------------------------------

  const query =
    search.trim().toLowerCase()

  const filteredPlayers = players.filter(
    (player) => {

      const searchableText = [
        player.name ?? '',
        player.seat,
        formatSeat(player.seat),
        player.bounty_display ?? '',
        player.stack?.toString() ?? '',
        formatNumber(player.stack),
      ]
        .join(' ')
        .toLowerCase()

      return searchableText.includes(query)
    }
  )

  // ----------------------------------------------
  // SORT
  // ----------------------------------------------

  const sortedPlayers =
    [...filteredPlayers].sort((a, b) => {

      const first = a[sortField]
      const second = b[sortField]

      // Always place missing values last.

      if (first == null && second == null) {
        return 0
      }

      if (first == null) {
        return 1
      }

      if (second == null) {
        return -1
      }

      const comparison =
        typeof first === 'number' &&
        typeof second === 'number'
          ? first - second
          : String(first).localeCompare(
              String(second)
            )

      return sortDirection === 'asc'
        ? comparison
        : -comparison
    })

  function changeSort(
    field: SortField
  ) {
    if (field === sortField) {

      setSortDirection(
        (previous) =>
          previous === 'asc'
            ? 'desc'
            : 'asc'
      )

      return
    }

    setSortField(field)

    setSortDirection(
      field === 'name' ||
      field === 'seat'
        ? 'asc'
        : 'desc'
    )
  }

  function renderSortIcon(
    field: SortField
  ) {
    if (sortField !== field) {
      return (
        <ArrowUpDown
          size={12}
          className="text-slate-600"
        />
      )
    }

    return sortDirection === 'asc'
      ? <ArrowUp size={12} />
      : <ArrowDown size={12} />
  }

  function renderSortableHeader(
    label: string,
    field: SortField
  ) {
    return (
      <th
        scope="col"
        aria-sort={
          sortField !== field
            ? 'none'
            : sortDirection === 'asc'
              ? 'ascending'
              : 'descending'
        }
        className="px-4 py-4"
      >

        <button
          type="button"
          onClick={() => changeSort(field)}
          className="flex items-center gap-2 whitespace-nowrap font-medium hover:text-slate-200"
        >

          {label}

          {renderSortIcon(field)}

        </button>

      </th>
    )
  }

  const columnCount =
    compact ? 5 : 7

  // ----------------------------------------------
  // COMPONENT
  // ----------------------------------------------

  return (
    <section className="min-w-0 overflow-hidden rounded-xl border border-slate-800 bg-[#111827]">

      {/* HEADER */}

      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 p-5">

        <div className="flex items-center gap-3">

          <div className="rounded-lg bg-emerald-500/10 p-2.5">

            <Users
              size={20}
              className="text-emerald-400"
            />

          </div>

          <div>

            <h3 className="font-semibold">
              Player Information
            </h3>

            <p className="mt-1 text-xs text-slate-400">

              {hasResult
                ? `${players.length} players detected`
                : 'Awaiting screenshot analysis'}

            </p>

          </div>

        </div>

        {!compact && (
          <div className="relative w-full sm:w-64">

            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"
            />

            <input
              type="search"
              aria-label="Search players"
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="Search players..."
              className="w-full rounded-lg border border-slate-700 bg-[#0b1018] py-2.5 pl-10 pr-3 text-sm outline-none focus:border-emerald-500"
            />

          </div>
        )}

      </div>

      {/* PLAYER TABLE */}

      <div className="overflow-x-auto">

        <table className="w-full whitespace-nowrap text-left text-sm">

          <thead className="bg-[#0b1018] text-xs uppercase tracking-wider text-slate-500">

            <tr>

              {renderSortableHeader(
                'Seat',
                'seat'
              )}

              {renderSortableHeader(
                'Player',
                'name'
              )}

              {renderSortableHeader(
                'Stack',
                'stack'
              )}

              <th
                scope="col"
                className="px-4 py-4 font-medium"
              >
                Bounty
              </th>

              {renderSortableHeader(
                'Name OCR',
                'name_confidence'
              )}

              {!compact && (
                <>
                  {renderSortableHeader(
                    'Stack OCR',
                    'stack_confidence'
                  )}

                  {renderSortableHeader(
                    'Bounty OCR',
                    'bounty_confidence'
                  )}
                </>
              )}

            </tr>

          </thead>

          <tbody className="divide-y divide-slate-800/70">

            {sortedPlayers.map(
              (player, index) => (

                <tr
                  key={`${player.seat}-${index}`}
                  className="transition-colors hover:bg-slate-800/40"
                >

                  <td className="px-4 py-4 text-xs text-slate-400">

                    {formatSeat(player.seat)}

                  </td>

                  <td className="px-4 py-4">

                    <div className="flex items-center gap-3">

                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-800">

                        <UserRound
                          size={17}
                          className="text-slate-400"
                        />

                      </div>

                      <span className="font-medium text-slate-200">

                        {player.name ?? 'Unknown'}

                      </span>

                    </div>

                  </td>

                  <td className="px-4 py-4 font-semibold tabular-nums text-emerald-400">

                    {formatNumber(player.stack)}

                  </td>

                  <td className="px-4 py-4 font-medium text-amber-400">

                    {player.bounty_display ?? '—'}

                  </td>

                  <td className="px-4 py-4">

                    <ConfidenceIndicator
                      value={player.name_confidence}
                      label="Name OCR confidence"
                    />

                  </td>

                  {!compact && (
                    <>
                      <td className="px-4 py-4">

                        <ConfidenceIndicator
                          value={player.stack_confidence}
                          label="Stack OCR confidence"
                        />

                      </td>

                      <td className="px-4 py-4">

                        <ConfidenceIndicator
                          value={player.bounty_confidence}
                          label="Bounty OCR confidence"
                        />

                      </td>
                    </>
                  )}

                </tr>

              )
            )}

            {sortedPlayers.length === 0 && (
              <tr>

                <td
                  colSpan={columnCount}
                  className="px-5 py-14 text-center"
                >

                  <Users
                    size={30}
                    className="mx-auto mb-3 text-slate-600"
                  />

                  <p className="text-sm text-slate-400">

                    {!hasResult
                      ? 'No analysis result available.'
                      : players.length === 0
                        ? 'No players were detected.'
                        : 'No matching players found.'}

                  </p>

                </td>

              </tr>
            )}

          </tbody>

        </table>

      </div>

      {/* FOOTER */}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 px-5 py-4 text-xs text-slate-500">

        <span>

          Showing {sortedPlayers.length} of {
            players.length
          } players

        </span>

        <span>

          Source: Screenshot recognition

        </span>

      </div>

    </section>
  )
}
