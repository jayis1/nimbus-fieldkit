# Outstanding validation: next gates

This is a preparation checklist, not authorization for device changes. Existing
private backups, image candidates, trial stages and retained markers stay intact.

## 1. SD mount policy

Live bounded writes, checksum readback, reboot persistence and both USB handoff
cycles already passed; see [SD validation](SD-VALIDATION.md). Do not repeat these
tests just because the README previously described writes as unresolved.

Next: obtain a fresh read-only `device/nimbus-sd-doctor.sh` report through the
existing pinned management path. The improved helper distinguishes main/FTP
mount options, block read-only metadata and observed USB-export state. It accepts
no action arguments. It does not identify the cause of a boot-time read-only
decision and does not authorize remounting from `ro=0` or gadget absence.

Before any persistent change, review the vendor event/automount decision path
as data only, including USB removal and lock detection. Do not execute the
automount script: its fallback can run a filesystem checker. Preserve the rule
that host USB export and local filesystem access must never overlap. Unknown
lock/error/export state must refuse writable policy rather than override it.

## 2. GameHack / Pi integration

Next: confirm the handheld is available, its current SanDisk AP connectivity,
Internet access and existing pinned Pi-worker connectivity. Do not change the
Pi subnet, gateway, saved Wi-Fi profiles or radio roles to obtain a PASS.

SanDisk TCP 2224 is currently uplink-only (`wlan1`). A downstream handheld cannot
be assumed to have management access. Review a narrow downstream access policy
and independent pinned pairing before deployment; no bind-to-all listener or
firewall rewrite is approved. Storage and optional-device behavior can be tested
separately from management access. The optional monitoring lab is not a required
gateway integration test; no packet capture or radio disconnect is implied here.

## 3. Consistent root capture

The approved restoration-only trial and basic post-trial SSH/browser/storage
follow-up passed; see [native evidence](ROOT-RESTORATION-TRIAL-REVIEW.md).
This did not produce a consistent root capture or prove native failure recovery.

Next design gate: a source-only capture worker with a bounded exact-size host
destination, private provenance, transport/completion handshake and enforced
read-only capture lifecycle. Test disconnect, truncation, unknown mount state
and restoration failure in fixtures. A capture interrupted by rw restoration
must never be qualified as consistent. No live capture or repeated service
interruption/remount is authorized until separately reviewed and approved.

## 4. Boot / recovery

The rescue image exists in a private backup, but its startup can invoke a
destructive updater. Do not boot rescue as an inspection method. See
[recovery review](RECOVERY-IMAGE-REVIEW.md).

Next: establish independently usable failed-boot access and the exact physical
unit's bootloader/partition recovery route. Successful restore and post-restore
vendor/management checks are required before calling a candidate flash-ready.
Checksums, clean offline fsck and the ro/rw trial cannot satisfy this gate.

## Immediate user evidence needed

- Fresh SD diagnostic output, without credentials or private logs.
- Whether GameHack and Pi are powered and available for read-only link checks.
- For the already approved speed baseline, exact synthetic-file locations from
  the Files view; both originally expected URLs returned 404. Do not re-upload
  or search unrelated files. See [baseline](TRANSFER-SPEED-BASELINE.md).

No formatting, repair, reboot, flash, rescue boot, network change or cleanup is
performed by this checklist or the SD diagnostic improvement.
