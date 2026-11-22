// SPDX-License-Identifier: AGPL-3.0-or-later
// SpeechFileReader is adapted from rokrokss/recly by Hyungrok Kim (2026).
// Source: AppleSpeechTranscriber.swift, Git blob a998ea6af91a6cc463cd5f19e183214cb6ed9235.
// Modified on 2026-11-20 for local archive reading and timestamped output.
// See ../THIRD_PARTY_NOTICES.md and ../LICENSE.
import Foundation
import Speech
import AVFoundation
import CoreMedia

struct NativeSegment: Codable { let start: Double; let end: Double; let text: String }
struct NativeResult: Codable {
    let provider: String; let locale: String; let source_file: String
    let segments: [NativeSegment]
}
@main struct NativeArchiveSpeech {
    static func main() async {
        let args = Array(CommandLine.arguments.dropFirst())
        guard args.count == 2 || args.count == 4 else { exit(2) }
        let tag = args[1]
        guard SpeechTranscriber.isAvailable,
              let locale = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: tag)) else {
            print("{\"available\":false}"); exit(4)
        }
        let installed = await SpeechTranscriber.installedLocales.contains { $0.identifier == locale.identifier }
        if args[0] == "--check" {
            let value: [String: Any] = ["available": installed, "locale": locale.identifier]
            print(String(data: try! JSONSerialization.data(withJSONObject: value), encoding: .utf8)!)
            return
        }
        guard args[0] == "--transcribe", args.count == 4, installed else { exit(4) }
        let source = URL(fileURLWithPath: args[2]), dest = URL(fileURLWithPath: args[3])
        guard !FileManager.default.fileExists(atPath: dest.path) else { exit(3) }
        let module = SpeechTranscriber(
            locale: locale, transcriptionOptions: [], reportingOptions: [],
            attributeOptions: [.audioTimeRange]
        )
        let analyzer = SpeechAnalyzer(modules: [module], options: .init(priority: .utility, modelRetention: .whileInUse))
        let collect = Task { () throws -> [NativeSegment] in
            var items: [NativeSegment] = []
            for try await result in module.results where result.isFinal {
                items.append(contentsOf: timedSegments(result.text, fallback: result.range))
            }
            return items
        }
        do {
            let file = try AVAudioFile(forReading: source)
            guard let format = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [module], considering: file.processingFormat)
            else { throw SpeechFileError.unsupportedFormat }
            let reader = try SpeechFileReader(file: file, format: format, startTime: 0)
            let inputs = AsyncThrowingStream<AnalyzerInput, Error>(unfolding: { try await reader.next() })
            _ = try await analyzer.analyzeSequence(inputs)
            try await analyzer.finalizeAndFinishThroughEndOfInput()
            let items = try await collect.value
            let result = NativeResult(provider: "apple-speech-mac-local", locale: locale.identifier,
                                      source_file: source.path, segments: items)
            let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            try encoder.encode(result).write(to: dest, options: .atomic)
            print("{\"completed\":true,\"segments\":\(items.count)}")
        } catch {
            await analyzer.cancelAndFinishNow(); collect.cancel()
            fputs("Native transcription failed: \(String(describing: error))\n", stderr); exit(1)
        }
    }
}
// Use the speech analyzer's attributed time ranges. Break long results at natural
// boundaries without estimating offsets from character counts.
private func timedSegments(_ text: AttributedString, fallback: CMTimeRange) -> [NativeSegment] {
    var segments: [NativeSegment] = []
    var start: Double?
    var end = 0.0
    var words = ""
    let punctuation = CharacterSet(charactersIn: "。！？；!?;")

    func finish() {
        if let start, end > start, !words.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            segments.append(NativeSegment(start: start, end: end, text: words))
        }
        start = nil
        words = ""
    }

    for run in text.runs {
        let piece = String(text[run.range].characters)
        if let time = run.audioTimeRange, time.start.seconds.isFinite, time.end.seconds.isFinite {
            if let current = start, !words.isEmpty,
               time.start.seconds - end >= 0.65 || end - current >= 7 ||
               (end - current >= 2 && words.unicodeScalars.last.map(punctuation.contains) == true) {
                finish()
            }
            if start == nil {
                start = time.start.seconds
                end = time.end.seconds
            } else {
                end = max(end, time.end.seconds)
            }
        }
        words.append(piece)
    }
    finish()
    if segments.isEmpty {
        return [NativeSegment(start: fallback.start.seconds, end: fallback.end.seconds, text: String(text.characters))]
    }
    return segments
}

private enum SpeechFileError: Error { case unsupportedFormat, conversion }

/// Pull-based input prevents a producer from decoding the entire recording into memory.
@available(iOS 26, macOS 26, *)
actor SpeechFileReader {
    let file: AVAudioFile
    let format: AVAudioFormat
    let converter: AVAudioConverter
    private var emitted: AVAudioFramePosition = 0
    /// The resume point as a frame of [format], so every buffer's start is a whole frame count.
    private let origin: AVAudioFramePosition
    private let totalFrames: AVAudioFramePosition

    init(file: AVAudioFile, format: AVAudioFormat, startTime: Double) throws {
        self.file = file
        self.format = format
        guard let converter = AVAudioConverter(from: file.processingFormat, to: format) else {
            throw SpeechFileError.unsupportedFormat
        }
        self.converter = converter
        file.framePosition = min(file.length, AVAudioFramePosition(max(0, startTime) * file.processingFormat.sampleRate))
        origin = AVAudioFramePosition((Double(file.framePosition) / file.processingFormat.sampleRate * format.sampleRate).rounded())
        totalFrames = AVAudioFramePosition((Double(file.length - file.framePosition) / file.processingFormat.sampleRate * format.sampleRate).rounded())
        converter.primeMethod = .none
    }

    func next() throws -> AnalyzerInput? {
        try Task.checkCancellation()
        guard emitted < totalFrames else { return nil }
        guard let output = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 16_384) else { throw SpeechFileError.conversion }
        var readError: Error?
        var conversionError: NSError?
        let status = converter.convert(to: output, error: &conversionError) { requested, state in
            if self.file.framePosition >= self.file.length { state.pointee = .endOfStream; return nil }
            let count = AVAudioFrameCount(min(Int64(min(requested, 16_384)), self.file.length - self.file.framePosition))
            guard let input = AVAudioPCMBuffer(pcmFormat: self.file.processingFormat, frameCapacity: count) else {
                state.pointee = .endOfStream; readError = SpeechFileError.conversion; return nil
            }
            do { try self.file.read(into: input, frameCount: count) }
            catch { state.pointee = .endOfStream; readError = error; return nil }
            state.pointee = .haveData
            return input
        }
        if let readError { throw readError }
        if let conversionError { throw conversionError }
        guard status != .error else { throw SpeechFileError.conversion }
        output.frameLength = min(output.frameLength, AVAudioFrameCount(totalFrames - emitted))
        guard output.frameLength > 0 else { return nil }
        // Counted in the buffer's own frames: the analyzer rejects a start in other units (seconds at
        // a 48 kHz timescale) as overlapping the previous buffer ten seconds into a 16 kHz recording.
        let start = CMTime(value: origin + emitted, timescale: CMTimeScale(format.sampleRate))
        emitted += AVAudioFramePosition(output.frameLength)
        return AnalyzerInput(buffer: output, bufferStartTime: start)
    }
}

