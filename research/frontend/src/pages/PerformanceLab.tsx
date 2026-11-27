
import {
  Activity,
  Timer,
  Gauge,
  Target,
  TrendingDown,
  RefreshCw,
  LoaderCircle,
  AlertCircle,
  CheckCircle2,
  Cpu,
  Info,
} from 'lucide-react'

import StatCard
  from '../components/dashboard/StatCard'

import {
  usePerformanceReport,
} from '../hooks/usePerformanceReport'


const panelClass =
  'rounded-xl border border-slate-800 ' +
  'bg-[#111827] p-5'


function formatMs(value: number) {

  return `${value.toLocaleString(
    'en-US',
    {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }
  )} ms`
}


function formatPercent(value: number) {

  return `${value.toFixed(2)}%`
}


function formatRuntime(value: string) {

  const names: Record<string, string> = {
    onnxruntime_cpu: 'ONNX Runtime CPU',
    openvino_cpu: 'OpenVINO CPU',
    openvino_gpu: 'OpenVINO GPU',
  }

  return names[value] ?? value
}


export default function PerformanceLab() {

  const {
    report,
    loading,
    error,
    refresh,
  } = usePerformanceReport()

  const best =
    report?.preprocessing
      .best_normalized_accuracy_candidate

  const ranking =
    report?.preprocessing.ranking ?? []

  const maxLatency = Math.max(
    1,
    ...ranking.map(
      item => item.mean_total_ms
    )
  )

  return (

    <div className="space-y-6">

      {/* PAGE HEADER */}

      <div className="flex flex-wrap items-center justify-between gap-4">

        <div>

          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-emerald-400">

            Performance Research

          </p>

          <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">

            Performance Lab

          </h1>

          <p className="mt-2 text-sm text-slate-400">

            Offline document OCR benchmarks,
            runtime comparisons and accuracy analysis.

          </p>

        </div>

        <button
          type="button"
          onClick={refresh}
          disabled={loading}
          className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm transition hover:bg-slate-700 disabled:opacity-50"
        >

          <RefreshCw
            size={16}
            className={
              loading ? 'animate-spin' : ''
            }
          />

          Refresh Report

        </button>

      </div>


      {/* RESEARCH NOTICE */}

      <div className="flex items-start gap-3 rounded-xl border border-sky-500/20 bg-sky-500/5 p-4">

        <Info
          size={20}
          className="mt-0.5 shrink-0 text-sky-400"
        />

        <div>

          <p className="text-sm font-medium text-sky-300">

            Recorded research benchmarks

          </p>

          <p className="mt-1 text-xs leading-relaxed text-slate-400">

            These measurements are from standalone
            synthetic document OCR experiments.
            They are not live inference measurements
            or verified application-level speedups.

          </p>

        </div>

      </div>


      {/* LOADING */}

      {loading && (

        <div className={`${panelClass} flex items-center gap-3`}>

          <LoaderCircle
            size={20}
            className="animate-spin text-emerald-400"
          />

          <span className="text-sm text-slate-400">

            Loading performance research report...

          </span>

        </div>

      )}


      {/* ERROR */}

      {error && (

        <div className="flex items-start gap-3 rounded-xl border border-red-500/20 bg-red-500/5 p-5">

          <AlertCircle
            size={20}
            className="shrink-0 text-red-400"
          />

          <div>

            <p className="font-medium text-red-400">

              Unable to load report

            </p>

            <p className="mt-2 text-sm text-slate-400">

              {error}

            </p>

            {report && (

              <p className="mt-2 text-xs text-amber-400">

                Displaying the previously loaded report.

              </p>

            )}

          </div>

        </div>

      )}


      {report && (

        <>

          {/* PERFORMANCE STATISTICS */}

          {best && (

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">

              <StatCard
                label="Mean OCR Latency"
                value={formatMs(
                  best.mean_total_ms
                )}
                icon={Timer}
                description="Recorded standalone OCR"
              />

              <StatCard
                label="P95 Latency"
                value={formatMs(
                  best.p95_total_ms
                )}
                icon={Gauge}
                description="95th percentile"
              />

              <StatCard
                label="Normalized Recall"
                value={formatPercent(
                  best.adjusted_recall_percent
                )}
                icon={Target}
                description="Synthetic document dataset"
              />

              <StatCard
                label="Latency Reduction"
                value={formatPercent(
                  best.reduction_percent
                )}
                icon={TrendingDown}
                description="Versus original preprocessing"
              />

            </div>

          )}


          {/* PREPROCESSING CHART */}

          <section className={panelClass}>

            <div className="mb-6 flex items-center gap-3">

              <Activity
                size={21}
                className="text-emerald-400"
              />

              <div>

                <h2 className="font-semibold">

                  Preprocessing Performance

                </h2>

                <p className="mt-1 text-xs text-slate-400">

                  Mean latency in milliseconds.
                  Lower is better.

                </p>

              </div>

            </div>

            <div className="space-y-5">

              {ranking.map(item => (

                <div key={item.configuration}>

                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">

                    <span className="capitalize">

                      {item.configuration}

                    </span>

                    <span className="font-mono text-slate-300">

                      {formatMs(item.mean_total_ms)}

                    </span>

                  </div>

                  <div className="h-3 overflow-hidden rounded-full bg-slate-800">

                    <div
                      className={`h-full rounded-full ${
                        item.configuration ===
                          best?.configuration
                          ? 'bg-emerald-500'
                          : 'bg-slate-500'
                      }`}
                      style={{
                        width: `${
                          item.mean_total_ms /
                          maxLatency * 100
                        }%`,
                      }}
                    />

                  </div>

                </div>

              ))}

            </div>

          </section>


          {/* PREPROCESSING DETAILS */}

          <section className={panelClass}>

            <h2 className="mb-5 font-semibold">

              Preprocessing Comparison

            </h2>

            <div className="overflow-x-auto">

              <table className="w-full whitespace-nowrap text-left text-sm">

                <thead className="border-b border-slate-800 text-xs text-slate-400">

                  <tr>
                    <th className="p-3">Method</th>
                    <th className="p-3">Mean</th>
                    <th className="p-3">P95</th>
                    <th className="p-3">Strict Recall</th>
                    <th className="p-3">Adjusted Recall</th>
                    <th className="p-3">Reduction</th>
                  </tr>

                </thead>

                <tbody>

                  {ranking.map(item => (

                    <tr
                      key={item.configuration}
                      className="border-b border-slate-800/70"
                    >

                      <td className="p-3 capitalize">

                        {item.configuration}

                      </td>

                      <td className="p-3 font-mono">

                        {formatMs(item.mean_total_ms)}

                      </td>

                      <td className="p-3 font-mono">

                        {formatMs(item.p95_total_ms)}

                      </td>

                      <td className="p-3">

                        {formatPercent(
                          item.strict_recall_percent
                        )}

                      </td>

                      <td className={`p-3 ${
                        item.accuracy_preserved
                          ? 'text-emerald-400'
                          : 'text-amber-400'
                      }`}>

                        {formatPercent(
                          item.adjusted_recall_percent
                        )}

                      </td>

                      <td className={`p-3 ${
                        item.reduction_percent >= 0
                          ? 'text-emerald-400'
                          : 'text-red-400'
                      }`}>

                        {formatPercent(
                          item.reduction_percent
                        )}

                      </td>

                    </tr>

                  ))}

                </tbody>

              </table>

            </div>

          </section>


          {/* OCR ACCURACY */}

          <section className={panelClass}>

            <h2 className="mb-5 font-semibold">

              OCR Model Accuracy

            </h2>

            <div className="grid gap-4 md:grid-cols-3">

              {report.accuracy_analysis.map(item => (

                <div
                  key={item.model}
                  className="rounded-xl border border-slate-800 bg-[#0b1018] p-4"
                >

                  <h3 className="mb-4 font-medium capitalize">

                    {item.model} Model

                  </h3>

                  <p className="text-xs text-slate-400">

                    Adjusted recall

                  </p>

                  <p className="mt-1 text-2xl font-semibold text-emerald-400">

                    {formatPercent(
                      item.adjusted_recall_percent
                    )}

                  </p>

                  <div className="mt-4 space-y-2 text-sm">

                    <div className="flex justify-between">

                      <span className="text-slate-400">

                        Strict recall

                      </span>

                      {formatPercent(
                        item.original_recall_percent
                      )}

                    </div>

                    <div className="flex justify-between">

                      <span className="text-slate-400">

                        Matched lines

                      </span>

                      {item.adjusted_matches}/
                      {item.expected_lines}

                    </div>

                    <div className="flex justify-between">

                      <span className="text-slate-400">

                        Unmatched

                      </span>

                      {item.remaining_unmatched_lines}

                    </div>

                  </div>

                </div>

              ))}

            </div>

          </section>


          {/* INFERENCE RUNTIMES */}

          <section className={panelClass}>

            <div className="mb-5 flex items-center gap-3">

              <Cpu
                size={21}
                className="text-emerald-400"
              />

              <div>

                <h2 className="font-semibold">

                  Inference Runtime Comparison

                </h2>

                <p className="mt-1 text-xs text-slate-400">

                  Synthetic neural network workloads,
                  not complete OCR inference.

                </p>

              </div>

            </div>

            <div className="grid gap-4 xl:grid-cols-3">

              {report.neural_runtimes.map(workload => (

                <div
                  key={workload.input_size}
                  className="rounded-xl border border-slate-800 bg-[#0b1018] p-4"
                >

                  <h3 className="mb-4 font-medium">

                    {workload.input_size} ×
                    {' '}{workload.input_size}

                  </h3>

                  <div className="space-y-3">

                    {workload.ranking.map(item => (

                      <div
                        key={item.runtime}
                        className="rounded-lg border border-slate-800 p-3"
                      >

                        <p className="text-sm">

                          {formatRuntime(item.runtime)}

                        </p>

                        <p className={`mt-2 font-mono text-lg ${
                          item.runtime ===
                            workload.mean_latency_winner
                            ? 'text-emerald-400'
                            : 'text-slate-300'
                        }`}>

                          {formatMs(item.mean_ms)}

                        </p>

                        <p className="mt-1 text-xs text-slate-500">

                          P95: {formatMs(item.p95_ms)}

                        </p>

                      </div>

                    ))}

                  </div>

                </div>

              ))}

            </div>

          </section>


          {/* REPORT SUMMARY */}

          <section className={panelClass}>

            <h2 className="mb-5 font-semibold">

              Research Report Status

            </h2>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

              {[
                {
                  label: 'Available reports',
                  value:
                    `${report.summary.available_reports}/` +
                    report.summary.expected_reports,
                },
                {
                  label: 'Missing reports',
                  value:
                    report.summary.missing_report_count,
                },
                {
                  label: 'Preprocessing configurations',
                  value:
                    report.summary.preprocessing_configurations,
                },
                {
                  label: 'Neural workloads',
                  value:
                    report.summary.neural_workloads,
                },
              ].map(item => (

                <div
                  key={item.label}
                  className="rounded-lg border border-slate-800 p-4"
                >

                  <p className="text-xs text-slate-400">

                    {item.label}

                  </p>

                  <p className="mt-2 text-xl font-semibold">

                    {item.value}

                  </p>

                </div>

              ))}

            </div>

          </section>


          {/* CONCLUSIONS AND LIMITATIONS */}

          <div className="grid gap-4 xl:grid-cols-2">

            <section className={panelClass}>

              <h2 className="mb-5 font-semibold">

                Research Conclusions

              </h2>

              <div className="space-y-4">

                {report.conclusions.map(item => (

                  <div
                    key={item}
                    className="flex items-start gap-3"
                  >

                    <CheckCircle2
                      size={17}
                      className="mt-0.5 shrink-0 text-emerald-400"
                    />

                    <p className="text-sm leading-relaxed text-slate-400">

                      {item}

                    </p>

                  </div>

                ))}

              </div>

            </section>

            <section className={panelClass}>

              <h2 className="mb-5 font-semibold">

                Research Limitations

              </h2>

              <div className="space-y-4">

                {report.limitations.map(item => (

                  <div
                    key={item}
                    className="flex items-start gap-3"
                  >

                    <AlertCircle
                      size={17}
                      className="mt-0.5 shrink-0 text-amber-400"
                    />

                    <p className="text-sm leading-relaxed text-slate-400">

                      {item}

                    </p>

                  </div>

                ))}

              </div>

            </section>

          </div>


          {/* REPORT METADATA */}

          <section className={panelClass}>

            <h2 className="mb-3 font-semibold">

              Production Architecture Decision

            </h2>

            <p className="text-sm leading-relaxed text-slate-400">

              {report.production_decision}

            </p>

            <div className="mt-4 border-t border-slate-800 pt-4 text-xs text-slate-500">

              Report version: {report.report_version}

              <p className="mt-2">

                Generated: {
                  new Date(
                    report.timestamp_utc
                  ).toLocaleString()
                }

              </p>

              <p className="mt-2">

                Application speedup verified: {
                  report.application_speedup_verified
                    ? 'Yes'
                    : 'No'
                }

              </p>

            </div>

          </section>

        </>

      )}

    </div>
  )
}
