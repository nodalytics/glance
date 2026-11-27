
import { useState } from 'react'

import {
  ChevronRight,
  ChevronDown,
} from 'lucide-react'

import type {
  JsonValue,
} from '../../utils/jsonUtils'

interface JsonTreeProps {
  value: JsonValue
  defaultExpanded?: boolean
}

interface JsonNodeProps {
  value: JsonValue
  name?: string
  depth: number
  defaultExpanded: boolean
  trailingComma?: boolean
}

function PrimitiveValue({
  value,
}: {
  value: string | number | boolean | null
}) {

  if (value === null) {
    return (
      <span className="text-slate-500">
        null
      </span>
    )
  }

  if (typeof value === 'string') {
    return (
      <span className="break-all text-emerald-400">
        {JSON.stringify(value)}
      </span>
    )
  }

  if (typeof value === 'number') {
    return (
      <span className="text-amber-400">
        {String(value)}
      </span>
    )
  }

  return (
    <span className="text-violet-400">
      {String(value)}
    </span>
  )
}

function JsonNode({
  value,
  name,
  depth,
  defaultExpanded,
  trailingComma = false,
}: JsonNodeProps) {

  const [expanded, setExpanded] =
    useState(defaultExpanded)

  const isArray =
    Array.isArray(value)

  const isObject =
    value !== null &&
    typeof value === 'object'

  const entries: [string, JsonValue][] =
    isObject
      ? isArray
        ? value.map(
            (item, index) => [
              String(index),
              item,
            ]
          )
        : Object.entries(value)
      : []

  const opening =
    isArray ? '[' : '{'

  const closing =
    isArray ? ']' : '}'

  const paddingLeft =
    depth * 18

  const keyLabel =
    name !== undefined
      ? (
          <>
            <span className="text-sky-400">
              {JSON.stringify(name)}
            </span>

            <span className="mr-2 text-slate-500">
              :
            </span>
          </>
        )
      : null

  // Primitive values.

  if (!isObject) {
    return (
      <div
        className="flex items-start py-0.5"
        style={{ paddingLeft }}
      >

        <span className="inline-block w-5 shrink-0" />

        <div className="min-w-0 break-all">

          {keyLabel}

          <PrimitiveValue value={value} />

          {trailingComma && (
            <span className="text-slate-500">
              ,
            </span>
          )}

        </div>

      </div>
    )
  }

  // Objects and arrays.

  return (
    <div>

      <div
        className="flex items-center py-0.5"
        style={{ paddingLeft }}
      >

        <button
          type="button"
          aria-expanded={expanded}
          aria-label={`${
            expanded ? 'Collapse' : 'Expand'
          } ${name ?? 'root'}`}
          onClick={() =>
            setExpanded(
              (previous) => !previous
            )
          }
          className="mr-1 flex h-5 w-4 shrink-0 items-center justify-center rounded text-slate-500 hover:bg-slate-800 hover:text-slate-200"
        >

          {expanded ? (
            <ChevronDown size={14} />
          ) : (
            <ChevronRight size={14} />
          )}

        </button>

        <div className="min-w-0 break-all">

          {keyLabel}

          <span className="text-slate-300">
            {opening}
          </span>

          {!expanded && (
            <>

              <span className="mx-2 text-slate-500">
                {entries.length}{' '}
                {isArray
                  ? 'items'
                  : 'properties'}
              </span>

              <span className="text-slate-300">
                {closing}
              </span>

              {trailingComma && (
                <span className="text-slate-500">
                  ,
                </span>
              )}

            </>
          )}

        </div>

      </div>

      {expanded && (
        <>

          {entries.map(
            ([key, child], index) => (

              <JsonNode
                key={key}
                name={
                  isArray
                    ? undefined
                    : key
                }
                value={child}
                depth={depth + 1}
                defaultExpanded={
                  defaultExpanded
                }
                trailingComma={
                  index < entries.length - 1
                }
              />

            )
          )}

          <div
            className="py-0.5 pl-5 text-slate-300"
            style={{
              paddingLeft: paddingLeft + 20,
            }}
          >

            {closing}

            {trailingComma && (
              <span className="text-slate-500">
                ,
              </span>
            )}

          </div>

        </>
      )}

    </div>
  )
}

export default function JsonTree({
  value,
  defaultExpanded = true,
}: JsonTreeProps) {

  return (
    <div className="font-mono text-xs leading-relaxed sm:text-sm">

      <JsonNode
        value={value}
        depth={0}
        defaultExpanded={
          defaultExpanded
        }
      />

    </div>
  )
}
