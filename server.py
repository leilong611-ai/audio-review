#!/usr/bin/env python3
"""Loopback-only recording library, local transcription, and versioned corrections."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import mimetypes
import os
from pathlib import Path
import platform
import re
import secrets
import subprocess
import tempfile
import threading
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'web'
DEFAULT_DATA = Path.home() / 'Library' / 'Application Support' / 'Local Audio Workbench' / 'Recordings'
AUDIO_TYPES = {
    '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4',
    '.aac': 'audio/aac', '.aiff': 'audio/aiff', '.caf': 'audio/x-caf',
    '.flac': 'audio/flac',
}
MAX_AUDIO = 64 * 1024 * 1024
RECORDING_ROUTE = re.compile(r'/api/recordings/([0-9a-f]{64})(?:/(audio|transcribe|corrections))?')


class Problem(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def read_json(file):
    return json.loads(file.read_text(encoding='utf-8'))


def write_json(file, value):
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=file.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
            temporary.replace(file)
        finally:
            temporary.unlink(missing_ok=True)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def build_engine():
    binary = ROOT / '.build' / 'transcribe'
    source = ROOT / 'native' / 'NativeArchiveSpeech.swift'
    binary.parent.mkdir(exist_ok=True)
    with (binary.parent / 'build.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not binary.exists() or binary.stat().st_mtime_ns < source.stat().st_mtime_ns:
            with tempfile.TemporaryDirectory(dir=binary.parent) as temporary:
                candidate = Path(temporary) / 'transcribe'
                subprocess.run(
                    ['/usr/bin/xcrun', 'swiftc', '-parse-as-library', '-O', str(source), '-o', str(candidate)],
                    check=True, timeout=120,
                )
                candidate.replace(binary)
    return binary


class Library:
    def __init__(self, path, engine):
        self.path = path
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.stat().st_uid != os.getuid() or self.path.stat().st_mode & 0o077:
            raise PermissionError('录音库须由当前用户拥有，且只允许当前用户访问。')
        self.engine = engine
        self.lock = threading.Lock()
        self.engine_lock = threading.Lock()
        self.active = set()

    def record(self, key):
        item = self.path / key
        if not (item / 'recording.json').is_file():
            raise Problem(404, '这条录音不存在。')
        return item

    def summary(self, item):
        value = read_json(item / 'recording.json')
        transcript = item / 'machine.json'
        if transcript.is_file():
            machine = read_json(transcript)
            value['segment_count'] = len(machine['segments'])
            value['duration'] = machine['end_time']
            value['state'] = 'complete'
        else:
            value['state'] = 'transcribing' if item.name in self.active else 'imported'
        return value

    def summaries(self):
        with self.lock:
            return sorted(
                (self.summary(item) for item in self.path.iterdir()
                 if re.fullmatch(r'[0-9a-f]{64}', item.name) and (item / 'recording.json').is_file()),
                key=lambda item: item['imported_at'], reverse=True,
            )

    def detail(self, item):
        with self.lock:
            return self._detail(item)

    def _detail(self, item):
        data = self.summary(item)
        data['machine'] = read_json(item / 'machine.json') if data['state'] == 'complete' else None
        versions = sorted((item / 'corrections').glob('[0-9]*.json'), reverse=True)
        data['versions'] = [int(path.stem) for path in versions]
        data['correction'] = read_json(versions[0]) if versions else None
        return data

    def import_audio(self, stream, length, name):
        extension = Path(name).suffix.lower()
        if extension not in AUDIO_TYPES:
            raise Problem(415, '请选择 WAV、M4A、MP3、AAC、AIFF、CAF 或 FLAC 文件。')
        if not 0 < length <= MAX_AUDIO:
            raise Problem(413, '请选择非空录音，大小不超过 64 MB。')
        if len(name) > 180 or name in {'.', '..'} or re.search(r'[\\/\x00-\x1f\x7f]', name):
            raise Problem(400, '录音文件名无效。')
        with tempfile.TemporaryDirectory(prefix='.import-', dir=self.path) as staging:
            stage = Path(staging) / 'recording'
            stage.mkdir()
            original = stage / ('original' + extension)
            digest = hashlib.sha256()
            with original.open('wb') as audio:
                remaining = length
                while remaining:
                    chunk = stream.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise Problem(400, '音频上传中断，请重新导入。')
                    audio.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
            key = digest.hexdigest()
            item = self.path / key
            with self.lock:
                if not item.exists():
                    original.chmod(0o400)
                    (stage / 'corrections').mkdir()
                    write_json(stage / 'recording.json', {
                        'id': key, 'name': name, 'extension': extension, 'bytes': length,
                        'imported_at': utc_now(),
                    })
                    stage.rename(item)
        return self.detail(item)

    def transcribe(self, item):
        if not self.engine_lock.acquire(blocking=False):
            raise Problem(409, '另一条录音正在转写，请稍后重试。')
        try:
            with self.lock:
                if (item / 'machine.json').exists():
                    return self._detail(item)
                self.active.add(item.name)
            data = read_json(item / 'recording.json')
            source = item / ('original' + data['extension'])
            digest = hashlib.sha256()
            with source.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            if digest.hexdigest() != item.name:
                raise Problem(409, '归档音频校验失败，已停止转写。')
            with tempfile.TemporaryDirectory(prefix='audio-asr-') as temporary:
                output = Path(temporary) / 'result.json'
                try:
                    result = subprocess.run(
                        [str(self.engine), '--transcribe', 'zh-CN', str(source), str(output)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180,
                    )
                except subprocess.TimeoutExpired:
                    raise Problem(422, '转写超时。原音已保留，建议先用较短的录音重试。') from None
                if result.returncode == 4:
                    raise Problem(422, '未检测到已安装的中文语音资产。原音已保留。')
                if result.returncode != 0 or not output.is_file():
                    raise Problem(422, 'Apple 听写无法读取这条音频。原音已保留，请检查格式。')
                raw = read_json(output)
            segments = []
            for segment in raw['segments']:
                start, end = float(segment['start']), float(segment['end'])
                content = segment['text'].strip()
                if math.isfinite(start) and math.isfinite(end) and 0 <= start < end and content:
                    segments.append({'start': start, 'end': end, 'text': content})
            segments.sort(key=lambda segment: segment['start'])
            with self.lock:
                write_json(item / 'machine.json', {
                    'engine': 'Apple Speech', 'locale': 'zh-CN', 'source_sha256': item.name,
                    'created_at': utc_now(), 'segments': segments,
                    'end_time': max((segment['end'] for segment in segments), default=0),
                })
                return self._detail(item)
        finally:
            with self.lock:
                self.active.discard(item.name)
            self.engine_lock.release()

    def correct(self, item, request):
        if not isinstance(request, dict) or type(request.get('base_revision')) is not int:
            raise Problem(400, '校对版本无效，请重新打开录音。')
        with self.lock:
            current = self._detail(item)
            machine = current['machine']
            if not machine:
                raise Problem(409, '转写完成后才能校对。')
            previous = current['correction']
            version = previous['revision'] if previous else 0
            if request['base_revision'] != version:
                raise Problem(409, '另一窗口已保存新版本。请先保留本页草稿，再重新打开录音。')
            changes = request.get('texts')
            original = [seg['text'] for seg in machine['segments']]
            if (not isinstance(changes, list) or len(changes) != len(original)
                    or any(not isinstance(text, str) or not text.strip() or len(text) > 12000 for text in changes)):
                raise Problem(400, '每一段都需要填写文字，并保持原有段落数。')
            changes = [text.strip() for text in changes]
            if changes != (previous['texts'] if previous else original):
                next_version = version + 1
                write_json(item / 'corrections' / f'{next_version:08}.json', {
                    'revision': next_version, 'saved_at': utc_now(), 'texts': changes,
                    'source_sha256': item.name,
                })
            return self._detail(item)


class Handler(BaseHTTPRequestHandler):
    server_version = 'LocalAudioWorkbench'
    protocol_version = 'HTTP/1.0'

    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.handle_request()

    def do_HEAD(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def handle_request(self):
        try:
            self.route()
        except Problem as error:
            self.json(error.status, {'error': str(error)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (OSError, ValueError, KeyError, TypeError):
            self.json(500, {'error': '本机处理失败。请检查交付目录是否可读写，再重试。'})

    def headers_for(self, status, mime, length, extra=None):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(length))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()

    def json(self, status, value):
        payload = json.dumps(value, ensure_ascii=False).encode()
        self.headers_for(status, 'application/json; charset=utf-8', len(payload))
        if self.command != 'HEAD':
            self.wfile.write(payload)

    def route(self):
        if self.headers.get('Host') != self.server.host:
            raise Problem(403, '请从本机工作台地址打开。')
        path = urlsplit(self.path).path
        library = self.server.library
        if self.command in {'GET', 'HEAD'}:
            static = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
            if path in static:
                file = WEB / static[path]
                mime = mimetypes.guess_type(file)[0]
                return self.file(file, mime + '; charset=utf-8')
            if path == '/api/session':
                return self.json(200, {'token': self.server.token})
            if path == '/api/recordings':
                return self.json(200, library.summaries())
            match = RECORDING_ROUTE.fullmatch(path)
            if match:
                item = library.record(match[1])
                if match[2] is None:
                    return self.json(200, library.detail(item))
                if match[2] == 'audio':
                    extension = read_json(item / 'recording.json')['extension']
                    return self.file(item / ('original' + extension), AUDIO_TYPES[extension], seekable=True)
        elif self.command == 'POST':
            if (self.headers.get('Origin') != 'http://' + self.server.host
                    or not secrets.compare_digest(self.headers.get('X-Workbench-Token', ''), self.server.token)):
                raise Problem(403, '操作只接受当前工作台页面发起的请求。')
            if path == '/api/recordings':
                name = unquote(self.headers.get('X-Recording-Name', ''))
                return self.json(201, library.import_audio(self.rfile, self.length(), name))
            match = RECORDING_ROUTE.fullmatch(path)
            if match and match[2] in {'transcribe', 'corrections'}:
                item = library.record(match[1])
                if match[2] == 'transcribe':
                    return self.json(200, library.transcribe(item))
                length = self.length()
                if not 0 < length <= 4 * 1024 * 1024:
                    raise Problem(413, '校对内容大小无效。')
                try:
                    request = json.loads(self.rfile.read(length))
                except (ValueError, UnicodeError):
                    raise Problem(400, '校对内容格式错误。') from None
                return self.json(200, library.correct(item, request))
        raise Problem(404, '找不到这个入口。')

    def length(self):
        try:
            return int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise Problem(400, '内容长度无效。') from None

    def file(self, path, mime, seekable=False):
        with path.open('rb') as file:
            size = os.fstat(file.fileno()).st_size
            start, end, status = 0, size - 1, 200
            extra = {'Accept-Ranges': 'bytes'} if seekable else {}
            request = self.headers.get('Range') if seekable else None
            if request:
                interval = re.fullmatch(r'bytes=(\d*)-(\d*)', request)
                if not interval or not any(interval.groups()):
                    return self.headers_for(416, mime, 0, {'Content-Range': f'bytes */{size}'})
                a, b = interval.groups()
                start = int(a) if a else max(0, size - int(b))
                end = min(int(b), size - 1) if a and b else size - 1
                if start > end:
                    return self.headers_for(416, mime, 0, {'Content-Range': f'bytes */{size}'})
                status = 206
                extra['Content-Range'] = f'bytes {start}-{end}/{size}'
            remaining = end - start + 1
            self.headers_for(status, mime, remaining, extra)
            if self.command != 'HEAD':
                file.seek(start)
                while remaining:
                    chunk = file.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8879)
    parser.add_argument('--data-dir', type=Path, default=DEFAULT_DATA, help='仓库以外的本机录音库')
    parser.add_argument('--check', action='store_true', help='检查环境和中文语音资产，不启动工作台')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('端口须在 1024–65535 之间。')
    data_dir = args.data_dir.resolve()
    if data_dir == ROOT or ROOT in data_dir.parents:
        parser.error('请把录音库放在源码目录之外。')
    mac_version = platform.mac_ver()[0]
    if not mac_version or int(mac_version.split('.')[0]) < 26:
        parser.exit(1, '需要 macOS 26 或更高版本。\n')
    try:
        engine = build_engine()
    except (OSError, subprocess.SubprocessError):
        parser.exit(1, '无法编译转写工具。请检查 Xcode 工具链及 macOS SDK。\n')
    if args.check:
        try:
            result = subprocess.run(
                [str(engine), '--check', 'zh-CN'], capture_output=True, check=False, timeout=20,
            )
            if result.returncode == 0 and json.loads(result.stdout).get('available'):
                print('已就绪。中文 Apple 语音资产可用。')
                return
        except (OSError, ValueError, subprocess.TimeoutExpired):
            parser.exit(1, '无法检查 Apple 语音资产。请确认系统支持 Apple Speech。\n')
        parser.exit(1, '中文 Apple 语音资产不可用。请确认系统支持并已安装中文资产。\n')
    try:
        library = Library(data_dir, engine)
    except PermissionError:
        parser.exit(1, '无法使用录音库。请使用当前用户独占且可读写的目录。\n')
    with (library.path / '.server.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, '此数据目录已有工作台在运行。\n')
        with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
            server.host = f'127.0.0.1:{args.port}'
            server.token = secrets.token_hex(32)
            server.library = library
            print('http://' + server.host, flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == '__main__':
    main()
