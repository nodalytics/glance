
import type {
  PokerPlayer,
} from '../types/poker'

export interface PlayerAnalytics {
  playerCount: number
  knownStackCount: number
  totalStack: number | null
  averageStack: number | null
  largestStack: number | null
  smallestStack: number | null
  averageNameConfidence: number | null
  averageStackConfidence: number | null
  averageBountyConfidence: number | null
}

function isValidNumber(
  value: unknown
): value is number {
  return (
    typeof value === 'number' &&
    Number.isFinite(value) &&
    value >= 0
  )
}

function average(
  values: number[]
): number | null {
  if (values.length === 0) {
    return null
  }

  return (
    values.reduce(
      (total, value) => total + value,
      0
    ) / values.length
  )
}

function averageConfidence(
  values: unknown[]
): number | null {
  const validValues = values.filter(
    (value): value is number =>
      isValidNumber(value) &&
      value <= 1
  )

  return average(validValues)
}

export function calculatePlayerAnalytics(
  players: PokerPlayer[]
): PlayerAnalytics {

  const stacks = players
    .map((player) => player.stack)
    .filter(isValidNumber)

  const totalStack =
    stacks.length > 0
      ? stacks.reduce(
          (total, stack) =>
            total + stack,
          0
        )
      : null

  return {
    playerCount: players.length,

    knownStackCount: stacks.length,

    totalStack,

    averageStack: average(stacks),

    largestStack:
      stacks.length > 0
        ? Math.max(...stacks)
        : null,

    smallestStack:
      stacks.length > 0
        ? Math.min(...stacks)
        : null,

    averageNameConfidence:
      averageConfidence(
        players.map(
          (player) =>
            player.name_confidence
        )
      ),

    averageStackConfidence:
      averageConfidence(
        players.map(
          (player) =>
            player.stack_confidence
        )
      ),

    averageBountyConfidence:
      averageConfidence(
        players.map(
          (player) =>
            player.bounty_confidence
        )
      ),
  }
}
