#!/bin/zsh
set -eu
umask 077
sample_dir="${0:A:h}"
demo_dir="$HOME/Library/Application Support/Local Audio Workbench/Demo"
destination="$demo_dir/reading-corner-demo.wav"
mkdir -p -- "$demo_dir"
if [[ -e "$destination" || -L "$destination" ]]; then
  print -r -- "演示文件已存在：$destination"
  exit 0
fi
tmp_dir=$(/usr/bin/mktemp -d "$demo_dir/.generate.XXXXXXXX")
cleanup() {
  /usr/bin/unlink "$tmp_dir/demo.aiff" 2>/dev/null || true
  /usr/bin/unlink "$tmp_dir/demo.wav" 2>/dev/null || true
  /bin/rmdir "$tmp_dir"
}
trap cleanup EXIT
if ! /usr/bin/say -v Tingting -o "$tmp_dir/demo.aiff" -f "$sample_dir/演示脚本.txt"; then
  print -u2 -- "无法生成演示音频。请确认系统可用 Tingting 中文语音，或用自有音频试用。"
  exit 1
fi
/usr/bin/afconvert -f WAVE -d LEI16 "$tmp_dir/demo.aiff" "$tmp_dir/demo.wav"
/bin/ln "$tmp_dir/demo.wav" "$destination"
print -r -- "$destination"
