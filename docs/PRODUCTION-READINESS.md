# Production readiness and public preview policy

The source-only preview `v0.1.0-preview.1` is a published **prerelease**, not a draft and not a production firmware image. The user selected public source/overlay assets rather than redistributing proprietary vendor-based rootfs contents. Full images and private provisioning material stay local. The preview does not contain a vendor update container or self-contained ARM toolchain.

Production-preparation source checkpoint: 84 local tests pass. GitHub Actions runs clean-checkout source tests on Python 3.11/3.13 plus shell syntax and tracked-file hygiene; image/browser tests that need unshipped local vendor inputs may skip there. Public assets identify the exact source commit and retain source-only/NOT FLASHABLE warnings. No hardware release gates are implied by CI success.

Offline provisioning/rescue follow-up: 90 local tests pass, including real host-key generation/uniqueness, permissions, tamper rejection and boot-image CRC fixtures. Clean CI skips the real key-tool test unless a trusted native Dropbear key utility is provided; key generation is not a hardware boot test. Existing source-preview downloads remain tied to their recorded earlier commits.

Current offline hardening work produced separate generic/private v4 candidates with rootfs-resident boot code, strict SSH key permissions, bounded archive checks and a selected-file policy report. **106 local tests pass**; integrity audits, inode metadata checks and read-only fsck passed for both builds. See [v4 hardening](OFFLINE-CANDIDATE-HARDENING.md). No spare test drive is available and recovery-console access is not established; neither v4 image is approved for native deployment.

## Current readiness gates

Latest local build: **[beta1 rootfs candidates and test plan](BETA1-TEST-PLAN.md)**, incorporating the latest Music/upload/icon/bottom-card UI. Generic and private 256MiB images passed offline integrity/policy/fsck; **144 tests run, 142 pass, 2 skips**. Neither image has been booted, restore-tested or packaged as an approved vendor update. Both remain local. v4 evidence below is historical, not evidence for beta1 native boot.

The user has accepted using the existing drive for a staged experimental trial despite the lack of a spare. See [experimental deployment preparation](EXPERIMENTAL-DEPLOYMENT.md). This changes the test-device plan, not the image's production/flash certification or the unproven recovery status. No firmware write has been performed.

