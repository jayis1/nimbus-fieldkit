# UI performance changes — installed, throughput measurement pending

The user confirmed basic dashboard/Settings/internal/SD behavior still works
after the root restoration trial, then requested better speed. First changes
target browser work, not unmeasured hardware throughput. Do not claim higher
upload/download MB/s, lower device CPU use or a quantified page-load speedup
from these changes.

## Changes

- `device/unified/mascot.js`: cache buddy geometry and compute it only after a
  relevant position/viewport change. Pointer frames no longer repeatedly read
  layout or scan the upload subtree. Music-bar mutations recheck clearance, but
  unchanged clearance no longer invalidates geometry. Coalesce animation frames
  and skip identical pupil transforms. Cancel pending work in hidden documents
  and refresh geometry on return/resize/visual-viewport changes. Preserve reduced
  motion, coarse-pointer behavior, manual visibility/persistence and teardown.
- Remove narrow-screen upload auto-hiding of Nib, honoring the earlier request
  to keep him visible; retain manual Show / hide and music-control clearance.
- `device/unified/upload-progress.js`: repeated byte events with the same integer
  percentage/message make no redundant DOM writes. Preserve genuine progress,
  indeterminate state, cancellation, endpoint restrictions and the distinction
  between 100% sent and confirmed device success. No buffering/concurrent upload,
  retry, fabricated throughput or change to actual file contents/protocol.
- `device/unified/bridge.js`: Settings accessibility/auth messages/attributes are
  updated only when their actual values change. Existing vendor authentication
  remains mandatory; no handler or protected action is bypassed.

## Validation and deployment boundary

**199 tests run, 197 pass, 2 Node-dependent skips**, using the documented host-only
sync fixture isolation. Localhost Chromium checks include navigation, themes,
vendor authentication UI, gaze/reset/layout clearance, manual visibility,
reduced motion/mobile visibility, real upload fixture confirmation/cancel and
media controls. New counters check fewer geometry measurements than the twelve
pointer frames (allowing concurrent stock layout changes), and **zero DOM
mutations for thirty identical upload-percentage events**. These operation-count
checks are not a wall-clock benchmark or native Firefox/device acceptance.

Retained beta1/beta2 images remain unchanged. Their
provenance test now verifies the archived payload hash against its recorded
build manifest and compares that exact payload to the image; it does not require
immutable older builds to match newly edited working-tree sources. No images
were rebuilt or overwritten to accommodate the improvements.

The existing mascot-r1 installer is for an earlier additive homepage insertion;
it must not be reused against the already-installed mascot homepage. A separate
guarded update is now prepared as described below. Do not overwrite existing
assets or claim these optimizations are live before installation evidence.

## Guarded package checkpoint

The user requested both upload and download speed work. Independent read-only
HTTP checks matched the served homepage (`c5247236d5ed0a5b09076bf34523807cd39f4738a194f87cee8fc533103a4d9a`)
and all three current asset hashes pinned in `scripts/package-ui-performance.py`.
No device endpoint was posted to and no file transfer benchmark ran in this
check; these were small static asset GETs, not throughput measurements.

Private local package: `build/nimbus-ui-performance-r1.tar`, SHA-256
**`563671b720884207638b66d6b78837320e73a97b77aefbffccc11283f71de0a7`**.
It contains the vendor-derived homepage, three first-party scripts, guarded
installer and manifests. **Never publish this archive.** Source-only builder and
scripts may follow normal release review. No vendor image, key or backup is
included. Native installation was pending at this preparation checkpoint; the
subsequent installed/served evidence follows below.

The installed update will add `/nimbus/data/fieldkit-performance-r1/` and change
exactly three script references in the current homepage. Audio/CSS assets,
vendor handlers, old scripts, services, keys and mounts remain untouched. Bridge
content retains `/data/fieldkit-v06/` as its toolkit resource prefix rather than
incorrectly looking for toolkit files in the new performance folder.

Private stage: `/root/nimbus-ui-performance-r1`, root-owned 0700. Installer checks
whole-source checksums and the current homepage/old-asset hashes, refuses reused
stage/integration, preserves a private exact homepage backup, copies and compares
new assets, and atomically replaces the homepage. Rollback verifies both the new
installed homepage/assets and old original asset hashes and refuses later edits.
It retains unreferenced new assets/backups instead of deleting evidence. Install
and rollback perform ordinary rootfs file writes and `sync`, not a remount,
firmware update, service interruption or guaranteed power-failure transaction.

Latest suite: **203 tests run, 201 pass, 2 skips**. Four new package tests cover
three-reference-only homepage changes; preserved original assets; guarded
install/rollback; refusal of changed original assets/homepage before install;
rollback refusal after later homepage/new-asset/original-asset edits; bounded
private archive scope; correct bridge resource prefix; shell syntax and
no-overwrite packaging. Fixtures use host-only sync isolation; native installer
continues to use real sync. Earlier 199-test counts describe the source checkpoint.

## Returned installation and independent served verification

The user returned successful whole-archive/source checksum verification,
matching old-asset/homepage guards, an exact private homepage backup and the
installer's success message. No remount, service restart, firmware write or
radio/security change was requested by this update. Private rollback evidence
is retained at `/root/nimbus-ui-performance-r1/backups/`; do not blindly invoke
an older homepage rollback against the newer installed page.

Independent read-only HTTP checks matched all four served artifacts:

| Path | SHA-256 |
| --- | --- |
| `/` | `89ebafcfae4ae1c4dbd862a5f60cf5313af99d440715d224f678e281c3d0b931` |
| `/data/fieldkit-performance-r1/bridge.js` | `5a748e55be9b8334da16fe59ae1cadeecdad46f99a0e4f2119195c5fdc16ec52` |
| `/data/fieldkit-performance-r1/mascot.js` | `82030ca9cdfb448ff74f85a828acfbea9ee3772607a5043257dfcaeca144e984` |
| `/data/fieldkit-performance-r1/upload-progress.js` | `42b34d438eb2adb06657151ce69ccf26ce675bdfd049f5fe00de7f0ed2d90113` |

User hard-refresh/visual acceptance and genuine transfer-throughput/content-hash
tests remain pending. A future root capture must include this newest UI state.
Current beta1/beta2 artifacts are intentionally not rebuilt or flash-qualified
by these observations. The user is being asked to approve a bounded 16MiB
synthetic-file upload/download baseline to each destination without overwriting
existing files; no benchmark media write or cleanup has occurred yet.

## Transfer-speed measurement boundary

First establish a bounded authorized baseline for a selected non-sensitive file
and explicit destination, recording bytes/time, Wi-Fi topology and concurrent
activity, then verify uploaded/downloaded content hashes. Keep internal and SD
results distinct. Diagnose network, browser, server and storage bottlenecks before
altering concurrency/buffers or services. A upload test writes the selected file
and needs destination/size consent; a read-only existing-file download does not
benchmark upload or sustained SD writes. No radio/security downgrade, overclock,
mount-policy change, forced SD write, cache-dropping or process kill is proposed.
