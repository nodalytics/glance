
export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue }

export function serializeJson(
  value: unknown,
  formatted = true
): string {
  return JSON.stringify(
    value,
    null,
    formatted ? 2 : undefined
  ) ?? 'null'
}

export function getJsonSize(
  value: string
): number {
  return new TextEncoder()
    .encode(value)
    .byteLength
}

export function getJsonLineCount(
  value: string
): number {
  return value.split('\n').length
}

export function createJsonFilename(
  section = 'complete'
): string {

  const timestamp = new Date()
    .toISOString()
    .replace(/[:.]/g, '-')

  const safeSection = section.replace(
    /[^a-zA-Z0-9_-]/g,
    '_'
  )

  return `poker-state_${safeSection}_${timestamp}.json`
}

export async function copyJsonToClipboard(
  content: string
): Promise<void> {

  if (!navigator.clipboard) {
    throw new Error(
      'Clipboard access is unavailable in this browser.'
    )
  }

  await navigator.clipboard.writeText(
    content
  )
}

export function downloadJson(
  content: string,
  filename: string
): void {

  const blob = new Blob(
    [content],
    {
      type: 'application/json;charset=utf-8',
    }
  )

  const url =
    URL.createObjectURL(blob)

  const link =
    document.createElement('a')

  link.href = url
  link.download = filename

  document.body.appendChild(link)

  try {
    link.click()
  } finally {
    link.remove()

    window.setTimeout(() => {
      URL.revokeObjectURL(url)
    }, 1000)
  }
}
