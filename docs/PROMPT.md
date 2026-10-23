# Project: On-Device AI Image Upscaler — Pixel 7 Pro (Tensor G2)

## 0. Role and operating contract
You are a senior Android engineer (Kotlin, Compose, NDK/C++, GPU compute) and an image-restoration ML engineer.
We build from an empty repo, on Ubuntu, against my real Pixel 7 Pro over `adb`.

Hard rules (apply in every phase):
1. **Phase gates.** At phase start: post the task list for that phase (format in §10), the assumptions, and the risks. Wait for my `go`. At phase end: run the verification, paste the commands and real output, update `PROGRESS.md`, stop.
2. **Docs before APIs.** Before writing code against LiteRT, `litert-torch` / `ai-edge-torch`, the NDK, AGP, WorkManager or any Android API, read the current official doc or source and cite the URL plus the version used in `docs/DECISIONS.md`. Do not trust memory for package coordinates, function signatures, flags or version numbers. Anything marked **[VERIFY]** below is a claim to check, not a fact.
3. **No unverified claims.** "Works" means you ran it and showed the output. Quality claims need an image grid as well as the numbers.
4. **Ask before** installing anything larger than ~200 MB, changing system settings, using `sudo`, or adding a third-party dependency.
5. **Decision log.** Every non-obvious choice gets 3–5 lines in `docs/DECISIONS.md`: context, options, choice, how to undo it.
6. **Pin versions.** Toolchain and libraries go in `gradle/libs.versions.toml`, `tools/requirements.txt` (exact `==`) and `docs/TOOLCHAIN.md`. No floating `+` versions.

## 1. Goal and non-goals
**Goal:** an Android app that upscales an existing photo 2x or 4x, fully on-device, as fast as the hardware allows, with natural-looking output in the spirit of OPPO "AI Clarity Enhancer": single-image SR, blended back toward a classical upscale so the result is not over-sharpened or plastic.

**Non-goals (v1):** face restoration, portrait/bokeh, multi-frame SR, camera capture, video, AGC/GCam integration, generative fill. Keep the engine's model interface open for a later face pass, and build nothing for it now.

**Hard exclusion:** no GCam modding. That means no feature-gate bypass, no Camera HAL vendor tags, and no copying of Google's proprietary assets such as `looknet_*.tflite` or Tomte/HDR+ Halide kernels. Those assets are unlicensed for redistribution, they depend on obfuscated app internals that change every release, and they reach private accelerator paths a third-party app cannot use.

## 2. Target and acceptance budgets
| Item | Value |
|---|---|
| Primary device | Pixel 7 Pro (`cheetah`), Tensor G2, Mali-G710 MP7, 12 GB, arm64-v8a only |
| Device family | All Tensor G2 devices: Pixel 7 `panther` (8 GB), 7a `lynx` (8 GB), Fold `felix` (12 GB), Tablet `tangorpro` (8 GB). Detect by `Build.SOC_MODEL` (`GS201` **[VERIFY]**), not by a codename list |
| Android versions | 13 / 14 / 15 (+ current). Test on whatever the Pro runs; list API-gated code paths (FGS type, Photo Picker backport) |
| SDK | minSdk 31, targetSdk/compileSdk = latest stable **[VERIFY]** |
| Memory sizing | Budget for the **8 GB** variants, not the 12 GB Pro |
| Form factors | Foldable posture changes and tablet widths: the UI uses window size classes, and jobs survive Activity recreation (WorkManager owns the job, not the Activity) |
| ABI | `abiFilters += "arm64-v8a"`; no other ABIs built anywhere |
| Perf target (set after Phase 2) | 12 MP → 2x total wall time ≤ T₂, 4x ≤ T₄, written down as numbers once measured |
| Memory | peak PSS ≤ 600 MB on any input; no OOM or LMK kill on a 12 MP 4x request (clean fallback is acceptable) |
| Quality | tiled `.tflite` vs untiled PyTorch: PSNR ≥ 40 dB (FP16), ≥ 45 dB (FP32); no seam is detectable by the seam metric (§6) |
| Thermals | 5 consecutive 12 MP 2x jobs finish without `THERMAL_STATUS_SEVERE` and without user-visible stalls > 2 s |

