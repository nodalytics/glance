
import type {
  Suit,
  Street,
} from '../types/poker'

export function formatNumber(
  value: number | null | undefined
): string {
  if (
    value == null ||
    !Number.isFinite(value)
  ) {
    return '—'
  }

  return new Intl.NumberFormat(
    'en-US'
  ).format(value)
}

export function formatConfidence(
  value: number | null | undefined
): string {
  if (
    value == null ||
    !Number.isFinite(value)
  ) {
    return '—'
  }

  return `${(value * 100).toFixed(2)}%`
}

export function formatDuration(
  seconds: number | null | undefined
): string {
  if (
    seconds == null ||
    !Number.isFinite(seconds) ||
    seconds < 0
  ) {
    return '—'
  }

  if (seconds < 60) {
    return `${seconds.toFixed(2)}s`
  }

  const minutes = Math.floor(
    seconds / 60
  )

  const remaining = Math.floor(
    seconds % 60
  )

  return `${minutes}m ${remaining}s`
}

export function formatFileSize(
  bytes: number
): string {
  if (
    !Number.isFinite(bytes) ||
    bytes < 0
  ) {
    return '—'
  }

  if (bytes < 1024) {
    return `${bytes} B`
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KiB`
  }

  return `${(
    bytes / (1024 * 1024)
  ).toFixed(2)} MiB`
}

export function formatStreet(
  street: Street | null | undefined
): string {
  if (!street) {
    return '—'
  }

  const labels: Record<Street, string> = {
    preflop: 'Preflop',
    flop: 'Flop',
    turn: 'Turn',
    river: 'River',
  }

  return labels[street]
}

export function formatSeat(
  seat: string
): string {
  return seat
    .split('_')
    .filter(Boolean)
    .map(
      (part) =>
        part.charAt(0).toUpperCase() +
        part.slice(1)
    )
    .join(' ')
}

export function getSuitSymbol(
  suit: Suit | null
): string {
  if (!suit) return '?'

  const symbols: Record<Suit, string> = {
    hearts: '♥',
    diamonds: '♦',
    clubs: '♣',
    spades: '♠',
  }

  return symbols[suit]
}

export function isRedSuit(
  suit: Suit | null
): boolean {
  return (
    suit === 'hearts' ||
    suit === 'diamonds'
  )
}
