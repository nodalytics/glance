
export interface PerformanceSummary {
  expected_reports: number
  available_reports: number
  missing_report_count: number
  missing_reports: string[]
  preprocessing_configurations: number
  neural_workloads: number
  accuracy_models: number
}

export interface PreprocessingResult {
  configuration: string
  document_count: number
  total_runs: number
  expected_lines: number
  recognized_lines: number
  strict_matches: number
  adjusted_matches: number
  strict_recall_percent: number
  adjusted_recall_percent: number
  adjusted_precision_percent: number
  mean_preprocessing_ms: number
  mean_inference_ms: number
  mean_total_ms: number
  median_total_ms: number
  p95_total_ms: number
  maximum_total_ms: number
  exact_adjusted_runs: number
  speedup_vs_original: number
  reduction_percent: number
  accuracy_preserved: boolean
}

export interface RuntimeResult {
  runtime: string
  mean_ms: number
  p95_ms: number
}

export interface NeuralWorkload {
  input_size: number
  mean_latency_winner: string
  mean_latency_ms: number
  p95_latency_winner: string
  p95_latency_ms: number
  ranking: RuntimeResult[]
}

export interface AccuracyResult {
  model: string
  expected_lines: number
  original_matches: number
  formatting_only_matches: number
  adjusted_matches: number
  remaining_unmatched_lines: number
  original_recall_percent: number
  adjusted_recall_percent: number
}

export interface PerformanceReport {
  success: boolean
  mode: 'offline'
  measurement_type: 'recorded_research_benchmarks'
  report_version: string
  timestamp_utc: string
  scope: string

  summary: PerformanceSummary

  preprocessing: {
    baseline: PreprocessingResult | null
    best_normalized_accuracy_candidate:
      PreprocessingResult | null
    ranking: PreprocessingResult[]
    summary: {
      configurations_tested: number
      configurations_passed: number
      configurations_failed: number
    }
  }

  neural_runtimes: NeuralWorkload[]
  accuracy_analysis: AccuracyResult[]
  conclusions: string[]
  limitations: string[]
  production_decision: string
  application_speedup_verified: boolean
}
