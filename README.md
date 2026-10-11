# Nimbus FieldKit

### One SanDisk homepage. An optional GameHack companion. A safer field toolkit.

Nimbus FieldKit repurposes the **SanDisk Connect Wireless Media Drive** as an optional Wi-Fi gateway, shared-storage device, and field node for the **GameHack Zero** ecosystem.

The project retains the vendor's file browser, media views, uploads, and administration interface while integrating a dark-mode toolkit into the **original homepage**. GameHack provides controller-first interaction and application execution; the Pi Zero W remains a separate USB worker.

**This is an independent development project—not an official SanDisk firmware release or a supported security upgrade.**

**Public preview:** [v0.1.0-preview.1](https://github.com/jayis1/nimbus-fieldkit/releases/tag/v0.1.0-preview.1) is a source/customization-overlay prerelease, **not an installable firmware image**. Full vendor-based rootfs images remain local pending redistribution and deployment review. See [production readiness](docs/PRODUCTION-READINESS.md).

> [!WARNING]
> The custom filesystem image is an **offline candidate only**. It has not been boot-tested, is not a vendor firmware-update container, and must not be flashed. A valid checksum or clean filesystem check does not establish bootability or recoverability.

> [!IMPORTANT]
> There are three distinct components: a localhost development dashboard, a native SanDisk toolkit/unified homepage, and staged GameHack enhancements. Their capabilities, dependencies, and validation status are different. None should be represented as an interchangeable finished product.

---

## Contents

- [Project goals](#project-goals)
- [Architecture and device roles](#architecture-and-device-roles)
- [Current status](#current-status)
- [Unified SanDisk homepage](#unified-sandisk-homepage)
- [Native toolkit and persistent switches](#native-toolkit-and-persistent-switches)
- [Optional GameHack enhancements](#optional-gamehack-enhancements)
- [Security model](#security-model)
- [128GB SD-card status](#128gb-sd-card-status)
- [Run the localhost prototype](#run-the-localhost-prototype)
- [Native packaging and installation boundaries](#native-packaging-and-installation-boundaries)
- [Custom rootfs image candidate](#custom-rootfs-image-candidate)
- [Testing and validation](#testing-and-validation)
- [Repository layout](#repository-layout)
- [Documentation index](#documentation-index)
- [GitHub and GitHub Pages](#github-and-github-pages)
- [Roadmap](#roadmap)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Licensing and acknowledgments](#licensing-and-acknowledgments)

## Project goals

1. **Keep the working vendor functionality.** Preserve file/media browsing, uploads, network setup, battery support, charging, and established device services unless a specific reviewed change is required.
2. **Use one device interface.** Enhance the original homepage rather than requiring a separate dashboard, iframe, or replacement operating environment for ordinary tasks.
3. **Make the SanDisk optional.** GameHack and its Pi worker must remain useful when the drive is disconnected.
4. **Keep operations explicit and reversible.** Prefer checksums, previews, exclusive file creation, bounded diagnostics, backups, and guarded installation over silent background changes.
5. **Separate permissions from execution.** Turning a toolkit feature ON allows a supported explicit action; it does not launch a daemon or rewrite vendor networking.
6. **Protect real access before removing old access.** Verify pinned key-only SSH, independent sessions, and reboot behavior before retiring Telnet.
7. **Report evidence honestly.** A staged implementation, host test, device test, and verified recovery procedure are different milestones.

### Explicit non-goals

- Monitor-mode, packet-injection, or deauthentication features in this toolkit.
- Adding NFC, Sub-GHz, or IR hardware through software.
- An unauthenticated browser shell or arbitrary remote-command API.
- Internet-exposed device administration.
- Automatic formatting, filesystem repair, firmware flashing, or partition changes.
- Replacing the Pi's USB-worker role with the SanDisk.
- Claiming that modern SSH fixes the device's old kernel and vendor libraries.

## Architecture and device roles

### Intended Internet path

```text
Phone hotspot
     │
     │ WPA2/CCMP uplink
     ▼
SanDisk Connect Wireless Media Drive
     │
     │ WPA2/CCMP access point + optional shared storage
     ▼
GameHack Zero handheld
     │
     │ Existing, separately paired USB Ethernet/SSH link
     ▼
Pi Zero W companion worker
```

The hotspot-to-SanDisk and SanDisk-to-client links have been investigated independently. **The complete GameHack/Pi topology is not yet hardware-validated.** Pi Internet forwarding is separate future work; this project does not silently enable it.

| Component | Responsibility | Not its responsibility |
| --- | --- | --- |
| SanDisk | Optional Wi-Fi gateway, stock file/media services, storage, native telemetry and toolkit scripts | Running GameHack's ARM64 applications, becoming the Pi worker, or guaranteeing private storage on stock shares |
| GameHack | Controller UI, coding frontend, media decoding/playback, reviewed backups and user interaction | Requiring the SanDisk for every application or silently rewriting the Pi USB profile |
| Pi Zero W | Existing pinned-SSH USB worker, job queue and results | Replacing the SanDisk gateway or accepting unverified pairing |
| Management computer | Development, testing, checksum verification, pinned SSH administration and private backups | Treating ordinary USB media access as a firmware-flashing interface |

### Network boundaries

The stock SanDisk AP uses `192.168.11.1`. GameHack's existing Pi USB network is separate, typically `192.168.77.0/24` in the associated project.

The tested custom SSH listener uses **TCP 2224**, bound to **`wlan1`**, the hotspot-facing interface. A handheld connected through the SanDisk AP on **`wlan0` does not automatically have that SSH access**. A reviewed downstream access policy and fresh device pairing are still required.

Do not assume a development unit's DHCP address is permanent. Find the current address through the hotspot/router, and verify the expected pinned host identity when reconnecting.

## Current status

The following records the development checkpoint, not a guarantee for another drive or a future release.

| Area | Status and evidence | Remaining boundary |
| --- | --- | --- |
| Native toolkit | Installed and exercised on the development drive; persistent switches and capability gates work | Each operation still requires its supported dependencies and explicit invocation |
| Unified homepage | User reported successful v0.5 installation; exact homepage hash was checked; v0.6 enhancement was subsequently delivered | Not every vendor workflow has a complete live regression test |
| Standalone v0.4 dashboard | Old entry-point page retired by the user after a verified private backup | Older runtime/settings/assets were deliberately preserved; browser caches may retain the page |
| Custom SSH | Patched Dropbear 2026.94, public-key login, pinned host key, independent sessions and reboot startup verified by the user | `wlan1` only; image provisioning and GameHack pairing are separate |
| Telnet | Persistent inetd entry disabled; no port-23 listener in the supplied post-reboot checks | Other legacy services and vendor account behavior still need review |
| Wi-Fi encryption | User verified AP CCMP-only operation and WPA2-PSK/CCMP hotspot uplink after reboot | Unique passphrase strength and full client/forwarding behavior are separate checks |
| Settings usability fix | Guarded live patch installed; served hashes verified; user reports Settings working | Basic live usability confirmed, not an exhaustive control test or native candidate-image validation |
| GameHack library | Backup/restore, mounted media, favorites, notes, switches and storage doctor implemented in the associated staging tree | Not deployed to a handheld card or validated with native playback |
| 128GB SD card | Full card detected at about 119GiB; block device and partition later report writable | Filesystem remains mounted read-only; actual write operation remains unresolved |
| Custom rootfs image | 256MiB ext3 candidate built; offline filesystem check and artifact checksums pass | No native boot, verified rescue/restoration, or vendor update package |

### Test checkpoints

- **78 SanDisk-project tests passed** at the latest image/UI checkpoint.
- **95 GameHack tests passed** in an isolated host test environment.
- Browser coverage uses **local fixtures**, not a proxy to live device APIs.
- Those counts describe the recorded checkpoint; run the suites for the current checkout.

## Unified SanDisk homepage

### One interface, not a side dashboard

The integration starts from a reviewed copy of the stock homepage. It preserves the original element IDs, script order, jQuery handlers, and vendor API wiring while adding a stylesheet and a **FieldKit / tools** entry.

The toolkit is isolated with **Shadow DOM**, not an iframe. Stock navigation and toolkit navigation remain on the same page.

### Retained vendor screens

- Files, folders, and upload controls.
- Photos, videos, music, and associated media views.
- Stock device/network settings and administration dialogs.
- Existing help and vendor UI handlers.

Keeping a handler does not certify its safety: **format, reset, and firmware upgrade remain destructive vendor operations** and are not exercised as routine dashboard tests.

### Enhancements

- Dark theme with an optional light theme.
- Global theme control available outside FieldKit.
- Quick-jump search: **Ctrl+K / Command+K**.
- Same-page Overview, Switches, Network, Vault & sync, Docs & Pi, and Security tabs.
- Native snapshots with feature state, capability reasons, storage, routes and available battery information.
- Browser actions that **prepare commands for an authorized terminal**, rather than executing them through a public web endpoint.
- Polling pause while stock screens are active or the browser tab is hidden.
- Retry handling when toolkit assets fail to load.
- Security-transition guidance that distinguishes completed checks from unverified prerequisites.

### Settings panel and web login

Stock administrative settings are protected by a **vendor web-admin session**. SSH login is a different authentication path and does not unlock these controls.

The staged usability fix adds:

1. A visible **Sign in** button next to the original web-admin password field.
2. The same vendor login routine used by the stock interface—no substitute backend or authentication bypass.
3. Explicit locked/unlocked status text.
4. Clear styling for unavailable controls.
5. Keyboard activation and focus visibility for supported, enabled actions.

Passwords are not saved by the enhancement. A visible row does not mean the action is authorized or available. The fix does not make protected actions work without a valid vendor session.

See [Unified dashboard](docs/UNIFIED-DASHBOARD.md), [v0.6 enhancements](docs/UNIFIED-ENHANCEMENTS.md), and [Custom rootfs candidate](docs/CUSTOM-ROOTFS-CANDIDATE.md).

## Native toolkit and persistent switches

Native operation uses shell scripts and an atomic JSON snapshot publisher, not the localhost Python server.

Feature settings are validated plain ON/OFF files in `.settings` beside the installed scripts. **They are never sourced or evaluated as shell code.** Fresh settings default OFF; migration imports only validated feature flags, not credentials or arbitrary configuration.

| Switch | Supported behavior | Important limits |
| --- | --- | --- |
| `network_health` | Read routes and interface counters | Not proof that the phone hotspot or Internet is reachable |
| `watchdog` | Bounded foreground repeated reports | Requires network health; does not reconnect or reset radios |
| `speed_tests` | Explicit bounded iperf client | Requires compatible iperf/iperf3 and an authorized target; unavailable on the tested drive |
| `backup_vault` | Explicit single-file vault copy with SHA-256 verification | Native limit is 64MiB; no recursive backup or overwrite |
| `offline_toolbox` | Read bundled documentation | No Internet required |
| `storage_alerts` | Report free space and low-space warning | Does not delete or clean files |
| `file_sync` | Explicit single-file copy to existing local/mounted storage | No automatic mounts or insecure transfer fallback |
| `pi_jobs` | Gate for a future securely paired native integration | Native enable refused without supported pairing; GameHack's existing Pi client stays separate |
| `local_git` | Create a new named bare repository when Git exists | Git unavailable on the tested drive; no network fetch or hook execution |
| `encrypted_archives` | Store reviewed pre-encrypted `.age`/`.gpg` files | Does not perform encryption or prove ciphertext authenticity |

Turning a switch ON **does not start a service**. Missing capabilities are explained and refused rather than presented as working.

### Example: explicit native operations

Run from the verified native installation directory, not a guessed path:

```sh
sh nimbus-agent.sh settings show
sh nimbus-agent.sh settings set network_health on
sh nimbus-agent.sh settings run network_health

sh nimbus-agent.sh settings set watchdog on
sh nimbus-agent.sh settings run watchdog 12 10
sh nimbus-agent.sh settings set watchdog off
```

For snapshot publication:

```sh
sh nimbus-dashboard.sh snapshot
```

The native snapshot publisher also has a bounded `watch` mode. Its bounds differ from the agent's diagnostic watchdog; consult the script help and [switch documentation](docs/TOGGLES.md) rather than treating them as one daemon.

Persistent ON state is not an autostart instruction. Finite file copies are not forcibly killed halfway through a write when their permission flag changes.

## Optional GameHack enhancements

The enhanced controller module is staged in the associated **GameHack Zero** project. Its source bundle is included alongside the custom image candidate; it is **not installed as an ARMv7 application on the SanDisk**.

### Versioned backup and verified restore

- Explicitly choose **one reviewed file**: a save, project export, field report, or Pi result.
- Stream the copy instead of reading an entire large file into memory.
- Support files up to **8GiB** in this GameHack library implementation.
- Create a new version directory for each backup.
- Record size, timestamp, and SHA-256 metadata.
- Verify the destination by reading it back.
- Preview and verify a backup before restoration.
- Restore to a **new filename only**, never overwrite an existing file.

The 8GiB GameHack-library limit is not the 64MiB limit of the older host/native helpers. Bulk directory snapshots, automatic retention, deletion policies, and remote transfers are not implemented by this batch.

### Media, favorites, and offline notes

- Browse a selected existing local/mounted library directory.
- Index supported music/video extensions with a 2,000-entry inspection bound.
- Play local files through GameHack's controller-aware mpv wrapper.
- Disable yt-dlp and external references for the local-playback path.
- Store root-scoped favorites with play/remove actions.
- Write and read small offline notes stored locally on the handheld.
- Independently toggle backups, media, favorites, and notebook features.
- Inspect mount type, read-only status, capacity and free space without performing a write test.

Notes are not silently uploaded to a public media share. The library does not automatically mount SanDisk storage or retrieve a remote HTTP directory listing.

### Relationship to newer GameHack media features

The associated GameHack staging tree also contains YouTube search/player, Jellyfin direct-play, and improved controller coding input. Nimbus complements these with storage and gateway roles; it does not turn the old SanDisk into a Jellyfin server or video transcoder.

Native display/audio handoff, codec support, Wi-Fi throughput, and real playback remain hardware-validation tasks. The Pi USB queue retains its existing independent pairing and execution path.

See [GameHack optional enhancements](docs/GAMEHACK-OPTIONAL-ENHANCEMENTS.md).

## Security model

### Verified live improvements

The development unit's administration transition included:

1. Restricting exposed legacy SSH private-key permissions as initial containment.
2. Building a maintained Dropbear candidate for the old ARM platform.
3. Disabling server password/PAM authentication, forwarding, and SFTP in that build.
4. Generating a unique device host key and a dedicated management-client key.
5. Pinning the host key before connection.
6. Testing independent root/public-key sessions and password-auth rejection.
7. Testing a patch that refuses to listen when interface binding fails.
8. Installing backed-up startup integration and verifying it after reboot.
9. Trialing Telnet retirement with timed restoration before making it permanent.
10. Verifying WPA2-CCMP operation after a separate controlled radio-setting change.

These are **specific improvements**, not proof that the entire drive is secure.

### Remaining risks

- Legacy Linux kernel and vendor libraries remain.
- Stock HTTP administration does not provide TLS confidentiality.
- FTP and other services have not all been retired or dependency-audited.
- Vendor account-sync, reset behavior, and factory settings need further review.
- Files on stock media shares can be readable despite `chmod` or `umask`.
- SSH port reachability is not authenticated device identity.
- Root access is broad privilege, not a narrowly scoped application API.
- A host pin originally obtained through Telnet inherits the trust limitations of that provisioning channel.
- Full disaster recovery and firmware restoration remain untested.

### File-transfer boundary

The custom Dropbear build excludes SFTP. Modern OpenSSH `scp` commonly uses SFTP by default, so **do not assume ordinary scp will work** or silently fall back to FTP/Telnet.

A reviewed authenticated transfer method remains future integration work. The current GameHack library operates on an explicitly selected existing local/mounted directory or reviewed local mirror.

### Private data

Never put these in public media shares, repository commits, screenshots, or release assets:

- Client or server private keys.
- Wi-Fi passphrases, vendor passwords, provider credentials, or session tokens.
- Raw settings/rootfs backups and private device logs.
- Unreviewed captures, project exports, personal files, or Pi job results.

Encrypt sensitive archives on a maintained management computer or GameHack environment before placing them on shared media. Secret-file exclusions are guardrails, not complete secret detection. SHA-256 catches mismatches but cannot authenticate a backup if an attacker can replace both payload and manifest.

Read [Security plan](docs/SECURITY-PLAN.md), [SSH candidate](docs/SSH-COMPATIBILITY-CANDIDATE.md), [SSH startup](docs/SSH-STARTUP-CANDIDATE.md), and [Telnet transition](docs/TELNET-RETIREMENT-TRIAL.md).

## 128GB SD-card status

**The reader detects the full card.** A commercial 128GB card displaying approximately 119GiB is normal decimal/binary unit conversion, not lost capacity.

Observed on the development unit:

- External card/partition: `/dev/mmcblk1` and `/dev/mmcblk1p1`.
- Filesystem: vendor Tuxera exFAT (`texfat`).
- Card mounts: `/mnt/sdcard` and its FTP bind mount.
- Initial kernel detection indicated read-only.
- Later disk and partition read-only checks returned `0`.
- The filesystem nevertheless remained mounted `ro`.
- After USB data disconnection, the mass-storage module unloaded and vendor automount restored the read-only filesystem mount.

**Writing the card has not been verified or fixed.** Do not infer safe writable operation from `blockdev --getro` alone.

### USB safety

The stock USB gadget can expose the same card partition to a computer. Do not enable local filesystem writes while a USB host may write it too.

Safely eject the exported volumes on the computer before disconnecting the data cable. Preserve important data, inspect the card/adapter's lock slider after safe shutdown, and diagnose the mount policy and filesystem before considering a write test.

The SD doctor is read-only:

```sh
sh device/nimbus-sd-doctor.sh
```

Run it on the SanDisk after reviewing it. It reports mount/partition information and bounded storage-related kernel messages. It does not format, repair, force a writable remount, or change firmware.

SanDisk card-reader behavior is separate from GameHack's own unresolved expansion-card controller issue. A custom image is not evidence of a hardware fix for either.

## Run the localhost prototype

The development dashboard runs on the **computer executing Python**, not inside the SanDisk. Its metrics describe that host unless a field explicitly states otherwise.

### Requirements

- Python **3.9+** for the localhost prototype.
- No third-party packages or Internet connection for basic prototype use.
- An existing/new local vault for reviewed files.

Image building and the latest GameHack applications have separate tool/runtime requirements; this prototype's Python minimum is not a blanket promise for every script in the repository.

### Start

```sh
mkdir -p vault
python3 fieldkit/server.py --vault ./vault
```

Open **http://127.0.0.1:8080**. Paste the randomly generated terminal token into the dashboard. It stays in page memory rather than browser storage.

The prototype supports listing, downloading, and hashing reviewed vault files. It does not provide browser file uploads, deletion, or program execution. This does not remove the vendor homepage's independent upload capability.

### Enable explicitly scoped connectivity checks

```sh
python3 fieldkit/server.py \
  --vault ./vault \
  --allow-network 192.168.1.0/24
```

Substitute a network you own or are authorized to test. Checks accept one numeric IP and at most 16 TCP ports; there is no discovery sweep or credential attack.

The prototype binds to IPv4 localhost. **Do not expose this development HTTP server to a LAN or the Internet.** A production remote service would need separate authentication, TLS, permissions, deployment and firewall review.

## Native packaging and installation boundaries

### Build a native script bundle

```sh
python3 scripts/package-native.py \
  --output build/nimbus-native-kit.tar
```

The packager refuses to overwrite an existing output. It packages source/scripts/docs; it does not install them or flash firmware.

This legacy native kit also contains standalone dashboard assets for its historical version. **For the current one-homepage design, use the unified integration—not the old standalone UI.** Existing verified installers and version lineage must be reviewed before reuse.

### Unified UI build

The unified builder requires a reviewed stock-web archive and, for a v0.6 upgrade, the verified previous v0.5 bundle:

```sh
python3 scripts/build-unified-dashboard.py \
  --stock-web /path/to/verified-stock-web.tar \
  --previous-bundle /path/to/verified-nimbus-unified-v05.tar \
  --output build/nimbus-unified-v06.tar
```

Do not overwrite a previously delivered archive or assume any archive called “v0.5” is the expected lineage. Installer guards check exact homepage hashes and backup state.

The v0.6 UI-only upgrade keeps the existing native v0.5 runtime/settings/vault rather than duplicating them. Rollback restores the previous integrated homepage, not necessarily the untouched factory homepage.

See [Native installation](device/NATIVE-INSTALL.md), [Unified integration](docs/UNIFIED-DASHBOARD.md), and the delivery notes for the exact candidate being considered.

## Custom rootfs image candidate

### Artifact

```text
build/nimbus-custom-rootfs-candidate-v4/
├── rootfs.ext3.candidate
├── rootfs.tar
├── gamehack-nimbus-library-staged-v1.tar
├── unified-source.tar
├── BUILD-MANIFEST.json
├── ROOTFS-POLICY.json
├── SHA256SUMS
├── mkfs.log
├── fsck-readonly.log
└── NOT-FLASHABLE.txt
```

The build directory also contains its extracted rootfs tree and an intermediate stock-web input. Build artifacts are intentionally excluded from Git by default.

The ext3 candidate is **268,435,456 bytes / 256MiB**, matching the reviewed rootfs partition size. It uses conservative filesystem features for investigation with the old vendor kernel. Native compatibility is still untested.

### Included changes

- Unified stock homepage and FieldKit assets, including the Settings usability fix.
- Patched, hash-pinned Dropbear binary and a provisioned-key-only startup path.
- Telnet disabled in the rootfs inetd configuration.
- Toolkit scripts and diagnostics.
- WPA2-AES defaults/first-use mode selection.
- Separate staged handheld enhancement source bundle.
- Rootfs-resident boot publisher with media used as data, strict SSH permission checks, and bounded archive/policy validation. See [v4 hardening](docs/OFFLINE-CANDIDATE-HARDENING.md).

Vendor binaries/modules and stock handlers are preserved. Kernel, bootloader, rescue, settings partition, media partition and physical partition layout are **outside this rootfs image**, not replaced by it.

### Build requirements and provenance

The current builder requires:

- Python 3.11+ for its `hashlib.file_digest` usage; the recorded build used Python 3.14.
- `fakeroot`, `mke2fs`, and `e2fsck`.
- The exact hash-checked vendor 3.04 rootfs archive.
- The tested ARM interface-fail-closed SSH binary.
- The reviewed v0.5 UI-lineage bundle and staged GameHack source bundle in the expected build workspace.
- Sufficient space for the extracted tree, tar, filesystem image, and intermediate artifacts.

These binary inputs are not all distributed with a clean source checkout. The source builder is not a one-command reproducible vendor firmware toolchain.

Example for the documented development workspace:

```sh
fakeroot python3 scripts/build-custom-image.py \
  --stock-rootfs /tmp/opencode/sandisk-fw-3-04/rootfs_nimbus_v3.04.tar \
  --ssh-binary /tmp/opencode/nimbus-ssh-review/dropbear-2026.94/dropbearmulti \
  --output build/nimbus-custom-rootfs-candidate-v4
```

The output directory must not already exist. Preserve prior candidates rather than overwriting them. Fakeroot preserves archive ownership metadata without requiring host root privileges; the builder does not mount the image or write a physical device.

The recorded toolchain was Bootlin ARM EABI/musl 2026.08-1. Its matching Buildroot recipe includes the identified musl security fixes. Dropbear's release signature was checked against the supplied signing key; that consistency check is not an independently established out-of-band signer identity. See the SSH review for exact hashes and provenance limits.

### Check artifacts locally

```sh
cd build/nimbus-custom-rootfs-candidate-v4
sha256sum -c SHA256SUMS
```

An offline read-only filesystem check is recorded in `fsck-readonly.log`. Optional recheck on the **regular candidate file only**:

```sh
e2fsck -f -n rootfs.ext3.candidate
```

Do not substitute a mounted filesystem or guessed `/dev/...` path into that command.

### Why it must not be flashed

The image is not a full disk or vendor updater package. No verified recovery/rescue path or native boot test exists, and the generic image deliberately contains **no personal host key or authorized_keys**. Without separate secure offline provisioning, its SSH launcher does not start while Telnet is disabled.

**Do not rename it to `nimbus.img`, write it with `dd`, or feed it to the vendor upgrade/rescue mechanism.**

Ordinary USB gadget mode exposes media partitions, not a proven safe firmware-flashing interface. Vendor update/rescue scripts can change bootloader state and write internal storage; they are not diagnostic commands.

The firmware-container inspector is read-only:

```sh
python3 scripts/inspect-firmware.py /path/to/sandiskmediafirmware-3-04.img
```

Passing the reproduced wrapper checks is not cryptographic authentication or flash approval. See [Firmware feasibility](docs/CUSTOM-FIRMWARE-FEASIBILITY.md) and [Custom candidate](docs/CUSTOM-ROOTFS-CANDIDATE.md).

Prior candidates are preserved for research, not current delivery. v4 preserves the vendor SD read-only default and adds no automatic writable remount. Private per-device v4 builds live under ignored `.private-provisioning/`, contain SSH identity material and must never be publicly redistributed. No spare test drive or established recovery console is available; native boot/recovery remain blocked.

## Testing and validation

### SanDisk project

From this repository:

```sh
python3 -m unittest discover -s tests -v
```

Coverage includes host API validation, native feature gates, snapshots, firmware inspection, unified-page structure, local Chromium interaction, guarded maintenance, and image artifact checks.

Some tests depend on optional local artifacts/tools, including Chromium, reviewed stock inputs, and a built image. They can skip when those are absent. Do not confuse a reduced/skipped run with the recorded full validation checkpoint.

### Associated GameHack project

Run its tests from its own `hackeros-v3` directory. Terminal/UI tests require an appropriate isolated environment with `pyte`, `pygame`/`pygame-ce`, and `evdev`:

```sh
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  python3 -m unittest discover -s tests -v
```

Dummy display/audio testing does not validate handheld hardware, video decoding, controller devices, or live media services. Do not install host packages onto removable cards as a substitute for preparing the target system.

### Evidence hierarchy

1. **Implemented:** code exists and has been reviewed.
2. **Host-tested:** behavior passes local unit/browser tests.
3. **Device-tested:** the specific operation ran on the actual hardware.
4. **Reboot-tested:** persistence survived a controlled reboot.
5. **Recovery-tested:** a real failure can be restored through a verified procedure.

The final level has not been established for custom firmware. Always state which level applies.

## Repository layout

```text
.
├── README.md                       # Project overview and public-facing guide
├── fieldkit/                       # Localhost prototype and shared helpers
│   ├── server.py
│   ├── index.html
│   ├── dashboard.css
│   ├── dashboard.js
│   ├── nimbus_fieldkit.py
│   └── tools.py
├── device/                         # Native shell toolkit and reviewed helpers
│   ├── nimbus-agent.sh
│   ├── nimbus-settings.sh
│   ├── nimbus-dashboard.sh
│   ├── nimbus-sd-doctor.sh
│   ├── retire-v04-homepage.sh
│   ├── image-start.sh
│   ├── unified/                    # Same-page bridge and stock dark stylesheet
│   ├── dashboard/                  # Native snapshot encoder
│   └── ssh/                        # SSH startup and guarded Telnet trial sources
├── scripts/                        # Offline builders, inventory and staging
│   ├── build-unified-dashboard.py
│   ├── build-custom-image.py
│   ├── inspect-firmware.py
│   ├── package-native.py
│   └── stage-gamehack.py
├── tests/                          # Regression and offline artifact tests
├── docs/                           # Design, delivery, security and evidence notes
└── build/                          # Ignored local candidates; not a public release
```

The associated GameHack staging tree is a separate project/workspace. Its newer `nimbus_library.py` and media changes are not automatically deployed by the older `stage-gamehack.py` helper. Do not use that helper to overwrite a newer integration without reviewing its guarded compatibility checks.

## Documentation index

| Topic | Document |
| --- | --- |
| Unified homepage design, installation and rollback | [UNIFIED-DASHBOARD.md](docs/UNIFIED-DASHBOARD.md) |
| v0.6 UI enhancements | [UNIFIED-ENHANCEMENTS.md](docs/UNIFIED-ENHANCEMENTS.md) |
| v0.6 delivery and validation | [UNIFIED-V06-DELIVERY.md](docs/UNIFIED-V06-DELIVERY.md) |
| Native feature gates | [TOGGLES.md](docs/TOGGLES.md) |
| Feature inventory | [FEATURES.md](docs/FEATURES.md) |
| Original native installation notes | [NATIVE-INSTALL.md](device/NATIVE-INSTALL.md) |
| GameHack integration | [GAMEHACK.md](docs/GAMEHACK.md) |
| New optional library and maintenance batch | [GAMEHACK-OPTIONAL-ENHANCEMENTS.md](docs/GAMEHACK-OPTIONAL-ENHANCEMENTS.md) |
| Security transition principles | [SECURITY-PLAN.md](docs/SECURITY-PLAN.md) |
| User-supplied security inventory | [SECURITY-LIVE-INVENTORY.md](docs/SECURITY-LIVE-INVENTORY.md) |
| Maintained SSH source/build review | [SSH-COMPATIBILITY-CANDIDATE.md](docs/SSH-COMPATIBILITY-CANDIDATE.md) |
| SSH persistence and live validation | [SSH-STARTUP-CANDIDATE.md](docs/SSH-STARTUP-CANDIDATE.md) |
| Timed Telnet trial and permanent retirement | [TELNET-RETIREMENT-TRIAL.md](docs/TELNET-RETIREMENT-TRIAL.md) |
| Vendor firmware inspection | [FIRMWARE-3.04-INSPECTION.md](docs/FIRMWARE-3.04-INSPECTION.md) |
| Recovery/update feasibility | [CUSTOM-FIRMWARE-FEASIBILITY.md](docs/CUSTOM-FIRMWARE-FEASIBILITY.md) |
| Built rootfs candidate and provisioning gates | [CUSTOM-ROOTFS-CANDIDATE.md](docs/CUSTOM-ROOTFS-CANDIDATE.md) |
| Current v4 offline startup/archive hardening | [OFFLINE-CANDIDATE-HARDENING.md](docs/OFFLINE-CANDIDATE-HARDENING.md) |
| Single-device experimental trial preparation | [EXPERIMENTAL-DEPLOYMENT.md](docs/EXPERIMENTAL-DEPLOYMENT.md) |
| Original Music view without Flash (UI installed; playback validation pending) | [HTML5-MUSIC.md](docs/HTML5-MUSIC.md) |
| Modern upload loading ring (CSS-only candidate) | [UPLOAD-LOADER.md](docs/UPLOAD-LOADER.md) |
| Genuine upload percentage (guarded XHR candidate) | [UPLOAD-PERCENTAGE.md](docs/UPLOAD-PERCENTAGE.md) |
| FieldKit toolbox icon and bottom upload card | [FIELDKIT-ICON.md](docs/FIELDKIT-ICON.md) |
| Local beta1 images and production qualification | [BETA1-TEST-PLAN.md](docs/BETA1-TEST-PLAN.md) |
| Public preview assets and production blockers | [PRODUCTION-READINESS.md](docs/PRODUCTION-READINESS.md) |
| Planned two-part GameHack/SanDisk Android/iOS companion | [MOBILE-COMPANION-APPS.md](docs/MOBILE-COMPANION-APPS.md) |

Some documents are chronological investigation notes. Earlier statements may be superseded by explicitly recorded follow-ups. Do not copy an old diagnostic command or deployment assumption without reading the current status and later entries.

## GitHub and GitHub Pages

This README is designed for a repository landing page and can serve as the basis of a documentation site. **No GitHub Pages deployment or repository publication is performed by editing it.**

GitHub Pages is appropriate for public documentation, sanitized screenshots, and static explanatory material. It is **not** a backend for controlling your SanDisk, running shell commands, or holding device credentials. A Pages-hosted UI also has a different origin from the local device; browser security restrictions and authentication must not be bypassed to make it work.

### Before publishing

- Review every tracked file, release asset, screenshot, log, and commit—not just the README.
- Keep `/numbus-backup/`, `/.private-backups/`, `vault/`, private Wi-Fi plans and `build/` out of source control as configured in `.gitignore`.
- Check for credential files elsewhere; the ignore list is not exhaustive.
- Remember that `.gitignore` does not remove already tracked files or purge history.
- Review vendor-binary redistribution rights before attaching rootfs archives, firmware blobs, or toolchains.
- Do not upload a live device snapshot as a “clean” image.
- Label screenshots as **fixture/demo data** when appropriate.
- Do not publish default/factory credentials or your private host/client keys.
- Confirm documentation links and sanitized source completeness before making a repository public.

Private backups are recovery material, not release assets. Release visibility and firmware readiness are separate decisions.

## Roadmap

### Near term

- Preserve the verified live Settings fix; the user reports Settings working after the patch. Native candidate-image Settings behavior remains a separate validation gate.
- Design a safe candidate SD-access policy without silently overriding boot-time read-only detection. Live bounded writes, reboot readback and both normal/writable-SD USB cycles passed; [evidence and remaining limits](docs/SD-VALIDATION.md).
- Keep candidate-image SD validation separate from the existing firmware's live test results; retained-marker cleanup is still pending.
- Pair GameHack through a reviewed downstream management path without exposing SSH globally.
- Add authenticated, pinned remote transfer rather than plaintext fallbacks.
- Deploy and native-test the optional mounted-library features on the handheld.
- Review legacy HTTP/FTP exposure and stock account/reset behavior.
- Add bounded private-log retention and clearer live/stale telemetry indications.

### Image release gates

- Define a secure per-device provisioning process for keys, passphrases and calibration.
- Verify exactly what the updater/rescue chain writes and preserves.
- Establish a matching, tested recovery route.
- Validate native boot and vendor functionality with a separately authorized deployment plan.
- Validate AP/uplink operation, SSH persistence, device charging and media workflows.
- Keep GameHack source deployment separate from the SanDisk ARMv7 image.
- Rebuild manifests after source changes and review privacy/licensing before any public binary release.

There is no promised flash date. A safe release requires evidence, not merely a successfully generated image file.

### Android and iOS companion apps

Provide **one two-part Android/iOS companion for GameHack Zero and SanDisk**, with independent handheld and drive sections plus optional shared storage/media/backup workflows. GameHack remains usable without SanDisk, and Pi USB networking stays independent. Each device needs its own paired identity and scoped API. The original enhanced homepage remains available without an app. Real-phone tests, signing and platform distribution are prerequisites; no mobile app is implemented or released yet. See [mobile companion plan](docs/MOBILE-COMPANION-APPS.md).

## Troubleshooting

### SSH port 2222 or 2223 is refused after reboot

Those were temporary development listeners. The verified persistent service uses **2224**. Use your own private client key and dedicated pinned host-key file. Do not disable host-key verification to suppress an error.

### SSH works from the hotspot side but not GameHack on the SanDisk AP

The listener is restricted to `wlan1`; GameHack is expected on `wlan0`. This is a known integration boundary, not a reason to bind administration indiscriminately to every interface.

### Settings look correct but administrative rows do nothing

Web-admin authentication is independent of SSH. The guarded live Settings patch adds an explicit **Sign in** button and locked-state explanation; hard-refresh the page if they are missing. Enter the device web-admin password there, not the SSH key passphrase. The user reports Settings working after installation. The patch does not bypass authentication or guarantee that every vendor setting is supported; destructive controls and native candidate-image behavior have not been validated.

### The old standalone dashboard still appears

The retired URL may be cached by the browser. Reload without cache and verify the server's fresh response. Do not delete the entire old installation: its settings/runtime may still be useful or needed for rollback.

### The SD card reports 119GiB instead of 128GB

That is normal unit conversion. Check the actual mount status and supported operations instead of reformatting to “recover” the expected number.

### The SD partition says writable but the filesystem says `ro`

These are different layers. Check USB ownership, the lock sensor, driver/mount policy and filesystem evidence. Do not force writes merely because the block read-only flag is zero.

### A feature refuses to turn ON

Read its capability reason. Some functions require absent binaries, a writable supported destination, or verified pairing. OFF remains available; the interface does not install dependencies automatically.

### The image passes fsck—can it be flashed?

**No.** Filesystem consistency is not boot validation, provisioning, updater compatibility, power-loss safety or disaster recovery.

## Contributing

Useful contributions include bounded tests, clearer capability reporting, controller accessibility, documentation corrections, private-data safeguards, and reviewed reversible deployment logic.

Please:

1. State whether your change targets the host prototype, native SanDisk, GameHack, or the offline image builder.
2. Preserve vendor IDs/handlers and the independent Pi USB profile unless a specific change is justified.
3. Include tests for malformed input, symlinks, existing destinations and partial failure where relevant.
4. Avoid automatically mounting, formatting, stopping services or modifying radio/firewall settings.
5. Keep credentials, real captures, backups and sensitive logs out of patches and issues.
6. Distinguish software tests from actual hardware evidence.
7. Document rollback and compatibility assumptions.

Use network diagnostics only on devices and networks you own or are explicitly authorized to test.

## Licensing and acknowledgments

This checkout currently has **no top-level project license file**. Do not assume the repository grants blanket redistribution rights; a project license and third-party inventory need review before public release.

Vendor firmware, web assets, kernel/modules, toolchains and other components retain their own licenses and distribution conditions. Their inclusion in a local research candidate does not establish permission to redistribute the resulting binary.

Acknowledgments:

- SanDisk/QSI and the published Wireless Media Drive sources and vendor components used for compatibility research.
- [Dropbear SSH](https://matt.ucc.asn.au/dropbear/dropbear.html).
- [Bootlin toolchains](https://toolchains.bootlin.com/) and Buildroot.
- [musl libc](https://musl.libc.org/), Linux, and e2fsprogs.
- Python, Chromium, pygame/pygame-ce, pyte and evdev for development/testing.
- GameHack Zero and its existing Pi companion and media integrations.

---

**Keep the working device. Verify the change. Preserve a way back.**
