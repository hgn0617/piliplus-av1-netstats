# 第三方来源与许可

- **PiliPlus**：GPLv3；本仓库记录的原版发行基线为 [2.1.6.2](https://github.com/bggRGjQaUbCoE/PiliPlus/releases/tag/2.1.6.2)。本仓库没有收录整份 App。
- **FFmpeg 7.0.2**：AV1 VideoToolbox 回移补丁来自 [官方提交 f9c5c535](https://github.com/FFmpeg/FFmpeg/commit/f9c5c5358cfef3847674c6f3b3ded9611ebc5647)，新增文件中的原作者和 LGPL 许可声明保留。源代码：<https://ffmpeg.org/releases/ffmpeg-7.0.2.tar.xz>。本次配置启用了 `--enable-version3`，同时收录 LGPL 2.1 与 LGPL 3.0 文本。
- **mpv 0.39 API 头文件**：`ios-network-overlay/client.h` 来自 [mpv v0.39.0/libmpv/client.h](https://github.com/mpv-player/mpv/blob/v0.39.0/libmpv/client.h)，原 LGPL 2.1-or-later 声明保留。
- **dav1d 1.2.1 头文件**：保留 VideoLAN/dav1d 作者版权及 BSD-2-Clause 声明，仅用于匹配原包 ABI 编译 Avcodec。
- **IINA / mpv / FFmpeg 等 Mac 运行库**：从 [IINA 1.5.0 官方发行包](https://github.com/iina/iina/releases/tag/v1.5.0) 提取，相关许可和源码以各自上游为准；仓库保存提取与修正路径的脚本。
- **AV1 测试样本**：来自 FFmpeg FATE 的公开测试样本 `seq_hdr_op_param_info.ivf`，用于组件解码检查，来源 <https://fate-suite.ffmpeg.org/av1/seq_hdr_op_param_info.ivf>。

第三方代码的原有许可不因本仓库根目录的许可而改变。构建的 App/IPA 仍包含各上游组件，分发时应随附对应许可及所需的源代码信息。
