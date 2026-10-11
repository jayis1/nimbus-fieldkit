# Original dashboard Music: HTML5-only UI installed, playback validation pending

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

## Guarded user-run UI installation

The temporary port-2225 connection has now passed a fresh existing-pin root login and writer inventory without observed writable root fds from the replacement listener/session. Both old management and vendor services remain running. This permits the separate requested UI patch to use that authenticated connection; it does not authorize the still-unreviewed root remount/handover.

Stream the exact local package directly to a **fresh private root stage**, verify its whole-archive hash on the drive **before extraction**, then run its guarded UI-only installer:

```sh
ssh -T -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/home/jais/.ssh/nimbus-test-known-hosts \
  -o HostKeyAlias='[172.16.10.178]:2224' \
  -o IdentitiesOnly=yes -i /home/jais/.ssh/nimbus-admin-ed25519 \
  -p 2225 root@172.16.10.178 '
set -eu
umask 077
stage=/root/nimbus-audio-html5-r1
[ "$(id -u)" = 0 ]
[ ! -e "$stage" ] && [ ! -L "$stage" ]
mkdir -m 700 "$stage"
cat > "$stage/package.tar"
printf "%s  %s\n" 9bc06350b3d54520b0f688100487c1737eea48c17325eef8c5511721b0fe9633 "$stage/package.tar" | sha256sum -c -
tar -xf "$stage/package.tar" -C "$stage"
sh "$stage/install.sh" install
' < '/home/jais/Projects/sandisk wifi dims/build/nimbus-audio-html5-ui-r1.tar'
```

This writes private root staging and the guarded homepage/audio UI assets on the live rootfs; it performs **no flashing, raw partition writes, service actions or mount changes**. Never bypass an archive/baseline hash refusal or rerun into a partial stage. No SFTP, HTTP media staging or host-key learning is involved. Preserve the existing Settings patch and keep both SSH listeners running. After successful installation, hard-refresh the original homepage and test an ordinary supported track; report playback/error behavior without posting credentials or private media. Independent served-asset verification and physical music playback remain pending.

## Live installation evidence

The user executed the guarded transfer/install through pinned port 2225. Reported whole-archive, package-file, live baseline, backup and final homepage checks passed; the installer completed. Agent read-only HTTP retrieval independently verified the served homepage matches the patched hash above and the served audio adapter matches current first-party source. The served Settings bridge (`9035367baf4d9ace5cc5f7d871700eb076ef11041c37b69af4cb8a7645bea138`) and CSS (`d1428615bd883030f5d11089aeb4a802eb0ca448c588e076baa9db53ac700164`) remain unchanged.

The UI patch is therefore **installed and served**, not merely an offline candidate. Browser playback on the physical drive, phone/codec coverage, playlist behavior and byte-range seeking remain pending. No agent browser authentication, media playback, Settings action, service stop, remount or flash was performed. Original homepage rollback material remains under private `/root/nimbus-audio-html5-r1/backups/`; guard against later homepage/audio edits before any rollback. The earlier inconsistent raw rootfs backup predates this UI patch and must not be described as current or restoration-tested. Existing v4 image artifacts remain unchanged and do not include this addition.

## Remaining startup Flash warning: exact controller fix prepared

The user still sees the Adobe Flash installation warning. A separate page-startup check in `/data/js/t4u.controller.js` displays the translated warning before Music is initialized; replacing Music's error handler alone did not cover it. Read-only HTTP verification confirmed that the live controller exactly matches the privately retained original, SHA-256 `7ba6554dd579ffb9d86ea20ed011ae083dbb50442820ff132751a219b1498d67`.

`scripts/package-flash-warning-fix.py` removes only that fingerprinted 391-byte startup block, retaining the rest of the controller and all navigation/upload/error handlers unchanged. It does not fake Flash detection or globally suppress device messages. The HTML5 Music adapter and useful playback failures remain intact. The custom-image builder now applies the same exact fix and records its source/adapter provenance for **future** builds; current v4 artifacts were not rebuilt. Standalone unified overlay generation still needs this separate controller fix alongside its HTML5 adapter.

Local-only candidate: `build/nimbus-flash-warning-ui-r1.tar`, whole-archive SHA-256 **`5b2fa15b740c42b2e86ce9122bc245b8cb189d145958108395cd6db9f03d3b06`**. Expected patched controller SHA-256: **`cad00ff693c6fa28dc0906c39ca85ae9679dec6851599833766b8a225d6e0c16`**. It contains a vendor-derived controller, so never redistribute the archive. Installer requires a fresh root-owned mode-0700 `/root/nimbus-flash-warning-r1` stage, verifies the exact original live hash, keeps a private original copy, atomically replaces only the controller and guards rollback against later edits. Partial staging must not be blindly rerun. Homepage, HTML5 adapter, Settings assets, services, mounts and firmware remain untouched by this fix.

Validation: **136 tests run, 134 pass, 2 Node-dependent skips**. The local Chromium browser fixture uses a Firefox user-agent to exercise the vendor's startup-check branch, confirms no Adobe/Flash-install warning text and still validates HTML5 WAV play/pause/seek plus original navigation/Settings. This is not native Firefox or device playback evidence. Installer fixture tests verify exact block removal, source preservation, backup/rollback and refusal to overwrite later controller edits. The targeted warning fix is **prepared, not installed**; its device/browser confirmation is pending. Hard-refresh after any successful install because the vendor script URL retains its old cache query.

Subsequent live result: the user executed the guarded warning-patch transfer/install through pinned port 2225; archive/package, live baseline, private backup and patched-controller checks all passed. Independent read-only HTTP verification confirmed the served controller hash `cad00ff693c6fa28dc0906c39ca85ae9679dec6851599833766b8a225d6e0c16` and absence of its obsolete warning/FlashDetect startup code. Homepage and HTML5 adapter hashes remain unchanged. The targeted warning fix is now **installed and served**. Its original controller remains privately backed up under `/root/nimbus-flash-warning-r1/backups/`. User hard-refresh confirmation and actual music playback remain pending; no services were stopped and no remount or firmware flash occurred.

Later user feedback briefly reported playback failure, then explicitly corrected it: playback still works. Independent read-only checks confirmed the installed audio adapter and upload-progress homepage/adapter hashes remained intact. Treat this as user-reported native playback success, not codec/mobile/playlist/seek certification. No playback-related fix or rollback was performed.
