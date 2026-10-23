# Progress

## Phase 0 — Environment ✅ (2026-10-23)
- Host: Ubuntu 24.04, JDK 21, Python 3.12; single SDK (Android Studio's) with NDK 28.2.13676358, CMake 4.1.2, platform 37.0; ccache 4.9.1. See `docs/TOOLCHAIN.md`.
- Device: Pixel 7 Pro (`cheetah`), Android 17 / SDK 37, GS201, 11.2 GiB RAM; `libOpenCL.so` and `libedgetpu_client.google.so` are vendor public libraries.
- Repo: `MoaazHF/upscaler` (public), `main` + `dev` protected (PR required, no force-push or deletion), merge commits only, co-author trailer on every commit.
- Open risks: R1 (NPU via LiteRT), R2 (confirm OpenCL loads from an app process), R3–R7 unchanged.
- Next: Phase 0.5 hardware spike, task list first.
