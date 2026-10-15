# Third-party components

The local application dynamically loads Qt and libmpv. Unmodified upstream components retain their own licenses; original application source is in src/. No ownership of upstream software or model weights is claimed.

| Component | Version/source | License notes |
| --- | --- | --- |
| Qt qtbase | 6.8.3, https://github.com/qt/qtbase/tree/v6.8.3 | LGPLv3 / GPL / commercial options; bundled license texts and SBOM |
| libmpv | https://github.com/zhongfly/mpv-winbuild/releases/tag/2026-09-21-e76a35ec95 | Asset explicitly named mpv-dev-lgpl-x86_64-20260921-git-e76a35ec95.7z; upstream https://github.com/mpv-player/mpv |
| mpv build recipes | https://github.com/zhongfly/mpv-winbuild and https://github.com/shinchiro/mpv-winbuild-cmake | Transitive codec/library build information is maintained upstream |
| MediaPipe | 1.0.1, https://github.com/google-ai-edge/mediapipe | Apache-2.0 code; bundled notice |
| FaceLandmarker model | https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task | Official MediaPipe model artifact; the public application does not bundle this artifact; its official download URL is provided |
| OpenCV | 5.0.0.93, https://github.com/opencv/opencv | Apache-2.0 and third-party notices in distribution |
| YuNet model | https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet | MIT text included in licenses/YuNet-LICENSE.txt |
| NumPy, Pillow, Matplotlib, Python | Packaged FaceEngine runtime | Bundled upstream license files; some are transitive MediaPipe imports |
| PyInstaller | 6.22.3 | GPL with bootloader exception; upstream license file included |
| Microsoft VC runtime | 14.44.35112 | Microsoft redistributable runtime components |

Tests use the MediaPipe public portrait fixture at https://storage.googleapis.com/mediapipe-assets/portrait.jpg and locally synthesized motion/test tones. This fixture is technical test data, not an Asian aesthetic benchmark. It is excluded from the portable application package. ffmpeg is a test-generation tool and is excluded from the runtime package.

Model hashes and packaged file checksums are recorded in the deliverable manifest. Native application models are installed separately. The Edge extension includes unchanged Framegen weights under their separate personal/non-commercial terms; see below.

## 0.2 additions: model restrictions matter

| Component | Source | Terms |
| --- | --- | --- |
| ONNX Runtime DirectML 1.24.4 | https://github.com/microsoft/onnxruntime | MIT code plus bundled ThirdPartyNotices; DirectML runtime terms apply |
| InsightFace algorithms / INSwapper | https://github.com/deepinsight/insightface | MIT code; **pretrained models are only for non-commercial research** |
| INSwapper 128 fp16 and ArcFace w600k_r50 weights | https://github.com/facefusion/facefusion-assets/releases/tag/models-3.0.0 | Upstream model restrictions retained; this asset mirror does not grant unrestricted model use |
| Browser extension | edge-extension, authored for this project | Manifest V3; no remote script loading; source included |

This is a local evaluation prototype, not an unrestricted commercial face-swap package. InsightFace separates its open-source code license from non-commercial research model terms. The ordinary beauty pipeline does not load these swap models. Review licensing before commercial use or public redistribution; the public package does not redistribute these pretrained model weights.

Swap model hashes:
- inswapper_128_fp16.onnx: c4eccca86ad177586c85c28bf1a64a9d9ed237e283a15818d831f7facfd3f420
- arcface_w600k_r50.onnx: f1f79dc3b0b79a69f94799af1fffebff09fbd78fd96a275fd8f0cbbea23270d1

Source-photo tests used https://raw.githubusercontent.com/nttstar/insightface-resources/master/images/t2.jpg (the official InsightFace resource repository); it is excluded from the runtime package. Public portrait fixtures are technical tests, not aesthetic acceptance data.

## 0.3 GPUPixel integration

GPUPixel 1.3.0, upstream revision `5415b738817553f339620b89ea755bdbfe44e166`, from https://github.com/pixpark/gpupixel . Apache-2.0 text is in licenses/GPUPixel-Apache-2.0.txt; upstream source, assets, and its third-party notices are in third_party/gpupixel. This package uses the actual upstream BeautyFaceFilter / BeautyFaceUnitFilter / BoxBlurFilter / BoxHighPassFilter implementations. It does not include or invoke Mars face-kit binaries.

Local modifications: CMake replaces core/gpupixel_context.cc with src/gpupixel_host_context.cpp to use the current Qt compatibility OpenGL context and rebind the shader/position attribute after host rendering. src/gpupixel_pipeline.cpp feeds the video FBO into the filter and maps controls. UTF-8 path fixes are marked in src/core/gpupixel.cc, src/utils/util.cc, src/source/source_image.cc and src/filter/beauty_face_unit_filter.cc. The build defines STBI_WINDOWS_UTF8. No GPUPixel beauty algorithm was replaced with a project-authored approximation.

