
import {
  ShieldCheck,
  ShieldAlert,
  CircleCheck,
  CircleAlert,
  TriangleAlert,
  Copy,
} from 'lucide-react'

import type {
  PokerState,
  ValidationIssue,
} from '../../types/poker'

import {
  formatSeat,
  getSuitSymbol,
} from '../../utils/formatters'

interface ValidationPanelProps {
  result: PokerState | null
}

function IssueList({
  issues,
  warning = false,
}: {
  issues: ValidationIssue[]
  warning?: boolean
}) {

  const Icon =
    warning ? TriangleAlert : CircleAlert

  return (
    <div className="space-y-3">

      {issues.map((issue, index) => (

        <div
          key={`${issue.code}-${index}`}
          className={`rounded-lg border p-3 ${
            warning
              ? 'border-amber-500/20 bg-amber-500/5'
              : 'border-red-500/20 bg-red-500/5'
          }`}
        >

          <div className="flex items-start gap-3">

            <Icon
              size={18}
              className={`shrink-0 ${
                warning
                  ? 'text-amber-400'
                  : 'text-red-400'
              }`}
            />

            <div className="min-w-0">

              <p className="break-all font-mono text-xs text-slate-400">

                {issue.code}

              </p>

              <p className="mt-2 text-sm text-slate-200">

                {issue.message}

              </p>

              {issue.slots?.length > 0 && (

                <p className="mt-2 text-xs text-slate-500">

                  Slots: {
                    issue.slots
                      .map(formatSeat)
                      .join(', ')
                  }

                </p>

              )}

            </div>

          </div>

        </div>

      ))}

    </div>
  )
}

function CheckRow({
  label,
  passed,
}: {
  label: string
  passed: boolean | null
}) {

  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-800 py-3 last:border-0">

      <span className="text-sm text-slate-400">
        {label}
      </span>

      {passed === null ? (

        <span className="text-xs text-slate-500">
          Unknown
        </span>

      ) : passed ? (

        <span className="flex items-center gap-2 text-xs text-emerald-400">
          <CircleCheck size={15} />
          Passed
        </span>

      ) : (

        <span className="flex items-center gap-2 text-xs text-red-400">
          <CircleAlert size={15} />
          Failed
        </span>

      )}

    </div>
  )
}

export default function ValidationPanel({
  result,
}: ValidationPanelProps) {

  const validation =
    result?.validation

  const cardValidation =
    validation?.card_validation

  const valid =
    validation?.valid === true

  const tableValid =
    validation?.table_validation?.valid

  const parserValid =
    validation?.parser_validation?.valid

  const StatusIcon =
    valid ? ShieldCheck : ShieldAlert

  return (
    <section className="rounded-xl border border-slate-800 bg-[#111827] p-5">

      <div className="mb-5 flex items-center gap-3">

        <div className="rounded-lg bg-emerald-500/10 p-2.5">

          <ShieldCheck
            size={20}
            className="text-emerald-400"
          />

        </div>

        <div>

          <h3 className="font-semibold">
            State Validation
          </h3>

          <p className="mt-1 text-xs text-slate-400">
            Consistency checks and detected issues
          </p>

        </div>

      </div>

      {!validation || !cardValidation ? (

        <p className="py-12 text-center text-sm text-slate-500">

          Awaiting analysis result.

        </p>

      ) : (

        <>

          <div className={`flex items-center gap-3 rounded-lg border p-4 ${
            !valid
              ? 'border-red-500/20 bg-red-500/5 text-red-400'
              : result.status === 'partial'
                ? 'border-amber-500/20 bg-amber-500/5 text-amber-400'
                : 'border-emerald-500/20 bg-emerald-500/5 text-emerald-400'
          }`}>

            <StatusIcon size={26} />

            <div>

              <p className="font-semibold">

                {!valid
                  ? 'Validation failed'
                  : result.status === 'partial'
                    ? 'Passed with warnings'
                    : 'Validation passed'}

              </p>

              <p className="mt-1 text-xs">

                {validation.error_count}
                {' errors · '}
                {validation.warning_count}
                {' warnings'}

              </p>

            </div>

          </div>

          <div className="mt-5">

            <CheckRow
              label="Card consistency"
              passed={cardValidation.valid}
            />

            <CheckRow
              label="Table data validation"
              passed={
                typeof tableValid === 'boolean'
                  ? tableValid
                  : null
              }
            />

            <CheckRow
              label="Screenshot parser validation"
              passed={
                typeof parserValid === 'boolean'
                  ? parserValid
                  : null
              }
            />

            <CheckRow
              label="Duplicate card check"
              passed={
                cardValidation.duplicate_count === 0
              }
            />

            <CheckRow
              label="Card occupancy known"
              passed={
                cardValidation.unknown_count === 0
              }
            />

          </div>

          <div className="mt-6 grid grid-cols-2 gap-3">

            {[
              {
                label: 'Board cards',
                value: cardValidation.board_count,
              },
              {
                label: 'Hero cards',
                value: cardValidation.hero_count,
              },
              {
                label: 'Occupied slots',
                value: cardValidation.occupied_count,
              },
              {
                label: 'Empty slots',
                value: cardValidation.empty_count,
              },
              {
                label: 'Unknown slots',
                value: cardValidation.unknown_count,
              },
              {
                label: 'Duplicate cards',
                value: cardValidation.duplicate_count,
              },
            ].map((item) => (

              <div
                key={item.label}
                className="rounded-lg bg-[#0b1018] p-3"
              >

                <p className="text-xs text-slate-500">
                  {item.label}
                </p>

                <p className="mt-2 text-xl font-semibold tabular-nums">
                  {item.value}
                </p>

              </div>

            ))}

          </div>

          {cardValidation.duplicates.length > 0 && (

            <div className="mt-6">

              <h4 className="mb-3 flex items-center gap-2 text-sm font-medium text-red-400">

                <Copy size={16} />
                Duplicate Cards

              </h4>

              {cardValidation.duplicates.map(
                (duplicate, index) => (

                  <div
                    key={index}
                    className="mb-2 rounded-lg border border-red-500/20 bg-red-500/5 p-3"
                  >

                    <p className="font-semibold">

                      {duplicate.rank}
                      {getSuitSymbol(
                        duplicate.suit
                      )}

                    </p>

                    <p className="mt-1 text-xs text-slate-400">

                      {duplicate.slots
                        .map(formatSeat)
                        .join(', ')}

                    </p>

                  </div>

                )
              )}

            </div>

          )}

          <div className="mt-6">

            <h4 className="mb-3 text-sm font-semibold">
              Validation Errors
            </h4>

            {validation.errors.length > 0 ? (

              <IssueList
                issues={validation.errors}
              />

            ) : (

              <p className="flex items-center gap-2 text-xs text-emerald-400">

                <CircleCheck size={15} />
                No validation errors

              </p>

            )}

          </div>

          <div className="mt-6">

            <h4 className="mb-3 text-sm font-semibold">
              Validation Warnings
            </h4>

            {validation.warnings.length > 0 ? (

              <IssueList
                issues={validation.warnings}
                warning
              />

            ) : (

              <p className="flex items-center gap-2 text-xs text-emerald-400">

                <CircleCheck size={15} />
                No validation warnings

              </p>

            )}

          </div>

        </>

      )}

    </section>
  )
}
