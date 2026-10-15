## Qt Code Review Report

**Scope**: current native files against work/v060/backup; seven C++/header files.
**Files reviewed**: 7
**Issues found**: 35 (30 from lint, 5 deduplicated from deep analysis; the five behavioral findings have been fixed and tested).

---

### Lint findings

#### [L-001] VAR-3
- **File**: `src/launcher.cpp:14`
- **Rule**: VAR-3
- **Finding**: Direct brace initialization — prefer copy-init (var = {...}) for safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-002] VAR-3
- **File**: `src/launcher.cpp:15`
- **Rule**: VAR-3
- **Finding**: Direct brace initialization — prefer copy-init (var = {...}) for safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-003] DEP-7
- **File**: `src/media_identity.h:17`
- **Rule**: DEP-7
- **Finding**: qMin/qMax/qBound — use (std::min)()/(std::max)()/std::clamp()
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-004] DEP-7
- **File**: `src/media_identity.h:19`
- **Rule**: DEP-7
- **Finding**: qMin/qMax/qBound — use (std::min)()/(std::max)()/std::clamp()
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-005] DEP-7
- **File**: `src/media_identity.h:20`
- **Rule**: DEP-7
- **Finding**: qMin/qMax/qBound — use (std::min)()/(std::max)()/std::clamp()
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-006] ERR-6
- **File**: `src/player.cpp:35`
- **Rule**: ERR-6
- **Finding**: QString::arg() has %60 but only 3 .arg() calls
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-007] DEP-7
- **File**: `src/player.cpp:47`
- **Rule**: DEP-7
- **Finding**: qMin/qMax/qBound — use (std::min)()/(std::max)()/std::clamp()
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-008] DEP-7
- **File**: `src/player.cpp:384`
- **Rule**: DEP-7
- **Finding**: qMin/qMax/qBound — use (std::min)()/(std::max)()/std::clamp()
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-009] DEP-11
- **File**: `src/player.cpp:393`
- **Rule**: DEP-11
- **Finding**: QDateTime::currentDateTime() — use currentDateTimeUtc() (100x faster, DST-stable)
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-010] VAR-3
- **File**: `src/player.cpp:418`
- **Rule**: VAR-3
- **Finding**: Direct brace initialization — prefer copy-init (var = {...}) for safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-011] DEP-7
- **File**: `src/player.cpp:493`
- **Rule**: DEP-7
- **Finding**: qMin/qMax/qBound — use (std::min)()/(std::max)()/std::clamp()
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-012] ERR-1
- **File**: `src/player.cpp:514`
- **Rule**: ERR-1
- **Finding**: QFile::open() return not checked — silent failure if file cannot open
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-013] ERR-1
- **File**: `src/player.cpp:542`
- **Rule**: ERR-1
- **Finding**: QFile::open() return not checked — silent failure if file cannot open
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-014] VAR-3
- **File**: `src/player.cpp:543`
- **Rule**: VAR-3
- **Finding**: Direct brace initialization — prefer copy-init (var = {...}) for safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-015] ERR-1
- **File**: `src/player.cpp:564`
- **Rule**: ERR-1
- **Finding**: QFile::open() return not checked — silent failure if file cannot open
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-016] ERR-1
- **File**: `src/player.cpp:604`
- **Rule**: ERR-1
- **Finding**: QFile::open() return not checked — silent failure if file cannot open
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-017] PAT-7
- **File**: `src/player.h:80`
- **Rule**: PAT-7
- **Finding**: QMap usage — verify copying is needed; std::map saves ~1.7KiB text
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-018] VAR-3
- **File**: `src/player.h:88`
- **Rule**: VAR-3
- **Finding**: Direct brace initialization — prefer copy-init (var = {...}) for safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-019] DEP-7
- **File**: `src/settings.h:36`
- **Rule**: DEP-7
- **Finding**: qMin/qMax/qBound — use (std::min)()/(std::max)()/std::clamp()
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-020] VAR-3
- **File**: `src/video.cpp:102`
- **Rule**: VAR-3
- **Finding**: Direct brace initialization — prefer copy-init (var = {...}) for safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-021] VAR-3
- **File**: `src/video.cpp:169`
- **Rule**: VAR-3
- **Finding**: Direct brace initialization — prefer copy-init (var = {...}) for safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-022] HDR-3
- **File**: `src/video.cpp:197`
- **Rule**: HDR-3
- **Finding**: Unprotected std::min/max — use (std::min)(a,b) for Windows macro safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-023] HDR-3
- **File**: `src/video.cpp:202`
- **Rule**: HDR-3
- **Finding**: Unprotected std::min/max — use (std::min)(a,b) for Windows macro safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-024] DEP-10
- **File**: `src/video.cpp:205`
- **Rule**: DEP-10
- **Finding**: .count()/.length() — prefer .size() for std consistency
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-025] DEP-10
- **File**: `src/video.cpp:206`
- **Rule**: DEP-10
- **Finding**: .count()/.length() — prefer .size() for std consistency
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-026] VAR-3
- **File**: `src/video.cpp:453`
- **Rule**: VAR-3
- **Finding**: Direct brace initialization — prefer copy-init (var = {...}) for safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-027] VAR-3
- **File**: `src/video.cpp:470`
- **Rule**: VAR-3
- **Finding**: Direct brace initialization — prefer copy-init (var = {...}) for safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-028] HDR-3
- **File**: `src/video.cpp:501`
- **Rule**: HDR-3
- **Finding**: Unprotected std::min/max — use (std::min)(a,b) for Windows macro safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-029] HDR-3
- **File**: `src/video.cpp:522`
- **Rule**: HDR-3
- **Finding**: Unprotected std::min/max — use (std::min)(a,b) for Windows macro safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

