'use strict';

const byId = (id) => document.getElementById(id);
const audio = byId('audio');
const picker = byId('audio-input');
const player = byId('play');
const position = byId('position');
const wave = byId('wave');
const source = '/api/recordings';
const svgNS = 'http://www.w3.org/2000/svg';
let token = '';
let records = [];
let recording = null;
let editing = false;
let originalView = false;
let busy = false;

function node(tag, value, css) {
  const item = document.createElement(tag);
  if (value !== undefined) item.textContent = value;
  if (css) item.className = css;
  return item;
}

function sayStatus(message = '', error = false) {
  const status = byId('status');
  status.textContent = message;
  status.dataset.error = String(error);
}

function timestamp(seconds) {
  const value = Math.floor(Math.max(0, seconds));
  const parts = [Math.floor(value / 60), value % 60];
  return parts.map((part) => String(part).padStart(2, '0')).join(':');
}

async function ask(path, options = {}) {
  const response = await fetch(path, options);
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error('工作台暂时无法读取结果，请重试。');
  }
  if (!response.ok) throw new Error(payload.error || '操作未完成。');
  return payload;
}

function post(path, body, headers = {}) {
  return ask(path, {method: 'POST', body, headers: {...headers, 'X-Workbench-Token': token}});
}

function plainName(name) {
  return name.replace(/\.[^./]+$/, '');
}

function renderCatalog() {
  byId('record-count').textContent = records.length + ' 条';
  picker.disabled = busy || editing;
  document.querySelector('.import').setAttribute('aria-disabled', String(picker.disabled));
  const entries = records.map((item) => {
    const button = node('button', undefined, 'record-button');
    button.type = 'button';
    button.disabled = busy || editing;
    button.setAttribute('aria-current', String(item.id === recording?.id));
    const icon = node('span', '♫', 'record-icon');
    icon.setAttribute('aria-hidden', 'true');
    const text = node('span');
    const status = {complete: item.segment_count + ' 段转写', imported: '待转写', transcribing: '转写中'};
    text.append(node('span', plainName(item.name), 'record-name'), node('span', status[item.state], 'record-info'));
    button.append(icon, text);
    button.addEventListener('click', () => doWork(async () => {
      sayStatus();
      select(await ask(source + '/' + item.id));
    }));
    return button;
  });
  byId('record-list').replaceChildren(...entries);
}

function select(item) {
  const different = recording?.id !== item.id;
  recording = item;
  originalView = false;
  editing = false;
  byId('empty').hidden = true;
  byId('detail').hidden = false;
  byId('record-label').textContent = item.name.startsWith('合成录音-') ? '合成演示录音' : '本机录音';
  byId('record-title').textContent = plainName(item.name).replace(/^合成录音-/, '');
  const format = item.extension.slice(1).toUpperCase();
  byId('record-meta').textContent = format + ' · ' + (item.bytes / 1024).toFixed(0) + ' KB';
  if (different) {
    audio.src = source + '/' + item.id + '/audio';
    wave.replaceChildren();
    resetWave();
    updatePlayer();
  }
  history.replaceState(null, '', '#' + item.id);
  renderCatalog();
  renderText();
}

function renderText() {
  const machine = recording.machine;
  const correction = recording.correction;
  const segments = machine?.segments || [];
  const noTranscript = byId('transcript-empty');
  const available = segments.length > 0;
  byId('transcribe').hidden = Boolean(machine);
  byId('transcribe').disabled = busy || recording.state === 'transcribing';
  byId('transcribe').textContent = recording.state === 'transcribing' ? '转写中…' : '本机转写';
  byId('controls').hidden = !available;
  byId('original').hidden = !correction || editing;
  byId('original').textContent = originalView ? '返回校对稿' : '查看机器稿';
  byId('edit').hidden = editing || originalView;
  byId('cancel').hidden = !editing;
  byId('save').hidden = !editing;
  byId('version').textContent = machine
    ? (originalView || !correction ? '机器稿 · Apple 本机听写' : '校对稿 V' + correction.revision + ' · 机器稿已保留')
    : '待转写';
  noTranscript.hidden = available;
  noTranscript.textContent = machine ? '已完成转写。未识别到可显示的语音。' : '转写完成后，点击每一段的时间可以回听原音。';

  const list = segments.map((segment, index) => {
    const row = node('div', undefined, 'segment');
    const stamp = node('button', '▶ ' + timestamp(segment.start), 'stamp');
    stamp.type = 'button';
    stamp.setAttribute('aria-label', '从 ' + timestamp(segment.start) + ' 回听第 ' + (index + 1) + ' 段');
    stamp.addEventListener('click', () => playAt(segment.start));
    const value = originalView ? segment.text : correction?.texts[index] ?? segment.text;
    const content = node(editing ? 'textarea' : 'p', editing ? undefined : value);
    if (editing) {
      content.value = value;
      content.maxLength = 12000;
      content.setAttribute('aria-label', '第 ' + (index + 1) + ' 段校对');
    }
    row.append(stamp, content);
    return row;
  });
  byId('segments').replaceChildren(...list);
  updatePlayer();
}

function resetWave() {
  const line = document.createElementNS(svgNS, 'line');
  line.setAttribute('x1', '0');
  line.setAttribute('x2', '500');
  line.setAttribute('y1', '24');
  line.setAttribute('y2', '24');
  line.setAttribute('stroke', 'currentColor');
  wave.replaceChildren(line);
}

