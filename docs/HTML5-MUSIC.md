# Original dashboard Music: HTML5-only candidate

The user requested browser music without Adobe Flash. The first-party adapter `device/unified/audio-html5.js` keeps the vendor Music view, playlist/controller objects and playback controls, but forces its existing jPlayer engine to use **HTML5 audio only**. This does not add a separate dashboard, a CDN dependency, transcoding, a server-side player or an unauthenticated command endpoint.

## Changes

- Removes the Music initialization's Flash-first preference (including Firefox) and its SWF options; only the Music component is affected, not the vendor video player.
- Replaces the Music error handler that recommends installing Flash with browser-codec/file/network guidance and a safe original-file link.
- Normalizes `.ogg`→`oga`, `.wave`→`wav` and uppercase extensions. MP3, M4A, Ogg/Vorbis and WAV are supplied to jPlayer; actual codec support remains browser/OS-dependent. FLAC/raw AAC/other formats get an open/download fallback, not a promise of in-browser support.
- Uses device `/storage/` and `/sdcard/` paths only, encodes filename segments (including spaces, Unicode, `#`, `?` and literal `%`), rejects traversal/schemes and avoids mutating playlist tracks or adding malformed duplicate cache queries.
- Handles rejected native play promises with a user-gesture or playback-failure message instead of an unhandled rejection. Autoplay/mobile background audio are not guaranteed.
- Uses text content for messages/filenames rather than HTML injection. Original-file links do not bypass device access controls. Vendor HTTP media transport remains plaintext; this is not a security upgrade to the legacy server.

Future unified-dashboard builds include the adapter before the bridge. Existing v4 images were **not rebuilt** and do not contain this new change.

## Local UI-only patch

`scripts/package-audio-ui.py` consumes the privately retained delivered v0.6 bundle and constructs a guarded local-only patch. It verifies the bundle manifest/homepage hash and inserts just one new script reference, leaving the installed Settings bridge/CSS unchanged. Source scripts/adapter may be published; the generated package contains a vendor-derived homepage and must remain local, outside public repositories/releases.

Prepared artifact: `build/nimbus-audio-html5-ui-r1.tar`, SHA-256 **`9bc06350b3d54520b0f688100487c1737eea48c17325eef8c5511721b0fe9633`**.

- Expected current homepage: `4cc858e35b5a4bdf34b05926c7a8997f1eabf96376d1ba92d9a99145186c9966`.
- Patched homepage: `457f1244a7f017b080da0d475ef2c67752509f39b52f604fd34c6da98523b50b`.
- Private root staging required by installer: `/root/nimbus-audio-html5-r1`, owned root:root with mode 0700.
- New additive served asset: `/nimbus/data/fieldkit-audio-r1/audio-html5.js`.

Installer refuses a changed homepage or prior staging/assets, checks all package files, keeps the original index in private backups, installs/verifies the additive audio asset and atomically replaces the homepage. A partial attempt requires review, not blind rerun. Rollback verifies installed homepage/audio hashes and refuses later edits before restoring the exact baseline; unused additive assets/backups remain. It does not edit SSH keys/hooks, Settings assets, Wi-Fi, media data, partitions, vendor services or firmware. Installation still writes the live rootfs UI and is a separate user-run action; no installation has occurred.

## Validation and limits

The local Chromium fixture serves the original vendor assets plus the adapter without proxying to the drive. A synthetic one-second PCM WAV with spaces, `#` and uppercase extension loads via HTML5, reports metadata/duration, plays, seeks and pauses. The Music component has no Flash object/embed; simulated codec errors use the new guidance. Original navigation and Settings regression checks still pass. The fixture explicitly allows autoplay so its play test is not evidence of default mobile/browser autoplay permission.

Suite checkpoint: **134 tests run, 132 pass, 2 Node-dependent tests skipped** because Node is unavailable. Package fixture tests check guarded install/rollback, changed-homepage refusal and preservation of later edits. The complete browser test provides actual HTML5 WAV evidence; MP3/M4A/Ogg, full playlist/shuffle/repeat, mobile playback, vendor HTTP byte-range seeking and native device playback still require testing.

Host `/tmp` is full. Browser tests used a disk-backed scratch directory and explicit `NIMBUS_BROWSER_TMPDIR`; no unrelated retained files were deleted. Some older shell fixtures assume scratch paths have no spaces, so the full suite used `/home/jais/.cache/nimbus-offline-tests` rather than the space-containing project path.

No physical UI install, candidate image boot, remount, repair or flash has occurred for this change.