## 3. Stack (decided; push back with numbers if something is wrong)
- **UI:** Kotlin, Jetpack Compose, Material 3, edge-to-edge, system Photo Picker (`PickVisualMedia`).
- **Work:** WorkManager `CoroutineWorker` + `setForeground()`. Foreground service type: `mediaProcessing` on API 35+, `dataSync` below **[VERIFY: types, time limits, manifest permissions per API level]**.
- **Bridge:** JNI, thin. Coarse-grained calls only (`init`, `process(job)`, `cancel`). Progress goes back through a single callback throttled to ≤ 10 Hz.
- **Engine:** C++20, NDK (pin the r-version), CMake + Ninja, `-O3`, `-march=armv8.2-a+fp16+dotprod` **[VERIFY Tensor G2 cores: Cortex-X1/A78/A55 all support fp16 + dotprod]**.
- **Inference:** LiteRT C++ `CompiledModel` API **[VERIFY: Maven/Prefab coordinates, headers, the accelerator enum, how TensorBuffers are created from AHardwareBuffer/OpenCL/GL]**.
- **Accelerators:** NPU → GPU → CPU (XNNPACK), chosen at runtime by probe-and-fallback. The choice is logged with its reason.
- **Image I/O:** decode with `ImageDecoder` (`ALLOCATOR_SOFTWARE`, target color space sRGB) or NDK `AImageDecoder`. Pick one in Phase 3 and justify it. Encode with **libjpeg-turbo** (row-streaming) built via CMake. `Bitmap.compress` / `AndroidBitmap_compress` need the full output bitmap in RAM, which breaks the streaming rule.

## 4. Known technical risks (prove or kill these first)
| # | Risk | Why it matters | Kill test (phase) |
|---|---|---|---|
| R1 | LiteRT NPU accelerator may not support Tensor G2. Vendor plugins target Qualcomm/MediaTek; Google Tensor support is newer or partial **[VERIFY]**. Google's own apps reaching the G2 TPU (e.g. GCam's `looknet` float model plus Halide tonemap, ~1.7 s/shot per community teardowns) is **not** evidence that third-party apps can: those use private system interfaces | NPU may not exist for us. GPU becomes the main path | Docs check + `benchmark_model` with the NPU option (P2) |
| R2 | Apps may not be able to load OpenCL on Pixel. `libOpenCL.so` is a vendor lib and needs `<uses-native-library android:name="libOpenCL.so" android:required="false"/>` on API 31+, and may be absent anyway **[VERIFY]** | LiteRT GPU then drops to an OpenGL ES backend, or to CPU | Load test from an app process, not `adb shell` (shell has a different linker namespace) (P2/P3) |
| R3 | Converter emits NCHW↔NHWC `TRANSPOSE` ops or ops the GPU backend can't run (PReLU, PixelShuffle→`DEPTH_TO_SPACE`, residual add with nearest upsample) | Silent CPU partitions destroy throughput | Model analyzer / op dump: 100% of ops on the GPU delegate, 0 `TRANSPOSE` in the hot graph (P1) |
| R4 | FP16 overflow or banding in SRVGGNetCompact activations | Color blotches in highlights | FP16 vs FP32 PSNR + max abs error per channel on the test set (P1) |
| R5 | Output size: 12 MP × 4x = 192 MP. RGBA8 alone is 768 MB | OOM / LMK | Streaming encoder + size cap (P3) |
| R6 | Thermal throttling on sustained GPU load | Throughput collapses after ~30–60 s | 120 s sustained benchmark (P2) |
| R7 | Pixel Ultra HDR JPEGs (gain map) and Display P3 inputs | Color shift, lost HDR | Explicit v1 policy: convert to sRGB, drop the gain map, record it in DECISIONS (P3) |

