# Audio Review｜本地录音工作台

A small macOS workbench for transcribing audio, jumping to any transcript segment, and saving corrections while keeping the original audio and machine transcript.

[Download source ZIP](https://github.com/leilong611-ai/audio-review/archive/refs/heads/main.zip) · [简体中文使用说明](README.zh-CN.md)

## Try it on macOS

Download the source ZIP above and extract it before opening Terminal.

The current candidate has been tested on macOS 27.2.1. First-run reports on macOS 26 are especially welcome.

1. Use macOS 26+, Python 3.9+, an Xcode toolchain with the macOS 26 SDK or later, and installed Simplified Chinese Apple Speech assets. The current interface and transcription are in Simplified Chinese.
2. In Terminal, enter the extracted folder and run `/bin/zsh ./Start.command --check`. The first check compiles the speech helper. When it reports readiness, start the workbench with `/bin/zsh ./Start.command --data-dir ~/workbench-demo` to keep trial recordings in a separate library.
3. In a second terminal, enter the same folder and run `/bin/zsh ./samples/make-demo.command` to generate a fictional demo WAV for personal local testing. The script uses the Tingting system voice. Open the local address printed in the launch terminal. The system selects a port when the workbench starts. Import the WAV printed by the demo command, or use audio you have permission to process.
4. Click **本机转写** to transcribe. Click a timestamp to play that section. Use **开始校对** and **保存校对** to edit and save. Reload to check the saved revision. Stop the workbench with Ctrl+C in the launch terminal.

## Where your data stays

The workbench listens only on the local loopback address. The default library is `~/Library/Application Support/Local Audio Workbench/Recordings`. With `--data-dir`, the selected library holds the audio, filenames, machine transcripts and saved corrections. Use the same option when restarting to reopen that library. Other software on the same Mac can potentially access the running workbench. Use synthetic audio on shared Macs and in public reports.

## Help improve it

A useful first contribution can be an installation report, a repeatable test for playback or correction, or clearer instructions for a missing speech asset. [Open an issue](https://github.com/leilong611-ai/audio-review/issues/new/choose) with your OS and browser versions, the steps, and the result. Pull requests are welcome in English and Chinese.

[Contributing guide](CONTRIBUTING.md) · [Architecture and data flow](docs/architecture.md)

## License

Audio Review is licensed under the GNU Affero General Public License, version 3 or any later version (AGPL-3.0-or-later).

[Full license](LICENSE) · [Third-party notices and modification details](THIRD_PARTY_NOTICES.md)
