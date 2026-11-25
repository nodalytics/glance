
import {
  formatConfidence,
} from '../../utils/formatters'

interface ConfidenceIndicatorProps {
  value?: number | null
  label?: string
}

export default function ConfidenceIndicator({
  value,
  label = 'OCR confidence',
}: ConfidenceIndicatorProps) {

  if (
    typeof value !== 'number' ||
    !Number.isFinite(value) ||
    value < 0 ||
    value > 1
  ) {
    return (
      <span className="text-xs text-slate-500">
        —
      </span>
    )
  }

  const percentage = value * 100

  const color =
    value >= 0.95
      ? 'text-emerald-400'
      : value >= 0.75
        ? 'text-amber-400'
        : 'text-red-400'

  const barColor =
    value >= 0.95
      ? 'bg-emerald-500'
      : value >= 0.75
        ? 'bg-amber-500'
        : 'bg-red-500'

  return (
    <div
      title={`${label}: ${formatConfidence(value)}`}
      className="min-w-16 space-y-1"
    >

      <span
        className={`text-xs font-medium tabular-nums ${color}`}
      >
        {formatConfidence(value)}
      </span>

      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percentage}
        className="h-1 overflow-hidden rounded-full bg-slate-800"
      >

        <div
          className={`h-full rounded-full ${barColor}`}
          style={{
            width: `${percentage}%`,
          }}
        />

      </div>

    </div>
  )
}
