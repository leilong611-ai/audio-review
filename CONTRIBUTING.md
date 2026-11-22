# Contributing / 参与贡献

## Find a useful first change

- Test first launch on a Mac, especially macOS 26. Report which speech assets and SDK are installed, along with the step that worked or failed.
- Add a repeatable local test for timestamp playback, duplicate audio import, or correction persistence.
- Improve the setup instructions or the messages for missing speech assets and a port already in use.

## Open an issue or pull request

1. Start with an issue for a new feature or a change that affects the data written to disk.
2. Fork this repository, create a branch, and keep the pull request focused on one change.
3. Write the steps you ran and the expected and observed behavior. Include macOS, Python, SDK and browser versions when they are relevant.
4. Use only synthetic examples. Replace personal file paths and remove real names, credentials, recordings, transcripts and identifying screenshots before sharing.

For code changes, try `/bin/zsh ./Start.command --check` and run the demo in [the README](README.md). A change to imports or corrections should also verify that the original audio and machine transcript are preserved. Use English for code names, comments, and commit messages. Keep the English and Simplified Chinese setup steps in sync when behavior changes.

The [architecture and data flow](docs/architecture.md) describes what the app reads, writes, and serves. Update it and describe your verification in the PR when a change affects storage, access, or networking. Use synthetic examples and redact terminal output before sharing it.

欢迎用中文提交 Issue 或 PR。首次参与可以从安装验证、回听和校对测试、错误提示入手。请用虚构样例复现，并说明环境、步骤、预期与实际结果。

## License / 贡献许可

Contributions are submitted under the project’s [AGPL-3.0-or-later license](LICENSE).
