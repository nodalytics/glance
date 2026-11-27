# Performance Feasibility Report

Generated: 2026-11-26T19:39:37.407681+00:00

## Scope

General-purpose offline document OCR and synthetic inference research.

## Report Availability

| Report | Available |
|---|---|
| hardware | YES |
| profiling | YES |
| baseline | YES |
| threads | YES |
| onednn | YES |
| models | YES |
| accuracy | YES |
| errors | YES |
| runtimes | YES |
| devices | YES |
| neural | YES |
| preprocessing | YES |

## Preprocessing Results

| Method | Mean ms | Adjusted recall | Strict recall |
|---|---:|---:|---:|
| gaussian | 606.276 | 100.000% | 57.143% |
| otsu | 616.486 | 98.214% | 85.714% |
| original | 673.805 | 100.000% | 60.714% |
| clahe | 689.767 | 98.214% | 57.143% |
| grayscale | 702.809 | 100.000% | 57.143% |
| nlm | 2904.417 | 100.000% | 60.714% |

## Neural Runtime Results

| Input size | Mean winner | Mean ms | P95 winner | P95 ms |
|---|---|---:|---|---:|
| 64 x 64 | onnxruntime_cpu | 0.267953 | onnxruntime_cpu | 0.622550 |
| 128 x 128 | onnxruntime_cpu | 0.624473 | onnxruntime_cpu | 1.287830 |
| 256 x 256 | onnxruntime_cpu | 6.680027 | openvino_gpu | 12.548580 |

## Adjusted OCR Accuracy

| Model | Original recall | Adjusted recall |
|---|---:|---:|
| tiny | 60.714 | 100.0 |
| small | 67.857 | 85.714 |
| medium | 94.643 | 100.0 |

## Research Conclusions

- Lightweight model selection produced the largest observed standalone OCR performance improvement.
- Gaussian preprocessing is a provisional candidate based on normalized accuracy and measured latency.
- ONNX Runtime CPU and OpenVINO CPU/GPU execution have been demonstrated.
- Synthetic runtime results do not establish actual OCR runtime performance.

## Limitations

- Small synthetic document dataset.
- Repeated runs are not independent documents.
- Normalization can conceal formatting errors.
- Actual OCR model conversion remains unresolved.
- No controlled C++ versus Python benchmark.
- No verified application-level latency improvement.
- Fixed benchmark order may affect timing.

## Production Decision

Defer final runtime and language selection until representative models and production requirements have been independently validated.
