# Nimbus beta1 — local offline image and production qualification plan

## Delivery status

Built at implementation checkpoint `e50f628`, with exact input/overlay hashes recorded in each `BUILD-MANIFEST.json`. **Beta1 is an offline rootfs candidate, not an installable vendor firmware update, not flash-approved and not production-ready.** No live image deployment occurred. Old v4 images and backups are retained unchanged.

| Variant | Local image path | SHA-256 |
| --- | --- | --- |
| Generic, no personal SSH keys | `build/nimbus-custom-rootfs-beta1/rootfs.ext3.candidate` | `8b35a3aa55d6df7013f7f8a0bd2e86bf1be818b3e8eb55e993fe8be26881e278` |
| Private, provisioned for drive-a | `.private-provisioning/drive-a-rootfs-beta1/rootfs.ext3.candidate` | `3c602f779a15a6906a3796adfb8101aa5c59d38296d53e332fde3566580d382c` |

Each image is **268435456 bytes (256 MiB)**. Each directory includes `rootfs.tar`, build/policy manifests, checksums, read-only fsck/mkfs logs, UI bundle, separate GameHack source bundle and `NOT-FLASHABLE.txt`. These are rootfs-only build artifacts: kernel, bootloader, rescue, settings/calibration and media partitions remain external.

**Both variants stay local:** the generic image also contains vendor components with unresolved redistribution rights. The private variant additionally contains its previously generated unique offline host identity and the selected client public key, validated by the trusted host Dropbear utility. It does not copy the live host private key or generate a shared tester key. Its offline identity differs from the running drive; native pairing/pinning must be reviewed before a boot trial. Generic SSH cannot start without provisioning, and Telnet is disabled; never deploy the generic image expecting management access. No private credentials, backups or vendor-based images are published.

## Included changes

- Vendor 3.04 rootfs/services/modules/API handlers preserved, with v4 rootfs-resident boot helpers and fail-closed key-only wlan1 management.
- Integrated original homepage, Settings sign-in/accessibility fix, dark/light theme and optional FieldKit feature controls; no separate hosted dashboard or arbitrary-execution web endpoint.
- HTML5 Music adapter and exact obsolete startup Flash-warning removal.
- Real XHR multipart upload percentage, explicit 100%-sent/awaiting-device distinction, cancel/error handling and unchanged device upload endpoint.
- Theme-aware FieldKit toolbox icon and bottom-right upload card, raised above the visible vendor music bar.
- Existing SD startup/USB-return policy preserved. **No automatic writable remount:** the live temporary SD remount is not a persistent beta-image feature. Supporting both writable storage destinations across reboot remains separate policy/ownership work.
- Separate GameHack source integration bundle; no handheld deployment or Android/iOS implementation is implied.

## Offline evidence

Both images passed builder and independent `e2fsck -f -n` checks (exit 0), complete artifact integrity audits, selected rootfs policy checks and vendor module inventory/content comparison. Independent image inode inspection confirmed root:root 0700 for startup helper, management binary and provisioning directory. Regression tests compare archived UI and security files with bytes read from the actual ext3 images; private key comparisons do not print key content.

Latest full suite: **144 tests run, 142 pass, 2 Node-dependent skips**. Beta-specific regression verifies latest CSS/audio/progress source bytes and source-manifest hashes, script inclusion, warning removal, generic/private key scope, archive ownership/modes and false flash/boot/recovery gates. Local browser tests cover generated WAV playback, upload multipart/progress/cancel/error, layout, themes and original navigation/Settings. These do not certify the vendor backend, native image boot or restoration.

Latest live CSS was independently verified over read-only HTTP as `3f79ca2d9923e06615bde777fb71d2f8aa73bd05de1e1e9aeb464fb8149a6886`; the user described the update as perfect. Music playback was confirmed by the user after correcting a brief failure report, and SD uploading was reported to appear functional after the temporary non-forced remount. These are **installed-firmware** observations, not beta-image test results.

