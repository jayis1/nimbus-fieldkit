# Dashboard Pi A/B and homepage battery update — installed, visual acceptance pending

Owner requested correction of the live SanDisk dashboard to the current GameHack
architecture, then an always-visible battery indicator on the homepage.

## Prepared changes

- `fieldkit/index.html`: explicit GameHack onboard Wi-Fi → shared network/SanDisk
  AP → pinned SSH to Pi A → A's USB/data link to Pi B. A stays managed, B monitor
  capability/provisioning remain unqualified; retired handheld USB is not offered.
  Pi task/queue/relay boundaries no longer claim automatic A→B dispatch.
- `fieldkit/dashboard.js`: updated requirements and honest missing-telemetry error;
  failed refresh clears stale measurements/flags instead of leaving them live.
- `device/unified/bridge.js`: `#overview` and other valid toolkit hashes open the
  FieldKit surface; loads the new homepage battery asset without replacing stock
  media, authentication or settings handlers.
- `device/unified/battery.js`: persistent accessible homepage battery indicator,
  read-only vendor getBatteryLevel RPC every 30 seconds while visible, bounded
  request time, strict percentage/error parsing, charging state and Unknown on
  failure. It does not infer charge from charger presence/voltage, expose a shell
  or alter radio/services/admin settings. Overview can use that measured battery
  even if the general telemetry snapshot is missing.
- Unified builder includes the new first-party battery asset; no release/image or
  existing device files are overwritten merely by changing sources.

## Read-only native observations

HTTP homepage/toolkit assets are reachable. Configured native snapshot URL,
runtime docs and runtime dashboard page under the expected exported storage
path returned 404. Read-only vendor battery RPC returned HTTP 200:

```xml
<nimbus errcode="0"><level>100</level><status>charge</status></nimbus>
```

That is reported 100%/charging at observation time, not a calibration guarantee
or permanent state. It is independent of the earlier sysfs capacity limitation.
No settings or device files were changed by these requests.

## Validation and installation gate

20 targeted dashboard tests passed, including local Chromium tests for genuine
100%/charging, zero/discharging, malformed/out-of-range/refused/unavailable battery
responses and the existing dashboard controls. `git diff --check` passed.
Full workspace regression not run at this checkpoint.

Actual missing-snapshot cause is not established: source/path existence versus
HTTP export/publisher state must be checked, not guessed or filled with fake
telemetry. `device/dashboard-ui-preflight.sh --check` reads only known UI/publisher
metadata/hashes and free space, with no snapshot publication, staging, service or
mount changes. Owner runs it through existing strictly pinned SSH, keeping the
encrypted key passphrase local. Returned baselines are needed for a bounded,
backup/rollback guarded UI-only installation and a reviewed real publisher-path
fix. No radio mode, SSH policy/key, firmware flash or background publisher follows
from the requested UI correction. None of these changes is deployed yet.

Owner attempted the read-only UI preflight through temporary 2225 and received
`Connection refused` before authentication/remote execution. No preflight,
publisher, upload or UI installation ran in that attempt. Next is the same
read-only check through existing strictly pinned 2224, not a blind listener
restart, reboot or modification of retained temporary stages. Cause of 2225 loss
is unknown; prior listener/session observations must not be treated as current.

## Guarded package checkpoint

`scripts/package-dashboard-ab.py` now builds a deterministic first-party-only
package for the four supplied baseline hashes, adding `battery.js`. It preserves
stock `index.html`, refuses changed/symlink/hardlink files and keeps transaction
evidence. Fixture checks cover install, rollback, mid-update failure, later-edit
refusal and read-only-root refusal. Host fixture `sync` is stubbed to avoid
unrelated global host I/O; production retains device `sync`. Neither fixture
success nor that command proves device durability or power-loss recovery.

Owner commands and mandatory saved PC baseline backup:
[guarded deployment guide](DASHBOARD-AB-INSTALL.md). Device `/tmp` backups are
volatile. Package built locally; no staging/install/live UI acceptance occurred.

Latest scoped regression: 24 tests passed (15 dashboard/battery/package, five
unified dashboard, four mascot UI); `git diff --check` passed. Full workspace
regression was not rerun. These results do not certify native installation,
durability, USB ownership or the future Wardriving GO workflow.

## Native deployment — 2026-10-13

Owner explicitly requested installation and locally unlocked the existing key.
Strictly pinned normal SSH port 2224 was used through the owner-provided agent;
no passphrase was collected or listener restarted.

- Saved original UI archive to
  a private owner-selected `original-ui.tar` backup, synced it locally
  and read back all four baseline contents/metadata against the supplied hashes.
- Fresh tmpfs stage `/tmp/nimbus-dashboard-ab-r1` passed
  `DASHBOARD-AB-CHECK=PASS`; installation returned `DASHBOARD-AB-INSTALL=PASS`.
- All five deployed HTTP assets matched package hashes; SSH hashes matched too.
  Retained stage STATUS is `INSTALLED`.
- Read-only vendor battery RPC now returned level `100`, status `full`.
- Mount listing remained unchanged, including root rw and no media mount.
  No services, radio settings, USB mode, SSH policy or stock homepage were changed.

Live user-visible rendering/navigation acceptance remains pending a hard refresh
of the drive's `#overview` page. HTTP hashes/RPC are not rendered-browser
acceptance or power-loss recovery evidence. Same-boot guarded rollback remains
available through the retained stage; PC backup survives loss of device tmpfs.

Follow-up: a fresh native headless Chromium page rendered `Battery: 100% · Full`.
Standalone source now independently loads the vendor battery reader, instead of
requiring homepage controls; embedded/standalone missing-snapshot fixtures pass.
These new source changes are **not redeployed** and are included in the new
[64 GB-targeted beta5 offline candidate](FIRMWARE-64GB-BETA5.md).