| Gate | State | Required evidence |
| --- | --- | --- |
| Source regression | Latest recorded full workspace suite passes; clean-clone CI added | Source tests, shell syntax and tracked-file hygiene |
| Offline image integrity/policy | Passed for local generic/private beta1 builds; prior v4 retained | SHA-256 list, geometry, offline fsck, archive/image checks and vendor modules; not native boot evidence |
| Settings interaction | Basic live usability PASSED by user report; served hashes verified | User confirms Settings work after patch; not an exhaustive control/destructive-operation test |
| Live SSH/Telnet/WPA2 transition | User verified on installed device | Separate from candidate-image boot/provisioning |
| Secure provisioning | Offline SSH personalization implemented; native/Wi-Fi gates BLOCKED | Unique host keys, authorized clients, pinned identity, private configuration and tested access before removing fallback |
| Image boot and vendor behavior | BLOCKED | Native boot, charging, battery, media, AP/uplink, USB transitions and restart behavior |
| Recovery/restoration | Installed rescue located offline; fresh rootfs capture inconsistent; restore BLOCKED | Matching verified rescue route and successful restore; raw-backup checksums alone are insufficient; see [backup review](EXPERIMENTAL-DEPLOYMENT.md#physical-backup-review--2026-10-11) and [capture constraints](CONSISTENT-CAPTURE-REVIEW.md) |
| SD writes | Live writes, reboot/readback and both normal/writable-SD USB cycles PASSED; image policy pending | Boot/USB return restores SD ro; safe candidate mount policy and native-image validation remain unverified; see SD validation evidence |
| GameHack downstream pairing | BLOCKED | wlan0 policy plus pinned fresh handheld pairing/transfer; no global management exposure |
| Legacy services/accounts | BLOCKED | HTTP/FTP dependency and privacy review, account/reset behavior, logs and access restrictions |
| Vendor redistribution | BLOCKED | Applicable SanDisk/QSI/Tuxera and other binary license permissions |
| Deployment/update path | BLOCKED | Reviewed format/partition preservation, abort behavior, power-loss and rollback considerations |
| Two-part Android/iOS companion | Planned, not implemented | Independently paired GameHack/SanDisk APIs, optional shared workflows, real-device client tests, signing/distribution and compatibility matrix |

`python3 scripts/audit-image-readiness.py build/nimbus-custom-rootfs-candidate-v4` produces a read-only integrity/blocker report. Exit 2 means artifacts pass integrity but are not release/flash approved; exit 1 means invalid/mismatched artifacts. The script never turns mutable manifest booleans into a hardware certification and never flashes or mounts anything.

## Public preview assets

The user additionally requested **one two-part Android/iOS companion for both GameHack Zero and SanDisk** for the production release track. See [mobile companion apps](MOBILE-COMPANION-APPS.md). GameHack must work independently of the optional drive; shared workflows require both devices' explicit authorization and verified capabilities. This is planned work, not an official vendor app update or an already deployed mobile backend. It must not weaken current SSH/vendor-service restrictions or change Pi USB networking.

Publish first-party source/customization overlays, checksums, build instructions and these explicit limits. Do not include vendor stock rootfs, extracted web assets, proprietary binaries, firmware blobs, calibration, private keys or settings backups. GitHub's source archives and a source-preview bundle are source downloads, **not** an installable firmware image.

Existing feature wrappers in this repository include legacy integration code. The newer GameHack library lives in the associated staging tree; it is not silently represented as already deployed or bundled in every source archive.

## Next live input

### UI-only Settings patch

`device/unified/install-settings-fix.sh` is a reviewed source helper for the exact delivered v0.6 bridge/CSS baseline. Packaging substitutes the correct v0.6 asset prefix and includes script/assets checksums. Installer verifies baseline hashes, keeps private root-stage backups, replaces only two assets with verified temporary files and leaves homepage/runtime/network/services untouched. Rollback requires the installed assets still match the patch; later user edits are not overwritten. A partial install is not an invitation to rerun: original asset backups remain and require review.

The user executed the guarded r1 package install from `/root/nimbus-settings-fix-r1`. Reported checks passed for the copied archive, packaged files, original live baseline and private backup assets. The installer reported successful completion. Agent read-only HTTP checks independently verified the served patched bridge/CSS against the package, and verified `/data/index.html` remains identical to the shipped unified v0.6 homepage. No browser authentication or Settings action was performed by the agent.

| Live asset | SHA-256 after patch |
| --- | --- |
| `fieldkit-v06/bridge.js` | `9035367baf4d9ace5cc5f7d871700eb076ef11041c37b69af4cb8a7645bea138` |
| `fieldkit-v06/stock-dark.css` | `d1428615bd883030f5d11089aeb4a802eb0ca448c588e076baa9db53ac700164` |

Private original asset copies remain under `/root/nimbus-settings-fix-r1/backups`. Guarded rollback, only if needed and after review: `sh /root/nimbus-settings-fix-r1/install-settings-fix.sh rollback`. No rollback has been performed. Package installation is not proof of actual browser sign-in/click behavior.

Following the requested hard-refresh, explicit web-admin sign-in and non-destructive dialog checks, the user reported: **"yes settings work now"**. This establishes user-reported basic live Settings usability after the patch. No per-control test matrix was supplied, and no reset, format, firmware upgrade or saved network change is represented as tested. The candidate image's native Settings behavior remains part of its separate boot/vendor-functionality gate.

Real web-admin login is still required. Testing the patched live page must not involve format/reset/firmware upgrades; use non-destructive navigation and Settings dialogs only.

Earlier SD evidence showed `texfat ro` after USB gadget unload, despite block read-only flags being zero. Vendor automount code does not explicitly request ro in the reviewed path; boot detection reported ro. Subsequent user-run non-forced remount and bounded write/readback passed; see [SD validation](SD-VALIDATION.md). Do not patch a presumed capacity limit or force read-only flags clear. Never call the automount script as a diagnostic: its exFAT fallback invokes an automatic checker.

User follow-up: SD data is considered disposable and backup is declined. Card unlocked state is probable, not confirmed. This removes the data-backup prerequisite for a separately guarded bounded write test, not the exclusive-ownership, lock-state or mount-policy checks. No format, repair, forced remount or firmware flash has been performed or implied.

See [offline provisioning](OFFLINE-PROVISIONING.md) for private SSH personalization. Generic public images never acquire a shared host private key. Personalizing an offline image does not certify native boot, network access or recovery.

See [installed rescue review](RECOVERY-IMAGE-REVIEW.md): a CRC-consistent `Nimbus-rescue-V1.0.6` image was located in the verified private boot backup. Static inspection confirms the default updater formats/extracts a rootfs tar and has dangerous repartition/write-failure paths. No rescue/updater was executed. A private provisioned 256 MiB candidate has been built and passed integrity, archive/image key-content and archive root-ownership checks; it remains local, non-flashable and not production-ready.

No production release date is promised. No new flashing, filesystem repair, radio changes or service retirement is authorized by CI or by publishing a preview.

Latest deployment follow-up: [pinned beta1 chain review](DEPLOYMENT-CHAIN-REVIEW.md) is complete for the selected rescue/updater/hooks, with the unchanged vendor path rejected. Deployment/recovery gates remain blocked, not silently promoted. A fresh read-only writer/listener/power checkpoint is prepared; no hardware output or handover/remount/flash is implied.

The subsequent beta2 build adds the original decorative desktop buddy; generic/private image integrity and builder offline fsck/policy checks passed. **150 tests run, 148 pass, 2 skips** (fixture host sync isolated). See [beta revisions](BETA1-TEST-PLAN.md). Native deployment, recovery, persistent SD policy and redistribution remain blocked. Physical-device workflows/buddy are not a Virtual Nimbus purchase gate; companion access notes remain in the separate app repository.