Read-only integrity audit (expected exit **2** = intact but not approved):

```sh
python3 scripts/audit-image-readiness.py build/nimbus-custom-rootfs-beta1
python3 scripts/audit-image-readiness.py .private-provisioning/drive-a-rootfs-beta1
```

The mutable manifest cannot certify native hardware or licensing. Do not rename this ext3 image to a vendor `.img`, feed it to the updater, boot rescue as a diagnostic, or raw-write it with `dd`.

## Before any native beta trial

1. **Current, consistent rollback capture:** retain all original backups; the fresh live raw rootfs capture is inconsistent and its journal-reviewed copy failed full checking. It is not a restoration image. Review bounded writer/SSH handover and non-forced root read-only capture separately; no root freeze/remount/service-stop authorization comes from this build. See [capture review](CONSISTENT-CAPTURE-REVIEW.md).
2. **Recovery/restoration:** independently establish the exact installed-device recovery entry and matching restore route. Rescue currently auto-invokes a destructive updater; it is not a passive rescue shell. No guaranteed recovery is available and the only drive could be bricked.
3. **Deployment chain:** review the entire vendor wrapper/rescue updater, not merely a rootfs payload. Enumerate partition preservation, firmware-pool/environment writes, fallbacks, hook behavior, failure/abort and rollback routes. A safe package does not cancel earlier updater side effects.
4. **Power and management:** arrange stable external power without simultaneous USB media ownership; recheck geometry/USB state, private image identity/client pairing, wlan1 availability and exact artifact hash. Battery-only preflight is not stable-power evidence.
5. **Separate trial approval:** review exact operations, expected duration, interruption risks and limits of recovery before a write. Current deliverables contain no deployment command or approved updater container.

## Native beta test matrix — all pending for this image

Record image hash, hardware identity (privately), power, steps, expected/actual outcome and sanitized evidence. Never publish keys, passphrases, private media or complete network traces. Stop on unexpected partition/identity changes, I/O errors, failed access or corruption; do not stack another unreviewed flash on a failed trial.

| Area | Tests / acceptance evidence |
| --- | --- |
| Boot and management | Cold boot/reboot, expected pinned new identity, authorized login and rejected wrong keys, wlan1-only listener, no Telnet, no boot script execution from media |
| Vendor functionality | AP/uplink, preserved credentials/settings, charging/battery, original media views and non-destructive Settings dialogs |
| Storage | Internal/128GB SD detected together; small disposable upload to each under approved ownership/mount state; saved-content hash/readback; preserve SD lock and ro-default behavior |
| Upload | Single/multiple files, Unicode/spaces, aggregate byte percentage, 100% awaiting confirmation, recognized/unknown device responses, interrupted network and cancel without false success; check partial files before retry |
| Music | Supported MP3/WAV/M4A/Ogg samples, play/pause/seek, playlist/shuffle/repeat, unsupported-codec original-file fallback, phone user gestures; no Flash warnings |
| UI | Toolbox icon, bottom card and reachable Cancel, visible music-bar clearance, light/dark, narrow viewport, reduced motion |
| USB ownership | Approved outbound/return transition, no simultaneous host/device writes, preserved marker readback and no silent writable-lock override |
| FieldKit / GameHack | Persistent ON/OFF flags, original homepage retained, independent Pi USB-worker behavior, optional paired queue workflows; no monitor-mode features |
| Restore | Verified matching restoration and post-restore boot/data/settings identity evidence; boot success alone is insufficient |

## Production promotion

Require native matrix results, matching recovery/failure-path evidence, secure provisioning/reset behavior, legacy-service/account/privacy review, vendor license/redistribution permission, and the safe writable-SD policy if persistent dual-destination writes are promised. GameHack pairing and companion-app implementation need their own acceptance evidence. Fixes require newly named images/hashes and appropriate regression/retest; do not relabel this artifact production based on UI success. Public distribution remains source/overlays only until redistribution and deployment gates pass.
