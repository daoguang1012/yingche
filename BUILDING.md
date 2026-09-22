# Rebuilding 0.4.1

Runtime needs no development tools. This package includes application source, modified GPUPixel source, Deep-Live-Cam core/upstream source, selected InsightFace source, model provenance and license notices.

Native: MSVC C++17 x64, CMake >=3.21, Ninja, Qt 6.8.3 (Widgets/OpenGLWidgets/OpenGL), bundled tools/mpv/include. Configure CMake with your Qt prefix and a developer command prompt. Example: `cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=YOUR_QT_DIR`, then `cmake --build build`. Run build.cmd from an x64 MSVC developer prompt, passing -DCMAKE_PREFIX_PATH=YOUR_QT_DIR when needed. Copy Qt platform/runtime DLLs and libmpv into app; GPUPixel LUTs go in app/gpupixel/res.

Face worker: Python 3.12, mediapipe 1.0.1, opencv-python-headless 5.0.0.93, numpy 2.5.3, onnxruntime-directml 1.24.4, Pillow 12.3.0, PyInstaller 6.22.3. Install versions available for the target platform and run `python tools/face_worker.py models/face_landmarker.task` to inspect startup. Build with `pyinstaller --distpath build/engine-dist --workpath build/engine-build build-support/FaceEngine.spec`, then copy engine-dist/FaceEngine to app/face_engine_v041. No InsightFace pip build, CUDA or scikit-image required; selected Python runtime sources are in tools/insightface_runtime. DirectML is preferred and CPU fallback is labelled.

Browser: install/activate Emscripten 6.0.10 locally at tools/emsdk, then `python tools/build_gpupixel_web.py`. The script records its compiler, upstream revision, artifact length and SHA256 in edge-extension/gpupixel-build.json. It embeds local WASM/LUTs, without remote code or dynamic JS eval. Manifest CSP includes wasm-unsafe-eval specifically for WebAssembly.

To reproduce extracted DLC functions, run tools/vendor_dlc_core.py against the included upstream revision. Keep the project-authored NumPy similarity_transform.py in tools/insightface_runtime/utils. Model download scripts verify checksums; model licenses are separate from code licenses. Missing models are reported at runtime, not silently substituted.

Tests are in tests/. Fixture URLs/provenance are in THIRD_PARTY.md and validation data. Technical/public fixture media and test browser binaries are excluded from the player archive. Source testing uses work/ and --control-dir to avoid normal user settings. Place the built app/runtime DLLs in app/, the launcher in the project root, and install models with DownloadModels.cmd. The public distribution uses the same compiled player, worker and extension as the verified local 0.4.1 build.

Unused Mars/MNN binary directories are intentionally omitted; the root build disables the GPUPixel face detector. The Python worker requirements are in requirements-face.txt. Model download and verification are separate from application startup.