## 5. Models
- **Default ("Fast"):** `realesr-general-x4v3` (SRVGGNetCompact, ~1.2 M params) from the official Real-ESRGAN GitHub release. Record the SHA-256 and the license (BSD-3 **[VERIFY]**) in `models/LICENSES.md`.
- **Optional denoise control:** `realesr-general-wdn-x4v3`. Real-ESRGAN's `-dn` interpolates weights between the two models. Bake at most 2 presets as separate `.tflite` files, and only if Phase 1 shows a visible gain.
- **Later ("Quality"):** `RealESRGAN_x4plus` (RRDBNet). Benchmark only in Phase 2; do not integrate in v1.
- **Layout:** export with an **NHWC float input of 1×H×W×3** by wrapping the PyTorch module (permute in, permute out) so the converter folds the transposes. Explain the result and verify it with the op dump (R3).
- **Precision:** an FP32 `.tflite` is the reference. On GPU, use FP16 compute (precision-loss-allowed flag / FP16 weights) **[VERIFY: how LiteRT expresses this]**. Build INT8 only if the NPU path requires it, and only ship it if PSNR vs FP32 ≥ 38 dB and the grid looks the same.
- **Static shapes:** one compiled model per tile size. The tile size is picked from the Phase 2 data, not assumed to be 128.
- **2x mode:** the model is native x4. Compare (a) x4 then a Lanczos/area downscale to 2x against (b) a 0.5x pre-downscale then x4. (b) costs 4x less compute. Choose with PSNR/LPIPS and grids.

## 6. Pipeline (per job)
```
Decode (EXIF orientation applied, → sRGB, alpha split off if present)
 → Analyze: size, noise σ (MAD of a high-pass), JPEG quality (quant-table read or blockiness), all plain C++
 → Plan: scale, tile size, overlap, Natural↔Sharp default from noise/JPEG estimate, output-size cap
 → Tile loop (row-major, one tile row in flight):
      read padded tile (reflect padding at borders)
      RGBA8 → model input dtype (NEON)        ── CPU thread A
      inference                               ── accelerator
      model output → RGB float/half (NEON)    ── CPU thread B
      accumulate into a row-band buffer with separable raised-cosine weights over the overlap
 → When a band is complete: blend with a Lanczos-3 upscale of the same band:
      out = lanczos + s · (sr − lanczos)   (s = Natural↔Sharp ∈ [0,1]); optionally blend on luma only to avoid chroma shift
 → Encode band rows → libjpeg-turbo (or PNG for alpha inputs) → MediaStore pending item (IS_PENDING=1 → 0)
 → Copy EXIF (ExifInterface), update dimensions, drop the thumbnail and orientation tag
```
Rules:
- **Overlap ≥ the model's effective receptive-field margin.** Compute the RF of SRVGGNetCompact (conv count × kernel) and justify the overlap. 16 px is a starting guess, not a spec.
- **Pipelining.** Use double-buffered input/output tensors so CPU conversion of tile N+1 and N−1 overlaps inference of tile N. This is usually the largest single win once the model is on GPU.
- **Seam metric.** Mean abs gradient across tile boundaries in (tiled − untiled) output must be ≤ 1.1 × the same metric at non-boundary columns.
- **Color.** Mean per-channel delta between output (downscaled to the input size) and input must be < 1.0 / 255.

