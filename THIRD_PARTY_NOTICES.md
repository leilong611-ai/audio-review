# 第三方代码与署名 / Third-party notices

`native/NativeArchiveSpeech.swift` 的 `SpeechFileReader` 改编自 [rokrokss/recly](https://github.com/rokrokss/recly) 中的 `AppleSpeechTranscriber.swift`。原作版权归 Hyungrok Kim。上游文件 [Git blob a998ea6](https://api.github.com/repos/rokrokss/recly/git/blobs/a998ea6af91a6cc463cd5f19e183214cb6ed9235)。2026-11-20 的改编调整了文件读取与时间戳输出，用于按段回听。本候选附有 [GNU AGPL 许可原文](LICENSE)。上游的许可补充与品牌使用见 [上游许可说明](https://github.com/rokrokss/recly/blob/main/LICENSE-EXCEPTIONS.md) 和 [上游商标政策](https://github.com/rokrokss/recly/blob/main/TRADEMARK.md)。

转写调用 macOS 的 Apple Speech 框架。演示脚本可用 macOS 系统语音生成个人本机测试音频。仓库提供虚构文稿和脚本。系统语音的使用范围见 [Apple 软件许可](https://www.apple.com/legal/sla/)。

The `SpeechFileReader` in `native/NativeArchiveSpeech.swift` is adapted from `rokrokss/recly`, copyright Hyungrok Kim. The linked Git blob identifies the source. The adaptation dated 2026-11-20 changes audio reading and timestamp output to support segment playback. The project uses Apple Speech on macOS.
