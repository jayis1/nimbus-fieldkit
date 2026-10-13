# Source publication boundaries

This GitHub update publishes first-party source, tests, documentation and README
status only. It is **not a firmware release**, a native GO endpoint, a supported
security replacement or authorization to repeat hazardous device trials.

- Owner credentials/private keys, account tables/hashes, provisioning/baselines,
  media, raw captures/backups and the local owner-specific agent/identity handoff
  are excluded. Generated binaries, firmware/rootfs/vendor inputs and private
  evidence are not committed or uploaded as release assets.
- Public examples use documentation-only `192.0.2.10`, not the development
  drive's DHCP address. Replace it only after owner-confirmed reachability and
  strict host-key verification. Do not scan for devices or bypass pins.
- Private image checksums and identifying workstation/evidence paths have been
  anonymized where needed. Original local documents/evidence are retained
  privately; anonymous labels such as drive-a are test/example labels, not keys.
- The capture transport planner now requires an explicit current device address;
  it still only constructs a plan and never launches SSH. Port2225 remains a
  historical gated trial role, not an assumed current listener.
- Historical native commands in checkpoint documents are evidence/proposals,
  not automatic installation instructions. Retain failed/used stages, refresh
  prerequisites and obtain exact approval where required. Never recreate a used
  stage or repeat a flash/remount/reset/radio action merely to get a pass.
- Feature freeze, recovery/privacy/provisioning/license gates remain in force.
  Rootfs candidates are NOT FLASHABLE; BusyBox is unchanged; WiGLE is deferred.

Local targeted checkpoint:88 GO and104 SFTP tests passed, no skips, with a new
opaque ARM framing artifact built/audited/emulated only. Full-suite status is
recorded separately; no full firmware or recipient qualification is implied.

## Full-suite publication checkpoint

Initial full run found34 failures and1 error. The shell fixtures sequentially
rewrote already-inserted `/tmp` paths; synthetic path rewriting is now one-pass
with whitespace-free private temporary directories and ordinary Linux fallback.
Production path/owner/state checks were not relaxed. The script-bundle transfer
validator now has a separate exact guarded-bundle set for media guard/battery/docs,
retaining the historical allowed sets rather than arbitrary file expansion.

Rerun: **596 tests,592 passed,4 skips,0 failures/errors**. Skips were clean-vendor
module comparison, two stock-audio/JS checks and real Dropbear-key provisioning
validation when their external inputs/tools were unavailable. Those skipped gates
are not cleared by publication; prior evidence is not erased or relabelled.
