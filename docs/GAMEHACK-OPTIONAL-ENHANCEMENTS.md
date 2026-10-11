# Optional GameHack / SanDisk enhancement batch

Implemented staged handheld module: `GameHack-Zero/hackeros-v3/staging/opt/hackeros/nimbus_library.py`, linked from the existing optional Nimbus menu. Adds versioned single-file backups up to 8 GiB, restore preview/verification with no overwrite, bounded media browsing and controller local playback, favorites, private offline notes, persistent feature switches and a read-only storage doctor. Existing mpv player is extended with explicitly validated local file URIs, disabling yt-dlp and external media references for local files. Pi USB queue controls remain independent; monitor/capture workflows are removed from this optional menu.

Handheld service diagnostics and shared FieldKit probes include port 2224. Handheld reports distinguish TCP reachability from authenticated, host-pinned SSH. Optional component remains usable without the drive; no new mandatory SanDisk dependency, mounting, routing or credential storage is introduced.

Storage library operates on an explicitly selected existing local/mounted folder. It does not yet fetch remote directories or provide remote SSH/SFTP transfer. Stock SD/share read-only status and wlan1-only administration prevent claiming a deployed end-to-end handheld integration. Backups to stock media remain plaintext; secret-file exclusions are not comprehensive, and sensitive archives must be encrypted before sharing. SHA-256 detects mismatches, not malicious changes to both payload and manifest.

## Obsolete standalone homepage removal

`device/retire-v04-homepage.sh` retires exactly `/mnt/storage/nimbus-fieldkit-v04/dashboard/index.html` after verified copying into a new private `/root/nimbus-retired-v04-homepage` directory. Other assets, snapshots, native runtime/settings and the customized original `/nimbus/data/index.html` remain untouched. The private root backup is not a served dashboard. This script has not been executed on the device by the agent. Browser caches can retain an old page; verify fresh HTTP status after running it.

## 128GB SD card

Prior live evidence showed an approximately 120 GiB read-only `/mnt/sdcard`. This establishes prior detection, not current write capability. `device/nimbus-sd-doctor.sh` collects mount source/type/options, partitions, sysfs size/read-only metadata and bounded storage-related kernel messages. It performs no mounts, repairs, formatting or card writes. Required next input is live output; do not guess partition names or force writable remount of an errored filesystem. A 128GB decimal card normally displays approximately 119GiB. SanDisk reader support is separate from the handheld's unresolved TF2 controller issue.

## Deployment boundary

All feature changes are staged source. No handheld/Pi card, release manifest, system image or live drive homepage was updated. Do not use the old 4.2.0 manifest to install changed sources. Native mpv, control/display/audio, network, secure pairing and actual card writes still require separate validation. Unit tests are not hardware validation.

Validation: 95 handheld tests passed in an isolated host venv with pyte, pygame-ce and evdev; 73 SanDisk-project tests passed, including isolated legacy-page retirement guards. No system or device dependencies installed. Source bundle: `build/gamehack-nimbus-library-staged-v1.tar`, not a deployment updater.

Maintenance-only bundle was uploaded and exact HTTP readback verified at `/mnt/storage/Scotti Upload/nimbus-optional-maintenance-v1-1e6f3c24611c.tar`; SHA-256 `0a17d5212df370c1a4fdbea0c627c9d499c598cab8a3caeac5145f29d6f8f233`. Contains only two shell helpers plus checksums, not a new dashboard. User must explicitly execute retirement/diagnostics via authorized SSH. No helper executed on the drive by the agent; old v0.4 URL retirement and SD diagnosis remain awaiting user output.
