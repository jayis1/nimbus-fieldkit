# Unified dashboard v0.5 candidate delivery

Built from the user's checksum-verified `numbus-backup/stock-web.tar`. The resulting homepage retains stock IDs/scripts and adds same-page toolkit navigation and dark styling. No iframe or separate linked dashboard is used.

Validation: 69 tests passed, including exact stock-ID/script preservation, original navigation jQuery handlers still present, same-page toolkit/stock navigation, applied Shadow DOM styling, theme propagation, ten feature cards, prepared commands, package reproducibility, installer syntax/guards and file hashes. Browser tests use local fixtures with vendor device APIs deliberately unavailable; they do not establish live upload/media/Wi-Fi/admin behavior. Screenshot `/tmp/opencode/nimbus-unified-browser.png` contains fixture data, not live measurements.

Built archive: `build/nimbus-unified-v05.tar`.

SHA-256: `b3428f09554e852f58a19d9c1c214cf557dce9328694ff20cc435b104a8eb0b4`.

Read-only GET of the live homepage matched the expected original backup hash before delivery. Archive uploaded through the existing normal media-upload API to a previously unused random filename and verified by HTTP readback:

`/mnt/storage/Scotti Upload/nimbus-unified-v05-a1bdda0eabc0.tar`.

**Not installed:** no root commands were executed by the agent, no homepage/system file changed, no firmware flashing or service/radio changes. The user must explicitly run the checksum-verified staged installer in the root session. New destination is `/mnt/storage/nimbus-unified-v05`; existing v0.3/v0.4 installations remain untouched. See `UNIFIED-DASHBOARD.md` for scope and rollback.

Toolkit controls prepare terminal commands; no direct browser shell/toggle API was introduced. Post-install validation must check homepage load, stock Files/Photos/Videos/Music/Settings navigation, toolkit snapshot, dark/light styling and read-only settings before any active vendor operation. Do not test firmware upgrade/reset/format as a UI smoke test.
