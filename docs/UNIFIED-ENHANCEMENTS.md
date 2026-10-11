# Unified dashboard UI upgrade v0.6

This is a UI-only upgrade over the shipped v0.5 archive, not a firmware or security-service change.

## Enhancements

- Global dark/light theme button in the stock navigation, usable without opening FieldKit.
- Quick-jump dialog, also reachable by Ctrl+K / Command+K: search stock Files, Photos, Videos, Music and Settings plus toolkit Overview, Switches, Network, Vault, Docs/Pi and Security. Enter selects the first result; Escape closes the native dialog. Navigation runs no operations.
- Same-page security-readiness panel distinguishing completed backup verification from unverified SSH, Wi-Fi and recovery prerequisites.
- Bundled security transition plan, displayed as text on explicit request; never displays passwords/keys or executes hardening commands.
- Toolkit refresh polling pauses when stock screens are active or the browser tab is hidden.
- Failed toolkit loading can be retried without replacing vendor navigation or launching a second server.

## Upgrade preservation and gates

Build with `--previous-bundle build/nimbus-unified-v05.tar --output build/nimbus-unified-v06.tar` in addition to `--stock-web numbus-backup/stock-web.tar`. Do not overwrite the shipped v0.5 archive. The previous manifest/page hash and original stock lineage are validated during build.

v0.6 assets go into a fresh `/nimbus/data/fieldkit-v06` directory, staged from `/mnt/storage/nimbus-unified-v06`. The installer requires the exact shipped v0.5 homepage hash, saves that homepage before replacement and validates every copied asset. Rollback restores v0.5, not the original pre-toolkit page.

The active native runtime stays at `/mnt/storage/nimbus-unified-v05/native`: its settings, vault, docs, snapshot and publisher are not migrated or overwritten. No new native runtime is shipped in the upgrade. Other installation directories and verified backups are retained.

No Telnet disabling, root-password change, SSH installation, firewall edit, Wi-Fi change, network restart or reboot is included. Those are a later separately verified transition. See `SECURITY-PLAN.md`; access replacement must be verified before closing Telnet. Historical SSH binaries/listeners are not proof of a maintained secure replacement.