## 7. Performance rules
- Compile once per (model, tile size, accelerator). Cache the compiled artifact if LiteRT supports a serialization/cache dir **[VERIFY]**. Run one warm-up inference at init and exclude it from timings.
- No heap allocation inside the tile loop. All buffers come from a preallocated arena sized from the plan. Verify with a debug allocation counter that asserts 0 allocations per tile.
- Zero-copy: use AHardwareBuffer- or GPU-backed `TensorBuffer`s where LiteRT supports them for the chosen backend. Otherwise use one host buffer per tensor, reused.
- NEON for RGBA8↔float/half and for blending. Keep a scalar reference implementation of each, and test the NEON version bit-exact or within ≤ 1 LSB.
- Store the model `.tflite` in assets with `noCompress += "tflite"` so it can be mmapped. Check page alignment **[VERIFY: AGP 16 KB page-size alignment requirements]**.
- Thermals: use `PowerManager.addThermalStatusListener` for state changes, plus `getThermalHeadroom(forecast)` polled no faster than its documented rate limit (it returns NaN when called too often) **[VERIFY]**. Policy: headroom > 0.85 → insert sleep between tiles; ≥ SEVERE → pause the job, show it in the notification, resume below the threshold.
- Memory cap: decide output limits from `ActivityManager.MemoryInfo` + the plan's arena size. Over the cap → offer 2x or a capped long edge. Never crash.
- Instrumentation: per-stage timers (decode, analyze, convert-in, infer, convert-out, blend, encode, save) logged as one structured line per job, plus `ATrace_beginSection` markers so Perfetto shows the pipeline overlap.

## 8. Build-time performance (local loop)
- One module per concern: `:app` (UI + worker), `:engine` (NDK + Kotlin wrapper). Same-ABI, debug-only native build in the local loop.
- `org.gradle.configuration-cache=true`, `org.gradle.caching=true`, `org.gradle.parallel=true`. Use the version catalog and the latest stable AGP/Kotlin **[VERIFY]**.
- CMake: Ninja and ccache (`CMAKE_CXX_COMPILER_LAUNCHER=ccache`), and only `arm64-v8a`. A host-native CMake target builds the pure-C++ parts (tiler, blend, convert scalar path, analyze) for x86_64 so unit tests run in seconds without a device.
- Measure: record warm incremental build times for (a) a Kotlin-only edit and (b) a single `.cpp` edit in `docs/TOOLCHAIN.md` in Phase 3. Investigate if (b) exceeds 20 s.

## 9. Repo layout
```
upscaler/
├── tools/                  convert.py, reference_upscale.py, eval.py, bench_device.sh, requirements.txt
├── testset/                fixed images (≥ 2 each: portrait, foliage, architecture, text, low-light, heavy JPEG, Ultra HDR from my Pixel, PNG+alpha)
├── models/                 *.tflite (git-ignored) + LICENSES.md + checksums.txt
├── docs/                   DECISIONS.md, TOOLCHAIN.md, BENCHMARKS.md
├── app/                    Compose UI, worker/, engine/ (Kotlin wrapper)
├── engine/src/main/cpp/
│   ├── CMakeLists.txt      (Android target + host test target)
│   ├── jni_bridge.cpp
│   ├── runtime.{h,cpp}     LiteRT CompiledModel, accelerator probe/fallback
│   ├── tiler.{h,cpp}       plan, padding, overlap weights, band accumulator
│   ├── blend.{h,cpp}       Lanczos-3, Natural↔Sharp blend
│   ├── pixel_convert.{h,cpp}  NEON + scalar reference
│   ├── analyze.{h,cpp}     noise, JPEG quality
│   ├── jpeg_writer.{h,cpp} libjpeg-turbo row-streaming
│   └── cli/main.cpp        adb-shell CLI
├── engine/src/test/cpp/    GoogleTest, host-run
└── PROGRESS.md
```
`tools/reference_upscale.py` is the **golden reference**. The C++ tiler/blend must reproduce it on the same inputs (§11, P3).

## 10. Task format (each phase's plan uses this)
```
### Task N: <title>
Acceptance: 1–3 testable bullets
Verify: exact command(s) + expected signal
Depends on: Task ids
Files: list
Size: XS/S/M (anything L+ is split)
```
Put a checkpoint after every 2–3 tasks: build green, tests green, the device check passes, and I review before you continue.

## 11. Phases