#### [L-030] HDR-3
- **File**: `src/video.cpp:525`
- **Rule**: HDR-3
- **Finding**: Unprotected std::min/max — use (std::min)(a,b) for Windows macro safety
- **Mitigation**: Original scanner output retained for review. Keep any future cleanup scoped; this delivery does not claim a clean lint run or rewrite unrelated style. Runtime error paths are covered separately below.

---

### Deep analysis findings

#### [D-001] R release while Shift is held — fixed
- **File**: `src/player.cpp:465`
- **Category**: Model Contracts / Ownership & Lifecycle
- **Confidence**: 98/100
- **Finding**: The modifier guard originally discarded R-up after a modified hold.
- **Trace**: Trace eventFilter -> previewOriginal -> originalHeld. Accept R release regardless of modifiers when a hold exists. Actual R/Shift sequence restored state.
- **Mitigation**: Implemented in the current source; test evidence is included in 0.6.0验证数据.json.

#### [D-002] Paused transition endpoint cached — fixed
- **File**: `src/video.cpp:232`
- **Category**: Thread Safety / API & C++ Correctness
- **Confidence**: 92/100
- **Finding**: The final interpolated GPUPixel settings could miss cache invalidation.
- **Trace**: Trace displayedBeauty -> gpupixelDirty -> cached render. Compare every displayed parameter and invalidate including the endpoint. Exact zero-output pixel equality passed.
- **Mitigation**: Implemented in the current source; test evidence is included in 0.6.0验证数据.json.

#### [D-003] Delayed terminal repaint skipped — fixed
- **File**: `src/video.cpp:25`
- **Category**: Performance & Quality
- **Confidence**: 88/100
- **Finding**: An elapsed-time-only timer could stop before the final paused repaint after a GUI delay.
- **Trace**: Keep a transition pending until paintGL applies blend=1. A 350 ms deliberate GUI delay followed by exact original pixels passed.
- **Mitigation**: Implemented in the current source; test evidence is included in 0.6.0验证数据.json.

#### [D-004] No-save warning overwritten — fixed
- **File**: `src/player.cpp:416`
- **Category**: Error Handling
- **Confidence**: 97/100
- **Finding**: Opening or editing media could replace the read-only-settings warning with normal save language.
- **Trace**: Persist the no-save notice through restore/edit; corrupt, structurally invalid and future-version configs stayed byte-identical and visibly no-save.
- **Mitigation**: Implemented in the current source; test evidence is included in 0.6.0验证数据.json.

#### [D-005] Saved file could exceed load limit — fixed
- **File**: `src/player.cpp:542`
- **Category**: Error Handling
- **Confidence**: 93/100
- **Finding**: Unbounded media entries could generate a file rejected by the next startup.
- **Trace**: Cap new records at 2000 without eviction and check compact bytes against the same 4 MiB load limit before commit. Existing file is preserved when the bound is reached.
- **Mitigation**: Implemented in the current source; test evidence is included in 0.6.0验证数据.json.

---

### Investigation targets (human verification needed)

#### [I-001] Synchronous cut readback under heavier rendering load
- **File**: `src/video.cpp:181`
- **Category**: Performance & Quality
- **Confidence**: 76/100
- **Finding**: Tiny GPU readback can still synchronize the GUI render thread.
- **Unverified because**: Genuine 1080p60 high-motion and long GPU stress were not available. No p95 distribution was captured.
- **How to verify**: Repeat real 60fps playback with app-level GPU telemetry and latency capture. The real 30fps physical-display run measured cumulative mean 0.191 ms / maximum 4.229 ms, with 0 drops in that segment.

---

### Summary

Six read-only domain reviews completed. No remaining newly confirmed behavioral defect from those reviews; lint records and empirical limits remain visible. Physical unplug, new single-monitor session and final visual preference still need manual validation. No project source was changed by the review agents.
