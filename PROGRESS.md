# Progress

## Phase 0 — Environment ✅ (2026-10-23)
- Host: Ubuntu 24.04, JDK 21, Python 3.12; single SDK (Android Studio's) with NDK 28.2.13676358, CMake 4.1.2, platform 37.0; ccache 4.9.1. See `docs/TOOLCHAIN.md`.
- Device: Pixel 7 Pro (`cheetah`), Android 17 / SDK 37, GS201, 11.2 GiB RAM.
- Repo: `MoaazHF/upscaler` (public), `main` + `dev` protected, merge commits only, co-author trailer on every commit. Released as `v0.0.0`.

## Phase 0.5 — Hardware spike ✅ (2026-10-23) — verdict: GO
- Main path: GPU OpenCL, FP16, `body` variant, tile 384. No NPU (LiteRT Tensor NPU = G5/G6 only). OpenCL loads in an app process.
- Numbers: 12 MP 4x inference ≈ 29 s cool / 48 s throttled; 2x (pre-downscale) ≈ 7–12 s. Budgets: T₂ ≤ 20 s, T₄ ≤ 60 s end to end.
- Quality: fp32 134 dB, fp16 weights 81.5 dB, int8 40.0 mean / 36.5 min (dropped).
- Open: GPU FP16 compute accuracy (Phase 3 gate ≥ 40 dB); overlap 16 vs 34 px (Phase 1); busy-wait CPU heat (Phase 5).
- Next: Phase 1 (golden reference: tiling, overlap, blend, 2x strategy), task list first.