async function loadWave() {
  const item = recording;
  if (!item || item.bytes > 8 * 1024 * 1024 || !Number.isFinite(audio.duration) || audio.duration > 180 || !window.AudioContext) return;
  let context;
  try {
    const response = await fetch(source + '/' + item.id + '/audio');
    if (!response.ok) return;
    context = new AudioContext();
    const buffer = await context.decodeAudioData(await response.arrayBuffer());
    if (item.id !== recording?.id) return;
    const samples = buffer.getChannelData(0);
    const blocks = 90;
    const chunk = Math.max(1, Math.floor(samples.length / blocks));
    const bars = [];
    for (let i = 0; i < blocks; i += 1) {
      let peak = 0;
      for (let j = i * chunk; j < Math.min(samples.length, (i + 1) * chunk); j += 6) peak = Math.max(peak, Math.abs(samples[j]));
      const height = Math.max(1.5, Math.min(43, peak * 65));
      const bar = document.createElementNS(svgNS, 'rect');
      bar.setAttribute('x', String(i * 500 / blocks));
      bar.setAttribute('y', String(24 - height / 2));
      bar.setAttribute('width', '2.7');
      bar.setAttribute('height', String(height));
      bar.setAttribute('rx', '1.2');
      bar.setAttribute('fill', 'currentColor');
      bars.push(bar);
    }
    wave.replaceChildren(...bars);
  } catch {
    // The range slider stays available when waveform decoding is unsupported.
  } finally {
    if (context) await context.close().catch(() => {});
  }
}

function updatePlayer() {
  const duration = audio.duration;
  const ready = Number.isFinite(duration) && duration > 0;
  position.disabled = !ready;
  if (ready) {
    position.max = String(duration);
    position.value = String(audio.currentTime);
  }
  byId('elapsed').textContent = timestamp(audio.currentTime) + ' / ' + (ready ? timestamp(duration) : '—');
  const active = !audio.paused;
  player.setAttribute('aria-label', active ? '暂停原音' : '播放原音');
  player.firstElementChild.textContent = active ? 'Ⅱ' : '▶';
  wave.classList.toggle('playing-line', active);
  const segments = recording?.machine?.segments || [];
  const index = segments.findIndex((s) => audio.currentTime >= s.start && audio.currentTime < s.end);
  for (const [i, row] of Array.from(byId('segments').children).entries()) row.classList.toggle('active', i === index);
}

function playAt(seconds) {
  try {
    audio.currentTime = seconds;
    void audio.play().catch(() => sayStatus('原音暂时无法播放，请检查音频格式。', true));
    updatePlayer();
  } catch {
    sayStatus('原音还未加载，请稍后重试。', true);
  }
}

async function doWork(action) {
  if (busy) return;
  busy = true;
  renderCatalog();
  byId('transcribe').disabled = true;
  byId('save').disabled = true;
  byId('cancel').disabled = true;
  try {
    await action();
  } catch (error) {
    sayStatus(error.message || '操作未完成，请重试。', true);
  } finally {
    busy = false;
    renderCatalog();
    byId('transcribe').disabled = recording?.state === 'transcribing';
    byId('save').disabled = false;
    byId('cancel').disabled = false;
  }
}

picker.addEventListener('change', () => {
  const [file] = picker.files;
  picker.value = '';
  if (!file) return;
  void doWork(async () => {
    sayStatus('正在导入录音…');
    const item = await post(source, file, {
      'Content-Type': 'application/octet-stream',
      'X-Recording-Name': encodeURIComponent(file.name),
    });
    records = await ask(source);
    select(item);
    sayStatus(item.machine ? '录音库已有同一份音频，已打开现有记录。' : '已导入。点击「本机转写」开始。');
  });
});

byId('transcribe').addEventListener('click', () => doWork(async () => {
  sayStatus('正在用 Apple 本机听写转写…');
  byId('transcribe').textContent = '转写中…';
  try {
    const item = await post(source + '/' + recording.id + '/transcribe');
    records = await ask(source);
    select(item);
    sayStatus('转写完成，共 ' + item.machine.segments.length + ' 段。');
  } finally {
    renderText();
  }
}));

byId('edit').addEventListener('click', () => {
  editing = true;
  sayStatus();
  renderCatalog();
  renderText();
  byId('segments').querySelector('textarea')?.focus();
});
byId('original').addEventListener('click', () => {
  originalView = !originalView;
  renderText();
});
byId('cancel').addEventListener('click', () => {
  editing = false;
  sayStatus();
  renderCatalog();
  renderText();
});
byId('save').addEventListener('click', () => doWork(async () => {
  const fields = Array.from(byId('segments').querySelectorAll('textarea'));
  const texts = fields.map((field) => field.value.trim());
  const previous = recording.correction?.revision || 0;
  const item = await post(source + '/' + recording.id + '/corrections',
    JSON.stringify({base_revision: previous, texts}), {'Content-Type': 'application/json'});
  select(item);
  const version = item.correction?.revision || 0;
  sayStatus(version > previous ? '校对稿 V' + version + ' 已保存。' : '文字没有变化。');
}));

player.addEventListener('click', () => {
  if (audio.paused) playAt(audio.currentTime);
  else audio.pause();
});
position.addEventListener('input', () => {
  audio.currentTime = Number(position.value);
  updatePlayer();
});
for (const event of ['timeupdate', 'play', 'pause', 'ended', 'emptied', 'durationchange']) {
  audio.addEventListener(event, updatePlayer);
}
audio.addEventListener('loadedmetadata', () => { updatePlayer(); void loadWave(); });

void doWork(async () => {
  token = (await ask('/api/session')).token;
  records = await ask(source);
  const item = records.find((candidate) => '#' + candidate.id === location.hash) || records[0];
  if (item) select(await ask(source + '/' + item.id));
});
