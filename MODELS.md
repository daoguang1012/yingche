# 模型安装

公开 ZIP 不附带桌面人脸模型。运行 `DownloadModels.cmd` 主动选择下载：

- 1：MediaPipe FaceLandmarker + YuNet，人脸追踪、脸型/妆容定位，约 4 MB。
- 2：上述模型加 INSwapper、ArcFace、SCRFD、GPEN，合计约 549 MB。

下载来自清单内上游或其公开模型镜像，仅在本机写入 models 文件夹。每个文件核对长度及 SHA256，通过后才替换目标文件。已完整的文件跳过；失败后可重新运行。下载完成后重新打开播放器。

离线安装也可将 `model-manifest.json` 列出的文件放入 models，再运行 `powershell -NoProfile -File scripts/download_models.ps1 -Group All -CheckOnly` 检查。

InsightFace 模型限非商业研究，代码的 MIT 许可不涵盖权重；GPEN 遵守上游模型条件。见 [InsightFace](https://github.com/deepinsight/insightface#license)、[GPEN](https://github.com/yangxy/GPEN) 和每个清单项的 terms 链接。主程序的 AGPL 许可不会扩大模型权限。

映澈 0.6.0 不使用 2d106det.onnx 和单独的 inswapper_projection.npy，无需下载它们。

Edge 补帧单独附带约 2.9 MB 的 Framegen 权重，保留原始文件和许可告知，仅限个人使用及非商业研究，可按原条款原样再分发；不是 AGPL 许可模型。补帧默认关闭，无需另行下载。见 `edge-extension/vendor/framegen/WEIGHTS_LICENSE.md`。
