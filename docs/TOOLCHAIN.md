# Toolchain

Recorded 2026-10-23, Phase 0 (Task 0.1/0.2). Pinned versions are the source of truth for every build.

## Host
| Item | Found | Pinned / action |
|---|---|---|
| OS | Ubuntu 24.04.4 LTS, kernel 6.17.0-22 | — |
| Repo disk | `~/dev/upscaler` on ext4 (`/home`, 13 GB free) | old folder on `/mnt/E0D8…` is NTFS (`fuseblk`): not used for the repo |
| Python | 3.12.3, pip 24.0 | venv in `tools/.venv` (Phase 1) |
| JDK | OpenJDK 21.0.12.1 | keep (AGP needs 17+) |
| Android Studio | 2026.2.1 (snap) | SDK manager for everything below |
| **Android SDK** | Studio's SDK: `~/Downloads/android-studio` (9.5 GB). A second, older SDK at `~/Android/Sdk` holds only android-35 + adb | **single SDK = `~/Downloads/android-studio`**; `ANDROID_HOME` must point there |
| platform-tools / adb | 37.0.1 | from `ANDROID_HOME` |
| Platforms | 31, 33, 34, 35, 36, 36.1, **37.0** | compileSdk/targetSdk 37 **[VERIFY AGP support in Phase 4]** |
| Build-tools | 34.0.0, 35.0.0, 36.0.0 | AGP picks |
| NDK | 27.0.12077973, **28.2.13676358** | pin `ndkVersion = "28.2.13676358"` (r28c, 16 KB page-size default). r30 not needed; saves ~2.5 GB |
| CMake | SDK 3.22.1, **4.1.2**; system 3.28.3 | pin `4.1.2`. Any third-party dep with `cmake_minimum_required(<3.5)` gets `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` |
| Ninja | 1.11.1 (SDK CMake bundles its own) | keep |
| ccache | 4.9.1 (apt) | keep |
| git | 2.43.0; repo-local identity `MoaazHF <183323119+MoaazHF@users.noreply.github.com>` | GitHub noreply address (user id 183323119), so commits attribute to `MoaazHF` without exposing a personal email |
| gh | 2.98.0, logged in as `MoaazHF` | — |

## Device (probed 2026-10-23, read-only over adb)
| Item | Value |
|---|---|
| Model / device | Pixel 7 Pro, `cheetah`, serial `28251FDH300GA8`, USB `18d1:4ee7` |
| Android | 17, SDK 37, build `CP3A.261005.002.A1` |
| SoC | `ro.soc.model=GS201` (Tensor G2), `ro.soc.manufacturer=Google` |
| ABI / page size | arm64-v8a / 4096 B |
| RAM | 11.2 GiB (`MemTotal 11743508 kB`) |
| Free storage `/data` | 28 GB |
| GPU libs | `/vendor/lib64/libOpenCL.so`, `libOpenCL-pixel.so`, `egl/libGLES_mali.so` |
| `/vendor/etc/public.libraries.txt` | lists **`libOpenCL.so`**, `libOpenCL-pixel.so`, **`libedgetpu_client.google.so`** |
| Thermal status at idle | 0 (none) |

Notes:
- R2 (OpenCL unreachable from apps) is likely mitigated: `libOpenCL.so` is a vendor *public* library, so an app may load it after declaring `<uses-native-library android:name="libOpenCL.so" android:required="false"/>`. Still to confirm from an app process in Phase 0.5.
- `libedgetpu_client.google.so` is also public. It is a possible NPU route, but its API is undocumented; Phase 0.5 checks whether LiteRT uses it.
- The device runs Android 17 (SDK 37), so `compileSdk/targetSdk 37` matches the installed `platforms;android-37.0`.
