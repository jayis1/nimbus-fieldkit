# Existing SFTP rejection — read-only review

The user approved checking existing SFTP without automatic service changes. The
PC client, with strict pinned port-2224 host identity and key-only authentication,
returned `subsystem request failed on channel 0` and closed. No transfer ran.

## Retained build evidence

`/tmp/opencode/nimbus-ssh-review/dropbear-2026.94/localoptions.h` sets
`DROPBEAR_SFTPSERVER 0`. The retained binary SHA-256 is
`1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c`,
matching the executable digest pinned in `device/ssh/start-ssh.sh`.
`docs/SSH-COMPATIBILITY-CANDIDATE.md` and `docs/CUSTOM-ROOTFS-CANDIDATE.md`
also explicitly document disabled SFTP.

Dropbear's reviewed `src/svr-chansession.c` subsystem branch is compiled behind
`#if DROPBEAR_SFTPSERVER`; with it disabled, subsystem requests reach the unknown
subsystem rejection path. Its default options also explain that Dropbear does
not supply the separate SFTP server executable. A supported server alone cannot
enable the disabled branch in this management binary. No runtime option is
assumed to reverse that compile-time decision.

This identifies a build explanation for the observed refusal, not a fresh
attestation of the running executable. Next host-authenticated read-only check
will hash `/root/nimbus-ssh-test/dropbearmulti-bound` on-device and inspect only
four conventional server paths for existence/type/executable permissions. It
will not read keys, execute candidate servers, enumerate user media, stop SSH,
install packages, remount, write files, reboot or flash.

## Next change boundary

### Returned on-device inventory

The owner returned successful pinned SSH inventory:

- `/root/nimbus-ssh-test/dropbearmulti-bound` SHA-256 matches the retained
  SFTP-disabled build exactly:
  `1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c`.
- `/usr/libexec/sftp-server` exists, reported as a root-owned regular executable,
  mode 0755, 34508 bytes, date Apr 4 2012.
- `/usr/lib/openssh/sftp-server`, `/usr/lib/sftp-server` and
  `/opt/nimbus/sftp-server` were absent at those exact paths.

The server was not executed or hashed by this inventory. Existence, permission
bits and old timestamp do not establish architecture/libc compatibility,
security, confinement or protocol operation. No claim of absence elsewhere is
made. The on-disk SSH binary is confirmed, not independently attested against
the listener's `/proc` executable in this check.

Next proposed development step is host-only review of the existing server's
provenance, ELF dependencies and protocol/security behavior, plus a separately
named SFTP-enabled SSH candidate retaining current hardening. Any native
temporary listener or execution still requires its exact scope, server-side
storage confinement, fresh identity/power/ownership checks and separate approval.
No active executable replacement, restart or extra listener is authorized by
this inventory.

Existing SFTP is unavailable on the checked connection. The companion's free
capability probe must retain honest unavailable/unknown states and cannot enable
browsing/transfers merely from SSH login or a candidate path's existence.

Enabling it would require a separately reviewed compatible SSH build and
compatible server (or another explicitly approved authenticated protocol),
cross-toolchain/libc/architecture verification, least-privilege storage scope,
private backups, guarded deployment/rollback and separate native approval. Do
not replace the active management listener or reuse completed SSH/root trials.
Keep the independent known-pinned recovery listener responsive if a separately
approved management experiment is eventually designed; it is not guaranteed
recovery. Firmware flash readiness is unchanged.

Root SFTP would expose administrative filesystem authority; app-side path
filters are not server-side confinement. Production phone file access needs a
reviewed dedicated restricted identity/server scope, internal/SD ownership and
read-only/write policy, no-overwrite/readback handling and secret-file separation.
Do not relax password/forwarding/interface/host-pin rules to enable transfers.

This review authorizes no live service change or deployment. Physical SanDisk
access remains outside the Virtual Nimbus unlock.

## Restricted-service implementation follow-up

The user requested fixing authenticated file access after the companion probe's
USB and normal-state observations passed. Offline review rejected the retained
old server as the new-service candidate: executable stack, vendor loader and old
library dependencies. A separate maintained OpenSSH/internal-sftp profile is now
prepared for a dedicated non-root, key-only, read-only jailed service, leaving
management Dropbear unchanged. See [the candidate and USB lifecycle gates](RESTRICTED-SFTP-CANDIDATE.md).
This is source/configuration preparation, not an installed runtime or native
listener. No existing authentication, accounts, keys, services or mounts changed.