### Phase 0 — Environment (no code)
- Detect and print versions: Ubuntu, Python, `pip`, JDK, Android SDK cmdline-tools, platform-tools/`adb`, NDK, CMake, Ninja, ccache, Gradle wrapper target.
- Device: `adb devices -l`, `getprop ro.build.version.sdk`, `ro.product.board`, `ro.hardware`, and whether `/vendor/lib64/libOpenCL.so` exists (R2, first signal only).
- Output: a missing/installed table with install commands. Ask before running them.
- Repo bootstrap (§13): `git init -b main`, a `.gitignore` (build outputs, `models/*.tflite`, `out/`, `local.properties`, `.cxx/`), a `.gitattributes`, and the PR template. Initial commit on `main`, then create `dev` from it. Ask before creating the GitHub remote and before setting branch protection.
- **Done:** the phone is listed, every tool version is printed into `docs/TOOLCHAIN.md`, `main` and `dev` exist on the remote, and the protection rules are shown with `gh api repos/{owner}/{repo}/branches/{branch}/protection`.

### Phase 0.5 — Hardware spike (throwaway, 1 day)
- Branch `spike/hw-probe`: not merged, no PR flow. Findings move into `docs/` through a normal PR.
- Convert x4v3 at one fixed tile size (FP32, FP16, INT8-dynamic). Run `benchmark_model` on the phone for CPU/GPU/NPU, dump which processor each operation runs on, check that `libOpenCL` loads from an app process, and measure PSNR vs PyTorch per precision.
- Before running, decide and write down: the minimum speed (12 MP 2x ≤ 60 s, 4x ≤ 5 min on the best accelerator), and the rule "NPU fast but fails quality → ship on GPU".
- **Done:** a one-page verdict in `docs/BENCHMARKS.md` (main accelerator, precision, tile size, quality target per processor). Below the minimum speed → stop and re-scope with me.

### Phase 1 — Model conversion + golden reference (desktop)
- Download weights, verify checksums, record licenses.
- Convert to FP32 and FP16 `.tflite` with NHWC I/O (§5). Dump the op list and the delegate partition plan (R3). Converter choice **[VERIFY: litert-torch vs ai-edge-torch current name and API]**.
- `reference_upscale.py`: tiling, overlap weights, Lanczos blend, 2x strategies (a)/(b), run with the LiteRT Python interpreter on CPU.
- `eval.py`: PSNR, SSIM, LPIPS (optional), seam metric, color delta, side-by-side grids → `out/phase1/`.
- **Done:** the §2 quality budgets are met on the test set, the grids show no seams, R3 and R4 are answered in DECISIONS.

### Phase 2 — Device benchmark and accelerator verdict
- Push models and the official LiteRT `benchmark_model` (prebuilt for arm64 or built from source; pin the version).
- Matrix: {CPU 1/4 threads, GPU fp16, GPU fp32, NPU if available} × tile {96, 128, 192, 256}. Report median, p90, init time and **pixels/sec**.
- 120 s sustained run of the best configuration, logging throughput every 10 s and thermal status (R6).
- Answer R1 and R2 with evidence. Name the main path.
- **Done:** `docs/BENCHMARKS.md` table plus the chosen (accelerator, tile size), and the T₂/T₄ budgets in §2 filled in.

### Phase 3 — C++ engine + CLI
- Slices, each runnable on its own: (1) host-built tiler/blend matching the Python golden output, (2) LiteRT runtime with probe/fallback on device, (3) NEON convert vs scalar, (4) streaming JPEG writer, (5) pipelined tile loop, (6) CLI `upscaler_cli in.jpg out.jpg --scale 4 --strength 0.6 --accel auto`.
- **Done:** the CLI processes the test set from `/data/local/tmp`. Output vs Python golden: PSNR ≥ 40 dB, seam metric passes, peak RSS printed and within §2, per-stage timings printed.

