
import { useState } from 'react'

import {
  FileJson,
  Copy,
  Download,
  Check,
  ChevronsDownUp,
  ChevronsUpDown,
  Code2,
  ListTree,
  CircleAlert,
} from 'lucide-react'

import JsonTree from './JsonTree'

import type {
  PokerState,
} from '../../types/poker'

import {
  serializeJson,
  getJsonSize,
  getJsonLineCount,
  createJsonFilename,
  copyJsonToClipboard,
  downloadJson,
} from '../../utils/jsonUtils'

import type {
  JsonValue,
} from '../../utils/jsonUtils'

import {
  formatFileSize,
} from '../../utils/formatters'

interface JsonViewerProps {
  result: PokerState
}

type JsonSection =
  | 'complete'
  | 'table'
  | 'game'
  | 'cards'
  | 'players'
  | 'validation'
  | 'metadata'

type ViewerMode =
  | 'tree'
  | 'formatted'
  | 'compact'

const SECTIONS: {
  value: JsonSection
  label: string
}[] = [
  {
    value: 'complete',
    label: 'Complete Response',
  },
  {
    value: 'table',
    label: 'Table Information',
  },
  {
    value: 'game',
    label: 'Game Information',
  },
  {
    value: 'cards',
    label: 'Card Recognition',
  },
  {
    value: 'players',
    label: 'Player Records',
  },
  {
    value: 'validation',
    label: 'Validation Results',
  },
  {
    value: 'metadata',
    label: 'Processing Metadata',
  },
]

const MODES: {
  value: ViewerMode
  label: string
}[] = [
  {
    value: 'tree',
    label: 'Tree',
  },
  {
    value: 'formatted',
    label: 'Formatted',
  },
  {
    value: 'compact',
    label: 'Compact',
  },
]

