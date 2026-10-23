## What / Why
<!-- task id from tasks/todo.md -->

## How verified
<!-- commands + pasted output; device model + Android version -->

## Numbers
<!-- before → after for perf PRs; PSNR / seam metric for quality PRs; "n/a" otherwise -->

## Screenshots
<!-- UI PRs: light + dark -->

## Risk / Rollback

## Review checklist
- [ ] Meets the task's acceptance criteria; verify commands re-run
- [ ] Hot-loop rules: no allocations, no extra copies, NEON vs scalar test present
- [ ] JNI: no leaked refs, exceptions checked, no JNI calls on the inference thread
- [ ] Threading / cancellation: nothing blocks the main thread; cancel reaches the tile loop
- [ ] Memory: buffer lifetimes clear; 8 GB budget holds
- [ ] [VERIFY] items touched have a cited URL in docs/DECISIONS.md
- [ ] Conventional Commits, atomic, `Co-authored-by` trailer on every commit, no stray files