### Phase 4 — Android app
- Engine AAR consumed by `:app`. JNI surface ≤ 5 functions. Cancellation is checked between tiles and returns in < 500 ms.
- Compose: pick (Photo Picker), 2x/4x, Natural↔Sharp, before/after compare (drag divider + synced pinch-zoom over downsampled previews, never the full output bitmap), progress, cancel, save, share. States: empty, picked, processing, thermal-paused, done, error, cancelled.
- WorkManager foreground job with a progress notification and cancel action. The result goes to MediaStore `Pictures/Upscaler`.
- **Done:** the end-to-end flow works on the phone. Screen recording (`adb shell screenrecord`) of a 12 MP 2x run; process survives rotation, backgrounding and screen-off.

### Phase 5 — Optimization
- Baseline from Phase 4, then one change at a time with remeasurement: zero-copy buffers, pipelining depth, tile size retune, thermal policy, memory cap, removed copies.
- Perfetto trace before/after, showing CPU/accelerator overlap.
- Only if CPU stages (Lanczos, blend, convert) exceed 15% of wall time after NEON: prototype the slowest one in **Halide** (AOT-compiled for arm64, scheduled for the G2 big cores). Keep it only if it beats the hand-written NEON version by ≥ 1.5x. Same approach as Google's camera pipeline, using our own code.
- Run the final benchmark on one 8 GB device (Pixel 7 or 7a) if available. Otherwise simulate the budget with a lower memory cap and record that it was simulated.
- **Done:** a before/after table (wall time, pixels/sec, peak PSS, sustained throughput). A 12 MP 4x request completes or falls back cleanly, with no OOM.

## 12. Working style
- Small, reviewable diffs. Each task leaves the build green and goes through the PR flow in §13. Nothing lands on `dev` or `main` directly.
- Prefer the platform and stdlib. Every new dependency has a one-line justification in DECISIONS.
- If evidence contradicts this prompt (e.g. the NPU is unusable, or 128 px tiles are slow), stop, show the data, and propose the change. Don't silently work around it.
- `PROGRESS.md` per phase: done, measured numbers, open risks, next phase's first task.

## 13. Git workflow, PRs and review

### Roles
| Role | Who | Can |
|---|---|---|
| Author | implementing agent | branch, commit, push its own branch, open PRs into `dev`, address review comments |
| Reviewer + maintainer | human code reviewer (me, or the reviewer I name) | review, approve or request changes, merge into `dev`, approve release PRs `dev → main`, change protection rules |

There is no AI reviewer agent. The author never approves or merges its own PR. It opens the PR, fills in the template, and waits for a human review. If the reviewer uses a separate GitHub account, `dev` requires 1 approving review. If the agent pushes under the reviewer's own account, GitHub blocks self-approval, so `dev` requires a PR without a required approval, and the reviewer approves by merging.

### Branches
- `main`: released, always green, one tagged release per completed phase (`v0.<phase>.0`). Protected: PR required, no force-push, no deletion.
- `dev`: integration and on-device testing. Protected: PR required, human review before merge, merge commits only.
- Work branches always come from an up-to-date `dev`: `git switch dev && git pull --ff-only && git switch -c <type>/<scope>-<slug>`
  - Types: `feature/`, `fix/`, `perf/`, `refactor/`, `test/`, `docs/`, `chore/`, `build/`. Example: `feature/engine-tiler-overlap`, `perf/engine-double-buffer`.
  - One task (§10) = one branch = one PR. Don't stack a feature on another unmerged feature unless it truly depends on it; if it does, say so in the PR body and target the parent branch.
  - A redesign starts a new branch from `dev`. Pull reference code from the old branch with `git restore --source <old-branch> -- <path>` or `git cherry-pick <sha>`. Don't keep building on the stale branch.
- Keep up to date with `git fetch && git rebase origin/dev` on your own branch only, then push with `--force-with-lease`. Never force-push `dev` or `main`.
- After merge: delete the remote branch (auto-delete on merge) and the local one with `git branch -d` (never `-D` without asking).

