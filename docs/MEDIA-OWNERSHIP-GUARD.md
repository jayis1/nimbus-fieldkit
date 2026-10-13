# Native media ownership guards — source implementation, not lifecycle qualification

This is a fix to existing runtime/publication/transfer behavior within the feature
freeze. It adds no radio, service, mount or USB action.

## Fresh native observation

Strictly pinned normal SSH 2224 read `/proc/mounts`, `/proc/modules` and metadata
for allowlisted runtime paths. `g_file_storage` is loaded; `/mnt/storage`,
`/mnt/sdcard`, `/opt/nimbus/native` and the expected publisher path are absent.
Root remains rw. Loaded export code is evidence of export state, not independent
proof of physical host attachment. Existing vendor USB access setting is also
not proof of physical attachment.

Do not create substitute media directories, enable a rootfs-backed fallback
vault, mount media or change USB mode to make telemetry work. The current native
media publisher cannot safely be installed/started in that state. The independent
battery RPC/header can still work.

## Implemented source safeguards

`device/nimbus-media-guard.sh check-write|check-read ABSOLUTE_PATH` only reads
metadata and procfs. It performs no copy, mkdir, mount, module or service action.

- Rejects noncanonical paths, symlink components, known public media aliases and
  alternate mount aliases of the known internal/SD devices.
- Internal media requires one mount of `/dev/mmcblk0p4` at `/mnt/storage`; SD
  requires `/dev/mmcblk1p1` at `/mnt/sdcard`. Supported filesystem types are
  texfat/vfat/exfat/ext3. Different geometry/filesystems remain unqualified.
- Media checks refuse any loaded `g_*` gadget module, mass-storage function,
  missing/malformed module inventory, missing/ambiguous mount, contradictory
  options or a nested overmount along the selected path.
- Writes require explicit rw; reads may use an explicitly ro local mount.
  Non-media paths are not certified writable, private or safe by this helper.
- Linux's legitimate `/proc/mounts` symlink is supported. `NIMBUS_PROC_DIR` is a
  trusted fixture override, not a browser/user-facing privilege boundary.

Boot checks this trusted rootfs helper before media initialization. The publisher
checks before staging and before committing; settings/copy/vault/Git operations
check their state/source/destinations at the corresponding existing action gates.
OFF/read loops avoid reading known media flags after observed export. An observed
ownership loss leaves old settings/snapshot intact and preserves new partial
files/locks rather than deleting from newly exported media. Such stages require
inspection; do not remove locks or rerun automatically.

The native bundle includes the helper. Neither the updated runtime nor a rebuilt
firmware image is installed by editing or packaging these files. Immutable beta5
does not contain this helper and now correctly reports a source rebuild required.

## Limits / remaining gate

These are **sampled preconditions, not an ownership lock**. A vendor transition
can occur between checks or during a copy, Git initialization or boot copy. No
claim of uninterrupted exclusive ownership, full descendant drain, write
durability, physical USB attachment detection or safe hot-handoff follows.
Built-in/unrecognized USB export implementations and new devices require their
own review. The vendor automount/USB lifecycle must be integrated and qualified
before marking persistent SD/media policy or USB teardown release-ready.

Native read-only invocation of the new helper for `/mnt/storage` returned exit 2:
`Media mount directory absent or unsafe; never create a substitute`. This is the
expected refusal on the current drive, not positive media-write qualification.
No media data was written, service restarted, module unloaded or mode changed.

Fixture tests cover module/mount refusals, aliases/symlinks, ro read versus write,
settings/transfer/publication refusal before writing, and ownership loss before
commit with preserved original data and partial evidence. Host fixtures simulate
the transition; no actual USB or mount transition is performed by the tests.

Scoped regression: **89 tests passed, no skips** (11 media guard, 28 dashboard/
battery/package, 12 settings, six startup, 22 firmware/inventory, five policy,
five unified UI). `git diff --check` passed. Full workspace regression was not
run. These results do not close the native USB ownership lifecycle gate.
