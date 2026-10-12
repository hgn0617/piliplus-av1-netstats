# 本地构建版本

基线：PiliPlus `2.1.6+5472`，上游 Release 标签 `2.1.6.2`。

| 版本 | 变化 | SHA-256 |
| --- | --- | --- |
| iOS AV1 v2 | 仅回移 FFmpeg AV1 VT 并替换 Avcodec；用户已反馈可播放 | `18e50f71cfe0c43adcaf1f4f3bd4e411ae8d1d0e653a63d6ccf43d01a82d95d3` |
| iOS NetSpeed | 增加原生网速/缓冲叠加层及系统设置入口 | `1da63f1bef93a66bce35d771087aac57461a9320f7374b07f157bfeeae181292` |
| iOS NetSpeed Buf | 将视频内的中文标签改成 ASCII `Buf`，调整文字宽度计算 | `2757bc8b46dc7ad49930ff975dbeb636f65dcacb4b3d7e16847f341505ea6fb0` |

上述为已有本地构建的哈希。重新签名、重新压缩或在不同工具链下重建会改变最终 IPA 哈希；构建脚本会输出当前包的检查记录。

Mac 的库替换和网速显示维护在对应目录，当前样式为无背景、紧凑间距、细描边，并可保存字号与位置偏好。