### Commits
- [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): imperative summary` ≤ 72 chars. Scopes: `engine`, `app`, `worker`, `tools`, `models`, `build`, `docs`. Body explains *why*, plus any measured numbers (e.g. `perf(engine): double-buffer tiles` with `12MP 2x: 9.8s → 6.1s`).
- Atomic: each commit builds and passes tests so `git bisect` works. Unrelated changes go in separate commits.
- Stage explicitly (`git add <paths>` or `git add -p`); never `git add .` or `-A`. Check `git diff --staged` before committing.
- Never commit: `.tflite`/`.pt` weights (fetch with `tools/fetch_models.sh` + checksums), build dirs, keystores, `local.properties`, large test outputs. Test images under 1 MB each can be committed; anything larger needs Git LFS, ask first.
- **Co-author trailer is mandatory** on every commit. Leave a blank line after the body, then the last line is exactly
  `Co-authored-by: Claude <noreply@anthropic.com>`.
  The commit author is `MoaazHF <183323119+MoaazHF@users.noreply.github.com>`, set repo-locally with `git config user.name/user.email`. Check it before every commit with `git config user.email`; a personal email in a new commit is a bug. Merge with `gh pr merge --merge --body "<summary>\n\nCo-authored-by: Claude <noreply@anthropic.com>"`, so the merge commit carries the trailer too. Confirm with `git log --format='%h %s%n%(trailers:key=Co-authored-by)' origin/dev`. This is what earns the GitHub "Pair Extraordinaire" achievement (co-authored commits on merged PRs).
- **No squashing, ever.** Every commit is kept: no squash merges, no autosquash, no `reset --soft` recommits. Review fixes go in new commits. Each commit must still be clean (atomic, builds, Conventional Commit message), because it stays in history forever.

### Pull requests
- Open with `gh pr create --base dev`, with a body that follows `.github/pull_request_template.md`:

  ```
  ## What / Why            (task id from tasks/todo.md)
  ## How verified          (commands + pasted output; device model + Android version)
  ## Numbers               (before → after for perf PRs; PSNR/seam for quality PRs)
  ## Screenshots           (UI PRs: light + dark)
  ## Risk / Rollback
  ```

- Size: aim for ≤ 400 changed lines excluding generated files. Larger PRs get split unless the reviewer agrees.
- Required checks before asking for review (local until CI exists; a GitHub Actions CI is an optional later task, ask me):
  `./gradlew :app:lintDebug :engine:testDebugUnitTest assembleDebug`, host C++ tests via `ctest`, `clang-format --dry-run -Werror`, `ruff check tools/`.
- Merge `feature → dev` with a **merge commit** (squash and rebase merges are disabled on the repo). All branch commits keep their SHAs. The repo sets the merge commit's title to the PR title and its message to the PR body, so every PR body ends with the `Co-authored-by` trailer line.
- Release `dev → main` at the end of each phase via a PR titled `release: phase N`. Use a **merge commit** (keeps history traceable to `dev`), then `git tag -a v0.N.0` on `main` and push the tag. Only after I approve.
- Hotfix: `hotfix/<slug>` from `main` → PR to `main` → then merge `main` back into `dev`.

### Review checklist (the author self-checks each item in the PR body; the human reviewer verifies)
1. Correctness vs the task's acceptance criteria; the verify commands were re-run, not just read.
2. Hot-loop rules (§7): no allocations, no extra copies, NEON vs scalar test present.
3. JNI: no leaked local/global refs, exceptions checked, no JNI calls on the inference thread.
4. Threading and cancellation: nothing blocks the main thread; cancel reaches the tile loop.
5. Memory: lifetimes of AHardwareBuffer/TensorBuffer/Bitmap locks are clear; the 8 GB budget holds.
6. Docs-verified API use: [VERIFY] items touched have a cited URL in DECISIONS.
7. Commit hygiene: Conventional Commits, atomic, no stray files.

Review comments are labelled `blocker` / `should-fix` / `nit`. Any `blocker` → changes requested; the author fixes them in new commits on the same branch.
