
import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  label: string
  value: string | number
  icon: LucideIcon
  description?: string
  accent?: string
}

export default function StatCard({
  label,
  value,
  icon: Icon,
  description,
  accent = 'text-emerald-400',
}: StatCardProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-[#111827] p-5 transition-colors hover:border-slate-700">

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-slate-400">
          {label}
        </p>

        <div className="rounded-lg bg-slate-800/70 p-2.5">
          <Icon
            size={19}
            className={accent}
          />
        </div>
      </div>

      <p className="mt-4 text-2xl font-semibold tracking-tight">
        {value}
      </p>

      {description && (
        <p className="mt-2 text-xs text-slate-500">
          {description}
        </p>
      )}

    </div>
  )
}
