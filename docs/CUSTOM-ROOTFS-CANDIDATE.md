# Custom SanDisk rootfs candidates — offline only

Latest local output: `build/nimbus-custom-rootfs-beta2/`, with private counterpart `.private-provisioning/drive-a-rootfs-beta2/`. See [beta delivery/test plan](BETA1-TEST-PLAN.md). Both remain NOT FLASHABLE; beta1 is retained unchanged. Earlier v4 startup/security evidence remains in [v4 hardening](OFFLINE-CANDIDATE-HARDENING.md); all prior artifacts are retained. The v1 evidence below is historical, not a current delivery recommendation.

Follow-up: [private offline SSH provisioning](OFFLINE-PROVISIONING.md) can create a separately staged per-device candidate under ignored `.private-provisioning/`. That candidate contains a private host key and must never be publicly redistributed. The original generic v1 remains unchanged. [Installed rescue review](RECOVERY-IMAGE-REVIEW.md) identifies the installed rescue in private backups and explains why the raw ext3 artifact is not a vendor update payload. Boot/recovery gates still block flashing.

Contains a 256 MiB ext3 rootfs filesystem image (`rootfs.ext3.candidate`), rootfs tar, separate staged GameHack source bundle, manifests/checksums and build/check logs. This is **not a vendor update container, not a full-disk image, and not flash-ready**. Do not rename it to nimbus.img, copy it to the vendor updater or write it with dd. Boot and disaster recovery are untested. No live drive, bootloader, partition or firmware updater was touched by the build.

## Included

- Clean hash-pinned vendor 3.04 rootfs, retaining vendor binaries, modules, charging/network scripts and original web handlers. Kernel/bootloader/rescue remain external and unchanged, not bundled as a new boot image.
- One unified stock homepage with dark/light theme, quick jump, FieldKit tools and the Settings sign-in/accessibility fix. No standalone v0.4/native dashboard page.
- Tested patched Dropbear 2026.94 binary, key-only, no forwarding/SFTP, wlan1-only management on 2224, with failure to bind an interface closing the socket.
- Telnet commented out in inetd; other inetd services retained.
- Persistent toolkit scripts staged into internal media only when mounted writable and no prior install exists. Existing media runtime/settings are not overwritten. Snapshot publication remains read-only and manual/boot-triggered, not an unauthenticated web shell.
- WPA2-AES mode in vendor defaults/first-use mode selection. Existing separate settings partition is not included or silently rewritten; active Wi-Fi security still requires provisioning and native verification.
- SD diagnostics and guarded legacy dashboard retirement helper. No forced SD writes, filesystem repairs or formatting. 128GB is already detected on the live drive; current read-only-mount cause remains unresolved.
- GameHack backup/restore/media/favorites/notebook/storage-doctor source bundle, kept separate because it targets the ARM64 handheld, not this ARMv7 device. No images/cards were deployed.

## Settings fix

Stock protected controls are gated by vendor web-admin login (`token`), independently of SSH. Original UI expects Enter in its password field. Added explicit Sign in calling the same vendor login routine, clear locked/unlocked text, locked styling and keyboard activation for enabled controls. Does not force tokens, remove authentication or store passwords. Destructive settings actions are not exercised by browser tests. Live click behavior still requires verification; authentication gating is a likely explanation, not proof that every reported click problem is resolved.

## Provisioning / privacy limits

Personal host/client private keys, Wi-Fi passphrases, backups, calibration and live settings are not imported. Shared vendor SSH host keys are removed. Root password fields in stock shadow/shadow-backup are locked in the candidate; other vendor accounts remain, and vendor account-sync behavior still needs auditing. Legacy kernel, HTTP/FTP and vendor factory settings are not magically made modern or private.

The generic image deliberately contains **no SSH host key or authorized_keys**. Before any permitted boot, a separately reviewed secure offline provisioning method must place a unique Ed25519 host key and public authorized_keys into `/etc/nimbus` and pin its host identity. Without provisioning, candidate SSH does not start and Telnet is disabled: **do not flash this image expecting access**. Early-boot entropy, reboot behavior, wlan1 availability and native operation are untested for the image even though the live installed SSH configuration passed reboot tests.

## Build

Run under fakeroot (no host root privileges), using reviewed inputs:

```
fakeroot python3 scripts/build-custom-image.py \
  --stock-rootfs /tmp/opencode/sandisk-fw-3-04/rootfs_nimbus_v3.04.tar \
  --ssh-binary /tmp/opencode/nimbus-ssh-review/dropbear-2026.94/dropbearmulti \
  --output build/nimbus-custom-rootfs-candidate-v1
```

Output directory must not exist. Builder validates vendor/binary hashes, archive paths/hardlinks, ownership and scripts, creates only regular output files and an ext3 image with conservative old-kernel feature flags, then runs `e2fsck -f -n` offline. No updater wrapper is generated. Checksums establish artifact integrity, not bootability or flash safety. Mkfs filesystem metadata is not currently guaranteed byte-reproducible across builds/tool versions; source scripts/input hashes are pinned in the manifest.

## Built artifact and validation

Current `rootfs.ext3.candidate` SHA-256: `e0abedc3751cf43acab22a6c07097dcd43b4d75c9aacbe1f97b57ae9e0820e72`. Exact size: 268435456 bytes. Read-only e2fsck completed all five passes with no errors. Filesystem features are limited to has_journal, filetype, sparse_super and large_file; 1024-byte blocks, 128-byte inodes, approximately 42 MiB free before reserved-space accounting. Compatibility on the actual old kernel remains untested.

All output SHA256SUMS checks pass. 78 SanDisk-project tests and 95 GameHack tests passed, including browser checks for explicit Settings sign-in, locked-control keyboard exclusion and enabled-control keyboard activation, vendor-module byte preservation, and read-only extraction of image UI/security files matching the rootfs archive. These do not validate live vendor web login, destructive settings actions, SSH provisioning, media hardware or firmware boot.

An earlier pre-validation image tree is retained at `build/nimbus-custom-rootfs-candidate-v1-pre-settings-validation/` for investigation, not delivery; the current delivery path is the one at the top of this document. No firmware or UI installer was executed on the device by this build; the live Settings panel has not yet received this change.
