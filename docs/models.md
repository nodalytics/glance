# glance — models: where we evolve to

**Status: direction, not implementation.** Nothing here is built yet. This is
where glance should evolve: from hand-mapped screens plus classic vision to
**our own foundation model** that understands and operates any desktop app,
hands-off (see "The ultimate test" in [README.md](README.md)). The C++ engine
stays the fast, deterministic runtime that grabs, acts and verifies; models
plug in behind the same `Screen`/`Input` + state-JSON contracts.

## Why our own model

- Off-the-shelf vision-language models are slow, remote and costly per step,
  and they are not trained on *operating* apps from raw pixels at the
  latency a live loop needs.
- glance already produces the training data: timestamped grabs, structured
  states, and verified action traces (each action checked against the next
  grab). Use cases 1, 2 and 5 in the README form that data pipeline.
- Nothing about the model is settled up front. Token arrangement, encoders,
  decoders and architectures are all to be tried and measured.

## Reference: Kronos (ideas to borrow)

[Kronos](https://github.com/shiyu-coder/Kronos) (arXiv 2508.02739, MIT
license) is a decoder-only foundation model for financial candlestick
(K-line) series. Its parts:

- **Tokenizer.** Each 6-dimensional bar (OHLCV + amount) is encoded by a
  small Transformer autoencoder and quantized with Binary Spherical
  Quantization to 20 bits. The bits split into a **coarse** 10-bit subtoken
  and a **fine** 10-bit subtoken, two 1024-entry vocabularies instead of one
  of about a million. The coarse subtoken has its own reconstruction loss;
  the fine subtoken encodes the residual.
- **Predictor.** A causal Transformer (RoPE, RMSNorm) predicts
  p(coarse | past) · p(fine | past, coarse). During training the fine head
  is conditioned on the model's own *sampled* coarse token, not ground
  truth, to reduce exposure bias. Sizes run from 4M to 500M parameters with
  a 512–2048 context.
- **Data.** Over 12 billion bars from 45 exchanges at 7 frequencies, with
  cleaning (spike and illiquidity filters) and upweighting of under-
  represented markets.
- **Inference.** Temperature and top-p sampling over N Monte Carlo
  trajectories, averaged.

## Transferable ideas for glance

1. **Coarse→fine screen tokens.** Coarse tokens carry layout, regions and app
   identity; fine tokens carry text and pixel detail. Train them with
   separate reconstruction targets (low-res or layout for coarse, full detail
   for fine).
2. **Coarse→fine actions.** Predict the action type (click, type, scroll,
   key, wait) first, then its arguments (target element, coordinates, text)
   conditioned on the sampled type.
3. **Split large vocabularies** (UI element ids, coordinates, text) into
   sub-tokens instead of one huge softmax.
4. **Train on sampled coarse tokens** so training matches closed-loop
   rollouts.
5. **Modality dropout.** Randomly drop the accessibility tree, OCR text or
   pixels during training, so the model still works on apps that expose no
   accessibility data, which is exactly glance's case.
6. **Normalize and clip numeric state** (amounts, geometry, scroll offsets,
   timings), with z-scores clipped like Kronos's [-5, 5].
7. **Temporal embeddings:** time since the last input, event time and
   session position. UI state changes are timing-sensitive (animations,
   network waits).
8. **Data hygiene:** drop idle frames, dedupe near-identical grabs, and
   upweight rare apps and workflows.
9. **Monte Carlo planning:** sample N action trajectories, score them
   (with a learned value or the verify-after-act check), and act on the
   best.

Caveats: screens are far higher-dimensional than a 6-number bar, so the
visual tokenizer needs patch-based encoding and larger codebooks. Desktop
action traces are also much scarcer than market data, so bootstrapping from
a pretrained vision backbone and from accessibility trees (where apps
expose them) is likely more practical than pretraining from scratch.

## Research axes to try

- **Token arrangement:** pixel patches vs UI-element tokens vs OCR-text
  tokens. Options include interleaving `[state, action, state', …]`,
  diff-only frames, and multi-scale (whole screen → focused region).
- **Encoders:** a ViT-style patch encoder, a CNN backbone, a VQ/BSQ
  autoencoder (Kronos-style), or element-detector features from the glance
  engine.
- **Decoders and heads:** autoregressive token decoding, factored
  coarse/fine heads, and direct coordinate regression vs discretized grids.
- **Architectures:** decoder-only Transformers, encoder-decoder, state-space
  models for long sessions, and small on-device models for the live loop
  alongside a larger planner.

## First concrete steps (when this starts)

1. Record: a trace logger in glance that writes grab + state JSON + action +
   post-action grab (the verify-after-act result) for every step.
2. Benchmark: a fixed suite of desktop tasks with success criteria checked
   from grabs, so every model variant is measured the same way.
3. Baselines: today's template/glyph engine, then an off-the-shelf
   vision-language model, before training anything of our own.
