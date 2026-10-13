# Unofficial 64 GB Media Drive firmware — feature freeze

Owner instruction, 2026-10-13: **no new features until all previously requested
features are implemented, confirmed and ready for the unofficial update**.

This freeze supersedes open-ended wishlist expansion. Only implementation of
already agreed scope, bug fixes, integration, evidence collection, security,
recovery and release qualification may proceed. No new feature is implicitly
approved by adding it to a roadmap. Speculative tool feasibility lists are not
automatically new release commitments.

Target: SanDisk Wireless **Media Drive**, advertised **64 GB internal storage**.
No compatibility is assumed for Wireless Stick/Flash Drive, other capacities or
unverified hardware/bootloader revisions. A spare is not required: retain the
owner's accepted single-drive testing constraint and explicit remaining risks.

## Frozen work and acceptance ledger

| Existing scope | Actual state | Required before release |
| --- | --- | --- |
| Stock Files/Photos/Videos/Music/uploads/settings | Preserved in sources and installed UI; partial native evidence | New-image end-to-end regression, error/cancel/auth tests, media integrity |
| Unified dark/light homepage, quick jump, Nib, layout/performance | Implemented; fixture/native UI evidence varies | New-image narrow-screen, reduced-motion, navigation and no-handler-regression checks |
| Battery/charging and current dashboard | Live header renders 100%/Full; independent standalone-reader fix in beta5 | Native Overview, discharging/zero/failure/staleness checks; no percentage inferred from charger/voltage |
| Honest telemetry/storage/service inventory | Snapshot publisher exists; live media runtime currently missing | Publisher placement/lifecycle with USB-safe ownership; stale/error behavior and truthful metrics |
| Persistent independent feature flags | Implemented shell settings and capability gating | Recipient-state persistence, OFF default, unsupported-ON refusal; flags do not silently start work |
| Health, bounded watchdog, storage warnings, docs | Implemented shell/host helpers | Image-native operation and cancellation, no routing/radio/service changes |
| Verified vault/copy/sync and pre-encrypted archive storage | Implemented bounded single-file operations | Native size/hash/collision/failure tests, private placement and USB-owned-storage refusal |
| Speed tests and local Git | Dependency-gated helpers | Reviewed compatible runtimes and native bounded functionality; absent dependency is not completion |
| Pinned key-only management, legacy hardening | Live key-only management and prior reboot checks; image setup unresolved | Unique recipient identity/enrollment/entropy, first-use access, reset/Wi-Fi and legacy-account/service exposure review |
| Restricted read-only SFTP and GameHack file browsing | Separate ARM candidate and staged handheld integration | Non-root jail/auth/denial/enrollment, USB-safe teardown, native browse/download integrity |
| GameHack Wi-Fi → managed Pi A → A USB/data → Pi B | Architecture agreed; source/deployment incomplete | Per-node identities, power/USB roles, explicit relay/results/cancel, native peer reachability and standalone degradation |
| Wardriving GO: phone+SanDisk, optional A/B, optional GameHack | Pocket session/GPS/cache source models; native roles and synthetic own-child cleanup evidence; not enabled | Permissioned timestamped/accurate/stale GPS, least-privilege session endpoint, private bounded logs, real scan/coexistence/monitor capability and per-tier native tests |
| SD writable policy and media/USB handoff | Bounded live write/handoff evidence exists; startup returns read-only | Safe persistent policy that never overrides unknown locks, damage or host ownership; boot/handoff native tests |
| Complete unofficial installation/update | beta5 is rootfs-only, NOT FLASHABLE | Consistent private rollback input, independently usable recovery, preservation-safe container/write plan, failure/readback/native boot validation |
| Shareable recipient build | Clean pinned inputs; selected privacy/module checks | No owner credentials/data, recipient onboarding/reset tests, licenses/source notices and explicit hardware matrix |

“Confirmed” requires evidence at the appropriate layer: source, fixture, artifact,
native device and recipient setup are separate. Local passing tests cannot stand
in for hardware, power-loss recovery or licensing review. Unavailable telemetry
must remain unavailable rather than mark a gate done. Remaining obligations are
not dropped simply to call the image complete.

## Execution order

1. Fix test portability/known skips and regressions; keep immutable candidate
   provenance tests independent of later working-tree revisions.
2. Finish battery/dashboard lifecycle and read-only capability inventory, then
   qualify native runtime/media placement without changing USB ownership blindly.
3. Complete host durable-ACK and native reader cancellation/drain qualification;
   review current management prerequisites and obtain separate exact approval
   before service interruptions, remounts or raw capture.
4. Finish read-only SFTP and recipient provisioning/reset/access contracts, with
   native qualification and preservation of working management.
