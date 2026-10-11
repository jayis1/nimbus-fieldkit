#!/bin/sh
# Retire exactly the old standalone entry point; never touch unified homepage.
set -eu
[ "$(id -u)" = 0 ] || { echo 'Root required.'; exit 1; }
old=/mnt/storage/nimbus-fieldkit-v04/dashboard/index.html
retired=/root/nimbus-retired-v04-homepage
[ -f "$old" ] && [ ! -L "$old" ] || { echo 'Old v0.4 homepage absent or symlink; stopped.'; exit 1; }
[ ! -e "$retired" ] || { echo 'Retirement backup exists; stopped.'; exit 1; }
umask 077
mkdir "$retired"
chmod 700 "$retired"
cp "$old" "$retired/index.html"
chmod 600 "$retired/index.html"
cmp "$old" "$retired/index.html" || exit 1
sha256sum "$retired/index.html" > "$retired/SHA256SUMS"
# Delete only the verified legacy entry-point file after private backup.
rm "$old"
sync
echo 'Old v0.4 dashboard entry point retired; root backup preserved.'
echo 'Unified /nimbus/data/index.html, runtime, settings and all other files unchanged.'
