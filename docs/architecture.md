# Architecture and data flow

Local Audio Workbench serves its browser interface from a Python process on the same Mac. The process runs a Swift helper that uses installed Apple Speech assets. The browser and helper use the same local library.

| Step | Input | Result |
| --- | --- | --- |
| Start | macOS, Python, and the Xcode toolchain | The Python process binds to the IPv4 loopback interface. The system selects an available port unless the user specifies one. The launch terminal displays the address. |
| Import | A file selected by the user | The server keeps a separate copy of the original in the recording library. A SHA-256 check identifies identical audio and reuses the existing record. |
| Transcribe | The archived audio and installed Chinese speech assets | The Swift helper produces local timestamped text. The server retains the machine transcript and removes temporary output when processing finishes. |
| Play and correct | An archived file and its transcript | The browser seeks to the selected timestamp. Each saved correction has a revision. Original audio and the machine transcript stay available for comparison. |

The recording library defaults to the current user's Application Support directory, outside the checkout. Its new data directory is created with owner-only permissions. The web process is intended for a trusted single-user Mac. Other software on the same Mac can potentially reach the running service. System backup or synchronization behavior depends on the user's setup.

The workbench serves browser assets locally. The speech helper uses installed assets. Initial installation of the toolchain or speech assets may require a network connection. This project distributes the fictional demo text and a local generator. Use it for testing and keep the resulting audio on your Mac.

## Verifying a change

Run `/bin/zsh ./Start.command --check`, then start the workbench and follow [the demo workflow](../README.md). For a startup change, confirm that the printed address opens and that a second run without a custom port also starts. For audio and correction changes, check timestamp playback and revision persistence, and verify that the original and machine transcript stay intact.

Use synthetic examples in [contributions](../CONTRIBUTING.md). Share only the minimum sanitized information needed to reproduce a problem. Keep actual recording data, user paths, runtime addresses and identifying screenshots private. Discuss changes to data collection, storage or network access before implementing them.
