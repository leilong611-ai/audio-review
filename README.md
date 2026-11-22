# Local Audio Workbench

A small macOS workbench for transcribing audio, jumping to any transcript segment, and saving corrections while keeping the original audio and machine transcript.

[简体中文使用说明](README.zh-CN.md)

## Try it

The current candidate has been tested on macOS 27.2.1. First-run reports on macOS 26 are especially welcome.

1. Use macOS 26+, Python 3.9+, an Xcode toolchain with the macOS 26 SDK or later, and installed Simplified Chinese Apple Speech assets. The current interface and transcription are in Simplified Chinese.
2. Unpack the source. In a terminal, enter the extracted folder and run `/bin/zsh ./Start.command --check`. The first run compiles the speech helper. Once it reports readiness, run `/bin/zsh ./Start.command`.
3. In a second terminal, enter the same folder and run `/bin/zsh ./samples/make-demo.command` to generate a fictional demo WAV for personal local testing. Open the local address printed in the launch terminal. The system selects a port when the workbench starts. Import the WAV printed by the demo command, or use audio you have permission to process.
4. Click **本机转写** to transcribe. Click a timestamp to play that section. Use **开始校对** and **保存校对** to edit and save. Reload to check the saved revision. Stop the workbench with Ctrl+C in the launch terminal.

## Where your data stays

The workbench listens only on the local loopback address. It creates a private recording directory at `~/Library/Application Support/Local Audio Workbench/Recordings`. Audio, filenames and transcripts stay in that directory. Other software on the same Mac can potentially access the running workbench. Use synthetic audio on shared Macs and in public reports.

## Help improve it

A useful first contribution can be an installation report, a repeatable test for playback or correction, or clearer instructions for a missing speech asset. Open an issue with your OS and browser versions, the steps, and the result. Pull requests are welcome in English and Chinese.

[Contributing guide](CONTRIBUTING.md) · [Architecture and data flow](docs/architecture.md)

## License

Local Audio Workbench is licensed under the GNU Affero General Public License, version 3 or any later version (AGPL-3.0-or-later).

[Full license](LICENSE) · [Third-party notices and modification details](THIRD_PARTY_NOTICES.md)
