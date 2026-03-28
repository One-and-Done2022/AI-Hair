#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/Faceprompt/src/faceprompt/data"
TARGET_DIR="$ROOT_DIR/backend/app/data/faceprompt"
SERVICE_NAME="aiface-backend.service"

FILES=(
  "scenes.json"
  "scene_styling_rules.json"
  "hairstyles_male.json"
  "hairstyles_female.json"
  "stylings.json"
)

WATCH_MODE=0
RESTART_SERVICE=0

usage() {
  cat <<'EOF'
用法：
  scripts/sync_faceprompt.sh [--restart] [--watch]

参数：
  --restart   同步完成后自动重启用户级后端服务 aiface-backend.service
  --watch     持续监听 Faceprompt 数据目录，检测到改动后自动同步
  -h, --help  查看帮助

示例：
  scripts/sync_faceprompt.sh
  scripts/sync_faceprompt.sh --restart
  scripts/sync_faceprompt.sh --watch --restart
EOF
}

log() {
  printf '[sync_faceprompt] %s\n' "$*"
}

require_source_files() {
  for file in "${FILES[@]}"; do
    if [[ ! -f "$SOURCE_DIR/$file" ]]; then
      log "缺少源文件：$SOURCE_DIR/$file"
      exit 1
    fi
  done
}

restart_backend() {
  log "重启服务：$SERVICE_NAME"
  systemctl --user restart "$SERVICE_NAME"
  log "服务重启完成"
}

sync_once() {
  require_source_files
  mkdir -p "$TARGET_DIR"

  local changed=0
  for file in "${FILES[@]}"; do
    local source_file="$SOURCE_DIR/$file"
    local target_file="$TARGET_DIR/$file"

    if [[ -f "$target_file" ]] && cmp -s "$source_file" "$target_file"; then
      log "无变化：$file"
      continue
    fi

    install -m 0644 "$source_file" "$target_file"
    changed=1
    log "已同步：$file"
  done

  if [[ "$changed" -eq 0 ]]; then
    log "没有检测到需要同步的文件"
    return
  fi

  log "同步完成 -> $TARGET_DIR"

  if [[ "$RESTART_SERVICE" -eq 1 ]]; then
    restart_backend
  fi
}

watch_loop() {
  if ! command -v inotifywait >/dev/null 2>&1; then
    log "未安装 inotifywait，无法使用 --watch"
    log "Ubuntu 可执行：sudo apt install -y inotify-tools"
    exit 1
  fi

  sync_once
  log "开始监听：$SOURCE_DIR"

  inotifywait -m -e close_write,create,move,delete "$SOURCE_DIR" | while read -r _dir _event file; do
    case "$file" in
      scenes.json|scene_styling_rules.json|hairstyles_male.json|hairstyles_female.json|stylings.json)
        log "检测到变更：$file"
        sync_once
        ;;
      *)
        ;;
    esac
  done
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --watch)
      WATCH_MODE=1
      shift
      ;;
    --restart)
      RESTART_SERVICE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      log "未知参数：$1"
      usage
      exit 1
      ;;
  esac
done

if [[ "$WATCH_MODE" -eq 1 ]]; then
  watch_loop
else
  sync_once
fi