5. Implement remaining already agreed GO/GPS and A/B integration; keep live radio
   actions disabled until capabilities, authorization, bounds and restoration pass.
6. Complete SD/USB policy, safe installation/recovery and native image acceptance.
7. Rebuild from reviewed clean inputs, audit privacy/licenses/hardware evidence,
   and only then assess update readiness and separately review publication.

Parallel source-only fixes are allowed; prerequisites for a native/destructive
step must still be satisfied. The freeze is not blanket authorization to flash,
reset, format, remount, enable listeners/radios or publish. Do not rerun retained
trials, recreate 2225 blindly or discard previous evidence to obtain a pass.

Current baseline: [beta5 and known gaps](FIRMWARE-64GB-BETA5.md),
[release requirements](SHAREABLE-FIRMWARE-RELEASE.md),
[single-drive approval/evidence ledger](SINGLE-DRIVE-QUALIFICATION.md).

## First frozen-scope qualification checkpoint

The historical vendor-module comparison passed using the explicit hash-verified
clean vendor input: ten custom-image tests, **zero skips**. The capture-specific
regression passed **107 tests**, including the new full-size synthetic host
sync/readback/ACK case. No device operation was performed. Native capture under
reader load, native host-ACK integration, physical recovery, complete firmware
and the other frozen feature gates remain open.

## Media runtime follow-up

Read-only native inspection found loaded `g_file_storage`, absent media mounts
and no expected publisher runtime. The new read-only guard correctly refuses
`/mnt/storage` without creating a substitute. Source-only boot, publisher,
settings and transfer fixes now enforce sampled media checks; see
[ownership safeguards and limitations](MEDIA-OWNERSHIP-GUARD.md).
These changes are not installed on the drive or present in retained beta5.
Positive native publication/USB lifecycle testing remains blocked until a
separately reviewed normal ownership transition; no USB-mode change is made to
manufacture a PASS. No new feature was added.

## Restricted SFTP follow-up

Confinement metadata checks, dedicated public-key enrollment preparation and the
shutdown/USB decision model are implemented/tested as host-side source tools:
[checkpoint and limitations](SFTP-CONFINEMENT-ENROLLMENT.md). Native runtime
execution, trusted metadata collection, account/host-key provisioning, service
supervision, SFTP denial/readback and USB handoff still require completion.
These tools do not change the currently installed drive or beta5's readiness.

Read-only [layout collection and probe preparation](SFTP-LAYOUT-PREFLIGHT.md)
followed: native metadata frame parsed successfully, but confirmed no SFTP layout
or dedicated accounts. A version/probe-only package is prepared, not staged/run;
fresh charger online=0 blocks execution and exact trial approval is pending.

The owner subsequently approved that exact probe-only scope **after power check**.
The fresh read-only power recheck again refused online=0; no staging or candidate
execution occurred. Approval does not waive prerequisites or authorize a server.

After charging-only power prerequisites passed, that approved one-shot native
trial completed: OpenSSH 10.6p1 version and select/pselect passed; raw libc poll
failed as anticipated, and the selected fallback passed. Pinned management and
vendor homepage/battery follow-up worked. The used stage/PC evidence are retained.
Only process compatibility is qualified; service authentication, jail and USB
handoff gates remain open. See the [completed native checkpoint](SFTP-LAYOUT-PREFLIGHT.md#completed-native-process-probe--2026-10-13).

Next source batch implements an append-only private account planner and pins the
OpenSSH account-lock review. It preserves existing tables, refuses identity/group
collisions and distinguishes the password-unusable file-login marker from the
locked privsep account. Role-home evidence was tightened in the collector/parser.
No drive account change occurred; vendor writer/reset semantics and native
authentication remain open. See [account provisioning gates](SFTP-ACCOUNT-PROVISIONING.md).

The approved private baseline copy and local per-device account plan now passed
source/saved-file checks, without displaying contents or changing the drive.
Live shadow was found mode0744: permission hardening remains a security gate,
not fixed by private PC copies. Account writes/native auth/vendor persistence
are still unqualified. Private baseline-derived tables are never generic release
inputs; see the updated provisioning checkpoint.

The observed live shadow0744 defect has now received a scoped permission-only
native fix to0600, with independent unchanged-byte/inode checks and management/
basic vendor follow-up. This qualifies current mode, not writer exclusion,
reset/reboot persistence or native SFTP. Failed/used stages are retained; see
[hardening checkpoint](SHADOW-MODE-HARDENING.md).

The known shadow- backup has also been tightened to0600 without changing bytes;
all four known account-file hashes/inodes were independently checked. This is
current-mode hardening only. Actor coordination, native SFTP and persistence
remain separate gates; no frozen feature was declared complete from permissions.
