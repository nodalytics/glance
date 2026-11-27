
import {
  Cpu,
  Settings2,
} from 'lucide-react'

import type {
  PokerState,
} from '../../types/poker'

import {
  formatConfidence,
  formatNumber,
  formatSeat,
} from '../../utils/formatters'

interface RecognitionProfileProps {
  result: PokerState | null
}

export default function RecognitionProfile({
  result,
}: RecognitionProfileProps) {

  const metadata =
    result?.metadata

  const profile =
    metadata?.profile_info

  const screenshot =
    metadata?.screenshot

  const rows = [
    {
      label: 'Recognition profile',
      value:
        profile?.profile ??
        metadata?.recognition_profile ??
        '—',
    },
    {
      label: 'Recognizer',
      value: profile?.recognizer ?? '—',
    },
    {
      label: 'Suit templates',
      value: formatNumber(
        profile?.template_count
      ),
    },
    {
      label: 'Occupancy detection',
      value: profile
        ? profile.occupancy_detection_enabled
          ? 'Enabled'
          : 'Disabled'
        : '—',
    },
    {
      label: 'Dataset type',
      value: metadata?.dataset_type ?? '—',
    },
    {
      label: 'Table data origin',
      value: metadata?.table_data_origin
        ? formatSeat(
            metadata.table_data_origin
          )
        : '—',
    },
    {
      label: 'OCR items extracted',
      value: formatNumber(
        metadata?.ocr_item_count
      ),
    },
    {
      label: 'Screenshot',
      value: screenshot?.filename ?? '—',
    },
    {
      label: 'Image dimensions',
      value: screenshot
        ? `${screenshot.width} × ${screenshot.height}`
        : '—',
    },
    {
      label: 'Layout',
      value: screenshot?.layout ?? '—',
    },
  ]

  const thresholds = [
    {
      label: 'Rank confidence threshold',
      value: profile?.rank_confidence_threshold,
    },
    {
      label: 'Suit confidence threshold',
      value: profile?.suit_confidence_threshold,
    },
    {
      label: 'Suit margin threshold',
      value: profile?.suit_margin_threshold,
    },
  ]

  return (
    <section className="rounded-xl border border-slate-800 bg-[#111827] p-5">

      <div className="mb-5 flex items-center gap-3">

        <div className="rounded-lg bg-violet-500/10 p-2.5">

          <Cpu
            size={20}
            className="text-violet-400"
          />

        </div>

        <div>

          <h3 className="font-semibold">
            Recognition Profile
          </h3>

          <p className="mt-1 text-xs text-slate-400">
            Engine configuration and screenshot metadata
          </p>

        </div>

      </div>

      {rows.map((item) => (

        <div
          key={item.label}
          className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 py-3"
        >

          <span className="text-sm text-slate-400">

            {item.label}

          </span>

          <span className="break-all text-sm font-medium text-slate-200">

            {item.value}

          </span>

        </div>

      ))}

      <div className="mt-6">

        <div className="mb-4 flex items-center gap-2">

          <Settings2
            size={17}
            className="text-slate-400"
          />

          <h4 className="text-sm font-semibold">
            Recognition Thresholds
          </h4>

        </div>

        <div className="space-y-3">

          {thresholds.map((item) => (

            <div
              key={item.label}
              className="flex items-center justify-between gap-3 rounded-lg bg-[#0b1018] p-3"
            >

              <span className="text-xs text-slate-400">

                {item.label}

              </span>

              <span className="text-sm font-semibold tabular-nums text-violet-400">

                {formatConfidence(item.value)}

              </span>

            </div>

          ))}

        </div>

      </div>

      <p className="mt-5 text-xs leading-relaxed text-slate-500">

        These settings describe the recognition
        profile used for this analysis.
        They are read-only.

      </p>

    </section>
  )
}
