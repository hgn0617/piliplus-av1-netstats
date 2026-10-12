# PiliPlus AV1 与网速显示补丁

维护 PiliPlus macOS / iOS 的本地 AV1 VideoToolbox 修复、实时下载速度与缓冲显示，以及构建和验证记录。**这是非官方补丁仓库**，基线是 PiliPlus Release `2.1.6.2` 的 `2.1.6+5472` 发行包。

上游：[PiliPlus](https://github.com/bggRGjQaUbCoE/PiliPlus)。已有 macOS 问题报告：[PiliPlus #3252](https://github.com/bggRGjQaUbCoE/PiliPlus/issues/3252)。 本次 iOS 硬解与实时网速功能反馈：[PiliPlus #3260](https://github.com/bggRGjQaUbCoE/PiliPlus/issues/3260)。

## 当前状态

| 组件 | 实现 | 验证范围 |
| --- | --- | --- |
| macOS AV1 | 独立 App 副本采用 IINA 1.5.0 的 mpv 0.41 / FFmpeg 9.0.1 及其依赖 | M4 Mac 实际 8K AV1 播放信息显示 VideoToolbox；本地解码测试通过 |
| iOS AV1 v2 | 向 FFmpeg 7.0.2 回移 AV1 VideoToolbox 支持，仅替换 Avcodec.framework | 用户反馈修改包可正常播放；相同补丁在 Mac 解出 64 帧、均为硬件帧。未保存 iPhone 修复后的 hwdec 截图或功耗测量 |
| Mac 网速显示 | libmpv 初始化桥接 + Lua ASS 叠加层 | 实际 App 显示、开关、字号已检查；四角位置、HTTP 读取速度等组件测试通过 |
| iOS 网速显示 | 原版 mpv API 桥接，直接使用 osd-overlay，无需 Lua | 用户反馈手机能看到显示，但中文“缓冲”变成方框；最新补丁使用 ASCII `Buf`，Mac 组件渲染测试通过，最新 Buf 包的 iPhone 效果待确认 |

网速来自当前主媒体流的实际 I/O 读取速度，单位为 B/s、KB/s、MB/s；缓冲秒数由播放器估算。缓存达到目标时显示 0 B/s 属于正常情况，不表示视频必然会卡顿。该功能不直接改变 CDN 或网络线路。

## 使用方式

- Mac：应用菜单 **PiliPlus AV1 → 显示网速与缓冲**；快捷键 **Shift + Command + N**。同一菜单可以调四档字号和四角位置。
- iPhone：系统 **设置 → 应用 → PiliPlus AV1 网速**，可以调开关、字号、位置。IPA 需使用自己的 Sideloadly 配置签名安装。
- 显示采用紧凑纯文字和细描边，没有灰色背景。iOS 使用 `Buf 12.3s`。

## 仓库目录

```text
tools/                 macOS AV1 库替换与能力探测
mac-network-overlay/   Mac 原生桥接、Lua 样式、打包和渲染检查
ios-build-v2/          FFmpeg 7.0.2 AV1 VT 回移补丁、ABI 导出清单、构建模板
ios-network-overlay/   iOS 原生网速桥接、IPA 打包与主机组件检查
verification/          样本与验证摘要
docs/                  构建、版本记录、上游反馈
licenses/              第三方许可文本
```

构建入口见 [docs/BUILD.md](docs/BUILD.md)，验证边界见 [docs/VALIDATION.md](docs/VALIDATION.md)，版本和安装包校验值见 [docs/VERSIONS.md](docs/VERSIONS.md)。构建所需的原版 App/IPA、IINA 和 iOS SDK 由维护者自行取得；源码库不会自动替换 `/Applications` 中的 App，也不会替用户完成设备签名。

## 维护与更新

官方更新可能覆盖本地库修改。升级基线时，重新检查 libmpv API、FFmpeg ABI、动态库路径、原有文件哈希，以及 AVC/HEVC/AV1 的基础播放和音画输出，再生成新包。不能直接把旧桥接库套到任意新版发行包。

欢迎提供具体版本、编码、`hwdec`、视频分辨率/帧率与可复现现象。报告里请避免包含账号 cookie、带鉴权参数的完整视频 URL 和设备签名材料。

## 许可

本仓库原创维护代码采用 GPL-3.0-or-later，与 PiliPlus 的 GPLv3 许可衔接。FFmpeg 派生补丁与 mpv API 头文件保留各自上游许可；dav1d 头文件保留 BSD 许可。详见 [LICENSE](LICENSE) 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