MediaPipe VIDEO landmarks, OpenCV optical flow, YuNet recovery and the project-authored geometry/lips/blush shader remain separate components. In 0.4 the browser runs the same actual GPUPixel C++ filters compiled to WebAssembly; only geometry/makeup remain project-authored.

The host maps zero-smoothing plus explicit sharpening to a 1e-6 blurAlpha input because the upstream desktop shader gates sharpening on blurAlpha > 0. This retains the upstream shader and gives no visible smoothing contribution; an independent-sharpening pixel test is included.


## 0.4 Deep-Live-Cam and browser GPUPixel

Deep-Live-Cam upstream https://github.com/hacksider/Deep-Live-Cam , revision `d759e31b11d9432afdfddce698c0f7c9a715e086`. AGPL-3.0 license in licenses/Deep-Live-Cam-AGPL-3.0.txt. Corresponding upstream sources are in third_party/deep-live-cam; selected copied core functions are in tools/dlc_core. The headless integration and modifications are in tools/swap_engine.py, tools/face_worker.py and tools/face_tracking.py. No paid Ultimate edition code is included. The included source covers the modifications used by this local evaluation package; the public source and portable package carry the corresponding source and AGPL-3.0 license.

InsightFace 0.7.3 source distribution is included under third_party/insightface. Selected pure-Python runtime is tools/insightface_runtime; face_align's scikit-image transform import is replaced by the local NumPy implementation. Original algorithms and model terms remain upstream's. Runtime models use INSwapper 128 fp16, ArcFace w600k_r50 and SCRFD det_10g; a downloaded 2d106det artifact is not used as the live tracker.

GPEN-BFR-256 source/model: https://github.com/yangxy/GPEN ; artifact mirrored by the chosen upstream at https://huggingface.co/hacksider/deep-live-cam . Original training-model conditions apply; do not infer unrestricted commercial model rights from an open-source host. New download SHA256 provenance is in models/DLC-SHA256.json. Deep-Live-Cam source explicitly separates pretrained model permissions. The public package excludes model weights and supplies opt-in upstream download instructions.

WebAssembly is built with Emscripten 6.0.10 (MIT/University of Illinois Open Source licenses, https://github.com/emscripten-core/emscripten/blob/6.0.10/LICENSE). Actual GPUPixel code/LUTs are compiled and embedded locally. New adapters are src/web/gpupixel_web_context.cpp and gpupixel_web.cpp. Browser build metadata is edge-extension/gpupixel-build.json. Emscripten SDK is excluded from the player ZIP.

Real head-pose test clips: https://github.com/intel-iot-devkit/sample-videos , head-pose-face-detection-female.mp4 and head-pose-face-detection-female-and-male.mp4, CC BY 4.0. Derived comparison clips label AI FACE SWAP and identify original/processed panels; they are technical demonstrations, not real footage of the source identity. Original fixture media are excluded from the application archive. The test source face is the public InsightFace resource noted above; source images are not bundled with the runtime.

## Public release layout

Project-authored and integrated source is distributed under AGPL-3.0. Individual upstream files retain their own notices. The public snapshot omits unused Mars face-kit/MNN binaries; GPUPIXEL_ENABLE_FACE_DETECTOR=OFF remains required. Native face-tracking and face-swap weights are not bundled. Framegen browser weights are the explicitly documented exception. Small ONNX Runtime example models are omitted from the public runtime as well. No photos, playback history, browser profiles or local credentials are included.

## 0.6.0 additional real validation fixtures

Intel IoT DevKit sample-videos, https://github.com/intel-iot-devkit/sample-videos , CC BY 4.0. Additional files are driver-action-recognition.mp4 (1920x1080, 30 fps; car cabin, hand/phone occlusion and real edits) and face-demographics-walking.mp4 (768x432, 12 fps; entry/exit). URLs, sizes and SHA256 values are recorded in validation/real-fixture-sources.json. These original files and captured original/processed comparison frames are local test material, not bundled runtime assets. The player adds no interpolation to this native validation footage. Visual quality is not established by counters alone. No new model was downloaded for 0.6.0.

## 0.5.0 browser frame interpolation

Framegen 1.4.0, https://github.com/MONZikWasTaken/Framegen , commit `7440e8f432818836639e3177d7764e8ed892f3c7`. Runtime code is MIT. ES module export keywords are removed and the unchanged runtime body is wrapped in an isolated-world global for MV3 script injection. `rt_v7s.bin` and its manifest are bundled unchanged. Weights are licensed for personal and non-commercial research use only, with unchanged redistribution permitted when the notice is retained. Code license, model notice and SHA256 provenance are in `edge-extension/vendor/framegen/`.

The new scheduler, scene-change guard, resource lifecycle, fallback and presentation integration are project code in `edge-extension/interpolation.js` and `content.js`. Model inference runs on local WebGPU; there is no cloud inference or CDN fetch during use.
