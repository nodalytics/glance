
import {
  useEffect,
  useRef,
  useState,
} from 'react'

import {
  UploadCloud,
  Image as ImageIcon,
  X,
  AlertCircle,
  ScanLine,
  LoaderCircle,
} from 'lucide-react'

import AnalysisFeedback from './AnalysisFeedback'

import type {
  AnalysisState,
} from '../../types/analysis'

import type {
  ConnectionStatus,
} from '../../types/navigation'

import {
  formatFileSize,
} from '../../utils/formatters'

const MAX_FILE_SIZE =
  10 * 1024 * 1024

const ALLOWED_EXTENSIONS = [
  'png',
  'jpg',
  'jpeg',
  'bmp',
]

interface ScreenshotUploadProps {
  file: File | null

  onFileChange:
    (file: File | null) => void

  onAnalyze: () => void

  analysis: AnalysisState

  connectionStatus: ConnectionStatus

  backendBusy: boolean
}

export default function ScreenshotUpload({
  file,
  onFileChange,
  onAnalyze,
  analysis,
  connectionStatus,
  backendBusy,
}: ScreenshotUploadProps) {
  const inputRef =
    useRef<HTMLInputElement>(null)

  const previewRef =
    useRef<HTMLImageElement>(null)

  const [dragging, setDragging] =
    useState(false)

  const [error, setError] =
    useState<string | null>(null)

  const isProcessing =
    analysis.status === 'processing'

  const canAnalyze =
    file !== null &&
    connectionStatus === 'connected' &&
    !isProcessing &&
    !backendBusy

  // ----------------------------------------------
  // IMAGE PREVIEW
  // ----------------------------------------------

  useEffect(() => {
    const image = previewRef.current

    if (!file || !image) {
      return
    }

    const url =
      URL.createObjectURL(file)

    image.src = url

    return () => {
      image.removeAttribute('src')

      URL.revokeObjectURL(url)
    }
  }, [file])

  // ----------------------------------------------
  // FILE VALIDATION
  // ----------------------------------------------

  function selectFile(
    selected: File | undefined
  ) {
    if (
      !selected ||
      isProcessing
    ) {
      return
    }

    setError(null)

    const extension =
      selected.name
        .split('.')
        .pop()
        ?.toLowerCase() ?? ''

    if (
      !ALLOWED_EXTENSIONS.includes(
        extension
      )
    ) {
      setError(
        'Please select a PNG, JPEG or BMP image.'
      )

      return
    }

    if (selected.size === 0) {
      setError(
        'The selected file is empty.'
      )

      return
    }

    if (
      selected.size > MAX_FILE_SIZE
    ) {
      setError(
        'The screenshot exceeds the 10 MiB limit.'
      )

      return
    }

    onFileChange(selected)
  }

  function removeFile() {
    if (isProcessing) {
      return
    }

    onFileChange(null)

    setError(null)

    if (inputRef.current) {
      inputRef.current.value = ''
    }
  }

  // ----------------------------------------------
  // COMPONENT
  // ----------------------------------------------

  return (
    <section className="rounded-xl border border-slate-800 bg-[#111827] p-5">

      <div className="mb-5 flex items-center gap-3">

        <div className="rounded-lg bg-emerald-500/10 p-2.5">
          <ImageIcon
            size={20}
            className="text-emerald-400"
          />
        </div>

        <div>
          <h3 className="font-semibold">
            Screenshot Analysis
          </h3>

          <p className="mt-1 text-xs text-slate-400">
            Analyze a previously saved screenshot
          </p>
        </div>

      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".png,.jpg,.jpeg,.bmp"
        className="hidden"
        disabled={isProcessing}
        onChange={(event) => {
          selectFile(
            event.target.files?.[0]
          )

          event.target.value = ''
        }}
      />

      {!file ? (
        <div
          onDragOver={(event) => {
            event.preventDefault()

            setDragging(true)
          }}

          onDragLeave={() => {
            setDragging(false)
          }}

          onDrop={(event) => {
            event.preventDefault()

            setDragging(false)

            selectFile(
              event.dataTransfer.files[0]
            )
          }}

          className={`
            rounded-xl border-2 border-dashed
            px-5 py-12 text-center
            transition-colors
            ${
              dragging
                ? 'border-emerald-400 bg-emerald-500/10'
                : 'border-slate-700 bg-[#0b1018]'
            }
          `}
        >

          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/10">

            <UploadCloud
              size={30}
              className="text-emerald-400"
            />

          </div>

          <h4 className="font-medium">
            Drag and drop your screenshot
          </h4>

          <p className="mt-2 text-sm text-slate-500">
            or browse files from your computer
          </p>

          <button
            onClick={() => {
              inputRef.current?.click()
            }}
            className="mt-5 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-emerald-500"
          >
            Select Screenshot
          </button>

          <p className="mt-4 text-xs text-slate-500">
            PNG, JPEG, BMP · Maximum 10 MiB
          </p>

        </div>
      ) : (
        <div className="space-y-4">

          <div className="overflow-hidden rounded-lg border border-slate-800 bg-[#0b1018]">

            <img
              ref={previewRef}
              alt="Selected screenshot preview"
              className="max-h-96 w-full object-contain"
            />

          </div>

          <div className="flex items-center gap-3 rounded-lg bg-[#0b1018] p-3">

            <ImageIcon
              size={20}
              className="shrink-0 text-emerald-400"
            />

            <div className="min-w-0 flex-1">

              <p className="truncate text-sm font-medium">
                {file.name}
              </p>

              <p className="mt-1 text-xs text-slate-500">
                {formatFileSize(file.size)}
              </p>

            </div>

            <button
              disabled={isProcessing}
              onClick={removeFile}
              aria-label="Remove screenshot"
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-red-400 disabled:opacity-30"
            >
              <X size={18} />
            </button>

          </div>

          <button
            disabled={!canAnalyze}
            onClick={onAnalyze}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-emerald-500 disabled:opacity-40"
          >

            {isProcessing ? (
              <>
                <LoaderCircle
                  size={18}
                  className="animate-spin"
                />

                Analyzing Screenshot...
              </>
            ) : (
              <>
                <ScanLine size={18} />

                {analysis.status === 'success'
                  ? 'Analyze Again'
                  : analysis.status === 'error'
                    ? 'Retry Analysis'
                    : 'Analyze Screenshot'}
              </>
            )}

          </button>

          {connectionStatus !== 'connected' && (
            <p className="text-center text-xs text-amber-400">
              Waiting for backend connection.
            </p>
          )}

          {backendBusy && !isProcessing && (
            <p className="text-center text-xs text-amber-400">
              Backend is currently busy.
              Please wait.
            </p>
          )}

          <AnalysisFeedback
            analysis={analysis}
          />

        </div>
      )}

      {error && (
        <div
          role="alert"
          className="mt-4 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400"
        >

          <AlertCircle
            size={18}
            className="shrink-0"
          />

          {error}

        </div>
      )}

    </section>
  )
}
