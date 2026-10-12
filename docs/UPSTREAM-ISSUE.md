# iOS AV1 硬解修复补丁与实时网速/缓冲监控功能建议

感谢维护 PiliPlus。我把本次在 Mac 和 iPhone 上做的本地修改整理到了非官方维护仓库：

https://github.com/hgn0617/piliplus-av1-netstats

这里有两个相关反馈：iOS AV1 硬解，以及播放时的实时网速显示。已有 macOS AV1 反馈见 #3252；iOS 历史讨论见 #3125，其中评论也提到 AV1 不能硬解。下面补充发行包检查、具体补丁和功能需求。

## 一、iOS：开启硬解后，AV1 仍显示 hwdec: no

环境：iPhone 17，iOS 27（本机报告的版本，未记录完整系统 build）；PiliPlus 官方 IPA `2.1.6+5472`，Release 标签 `2.1.6.2`。

复现：开启硬解、选择 `videotoolbox`，使用 AV1 视频，重新打开播放器，在播放信息中仍看到 `codec: av1`、`hwdec: no`，并有明显卡顿。设置里选中了硬解，和实际已经启用硬解，是两件需要分别检查的事。

检查这份官方 IPA：内置 mpv 为 0.39.0，Avcodec ABI 为 `61.3.100`（FFmpeg 7.0.2）；原编译配置包含 H.264/HEVC 等 VideoToolbox 硬件加速，但没有 AV1 VideoToolbox 硬件加速。这是对这份发行包的检查，不据此断言所有新版或所有设备都有同样问题。

### 本地修复

采用 FFmpeg 官方 AV1 VideoToolbox 提交：

https://github.com/FFmpeg/FFmpeg/commit/f9c5c5358cfef3847674c6f3b3ded9611ebc5647

向 FFmpeg 7.0.2 回移补丁，仅重新编译并替换 `Avcodec.framework`，保持 `61.3.100` ABI 和原有 359 个导出/转发接口，沿用原版 dav1d 1.2.1 头文件。mpv、Avformat、Avutil、TLS 和 Flutter 播放组件继续使用原发行包的版本。

完整回移补丁：

https://github.com/hgn0617/piliplus-av1-netstats/blob/main/ios-build-v2/ffmpeg-7.0.2-av1-vt-backport.patch

这个最小替换版在我的 iPhone 上已经能正常播放。此前试过全量替换 mpv 和依赖的包，会出现普通视频也一直转圈、没有音画，所以最终保留了原有播放器，仅回移 Avcodec 的 AV1 VT 支持。

验证边界：相同补丁的 Mac 组件测试解出 64 帧且全部为 VideoToolbox 硬件帧，禁止软件回退；iPhone 上的反馈是修改包可正常播放，没有保存修复后的 `hwdec` 截图，也没有做手机功耗、HDR/色彩或所有分辨率的回归测量。这些仍需正式集成时验证。

建议检查 iOS 原生库的 AV1 VT 构建选项，并在正式发布测试中验证“启用硬解设置”和实际 `hwdec` 状态一致。Mac 上此前 CPU 温度约 95°C、逼近 100°C 的现象属于 #3252 的 Mac 测试，不能套用为手机温度测量。

## 二、功能请求：显示正在播放的视频的实时网速与缓冲秒数

我在香港使用时经常遇到 B 站播放卡顿，希望能在播放画面的角落显示：

```text
1.25 MB/s  Buf 12.3s
```

需要的是当前视频媒体流的真实下载/读取速度和剩余缓冲时间，方便判断卡顿发生时缓存是否快用完。已有 CDN 测速（包括 #3055 对测速进度的改进）有价值，但它采样的是测速请求；这里希望显示实际播放中的媒体流数据。

希望支持：

- 可开启/关闭，默认行为由项目决定。
- 四个角的位置可选，字号可调，设置保存。
- 紧凑纯文字、无大背景块，文字可有细描边，尽量避开字幕和控制区。
- 每约 0.5–1 秒更新，随播放器生命周期启动/清理，不额外发测速请求。
- 缓存满而暂停下载时允许显示 0；缓冲字段不可用时显示 `--`，避免误导用户。

### 已做的可行性验证

mpv 提供 `cache-speed`（等同主 demuxer 的 `raw-input-rate`，B/s）和 `demuxer-cache-duration`。后者是近似值，可能不可用；前者不代表整台设备的总网速，也未必包含独立外部音轨。UI 文案应说明这些边界。

我在 Mac 上用 Lua/ASS 叠加层实现并检查了实际 App 画面；iOS 用原版 mpv 的 `osd-overlay` 接口实现，保留已能播放的 v2 解码库。手机能看到显示，但 iOS 内置字体没有显示中文“缓冲”，于是本地修订用 ASCII `Buf`。最新 Buf 包的手机效果尚待确认。

原生实现源码和验证记录：

https://github.com/hgn0617/piliplus-av1-netstats/tree/main/ios-network-overlay

正式功能如果直接放在 Flutter 播放界面中，字体、布局、无障碍和设置入口应该能更自然地融入现有播放器。本地桥接方案主要用于验证底层数据和显示的可行性，供维护者参考。

感谢！如果需要继续拆分跟踪这两个问题，可以按项目的维护习惯分别处理。
