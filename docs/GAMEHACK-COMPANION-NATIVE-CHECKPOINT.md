# GameHack companion probe: first native checkpoint

## Returned owner-run evidence

The owner connected using the existing admin key and strict host checking against
the retained known-hosts file on management port 2224. The encrypted client key
required its passphrase locally; the earlier agent BatchMode authentication failure
did not establish that the authorized key had been removed. No passphrase was
collected or authentication policy changed.

The owner streamed `device/nimbus-companion-status.sh` to `sh -s` through that
session, without installing a device file. It returned valid
`nimbus-companion-status/v1` JSON with:

| Observation | Result |
| --- | --- |
| Internal local mount | absent |
| SD main local mount | absent |
| SD FTP local mount | absent |
| USB export module | active |
| Management TCP 2224 listener | observed |
| Remote browsing/SFTP/backup transfer | not qualified |
| Network/mount/remote-write permissions | false |

The PC independently enumerated the SanDisk internal and card media as USB disks
with no PC mountpoints at its inventory checkpoint. The handheld's 256GB card is
a separate disk and must not be ejected or altered as part of this workflow.

This confirms the shell/awk report runs on the physical drive and refuses to
advertise transfer readiness while USB owns media. It does not prove sustained
ownership, writable media, SFTP, downstream GameHack pairing, playback, or native
failure recovery. JSON authentication/host-pin fields deliberately remain
`not_tested`: those checks are external SSH-client evidence, not something the
remote report can authenticate about itself.

No mount, media write, installer, service change, radio change or image write ran.
The minimal source-only archive remains immutable:
`build/nimbus-gamehack-companion-status-v1.tar`, SHA-256
`2246ddd03c211490fa7ffac73c0259252eba40613a2a620677e0205ad5f589c3`.
Validation: 12 companion probe/packaging tests and 2 native-kit packaging tests
passed. First native observation passed; native failure paths remain untested.

## Next normal-state gate

The owner should safely eject the SanDisk USB device using the PC's normal eject
workflow and physically disconnect its USB data connection, retaining device
power. Eject alone does not prove that the drive has stopped exporting media.
Do not manually load/unload a gadget or invoke vendor automount/repair scripts.

Re-run the same strict-pinned streamed helper after normal vendor restoration.
Required observations are export inactive and known local media mount states.
Unknown/absent state remains blocked; do not force a mount to satisfy the gate.
Compare with browser internal/SD visibility. Existing SD boot/USB-return read-only
policy is not automatically changed by this integration work.

Only after this gate should the next restricted authenticated transport and
downstream pairing design be reviewed. Existing root management access is not
production app-side storage confinement. Pi routing/pairing stays independent.

## Returned normal-state evidence

After USB disconnection, the owner reran the same strictly pinned key-authenticated
streamed helper. Its report returned internal `read_write`, SD main `read_only`,
SD FTP `read_only`, USB export `inactive`, and management listener `observed`.
This completes the probe's USB/normal-state native observation gate. No forced
mount or SD policy change was needed. Basic browser visibility after this specific
cycle, remote file content integrity and current GameHack connectivity remain
separate checks, not supplied by the mount report.

Source-side client work now includes `fieldkit/tools.py` `companion_report` and
the `companion-report` stdin command. It validates the bounded schema, rejects
duplicate fields and self-declared authority, and distinguishes USB blocking,
unconfirmed storage and observed local mounts. Even normal rw mounts never enable
remote browsing or transfers. The reader cannot verify how a saved report was
obtained; SSH-client evidence must be checked separately. This consumer is source
only and has not been installed on the handheld or added to its release manifest.
