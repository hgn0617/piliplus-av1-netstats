# PiliPlus AV1 与网速显示补丁

维护 PiliPlus macOS / iOS 的本地 AV1 VideoToolbox 修复、实时下载速度与缓冲显示，以及构建和验证记录。**这是非官方补丁仓库**，基线是 PiliPlus Release `2.1.6.2` 的 `2.1.6+5472` 发行包。

上游：[PiliPlus](https://github.com/bggRGjQaUbCoE/PiliPlus)。已有 macOS 问题报告：[PiliPlus #3252](https://github.com/bggRGjQaUbCoE/PiliPlus/issues/3252)。 本次 iOS 硬解与实时网速功能反馈：[PiliPlus #3260](https://github.com/bggRGjQaUbCoE/PiliPlus/issues/3260)。

## 当前状态

| 组件 | 实现 | 验证范围 |
| --- | --- | --- |
| macOS AV1 | 独立 App 副本采用 IINA 1.5.0 的 mpv 0.41 / FFmpeg 9.0.1 及其依赖 | M4 Mac 实际 8K AV1 播放信息显示 VideoToolbox；本地解码测试通过 |
| iOS AV1 与 CDN 测速 | 从 Flutter 源码重编译 iOS 主程序，加入 5 MB / 5 秒 CDN 测速、1/4/8/全部并发，再叠加 AV1 VideoToolbox 和播放网速显示 | iPhone 已通过 iLoader 安装验证；CDN 测速单元测试通过；播放和真机 AV1 hwdec 仍需实际检查 |
| Mac 网速显示 | libmpv 初始化桥接 + Lua ASS 叠加层 | 实际 App 显示、开关、字号已检查；四角位置、HTTP 读取速度等组件测试通过 |
| iOS 网速显示 | 原版 mpv API 桥接，直接使用 osd-overlay，无需 Lua | 已随完整 Flutter 重编译包安装到 iPhone；设置项位于“设置 → 应用 → PiliPlus” |

网速来自当前主媒体流的实际 I/O 读取速度，单位为 B/s、KB/s、MB/s；缓冲秒数由播放器估算。缓存达到目标时显示 0 B/s 属于正常情况，不表示视频必然会卡顿。该功能不直接改变 CDN 或网络线路。

## 使用方式

- Mac：应用菜单 **PiliPlus AV1 → 显示网速与缓冲**；快捷键 **Shift + Command + N**。同一菜单可以调四档字号和四角位置。
- iPhone：系统 **设置 → 应用 → PiliPlus**，可以调开关、字号、位置。IPA 需使用自己的 iLoader/Sideloadly 配置签名安装。
- iPad：IPA 声明同时支持 iPhone/iPad（`UIDeviceFamily = [1, 2]`），可用同样的签名方式安装；当前没有把包直接安装到 iPad。
- 显示采用紧凑纯文字和细描边，没有灰色背景。iOS 使用 `Buf 12.3s`。

## 仓库目录

```text
tools/                 macOS AV1 库替换与能力探测
mac-network-overlay/   Mac 原生桥接、Lua 样式、打包和渲染检查
mac-cdn-speed/         Mac CDN 测速 5 MB / 5 秒、并发与实时进度补丁
ios-build-v2/          FFmpeg 7.0.2 AV1 VT 回移补丁、ABI 导出清单、构建模板
ios-network-overlay/   iOS 原生网速桥接、IPA 打包与主机组件检查
verification/          样本与验证摘要
docs/                  构建、版本记录、上游反馈
licenses/              第三方许可文本
```

构建入口见 [docs/BUILD.md](docs/BUILD.md)，验证边界见 [docs/VALIDATION.md](docs/VALIDATION.md)，版本和安装包校验值见 [docs/VERSIONS.md](docs/VERSIONS.md)。构建所需的原版 App/IPA、IINA 和 iOS SDK 由维护者自行取得；源码库不会自动替换 `/Applications` 中的 App，也不会替用户完成设备签名。

## 维护与更新

2026-10-22 增加 [Mac CDN 测速改进](mac-cdn-speed/README.md)：每项最多 5 MB 或 5 秒，默认 4 项并发，可选全部并发；实时显示测速进度，到时显示已下载数据的平均速度。该逻辑已同步到 iOS 源码构建。

官方更新可能覆盖本地库修改。升级基线时，重新检查 libmpv API、FFmpeg ABI、动态库路径、原有文件哈希，以及 AVC/HEVC/AV1 的基础播放和音画输出，再生成新包。不能直接把旧桥接库套到任意新版发行包。

欢迎提供具体版本、编码、`hwdec`、视频分辨率/帧率与可复现现象。报告里请避免包含账号 cookie、带鉴权参数的完整视频 URL 和设备签名材料。

## 许可

本仓库原创维护代码采用 GPL-3.0-or-later，与 PiliPlus 的 GPLv3 许可衔接。FFmpeg 派生补丁与 mpv API 头文件保留各自上游许可；dav1d 头文件保留 BSD 许可。详见 [LICENSE](LICENSE) 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