export default function JsonViewer({
  result,
}: JsonViewerProps) {

  const [section, setSection] =
    useState<JsonSection>('complete')

  const [mode, setMode] =
    useState<ViewerMode>('tree')

  const [expanded, setExpanded] =
    useState(true)

  const [treeRevision, setTreeRevision] =
    useState(0)

  const [feedback, setFeedback] =
    useState<{
      type: 'success' | 'error'
      message: string
    } | null>(null)

  const selectedData =
    section === 'complete'
      ? result
      : result[section]

  const jsonText =
    serializeJson(
      selectedData,
      mode !== 'compact'
    )

  const jsonValue =
    JSON.parse(jsonText) as JsonValue

  const lines =
    jsonText.split('\n')

  const size =
    getJsonSize(jsonText)

  const lineCount =
    getJsonLineCount(jsonText)

  function changeSection(
    nextSection: JsonSection
  ) {
    setSection(nextSection)
    setFeedback(null)
    setTreeRevision(
      (previous) => previous + 1
    )
  }

  function changeMode(
    nextMode: ViewerMode
  ) {
    setMode(nextMode)
    setFeedback(null)
  }

  function changeExpansion(
    nextExpanded: boolean
  ) {
    setExpanded(nextExpanded)

    setTreeRevision(
      (previous) => previous + 1
    )
  }

  async function handleCopy() {

    try {
      await copyJsonToClipboard(
        jsonText
      )

      setFeedback({
        type: 'success',
        message: 'Selected JSON copied to clipboard.',
      })

    } catch (error) {

      setFeedback({
        type: 'error',
        message:
          error instanceof Error
            ? error.message
            : 'Unable to copy JSON.',
      })

    }
  }

  function handleDownload(
    complete = false
  ) {

    try {
      const content = complete
        ? serializeJson(result)
        : jsonText

      const filename =
        createJsonFilename(
          complete
            ? 'complete'
            : section
        )

      downloadJson(
        content,
        filename
      )

      setFeedback({
        type: 'success',
        message: 'JSON download requested.',
      })

    } catch (error) {

      setFeedback({
        type: 'error',
        message:
          error instanceof Error
            ? error.message
            : 'Unable to download JSON.',
      })

    }
  }

  return (
    <section className="min-w-0 overflow-hidden rounded-xl border border-slate-800 bg-[#111827]">

      {/* HEADER */}

      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 p-5">

        <div className="flex items-center gap-3">

          <div className="rounded-lg bg-emerald-500/10 p-2.5">

            <FileJson
              size={20}
              className="text-emerald-400"
            />

          </div>

          <div>

            <h3 className="font-semibold">
              JSON Response
            </h3>

            <p className="mt-1 text-xs text-slate-400">
              Structured analysis data
            </p>

          </div>

        </div>

        <button
          type="button"
          onClick={() => handleDownload(true)}
          className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-xs font-medium text-white hover:bg-emerald-500"
        >

          <Download size={16} />

          Export Full Response

        </button>

      </div>

      {/* TOOLBAR */}

      <div className="space-y-4 border-b border-slate-800 p-4">

        <div className="flex flex-wrap items-center justify-between gap-3">

          <select
            aria-label="JSON response section"
            value={section}
            onChange={(event) =>
              changeSection(
                event.target.value as JsonSection
              )
            }
            className="w-full rounded-lg border border-slate-700 bg-[#0b1018] px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-emerald-500 sm:w-auto"
          >

            {SECTIONS.map((item) => (

              <option
                key={item.value}
                value={item.value}
              >
                {item.label}
              </option>

            ))}

          </select>

          <div className="flex flex-wrap items-center gap-2">

            <button
              type="button"
              onClick={() => void handleCopy()}
              className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800"
            >

              <Copy size={15} />
              Copy JSON

            </button>

            <button
              type="button"
              onClick={() => handleDownload()}
              className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800"
            >

              <Download size={15} />
              Download

            </button>

          </div>

        </div>

        {/* VIEW MODE */}

        <div className="flex flex-wrap items-center justify-between gap-3">

          <div className="flex rounded-lg border border-slate-800 bg-[#0b1018] p-1">

            {MODES.map((item) => (

              <button
                key={item.value}
                type="button"
                aria-pressed={
                  mode === item.value
                }
                onClick={() =>
                  changeMode(item.value)
                }
                className={`flex items-center gap-2 rounded-md px-3 py-2 text-xs transition-colors ${
                  mode === item.value
                    ? 'bg-slate-800 text-emerald-400'
                    : 'text-slate-500 hover:text-slate-200'
                }`}
              >

                {item.value === 'tree'
                  ? <ListTree size={14} />
                  : <Code2 size={14} />}

                {item.label}

              </button>

            ))}

          </div>

          {mode === 'tree' && (

            <div className="flex flex-wrap items-center gap-2">

              <button
                type="button"
                onClick={() =>
                  changeExpansion(true)
                }
                className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-400 hover:bg-slate-800"
              >

                <ChevronsUpDown size={15} />
                Expand All

              </button>

              <button
                type="button"
                onClick={() =>
                  changeExpansion(false)
                }
                className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-400 hover:bg-slate-800"
              >

                <ChevronsDownUp size={15} />
                Collapse All

              </button>

            </div>

          )}

        </div>

        {/* FEEDBACK */}

        {feedback && (

          <div
            role={
              feedback.type === 'error'
                ? 'alert'
                : 'status'
            }
            className={`flex items-center gap-2 rounded-lg border p-3 text-xs ${
              feedback.type === 'success'
                ? 'border-emerald-500/20 bg-emerald-500/5 text-emerald-400'
                : 'border-red-500/20 bg-red-500/5 text-red-400'
            }`}
          >

            {feedback.type === 'success'
              ? <Check size={16} />
              : <CircleAlert size={16} />}

            {feedback.message}

          </div>

        )}

      </div>

      {/* JSON CONTENT */}

      <div className="max-h-[650px] min-h-80 overflow-auto bg-[#080d15] p-4">

        {mode === 'tree' ? (

          <JsonTree
            key={`${section}-${treeRevision}`}
            value={jsonValue}
            defaultExpanded={expanded}
          />

        ) : (

          <div className="font-mono text-xs leading-relaxed sm:text-sm">

            {lines.map((line, index) => (

              <div
                key={index}
                className="flex min-w-max"
              >

                <span
                  aria-hidden="true"
                  className="mr-4 inline-block w-10 shrink-0 select-none text-right text-slate-600"
                >

                  {index + 1}

                </span>

                <span className="whitespace-pre text-emerald-300">

                  {line}

                </span>

              </div>

            ))}

          </div>

        )}

      </div>

      {/* FOOTER */}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 px-5 py-4 text-xs text-slate-500">

        <div className="flex flex-wrap items-center gap-4">

          <span>
            {formatFileSize(size)}
          </span>

          <span>
            {lineCount} serialized lines
          </span>

          <span>
            UTF-8
          </span>

        </div>

        <span className="font-mono">
          application/json
        </span>

      </div>

    </section>
  )
}
