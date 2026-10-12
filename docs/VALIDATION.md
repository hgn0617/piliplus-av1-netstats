# 验证范围

记录时间：2026-10-12。

## macOS

Apple M4 / macOS 15.5 上，官方发行包的 AV1 播放曾显示 `libdav1d`、`hwdec: no`，CPU 温度约 95°C。升级独立 App 副本的播放器库后，实际 8K AV1 播放显示 `hwdec: videotoolbox`，画面能够渲染。没有采集修复前后的功耗瓦数、色彩或长期性能对比。

网速显示经过实际 App 画面检查。受控 HTTP 测试验证了真实读取速度、播放进度、缓冲字段、开关、四档字号和四个角的位置；AV1 使用 `videotoolbox-copy`。后续去除背景、缩短间距后再次检查实际 App 画面。

## iOS

设备与系统由用户报告为 iPhone 17 / iOS 27，未记录完整系统 build。

第一版全量替换播放器库的 IPA 曾出现普通视频也一直转圈、音画都没有的反馈。该方案没有作为成功修复收录。AV1 v2 仅替换 Avcodec，用户明确反馈“成功了，很好”。

v2 的 FFmpeg ABI 为 61.3.100，保留原有 359 个导出/转发符号。相同回移补丁的 Mac 组件测试解出 64 帧且全部为 VideoToolbox 硬件帧，软件回退被禁止。**这不是 iPhone 进程内硬解测量**，也不证明手机端所有分辨率、HDR 或功耗表现。

iOS 网速包保留 v2 解码库逐字节一致、原 mpv 与 Runner 的执行代码一致，并检查 IPA 完整性与签名结构。原生桥接源码在 Mac 上进行了真实 HTTP 播放与渲染测试；这不能代替 iPhone 真机测试。

用户后续报告 iPhone 可以看到网速叠加层，但中文“缓冲”显示方框。最新修订使用英文 `Buf`；其组件显示效果已检查，最新 IPA 在 iPhone 上的效果尚待用户确认。

## 检查记录

- `verification/result.json`：Mac 实际解码与 App 播放摘要。
- `mac-network-overlay/verification.json`：Lua/OSD 组件测试。
- `ios-build-v2/build-record.json`：AV1 v2 构建及用户反馈。
- `ios-build-v2/host-av1-vt-result.json`：64 帧硬件解码组件结果。
- `ios-network-overlay/build-record.json`：最新 Buf IPA 的构建检查。
- `ios-network-overlay/verification.json`：原生 OSD 主机组件测试。
