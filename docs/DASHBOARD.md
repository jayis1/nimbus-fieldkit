# SanDisk FieldKit dark dashboard — v0.4

An offline-first dark dashboard served by the SanDisk's **existing static file service**, alongside the stock UI. No root, Python, replacement daemon, firmware changes or new listening port required.

## What is integrated

- Overview: measured gateway, storage, memory estimate, enabled feature flags, uptime and battery only when its driver exposes capacity.
- All ten native ON/OFF switches, with actual availability/dependency reasons.
- Network: subnets, interface counters, measured receive-rate history from successive snapshots. No monitor-mode controls; vendor monitor interfaces are not used or modified.
- Vault: up to 64 simple-named regular files, native download and explicit hash/backup/sync/archive command preparation.
- Offline docs, local Git/speed-test prerequisites, and guidance for the existing GameHack Pi queue controls.
- Security: kernel TCP listeners, the legacy-firmware warning and the key-pinned SSH/recovery checklist. A listener does not establish secure authentication or network reachability.
- Dark by default; optional light mode persists in browser storage. Only theme preference is persisted; tokens/passwords are not.

## Installation boundary

Install the checksum-verified v0.4 bundle into a **new** `/mnt/storage/nimbus-fieldkit-v04` directory. Keep v0.3 intact. Then, on the drive:

```sh
cd /mnt/storage/nimbus-fieldkit-v04
sh nimbus-dashboard.sh import-settings /mnt/storage/nimbus-fieldkit-v03
sh nimbus-dashboard.sh snapshot
```

Import copies only validated ON/OFF files, refuses symlinks/malformed values and refuses an existing destination settings directory. It starts no feature and copies no passwords, private keys, jobs or device configuration.

Open:

```text
http://DEVICE_IP/storage/nimbus-fieldkit-v04/dashboard/index.html
```

For the presently observed upstream IP: `http://172.16.10.178/storage/nimbus-fieldkit-v04/dashboard/index.html`. On the drive's stock AP, use `192.168.11.1` instead. Device addresses can change. Original SanDisk dashboard remains at `/`; this is not an overwrite of protected `/data` files.

## Live snapshot publisher

The browser reads `dashboard/state.json` every 15 seconds while visible. It does not collect telemetry itself. The native shell publisher writes atomic snapshots using POSIX awk and existing system files. It reads routes/counters/memory/uptime, toolkit-storage free space, exposed battery capacity/status, feature flags, designated vault metadata and kernel TCP listeners. It does not read credential databases, keys, packet captures or user directories recursively.

One snapshot is enough to view the dashboard. For fresh data, when network_health and watchdog are ON:

```sh
sh nimbus-dashboard.sh watch 120 15
```

This publishes at most 120 snapshots (~30 minutes), in the foreground, stopping when watchdog/health is OFF. Ctrl+C stops it without touching Wi-Fi. A snapshot gets a timestamp and publisher label; the UI flags stale data and makes no Internet-success claim from a default route. Do not close the Telnet session expecting a daemon to survive; no boot/autostart service is installed. The old CLI watchdog remains independently available.

**Snapshots are ordinary media files served by the stock HTTP service.** Anyone with access to that share may see network/storage identifiers and feature state. Use secured Wi-Fi and a trusted management network; do not publish these files to the Internet. POSIX permission bits on exFAT are not a confidentiality boundary.

## Browser toggles and actions: truthful and explicit

The stock server does not provide a secure authenticated API for our shell features. Therefore clicking a switch or action opens a command drawer for your authenticated terminal. It does **not** launch commands or visually claim a setting changed before it did. Copy/run the command, publish a snapshot, and Refresh to see confirmed state. HTTP clipboard limitations are handled with selection/copy fallback.

There is no web shell, upload-command inbox, automatic Telnet login, credential storage, guessed root access, or unauthenticated service control. Real direct browser write controls require a maintained authenticated/TLS backend and secure administration first. Legacy FTP/Telnet/HTTP security is not fixed by a new skin.

OFF blocks new finite operations; existing finite copies finish safely. Only our bounded watchdog/publisher loops observe OFF while running. Existing SanDisk Wi-Fi, routing and services remain untouched.

## Host dashboard

The same assets are served by the localhost Python prototype:

```sh
python3 fieldkit/server.py --vault ./vault --device 172.16.10.178
```

After token unlock, it can read the device's **explicit configured** native snapshot path. Without that snapshot it labels host telemetry as HOST DATA ONLY. Host files, host diagnostics and local host privacy remain separate from the SanDisk. Optional `--native-path` accepts only a static storage/sdcard snapshot path; it cannot target arbitrary URLs. Existing authorized CIDR/permission requirements still apply to active host diagnostics.

No fake telemetry is shipped. No external fonts, scripts, analytics, or CDN dependencies are loaded. Browser controls and strings are built with text nodes rather than inserting device data as HTML.
