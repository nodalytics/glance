# ADR-001 — Performance Architecture

**Status:** Proposed  
**Version:** 1.0.0  
**Date:** 2026-11-27

## 1. Context

The Python prototype has established functional offline image analysis, structured state generation, API communication and frontend visualization.

Performance research was conducted independently using general-purpose synthetic document OCR and neural network workloads.

The objective was to evaluate lightweight models, preprocessing methods, inference runtimes and available hardware acceleration.

## 2. Research Evidence

- Twelve performance research reports collected successfully.
- Medium OCR model mean latency: 27,100.388 ms.
- Tiny OCR model mean latency: 989.648 ms.
- Latest unprocessed Tiny OCR baseline: 673.805 ms.
- Gaussian preprocessing with Tiny OCR: 606.276 ms.
- Gaussian normalized line recall and precision: 100% on the tested dataset.
- Gaussian strict line recall: 57.143%.
- ONNX Runtime CPU execution verified.
- OpenVINO CPU and Intel integrated GPU execution verified.
- All nine synthetic neural runtime configurations passed numerical validation.

## 3. Architecture Decision

Retain Python for the existing offline functional prototype.

Use OpenCV as the established image-processing library.

Retain PP-OCRv6 Tiny as the leading lightweight document OCR research candidate and PP-OCRv6 Medium as an accuracy reference.

Treat Gaussian preprocessing as provisional pending independent validation.

Retain default CPU thread settings and enabled oneDNN acceleration.

Evaluate ONNX Runtime CPU as the primary alternative inference runtime and OpenVINO as an additional hardware acceleration option.

Evaluate C++ during production development using representative workloads and controlled performance comparisons.

## 4. Production Acceptance Criteria

Production technology selection must consider:

- Representative workload accuracy.
- Mean, median, P95 and P99 latency.
- Cold-start and initialization overhead.
- CPU and GPU resource consumption.
- Peak memory consumption.
- Runtime and model compatibility.
- Maintainability and deployment requirements.

## 5. Unresolved Issues

- Paddle2ONNX native DLL compatibility.
- Actual OCR model execution through alternative runtimes.
- Independent validation on larger representative datasets.
- Formatting-sensitive recognition accuracy.
- Controlled Python versus C++ comparison.
- End-to-end application latency.

## 6. Limitations

Synthetic document and neural network benchmarks do not establish production application performance.

Normalized recognition accuracy must not be interpreted as exact transcription accuracy.

The observed cross-experiment latency ratio is not a controlled application speedup.

## 7. Supporting Evidence

Research reports are stored under:

`test_output/performance/`

Consolidated reports:

- `performance_feasibility_report.json`
- `performance_feasibility_report.md`

## 8. Conclusion

The research establishes the feasibility of substantially faster standalone document OCR through lightweight model selection.

Final production architecture and latency guarantees remain subject to representative workload validation.