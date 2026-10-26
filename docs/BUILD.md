# 构建与维护

需要 macOS、Python 3、Apple 编译工具、`pkg-config`，以及合法取得的原版 PiliPlus App/IPA。渲染检查另需 Pillow。iOS 构建使用支持 AV1 VideoToolbox 声明的 iPhoneOS SDK；优先使用自己的 Xcode SDK。已有构建实际使用 SDK 18.5。

## Mac AV1 修复

取得 PiliPlus 官方 Mac App 和 IINA 1.5.0 App，在仓库根目录执行：

```sh
python3 tools/patch_player.py --source /path/to/PiliPlus.app --iina /path/to/IINA.app --output /path/to/PiliPlus-AV1.app
python3 tools/probe_player.py /path/to/PiliPlus-AV1.app --file verification/av1-sample.ivf
```

脚本保留原 entitlements、核对 API、复制依赖、修正 install name 并重新签名输出副本。输出路径必须尚不存在。

## Mac 网速显示

先准备上述已经完成 AV1 修复的 App 副本：

```sh
python3 mac-network-overlay/prepare_overlay.py --source /path/to/PiliPlus-AV1.app
python3 mac-network-overlay/rebuild_overlay.py
python3 mac-network-overlay/verify_overlay.py
```

输出位于 `mac-network-overlay/PiliPlus AV1.app`，不会自动安装。修改样式可编辑 `network_overlay.lua` 后重新运行 rebuild；原生菜单位于 `mpv_overlay_bridge.m`。

## iOS AV1 v2

把官方 IPA 放到 `ios-check/PiliPlus_ios_2.1.6+5472.ipa`。准备脚本会校验固定 SHA-256，提取原框架、下载 FFmpeg 7.0.2、应用回移补丁并生成本机配置。

```sh
python3 ios-build-v2/prepare_codec.py --sdk "$(xcrun --sdk iphoneos --show-sdk-path)"
python3 ios-build-v2/run_compile.py
python3 ios-build-v2/link_codec.py
python3 ios-build-v2/build_ipa.py
```

没有完整 Xcode 时，`--sdk` 可以指定自己已有的 iPhoneOS SDK。仓库不分发 Apple SDK。输出 `ios-build-v2/PiliPlus_iOS_2.1.6+5472_AV1-v2.ipa`。打包脚本拒绝覆盖已有 staging，维护者应保留前次记录并使用新的工作目录。

修改 FFmpeg 补丁时应使用干净的 7.0.2 源码重新应用，不要对同一目录重复打补丁。链接保留原框架 359 个导出/转发符号，并与原 Avutil、Swresample、Dav1d 连接。

## iOS 完整 AV1、CDN 测速与网速包

当前 iOS 包需要从 `.local-build/PiliPlus` 的 Flutter 源码重编译，才能包含 CDN 测速并发改动。Mac 上需要 CocoaPods；Flutter SDK 放在 `.local-build/flutter`。

```sh
PATH="$PWD/.local-build/flutter/bin:$PATH" \
  flutter build ios --release --no-codesign --build-name=2.1.6 --build-number=5472
python3 ios-network-overlay/build_from_flutter.py \
  --runner-app .local-build/PiliPlus/build/ios/iphoneos/Runner.app \
  --stage-name staging-flutter-2026 \
  --output-name 'PiliPlus_iOS_2.1.6+5472.ipa'
```

这个入口同时保留 Flutter 源码里的 CDN 测速设置：每项最多 5 MB 或 5 秒，默认 4 项并发，可切换 1、4、8 或全部并发；应用显示名为 `PiliPlus`。构建脚本再叠加已验证的 AV1 VideoToolbox `Avcodec.framework` 和播放器角落网速显示。

`build_from_flutter.py` 从 `.local-build/PiliPlus/build/ios/iphoneos/Runner.app` 开始，生成新的 `MpvCore.framework`、桥接 `Mpv.framework`、Settings.bundle，并对未签名的 Flutter 产物做临时 ad-hoc 签名。实际安装时仍需用自己的 iLoader/Sideloadly 账号签名。

## 旧版 iOS 网速包

先提供上述 v2 IPA 及 iOS SDK。执行：

```sh
python3 ios-network-overlay/build_ipa.py --stage-name staging-buf --output-name 'PiliPlus_iOS_2.1.6+5472.ipa' --base-sha256 <已验证的 AV1 v2 IPA SHA-256>
```

当前脚本固定校验本次成功 v2 IPA 的 SHA-256，因此别的工具链重建 v2 后，需要**先核对 ABI 和播放结果，再显式更新基线哈希**。这项校验不应为了通过打包而盲目跳过。

桥接通过 `Mpv.framework` 转发原 API；原库单独放入 `MpvCore.framework`，便于签名工具识别。显示数据取自 `cache-speed` 和 `demuxer-cache-duration`；文字通过原版 `osd-overlay` 绘制。设置描述位于打包脚本生成的 Settings.bundle 中。

可用同一原生源码做 Mac 组件测试：

```sh
python3 ios-network-overlay/prepare_host_test.py --source-app /path/to/PiliPlus-AV1.app
python3 ios-network-overlay/verify_host_overlay.py
```

这个旧入口只适合没有 Flutter 构建环境时保留官方主程序的版本；它不包含 iOS CDN 并发测速修改。生成 IPA 后使用自己的 Sideloadly 配置签名安装。应签名 `Mpv` 与 `MpvCore` 两个 framework，并检查普通 AVC/HEVC 视频音画、AV1 的实际 `hwdec`、旋转/全屏、字号和开关。主机测试不等于真机验证。

包内 `UIDeviceFamily` 为 `[1, 2]`，同时声明 iPhone 和 iPad；iPad 可以使用同一 IPA，但需要用自己的证书重新签名和安装，当前构建记录没有替用户完成真机安装。
