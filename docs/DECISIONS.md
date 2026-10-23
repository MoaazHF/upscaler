# Decisions

## D1 — Repo on ext4, not the NTFS data drive (2026-10-23)
- Context: `/mnt/E0D8B744D8B717AC` is `fuseblk` (NTFS): every file shows mode 777, symlinks and exec bits are unreliable, and Gradle/NDK/ccache run slower there.
- Choice: repo at `~/dev/upscaler` on `/home` (ext4).
- Undo: `git clone` anywhere else.

## D2 — One Android SDK: Android Studio's (2026-10-23)
- Context: two SDKs existed, `~/Android/Sdk` (android-35 + adb only) and Studio's `~/Downloads/android-studio`. Two SDKs mean mismatched adb servers and a missing NDK for terminal builds.
- Choice: `ANDROID_HOME=~/Downloads/android-studio` for both Studio and the terminal.
- Undo: repoint `ANDROID_HOME` in `~/.bashrc`.

## D3 — NDK 28.2.13676358, CMake 4.1.2 (2026-10-23)
- Context: both already installed. NDK r30 would cost ~2.5 GB with 13 GB free on `/home`.
- Choice: pin what's installed. A third-party dep with `cmake_minimum_required(<3.5)` gets `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`.
- Undo: install another side-by-side version and change `ndkVersion` / `cmake.version`.
- Open: LiteRT prebuilt compatibility with r28 is checked in Phase 0.5.

## D4 — Hardware spike before Phase 1 (2026-10-23)
- Context: the dev-team review flagged that the accelerator verdict decides model format, tile size and the quality budget.
- Choice: Phase 0.5, a throwaway `spike/hw-probe` branch outside the PR flow; findings land in `docs/` via a normal PR.
- Undo: skip to Phase 1.

## D5 — Human code review, co-authored commits (2026-10-23)
- Choice: no AI reviewer agent; a human reviews and merges every PR. Every commit carries `Co-authored-by: Claude <noreply@anthropic.com>`, kept through squash merges.
- Why: the maintainer wants co-authored commits on merged PRs (GitHub "Pair Extraordinaire").

## D6 — Merge commits only, no squashing (2026-10-23)
- Context: the maintainer wants every commit kept in history and counted.
- Choice: squash and rebase merges are disabled on the repo; linear history is off on `dev`. The merge commit's title is the PR title and its message is the PR body, which ends with the `Co-authored-by` trailer.
- Undo: re-enable squash merge in repo settings.
