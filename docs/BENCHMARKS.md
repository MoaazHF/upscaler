# Benchmarks

## Phase 0.5 hardware verdict (2026-10-23)

**Main path: GPU (OpenCL), FP16 compute, `body` variant, tile 384, PixelShuffle + residual done natively. No NPU.**

Device: Pixel 7 Pro (`cheetah`), Android 17 / SDK 37, GS201. Tool: LiteRT `benchmark_model` 2.3.0 (android_arm64, sha256 `844d518d…2b7a`), CompiledModel API. Model: `realesr-general-x4v3`.

### Answers to the plan's risks
| Risk | Verdict | Evidence |
|---|---|---|
| R1 NPU | **No NPU for G2.** LiteRT's Google Tensor NPU path supports only Tensor G5/G6 (beta, gated sign-up) | https://developers.google.com/edge/litert/next/tensor-sdk , https://developers.google.com/edge/litert/next/npu |
| R2 OpenCL from an app | **Works.** `libOpenCL.so`, `libOpenCL-pixel.so`, `libedgetpu_client.google.so` all `System.loadLibrary` OK from an app declaring `<uses-native-library … required="false"/>` | `spike/probe-app`, logcat `PROBE: OK loadLibrary OpenCL` |
| R3 ops off the GPU | **Fixed by the `body` variant.** Full graph: PReLU lowers to GREATER/MUL/SELECT and PixelShuffle to TRANSPOSE/RESHAPE → 136/141 ops on GPU, 2 partitions. Body graph (PReLU as max/min, no PixelShuffle): **166/166 ops on GPU, 1 partition**, ~1.9x faster | op dumps + `Replacing N out of M node(s)` lines |
| R4 FP16 | FP16 *weights* are near-lossless on CPU (81.5 dB). GPU FP16 *compute* accuracy is **not measured yet** → Phase 3 gate | `tools/spike_quality.py` |
| R6 thermals | Throttles after ~100 s sustained: tile time +7–20% at status 1, up to +70% at status 2 | sustained run below |

### Quality per precision (desktop CPU, 18 tiles of 128 px from 3 Kodak images, vs PyTorch fp32)
| Model | min PSNR | mean PSNR |
|---|---|---|
| fp32 | 132.12 dB | 134.38 dB |
| fp16 weights | 78.18 dB | 81.52 dB |
| int8 dynamic | 36.53 dB | 40.04 dB (fails the 38 dB floor) |

### Latency per tile (Inference avg, cool phone unless noted)
| Model | Tile | CPU 1 thread | CPU 4 threads | GPU fp16 | GPU fp32 |
|---|---|---|---|---|---|
| full | 128 | 1114 ms | 508 ms | 74.9 ms (2 partitions) | 134.8 ms |
| full | 256 | 4860 ms | 2055 ms | 248.0 ms | 528.4 ms |
| body | 128 | — | 390 ms | **40.0 ms** | 77.3 ms |

The full-model CPU rows and the GPU fp32 rows were taken back to back; the phone reached thermal status 2 during that matrix, so treat them as upper bounds.

### GPU fp16 throughput by tile (body variant, thermal status 0 before every run)
| Tile | ms/tile | raw input px/s | useful px/s (16 px overlap each side) | GPU footprint |
|---|---|---|---|---|
| 128 | 40.0 | 410 k | 230 k | 127 MB |
| 192 | 79.4 | 464 k | 322 k | 139 MB |
| 256 | 136.3 | 481 k | 368 k | 155 MB |
| **384** | **298.2** | **494 k** | **416 k** | **217 MB** |
| 512 | 523.9 | 500 k | 440 k | 304 MB |

Tile 384 is chosen: 94% of tile 512's useful throughput for 87 MB less GPU memory (8 GB devices).

### Sustained load (tile 384, GPU fp16, ~10 s windows)
| t | status | G3D / BIG °C | ms/tile |
|---|---|---|---|
| 0–23 s | 0 | 43→66 / 44→62 | 298–305 |
| 35–94 s | 1 | ~72 / ~70 | 319–358 |
| 106–141 s | 2 | 75–80 / up to 83 | 442–508 |

BIG cores heat although inference runs on the GPU. The benchmark's host thread likely busy-waits; the app must wait on GPU completion without spinning (Phase 5).

### Speed budgets (go/no-go floor: 12 MP 2x ≤ 60 s, 4x ≤ 5 min)
12 MP = 4000×3000 input. Inference only, tile 384, 16 px overlap:
- **4x:** 12 MP / 416 k px/s ≈ **29 s** cool, ≈ **48 s** fully throttled.
- **2x, strategy (b)** (0.5x pre-downscale, then x4): 3 MP → ≈ **7–12 s**.
- **2x, strategy (a)** (x4, then downscale): same as 4x. Phase 1 picks (a) or (b) on quality.

**Verdict: GO.** Both floors pass with margin. Budgets for §2: **T₄ ≤ 60 s, T₂ ≤ 20 s** (12 MP, end-to-end, including decode, encode and save).

### Open, carried forward
- GPU FP16 compute accuracy vs the FP32 golden: must reach ≥ 40 dB in the Phase 3 CLI; fallback FP32 (~2x slower, still ≈ 60 s for 4x).
- Overlap: SRVGGNetCompact stacks 34 3×3 convs, so its receptive field reaches 34 px from each output's source pixel. A 16 px overlap is not bit-exact at tile borders; Phase 1 measures the seam metric for 16 vs 34 px.
- Busy-wait CPU heat during GPU inference (Phase 5).
