# Rebuilding 0.6.0

Runtime needs no development tools. This package includes application source, modified GPUPixel source, Deep-Live-Cam core/upstream source, selected InsightFace source, model provenance and license notices.

Native: MSVC C++17 x64, CMake >=3.21, Ninja, Qt 6.8.3 (Widgets/OpenGLWidgets/OpenGL), bundled tools/mpv/include. Configure CMake with your Qt prefix and a developer command prompt. Example: `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=YOUR_QT_DIR`, then `cmake --build build`. Run build.cmd from an x64 MSVC developer prompt, passing -DCMAKE_PREFIX_PATH=YOUR_QT_DIR when needed. Copy Qt platform/runtime DLLs and libmpv into app; GPUPixel LUTs go in app/gpupixel/res.

Face worker: Python 3.12, mediapipe 1.0.1, opencv-python-headless 5.0.0.93, numpy 2.5.3, onnxruntime-directml 1.24.4, Pillow 12.3.0, PyInstaller 6.22.3. Install versions available for the target platform and run `python tools/face_worker.py models/face_landmarker.task` to inspect startup. Build with `pyinstaller --distpath build/engine-dist --workpath build/engine-build build-support/FaceEngine.spec`, then copy engine-dist/FaceEngine to app/face_engine_v060. No InsightFace pip build, CUDA or scikit-image required; selected Python runtime sources are in tools/insightface_runtime. DirectML is preferred and CPU fallback is labelled.

Browser: install/activate Emscripten 6.0.10 locally at tools/emsdk, then `python tools/build_gpupixel_web.py`. The script records its compiler, upstream revision, artifact length and SHA256 in edge-extension/gpupixel-build.json. It embeds local WASM/LUTs, without remote code or dynamic JS eval. Manifest CSP includes wasm-unsafe-eval specifically for WebAssembly.

To reproduce extracted DLC functions, run tools/vendor_dlc_core.py against the included upstream revision. Keep the project-authored NumPy similarity_transform.py in tools/insightface_runtime/utils. Model download scripts verify checksums; model licenses are separate from code licenses. Missing models are reported at runtime, not silently substituted.

Tests are in tests/. Fixture URLs/provenance are in THIRD_PARTY.md and validation data. Technical/public fixture media and test browser binaries are excluded from the player archive. Source testing uses work/ and --control-dir to avoid normal user settings. Place the built app/runtime DLLs in app/, the launcher in the project root, and install models with DownloadModels.cmd. The public distribution uses the same compiled player, worker and extension as the verified local 0.6.0 build.

Unused Mars/MNN binary directories are intentionally omitted; the root build disables the GPUPixel face detector. The Python worker requirements are in requirements-face.txt. Model download and verification are separate from application startup.

0.6.0 native output: app/BeautyPlayerV060.exe. Launcher output: work/v060/Yingche.exe; copy it to the root after checks. tools/beauty_stability.py is imported by the worker and included by PyInstaller.

The unchanged browser bridge still runs app/face_engine_v041/FaceEngine.exe with protocol 0.4.1. Its exact Python source and portable build spec are retained under legacy/bridge-v041. Build that spec separately and copy the resulting FaceEngine directory to app/face_engine_v041. Do not rebuild the legacy bridge from the new native worker source.

Native tests for this version are tests/*v060.py; browser default/migration checks are edge_defaults_v060.cjs and edge_defaults_browser_v060.py. Test dependencies and public media fixtures are separate from the runtime. Use isolated --control-dir settings, test browser profiles and owned process IDs. The synthetic 1080p60 codec fixture does not establish real 60 fps motion quality.

Browser interpolation uses the included Framegen 1.4.0 runtime and unchanged v7-small weights. No new compiler step is needed to load the extension. See edge-extension/vendor/framegen/SOURCE.md and its separate code/weight licenses.

The portable distribution includes both frozen workers, runtime DLLs, source, licenses and an opt-in native model downloader. It excludes personal configuration, test media, development tools and native model weights. Keep future source synchronization separate from Release approval as described in AGENTS.md.

Packaging: run `python scripts/package_release.py stage --runtime-root PATH_TO_VERIFIED_INSTALL --stage dist/Yingche-v0.6.0-windows-x64` from the Git checkout, then test an isolated copy with `tests/package_acceptance_v060.py`. Run `python scripts/package_release.py archive --stage dist/Yingche-v0.6.0-windows-x64 --assets dist/assets` after reviewing the staged files. Staging requires a new directory and preserves existing outputs; the packager never uploads or publishes a Release.
