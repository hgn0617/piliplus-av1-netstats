# Mac CDN 测速：5 MB / 5 秒与可选并发

2026-10-22，基于 PiliPlus `2.1.6+5472` / tag `2.1.6.2`，只重建 `App.framework`；沿用已修复 AV1 和播放网速显示的所有原生库。

- 每项最多接收 **5,000,000 字节（十进制 5 MB）**，或运行 **5 秒**，以先到者为准。快速线路可能不到 5 秒就结束。
- 独立计时器从发起连接开始运行；没有首包、收到数据后停传，也会按时结束。超时时用已接收字节 / 已经过时间显示平均 MB/s。
- 测试中每 250 ms 更新速度；显示等待、连接、测试中和最终速度。短文件正常结束也给出结果，HTTP 403 等单独显示错误。
- 默认 4 项并发；弹窗右上角可以选择 1、4、8、全部 21 项，并保存选择。切换时取消旧测试，关闭弹窗时取消活动请求和排队任务。
- 并发测量会共享本机及跨境出口带宽，结果不等于每条线路独占带宽时的峰值。5 秒也是短样本，不保证长期稳定速度。

## 重建

准备上游 `2.1.6.2` 源码和 Flutter `3.47.7` SDK（使用独立 SDK 与包缓存，避免影响其他项目），然后：

```sh
python3 mac-cdn-speed/rebuild_flutter.py --source /path/to/PiliPlus --flutter-sdk /path/to/flutter
python3 mac-cdn-speed/build_bundle.py --source-app '/path/to/PiliPlus AV1.app' --flutter-output /path/to/PiliPlus/build/cdn-release --output '/path/to/new/PiliPlus AV1.app'
```

`rebuild_flutter.py` 应用本目录补丁、上游要求的 22 个 Flutter 与 8 个 material_ui 补丁，使用锁定依赖、检查并测试，再构建 arm64/x86_64 通用框架。不会修改 Git 全局身份。

`build_bundle.py` 校验 Flutter 引擎完全一致、原生资源映射一致、所有其他库字节一致、Runner 两种架构的执行代码一致及完整签名。Runner 签名数据随 App 资源重新签名而更新。输出必须是尚不存在的路径。

## 验证记录

- `regression-verification.json`：本地 HTTP 服务验证 5 MB 截止、5 秒慢速/停传/无响应、短响应、403、取消及 1/4/8/21 项并发。
- `bundle-verification.json`：最终应用框架与其余库的完整性记录。
- `av1-regression.json`：安装应用中的 libmpv 仍使用 VideoToolbox 硬件解码 AV1 样本。
- 实际 App 验证了 4 项/全部并发、实时/最终读数、菜单、关闭及设置保存。真实 CDN 的短时间测速仅验证功能，不作为线路长期性能结论。

旧 App 保留在本目录 `backup/PiliPlus AV1.app`。应用副本、旧版备份和 SDK 不提交 Git。
