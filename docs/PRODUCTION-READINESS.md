# Production readiness and public preview policy

The source-only preview `v0.1.0-preview.1` is a published **prerelease**, not a draft and not a production firmware image. The user selected public source/overlay assets rather than redistributing proprietary vendor-based rootfs contents. Full images and private provisioning material stay local. The preview does not contain a vendor update container or self-contained ARM toolchain.

Production-preparation source checkpoint: 84 local tests pass. GitHub Actions runs clean-checkout source tests on Python 3.11/3.13 plus shell syntax and tracked-file hygiene; image/browser tests that need unshipped local vendor inputs may skip there. Public assets identify the exact source commit and retain source-only/NOT FLASHABLE warnings. No hardware release gates are implied by CI success.

Offline provisioning/rescue follow-up: 90 local tests pass, including real host-key generation/uniqueness, permissions, tamper rejection and boot-image CRC fixtures. Clean CI skips the real key-tool test unless a trusted native Dropbear key utility is provided; key generation is not a hardware boot test. Existing source-preview downloads remain tied to their recorded earlier commits.

## Current readiness gates

| Gate | State | Required evidence |
| --- | --- | --- |
| Source regression | Latest recorded full workspace suite passes; clean-clone CI added | Source tests, shell syntax and tracked-file hygiene |
| Generic offline image integrity | Passed for local v1 | SHA-256 list, geometry, offline fsck |
| Settings interaction | Local browser tests pass; live update pending | Real web-admin login and supported non-destructive controls |
| Live SSH/Telnet/WPA2 transition | User verified on installed device | Separate from candidate-image boot/provisioning |
| Secure provisioning | Offline SSH personalization implemented; native/Wi-Fi gates BLOCKED | Unique host keys, authorized clients, pinned identity, private configuration and tested access before removing fallback |
| Image boot and vendor behavior | BLOCKED | Native boot, charging, battery, media, AP/uplink, USB transitions and restart behavior |
| Recovery/restoration | Installed rescue located offline; restore BLOCKED | Matching verified rescue route and successful restore; raw-backup checksums alone are insufficient |
| SD writes | BLOCKED | Important-data backup, lock state, exclusive ownership, diagnosed mount policy, explicit tiny verified write/readback |
| GameHack downstream pairing | BLOCKED | wlan0 policy plus pinned fresh handheld pairing/transfer; no global management exposure |
| Legacy services/accounts | BLOCKED | HTTP/FTP dependency and privacy review, account/reset behavior, logs and access restrictions |
| Vendor redistribution | BLOCKED | Applicable SanDisk/QSI/Tuxera and other binary license permissions |
| Deployment/update path | BLOCKED | Reviewed format/partition preservation, abort behavior, power-loss and rollback considerations |

`python3 scripts/audit-image-readiness.py build/nimbus-custom-rootfs-candidate-v1` produces a read-only integrity/blocker report. Exit 2 means artifacts pass integrity but are not release/flash approved; exit 1 means invalid/mismatched artifacts. The script never turns mutable manifest booleans into a hardware certification and never flashes or mounts anything.

## Public preview assets

Publish first-party source/customization overlays, checksums, build instructions and these explicit limits. Do not include vendor stock rootfs, extracted web assets, proprietary binaries, firmware blobs, calibration, private keys or settings backups. GitHub's source archives and a source-preview bundle are source downloads, **not** an installable firmware image.

Existing feature wrappers in this repository include legacy integration code. The newer GameHack library lives in the associated staging tree; it is not silently represented as already deployed or bundled in every source archive.

## Next live input

### UI-only Settings patch

`device/unified/install-settings-fix.sh` is a reviewed source helper for the exact delivered v0.6 bridge/CSS baseline. Packaging substitutes the correct v0.6 asset prefix and includes script/assets checksums. Installer verifies baseline hashes, keeps private root-stage backups, replaces only two assets with verified temporary files and leaves homepage/runtime/network/services untouched. Rollback requires the installed assets still match the patch; later user edits are not overwritten. A partial install is not an invitation to rerun: original asset backups remain and require review. This patch has not been executed on the device by the agent.

Real web-admin login is still required. Testing the patched live page must not involve format/reset/firmware upgrades; use non-destructive navigation and Settings dialogs only.

SD remains `texfat ro` after USB gadget unload, despite block read-only flags being zero. Vendor automount code does not explicitly request ro in the reviewed path; boot detection previously reported ro. Do not patch a presumed capacity limit or force a remount. Confirm card/adapter lock state and important-data backup, then inspect SD-specific sensor/mount evidence. Never call the automount script as a diagnostic: its exFAT fallback invokes an automatic checker.

User follow-up: SD data is considered disposable and backup is declined. Card unlocked state is probable, not confirmed. This removes the data-backup prerequisite for a separately guarded bounded write test, not the exclusive-ownership, lock-state or mount-policy checks. No format, repair, forced remount or firmware flash has been performed or implied.

See [offline provisioning](OFFLINE-PROVISIONING.md) for private SSH personalization. Generic public images never acquire a shared host private key. Personalizing an offline image does not certify native boot, network access or recovery.

See [installed rescue review](RECOVERY-IMAGE-REVIEW.md): a CRC-consistent `Nimbus-rescue-V1.0.6` image was located in the verified private boot backup. Static inspection confirms the default updater formats/extracts a rootfs tar and has dangerous repartition/write-failure paths. No rescue/updater was executed. A private provisioned 256 MiB candidate has been built and passed integrity, archive/image key-content and archive root-ownership checks; it remains local, non-flashable and not production-ready.

No production release date is promised. No new flashing, filesystem repair, radio changes or service retirement is authorized by CI or by publishing a preview.
