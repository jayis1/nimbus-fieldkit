#!/bin/sh
# UI-only patch for the exact delivered v0.6 assets. No homepage/service writes.
set -eu
BASE=$(CDPATH= cd "$(dirname "$0")" && pwd)
TARGET=/nimbus/data/fieldkit-v06
[ "$(id -u)" = 0 ] || { echo 'Authorized root SSH session required.'; exit 1; }
[ ! -L /nimbus/data ] && [ -d "$TARGET" ] && [ ! -L "$TARGET" ] || exit 1
cd "$BASE"
baseline() {
  printf '%s  %s\n' \
    23124514cfac6725b267334336a82cc93bb55f1f7de31feb1616f4ffc2cd6fcd "$1/bridge.js" \
    d6f1bc8a29e0feca12361e52b157d62018810ca05d2517564d2aebce8cf70fe7 "$1/stock-dark.css" | sha256sum -c -
}
replace() {
  source="$1"; destination="$2"
  [ ! -L "$destination" ] || return 1
  temporary="$destination.nimbus-ui-new"
  [ ! -e "$temporary" ] && [ ! -L "$temporary" ] || return 1
  (set -C; cat "$source" > "$temporary") || return 1
  chmod 644 "$temporary"
  cmp "$source" "$temporary" || return 1
  mv "$temporary" "$destination"
}
case "${1:-}" in
 install)
  sha256sum -c SHA256SUMS || exit 1
  baseline "$TARGET" || { echo 'Live assets differ; refusing patch.'; exit 1; }
  [ ! -e backups ] && [ ! -L backups ] || { echo 'Prior attempt exists; review before rerunning.'; exit 1; }
  mkdir backups
  chmod 700 backups
  for file in bridge.js stock-dark.css; do
    cp -p "$TARGET/$file" "backups/$file"
    cmp "$TARGET/$file" "backups/$file"
  done
  baseline "$BASE/backups" || exit 1
  for file in bridge.js stock-dark.css; do
    replace "$BASE/$file" "$TARGET/$file"
    cmp "$BASE/$file" "$TARGET/$file"
  done
  sha256sum "$TARGET/bridge.js" "$TARGET/stock-dark.css" > installed.sha256
  sync
  echo 'Settings UI patch installed. Homepage/runtime/settings/SSH/Wi-Fi unchanged.'
  echo 'Hard-refresh the browser. Web-admin authentication remains required.'
  ;;
 rollback)
  baseline "$BASE/backups" || exit 1
  [ -f installed.sha256 ] && [ ! -L installed.sha256 ] || { echo 'Incomplete install; review assets manually.'; exit 1; }
  sha256sum -c installed.sha256 || { echo 'Assets changed after patch; refusing overwrite.'; exit 1; }
  for file in bridge.js stock-dark.css; do replace "$BASE/backups/$file" "$TARGET/$file"; done
  baseline "$TARGET"
  sync
  echo 'Previous v0.6 UI assets restored. No services changed.'
  ;;
 *) echo 'Usage: sh install-settings-fix.sh install|rollback'; exit 1;;
esac
