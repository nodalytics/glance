
import {
  Server,
  ScanLine,
  Activity,
  RefreshCw,
  LoaderCircle,
  AlertCircle,
  CircleCheck,
  ShieldCheck,
} from 'lucide-react'

import type {
  ReactNode,
} from 'react'

import {
  useApplicationInfo,
} from '../hooks/useApplicationInfo'

import {
  formatFileSize,
  formatNumber,
} from '../utils/formatters'

interface InformationRowProps {
  label: string
  value: ReactNode
}

function InformationRow({
  label,
  value,
}: InformationRowProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 py-3 last:border-0">

      <span className="text-sm text-slate-400">
        {label}
      </span>

      <span className="break-all text-sm font-medium text-slate-200">
        {value}
      </span>

    </div>
  )
}

export default function Settings() {
  const {
    data,
    loading,
    error,
    refresh,
  } = useApplicationInfo()

  return (
    <div className="space-y-6">

      <div className="flex flex-wrap items-center justify-between gap-4">

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-emerald-400">
            Configuration
          </p>

          <h1 className="text-3xl font-semibold">
            Settings
          </h1>

          <p className="mt-2 text-sm text-slate-400">
            Backend configuration and system information.
          </p>
        </div>

        <button
          onClick={refresh}
          disabled={loading}
          className="flex items-center gap-2 rounded-lg border border-slate-700 px-4 py-2.5 text-sm hover:bg-slate-800 disabled:opacity-50"
        >
          <RefreshCw
            size={17}
            className={
              loading ? 'animate-spin' : ''
            }
          />

          Refresh
        </button>

      </div>

      {loading && (
        <div
          role="status"
          className="flex items-center justify-center gap-3 rounded-xl border border-slate-800 bg-[#111827] p-10 text-slate-400"
        >
          <LoaderCircle
            size={22}
            className="animate-spin text-emerald-400"
          />

          Loading application information...
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-400"
        >
          <AlertCircle
            size={20}
            className="shrink-0"
          />

          {error}
        </div>
      )}

      {data && (
        <>
          <section className="rounded-xl border border-slate-800 bg-[#111827] p-5">

            <div className="mb-4 flex items-center gap-3">

              <Server
                size={22}
                className="text-emerald-400"
              />

              <h2 className="font-semibold">
                Application Information
              </h2>

            </div>

            <InformationRow
              label="Application"
              value={data.info.name}
            />

            <InformationRow
              label="Version"
              value={data.info.version}
            />

            <InformationRow
              label="Description"
              value={data.info.description}
            />

            <InformationRow
              label="Schema version"
              value={data.info.schema_version}
            />

            <InformationRow
              label="Processing mode"
              value={
                <span className="flex items-center gap-2 text-emerald-400">
                  <ShieldCheck size={16} />
                  Offline
                </span>
              }
            />

            <InformationRow
              label="Maximum upload size"
              value={formatFileSize(
                data.info.max_upload_size_bytes
              )}
            />

            <InformationRow
              label="Supported image formats"
              value={
                data.info.supported_image_formats
                  .map(
                    (format) =>
                      format
                        .replace('.', '')
                        .toUpperCase()
                  )
                  .join(', ')
              }
            />

          </section>

          <section className="rounded-xl border border-slate-800 bg-[#111827] p-5">

            <div className="mb-5 flex items-center gap-3">

              <ScanLine
                size={22}
                className="text-emerald-400"
              />

              <div>
                <h2 className="font-semibold">
                  Recognition Profiles
                </h2>

                <p className="mt-1 text-xs text-slate-400">
                  Default profile: {
                    data.profiles.default_profile
                  }
                </p>
              </div>

            </div>

            <div className="grid gap-4 xl:grid-cols-3">

              {data.profiles.profiles.map(
                (profile) => (
                  <div
                    key={profile.name}
                    className="min-w-0 rounded-xl border border-slate-800 bg-[#0b1018] p-4"
                  >

                    <div className="flex flex-wrap items-center gap-2">

                      <h3 className="break-all text-sm font-semibold">
                        {profile.name}
                      </h3>

                      {profile.name ===
                        data.profiles.default_profile && (
                        <span className="rounded-full bg-emerald-500/10 px-2 py-1 text-[10px] text-emerald-400">
                          Default
                        </span>
                      )}

                    </div>

                    <p className="mt-2 min-h-10 text-xs leading-relaxed text-slate-400">
                      {profile.description}
                    </p>

                    <p className="mt-4 break-all text-xs text-slate-500">
                      {profile.recognizer}
                    </p>

                    <div className="mt-4 space-y-3 border-t border-slate-800 pt-4">

                      <div className="flex items-center justify-between gap-2 text-xs">
                        <span className="text-slate-400">
                          Availability
                        </span>

                        <span
                          className={
                            profile.available
                              ? 'text-emerald-400'
                              : 'text-red-400'
                          }
                        >
                          {profile.available
                            ? 'Available'
                            : 'Unavailable'}
                        </span>
                      </div>

                      <div className="flex items-center justify-between gap-2 text-xs">
                        <span className="text-slate-400">
                          API support
                        </span>

                        <span
                          className={
                            profile.api_supported
                              ? 'text-emerald-400'
                              : 'text-slate-500'
                          }
                        >
                          {profile.api_supported
                            ? 'Supported'
                            : 'Internal only'}
                        </span>
                      </div>

                      <div className="flex items-center justify-between gap-2 text-xs">
                        <span className="text-slate-400">
                          Occupancy detection
                        </span>

                        <span className="text-slate-300">
                          {profile.occupancy_detection_enabled
                            ? 'Enabled'
                            : 'Disabled'}
                        </span>
                      </div>

                    </div>
                  </div>
                )
              )}

            </div>
          </section>

          <section className="rounded-xl border border-slate-800 bg-[#111827] p-5">

            <div className="mb-5 flex items-center gap-3">

              <Activity
                size={22}
                className="text-emerald-400"
              />

              <h2 className="font-semibold">
                Service Statistics
              </h2>

            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">

              {[
                {
                  label: 'Total Requests',
                  value:
                    data.statistics.statistics
                      .total_requests,
                  color: 'text-slate-200',
                },
                {
                  label: 'Successful',
                  value:
                    data.statistics.statistics
                      .successful_requests,
                  color: 'text-emerald-400',
                },
                {
                  label: 'Failed',
                  value:
                    data.statistics.statistics
                      .failed_requests,
                  color: 'text-red-400',
                },
                {
                  label: 'Rejected',
                  value:
                    data.statistics.statistics
                      .rejected_requests,
                  color: 'text-amber-400',
                },
                {
                  label: 'Busy Requests',
                  value:
                    data.statistics.statistics
                      .busy_requests,
                  color: 'text-blue-400',
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className="rounded-lg border border-slate-800 bg-[#0b1018] p-4"
                >
                  <p className="text-xs text-slate-400">
                    {item.label}
                  </p>

                  <p className={`mt-3 text-2xl font-semibold ${item.color}`}>
                    {formatNumber(item.value)}
                  </p>
                </div>
              ))}

            </div>

            <div className="mt-5">

              <InformationRow
                label="OCR pipeline"
                value={
                  data.statistics.pipeline_initialized
                    ? 'Initialized'
                    : 'Waiting for first analysis'
                }
              />

              <InformationRow
                label="Processing status"
                value={
                  data.statistics.busy ? (
                    <span className="flex items-center gap-2 text-amber-400">
                      <LoaderCircle
                        size={15}
                        className="animate-spin"
                      />
                      Busy
                    </span>
                  ) : (
                    <span className="flex items-center gap-2 text-emerald-400">
                      <CircleCheck size={15} />
                      Idle
                    </span>
                  )
                }
              />

            </div>
          </section>

          <p className="text-xs text-slate-500">
            Configuration is read-only. Statistics reflect
            the last successful refresh and reset when the
            backend restarts.
          </p>

        </>
      )}

    </div>
  )
}
