# Unified SanDisk homepage candidate v0.5

This replaces `/nimbus/data/index.html`, not a separate media-share dashboard. The user's verified stock homepage is transformed additively: its original markup, script order, IDs and API wiring remain, with a dark stylesheet and a new **FieldKit / tools** navigation entry. No iframe, second server or external assets are introduced.

## Retained vendor features

The stock Files, Photos, Videos and Music views remain, including search, uploads, downloads, folder creation/deletion, copy/move/rename context menus, playlists and media controls. Settings retain battery, Internet connection, language, About, admin login/logout/password, Wi-Fi name/security, connected clients, service settings, firmware upgrade, reset and formatting. Existing stock authentication/confirmations remain; destructive actions are not called automatically.

Retaining vendor code preserves its behavior and limitations, not guaranteed compatibility with every modern browser/media codec. Legacy Flash fallbacks remain legacy. Dark styling is an overlay, not a security upgrade or rewritten backend.

## Integrated toolkit

Click FieldKit / tools in the same navigation to see Overview, all ten persistent feature switches, Network, Vault/sync, Docs/Pi and Security. A Shadow DOM isolates toolkit IDs/styles from the vendor jQuery UI; it is still one page, not an iframe or linked side dashboard. Stock navigation restores stock content. Theme preference applies to both interfaces; dark is default.

Native runtime is staged under `/mnt/storage/nimbus-unified-v05/native`. Validated v0.3 ON/OFF flags are imported without copying vendor credentials. Snapshot publisher, local vault and docs use this installation's explicit paths. Previous installation directories remain untouched; old vault files are not silently migrated.

**Toolkit switches/actions still prepare terminal-confirmed commands.** Root access makes installing files possible but is not a secure browser command API. No root password, keys, unauthenticated shell endpoint or command inbox is added. A separate reviewed authenticated backend is required before claiming direct browser execution. Vendor controls continue to use the existing vendor API.

## Build, test and installation boundaries

Build locally from the verified private stock web backup:

```sh
python3 scripts/build-unified-dashboard.py --stock-web numbus-backup/stock-web.tar
```

Output is `build/nimbus-unified-v05.tar`. Only the stock homepage (not private databases/configuration) and reviewed toolkit files are packaged. The input archive is read through tarfile without bulk extraction. The bundle includes deterministic file hashes and an explicit installer; packaging does not connect to or modify the drive.

Before installation, independently verify the archive SHA-256 and stage into a new `/mnt/storage/nimbus-unified-v05` directory. In an authorized root session, `sh install.sh install` verifies bundle files and the exact original homepage hash, refuses an existing integration, saves the original homepage, imports feature flags, publishes a snapshot, copies new assets, and atomically replaces the homepage. No firmware, bootloader, partition, daemon, network or charging changes are included. Partial failures may leave additive files; installer refuses blind reruns rather than overwriting them.

Rollback: `sh install.sh rollback` validates the saved original and current candidate before atomically restoring the original homepage. It retains new assets/settings and refuses to overwrite an unfamiliar modified homepage.

Use `sh native/nimbus-dashboard.sh watch 120 15` for a bounded foreground publisher when watchdog/network_health flags are ON. No autostart service is installed.

Off-device backup hashes are verified, but live filesystem consistency and actual disaster recovery remain untested. The candidate must receive browser tests and live post-install validation before being described as deployed/fully functional. Keep root Telnet and the verified private backups available; do not use firmware reset/upgrade/format buttons as tests.
