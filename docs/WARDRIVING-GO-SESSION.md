# Pocket Wardriving GO — first source checkpoint

The first tier is **phone + SanDisk**, with no Pi or GameHack prerequisite.
This checkpoint implements a host-side protocol/state model and fixtures;
**it does not provide a phone app transport, native endpoint or working scan**.
No listener, permission prompt, background task, scan, radio-state change, location log,
mount or firmware change was performed. Source is not included in retained beta5.

WiGLE was discussed with the owner and explicitly deferred until after the
existing frozen firmware work. WiGLE export/account integration/upload is not
added to current GO scope; no automatic cloud sharing or WiGLE credentials are
introduced. Continue the agreed local pocket workflow first.

## Implemented model

`scripts/wardrive-go-session.py` models explicit consent, owner/session binding,
bounded start/status/stop, clock binding, GPS ingestion and private attribution.
No filesystem/network/subprocess interface exists. Python is a host test tool,
not an assumption about the drive's runtime. A compatible least-privilege native
implementation must separately enforce these rules.

Start requires independently qualified authenticated non-root transport,
authorized survey scope, scan/coexistence, private storage/media ownership,
bounded worker and restoration gates. Fixture `True` flags are not attestations
and cannot start a radio. Every status reports `source_model_only: true`,
`native_verified: false`, `radio_started: false`, `records_persisted: false`.

- Duration: 1–900 seconds; maximum sequence1800; wire message at most1024 bytes.
- Location: explicit granted/denied/revoked permission, native GPS/fused provider,
  acquired phone UTC timestamp, latitude/longitude and accuracy metres.
- Reject unknown/duplicate fields, malformed JSON, nonfinite/out-of-range values,
  booleans as numbers, wrong session, reused sequence and acquisition timestamps.
- An authenticated clock exchange must bind phone UTC to device monotonic time.
  No assumption of synchronized wall clocks. Maximum binding age60 seconds and
  conservative uncertainty1 second. The exchange itself is **not implemented**.
- A current fix must be at most5 seconds old including uncertainty, with accuracy
  at most100 metres. Future/clock-mismatched, stale, inaccurate or missing fixes
  are unknown, never plausible substitute points. Zero coordinates are valid.
- Status refresh ages fixes even without a new phone sample. Binding refresh
  clears previous coordinates. Monotonic clock regression stops the model.
- Denial/revocation clears coordinates and the clock binding, and disallows
  silently restarting sharing in the same session. Unavailable/suspended fixes
  clear coordinates; the model does not itself stop an external scanner.
- Private observation attribution refuses future observations, fixes acquired
  after an observation and stale fixes. There is no historical backfilling.
- Duration expiry, explicit stop or signalled link/storage/worker capability loss
  clears sharing. No automatic reconnect, remount, channel change or Pi fallback.
- Completion requires drain **and** restoration evidence; otherwise it remains
  `restoration_unconfirmed`. This is a modeled decision, not proof of either.

Coordinate-free status and redacted object/error representations avoid exposing
fixes through normal status/debug output. Actual observation/map data is private:
callers must not print it or place it in stock web/FTP shares. Model memory is not
at-rest encryption or guaranteed secure erasure.

## Location envelope

Version: `nimbus-go-location/v1`. Exactly these keys are accepted:
`schema`, `session_id`, `sequence`, `permission`, `fix_status`, `provider`,
`acquired_at_ms`, `latitude`, `longitude`, `accuracy_m`.

Session/principal identifiers are32 lowercase hex characters supplied by future
enrollment/session creation; unguessability is not authentication. Non-fix
messages use provider `none` and null acquisition/coordinate/accuracy fields.
No root key, arbitrary shell, radio command, target path or opaque payload belongs
in this envelope. Network/body limits, authentication and rate limiting must be
enforced **before** parsing by the future transport; this model supplies none.

Native app foreground sharing is the intended initial GPS source. Plain HTTP
vendor pages are not assumed to have browser geolocation permission. Hotspot
internet is not GPS transport or proof that phone/drive peer routing works.
Background location remains OFF; no phone platform permissions were changed.

## Evidence and next step

22 fixtures cover all independent start gates, bounds/consent, valid/zero fixes,
denial/revocation/suspension, stale/future/inaccurate fixes, clock age/uncertainty,
sequence/acquisition replay, cross-owner/session access, malformed input/privacy,
expiry/cancel/drain/restoration, capability loss and private attribution.
These are synthetic inputs only, not physical location or hardware evidence.

An additional collector source-safety test passed: **23 GO tests total**, no
skips. The existing104 SFTP tests also passed; full workspace regression was not
rerun. Shell syntax and `git diff --check` passed.

### Completed read-only native metadata inventory

`device/wardrive-go-capability-preflight.sh` ran through strictly pinned management
SSH2224, streamed to `sh -s` without installing a file. Exit0; retained evidence:
`/tmp/opencode/go-capability-native-bvxtym01/`. The collector reads fixed sysfs/
proc metadata and selected kernel config only. It does not execute the wireless
tools, issue scan/ioctl commands, read saved network settings or emit SSID/BSSID,
MAC addresses, credentials, coordinates or process arguments.

- wlan0/wlan1 both present, operstate up, wireless sysfs/proc entries observed.
- wl12xx, wl12xx_sdio, mac80211 and cfg80211 modules observed.
- iw, iwconfig and iwlist present **but not executed**.
- Kernel config reported WIRELESS_EXT/WEXT_CORE=y and
  CFG80211/MAC80211/WL12XX/WL12XX_SDIO=m.

These facts do not identify AP/uplink roles or establish advertised driver modes,
active/passive scan behavior, packet support, coexistence, or bounded restoration.
All scan/coexistence/monitor/native-GO qualification fields remain unqualified.
No service/network/radio/media change or live scan was requested.

Next work is bounded worker/cancellation and scan/coexistence trial review,
then a separately approved scan/coexistence
trial. Do not scan or switch modes merely to inventory support. In parallel the
app/endpoint needs non-root enrollment/revocation, bounded authenticated framing
and clock exchange, consent/foreground lifecycle and private bounded records.
Root management and existing SFTP/vault protocols are not the GO endpoint.

Private storage journaling/retention, results/export integrity, an independent
stop/deadline supervisor, USB ownership handling and restoration remain open.
Polling `tick()` in this model is **not** a guaranteed device timeout or continuous
ownership lock. App Android/iOS hotspot/permission tests, actual radio acquisition
labels and native recipient qualification are still required. Optional A→B and
GameHack tiers remain distinct unqualified integrations.

## Subsequent advertised-mode / interface-role query

`device/wardrive-go-radio-query.sh` adds only fixed read-only nl80211 GET queries:
`/usr/sbin/iw list` and `/usr/sbin/iw dev`. It first verifies the existing
standalone hasher and iw binary hashes. iw matches the selected file from the
hash-verified clean-derived beta5 archive:
`468f4271f5af9eaa5380f30b9717a58462baec4596e87461ff23859dfe44321e`.
The output filters disclose only allowlisted modes/interfaces, numeric PHY index
and optional channel/frequency; no MAC/SSID/association identity/configuration is
emitted. No scan, cached-result query or radio mutation command is included.

Completed native run through pinned SSH2224: exit0; evidence
`/tmp/opencode/go-radio-query-native-9h5ygbky/`. Both queries returned successfully.

- One PHY observed. `wlan0` is AP and `wlan1` is managed; **both are phy_index0**.
- Advertised modes include managed, AP, AP/VLAN, IBSS and monitor; two unrecognized
  modes are labelled other, not promoted into supported GO capabilities.
- No interface-combinations evidence was emitted by the selected filter. This
  is not proof that combinations are unsupported, nor a coexistence qualification.
- No channel field was emitted; do not infer the current channel from an absent
  output line or interface role alone.

These are observed roles and driver advertisements, not proof that wlan1 is
currently associated to a phone hotspot, that either interface is independently
tunable, or that monitor capture works. **They are two virtual interfaces on one
radio, not two independent survey radios.** Management remains pinned to2224;
do not switch wlan0/wlan1 to monitor, add/remove interfaces, retune, or reconfigure
routing as a shortcut. A managed-interface active scan may disturb both the AP
and management link and must be separately bounded/approved/qualified.

The host wait was30 seconds, not a claimed native cancellation guarantee. This
successful GET query is not evidence that a scan worker drains on timeout.

## Private cache-observation parser

`scripts/wardrive-go-observations.py` parses supplied iw cache text only; it
executes no command, performs no scan/cache read and writes no records. No real
network identifiers were collected by this work. A future native worker's output
format still needs qualification against this expected text layout.

Bounds:64 KiB input,128 unique records,512-byte lines,128-byte SSID display and
reported cache age at most60 seconds. Required fields are BSSID/interface,
frequency, dBm signal, reported last-seen age and SSID display. Malformed,
duplicate, cross-interface, multicast/zero identifiers, missing fields, truncation
and clock-impossible ages are refused without echoing input. Unselected IEs and
security/vendor fields are discarded. Hidden SSID display stays empty.

The returned private record labels acquisition mode **unknown**, source as
cache, observation time **unverified**, and location **null**. Estimated age from
the text must not be silently joined with a current GPS fix. SSID display escapes
are preserved but **not claimed to be original lossless SSID bytes**. This is not
WiGLE/export work, live scanning, encryption, retention or AP identity/security
assessment. Do not display private returned dictionaries in chat/public status.

Latest source tests:23 existing session/inventory plus4 query-filter and9 cache
parser tests = **36 GO tests passed, no skips**; shell syntax/diff checks passed.
Full workspace regression was not rerun. Native GO/scanning remains unqualified.

Before an active-scan trial, prepare a fixed-command worker with an independent
deadline/cancellation/drain path, explicit active-versus-passive acquisition
label, shared-radio/control-link safeguards, private bounded output and failure
evidence. Verify current inputs/interface roles/pinned management again; obtain
exact approval only once those prerequisites are met. No one-shot live scan was
performed or implicitly authorized by this read-only query.

## Synthetic supervisor source checkpoint

`device/wardrive-go-supervisor.c` implements a first-party own-process probe:
one synthetic child,1-second monotonic deadline,64 KiB output budget, TERM then
KILL escalation, nonblocking pipe drain and direct-child `waitpid(WNOHANG)`.
It uses `select`, not the known-incompatible raw native libc poll path. Output
payload is discarded, never republished in a status/log response.

The only accepted command is `--probe` with fixed synthetic modes normal/flood/
hang/ignore-term/late-output/nonzero. No external executable, radio command,
listener, filesystem writer, account operation or real survey is supplied. Cancel
signals are handled by the parent and reported as cancellation, not completion.
Timeout/output/error paths remain failed/partial even after observed cleanup.

The drain is for **one direct child only**. No full descendant containment or
kernel scan abort guarantee is claimed. Uninterruptible kernel work can outlive
signal/deadline attempts; unconfirmed reap/drain returns an error. Supervisor death
and link-loss supervision still need an independent reviewed guardian. This is
not the whole session watchdog or permission to execute a live scan.

Seven host tests passed covering normal output/drain/reap, worker failure, output
flood, deadlines including ignored TERM, late output, HUP/INT/TERM cancellation,
arbitrary-command refusal and absence of radio/storage executors. Host timing is
not evidence about the SanDisk kernel. Builder:
`scripts/build-go-supervisor.py`; output is a fresh inactive
`build/nimbus-go-supervisor-v1/`. Native staging/execution remains unapproved and
unperformed; completed build/emulation evidence belongs in its manifest.

BusyBox replacement is not required for this probe; see
[update assessment](BUSYBOX-UPDATE-ASSESSMENT.md). Do not substitute an unqualified
new BusyBox globally or treat its timeout applet as worker-drain qualification.

The pinned offline ARM build completed:37908 bytes, SHA-256
`8f6c35894309034b70085181e94f073ce29911f0f8703f047bc956663c0a6081`,
ARM EABI5 static EXEC, non-executable stack and GNU_RELRO. Emulator no-argument
refusal and normal synthetic child/drain/reap passed. This is not native driver
or legacy-kernel evidence. A wrong-SDK refusal test also passed; latest scoped
GO total is44 tests (23 session/inventory +4 query +9 cache +8 supervisor/build).
No actual scan worker was built or run; BusyBox remains unchanged.

## Controller-death / control-channel source follow-up

Supervisor v2 adds Linux `PR_SET_PDEATHSIG(SIGKILL)` for its own synthetic child
and a parent-ID recheck to close the fork/guard setup race. A killed parent does
not imply its replacement parent has reaped the terminated child; the host test
accepts a terminated zombie as **not running**, never as drain/reap proof. This
does not contain grandchildren, ensure a scan is cancelled inside a driver, or
provide a separate durable session guardian.

`--probe-controlled` accepts an owned pipe/socket on stdin, makes reads
nonblocking and accepts the fixed first frame `STOP\n`. EOF cancels; invalid or
truncated control input refuses/cancels without echoing it. Fragmented STOP is
handled. Regular-file control inputs are refused before fork. Input controls are
not authenticated transport; there is no new listener, peer identity or permission
to feed a real scan command. Stop only controls the synthetic child.

Four additional host tests cover EOF/STOP/malformed frames, regular-file refusal,
fragmentation and supervisor death. **48 scoped GO tests passed**, no skips;
full regression was not rerun. `git diff --check` passed.

Retained inactive build `build/nimbus-go-supervisor-v2/`:42004 bytes, SHA-256
`1b8c59f51a2663d3d7495ab2baa7c2e3c2a4eb013c103effa1994d253c71c4e3`.
Static ARM EABI5 ELF/non-executable-stack/GNU_RELRO audit and emulated no-argument
refusal, normal synthetic child and control-EOF cancellation/drain/reap passed.
Original v1 is retained unchanged. At this offline checkpoint neither build had
been staged/run on the drive; the later approved v2 run is recorded below.

### Initial native-probe proposal / approval boundary

Next qualifying action is a separately reviewed **synthetic own-process probe**,
not a survey: pinned SSH2224; fresh private tmpfs stage
`/tmp/nimbus-go-supervisor-probe-r1`; verified compressed input and binary hash;
one retained claim; fixed short normal/flood/hang/ignore-term/nonzero and controlled
EOF/STOP probe invocations. Retain private host outputs and stage, including on
failure. Validate current reachability/identity/resources before staging; stop on
failed prerequisites without repairing/reusing the stage to obtain a pass.

No native controller-SIGKILL trial is bundled implicitly; host guard coverage is
not native parent-death qualification. No scan, iw execution, radio/network/mount/
service change, media/account write, listener, reboot, BusyBox replacement or
firmware operation is part of this proposed probe. It tests select/fork/prctl/
signals/monotonic-time/own-child cleanup on the legacy kernel. It cannot qualify
scan-driver abort, full descendants or coexistence. This was the initial exact
approval boundary; subsequent owner approval and scoped completion follow.

## Approved native synthetic probe completed

Owner explicitly selected **Approve synthetic tests** after reviewing the fresh
private temporary stage and own-process-only scope. No Wi-Fi scan, service/
settings change, BusyBox update or firmware operation was included in that
approval. It is not authorization for later radio trials or automatic retries.

The fresh preflight passed through pinned SSH2224: authorized root/ARM machine,
root-owned sticky `/tmp` mounted tmpfs,3836 KiB free, external power observed,
reviewed standalone hasher matched and proposed stage absent. These are sampled
preconditions, not resource reservations or continuous ownership guarantees.

Fresh stage `/tmp/nimbus-go-supervisor-probe-r1` was created0700. Saved compressed
input was hash-verified before extraction, then payload hash/metadata checked;
binary was made0700 only after matching the reviewed hash. Package23781 bytes,
SHA-256 `959aa4643faa90c869f4f7b7a8b127a7deb312e27c86e145422debed05907767`.
One retained `CLAIM=ATTEMPTED` preceded the seven fixed invocations:

| Synthetic case | Observed exit/result | Cleanup |
| --- | --- | --- |
| normal | 0 / completed,128 bytes | own child reaped, pipe EOF |
| flood | 6 / output_limit,65536 bytes | own child reaped, pipe EOF |
| hang | 3 / timeout | own child reaped, pipe EOF |
| ignore-term | 3 / timeout | own child reaped, pipe EOF |
| nonzero | 5 / worker_failed | own child reaped, pipe EOF |
| control EOF | 7 / control_closed | own child reaped, pipe EOF |
| control STOP | 7 / control_stop | own child reaped, pipe EOF |

Unexpected exit/format/stderr would have stopped the sequence with retained
evidence, not retried it. All expected cases matched; stage retains
`COMPLETE=SYNTHETIC-CASES-OBSERVED`. Deliberate failure cases correctly remained
failed/cancelled, never actual survey success. No synthetic payload was published.

Private PC evidence/receipt:
`/tmp/opencode/go-supervisor-native-r1-2vi8p7cf/NATIVE-RECEIPT.json`, including
package, plan, exact runner and before/stage/run/follow-up logs. New pinned
management session passed; vendor homepageHTTP200; shadow and shadow- metadata
still root-owned single-link0600. Live BusyBox and iw binary hashes matched their
reviewed baseline. This does not recertify all accounts, services or media integrity.

This qualifies the observed **legacy-kernel synthetic runtime and own-child
cleanup** for these cases. It does not qualify controller-SIGKILL behavior on
the device, descendants, independent session guardian, scan-driver abort,
AP/uplink coexistence, authenticated app transport, location logging or native GO.
No iw command, real scan/cache read, radio/network/mount/service change, account
write, BusyBox replacement, reboot or flash occurred during this probe.

**Keep the used stage/claim and immutable v1/v2 builds. Do not rerun/recreate the
trial by default or change old build manifests to claim later native success.**
The next real-worker design must cover descendants/controller loss and private
outputs on the shared radio, then receive its own qualification/approval.

Latest source follow-up supplies a pinned fixed **read-only** iw worker with
non-root/capability checks, descriptor execution, stripped environment/inherited
fds and ordinary-fork limits; it is not a full sandbox or scan worker. Inactive
ARM artifact and58 GO /104 SFTP tests passed. No new device operation occurred;
dedicated identity, native exec/dependencies and containment remain open. See
[read-only worker evidence and gates](GO-READONLY-WORKER.md).

Next host checkpoint adds app-control enrollment/revocation policy, bounded
framing and one-use clock exchange coupled to this session model. It is not a
cryptographic verifier or native endpoint.80 GO/104 SFTP fixtures passed; no
device operation. See [app-control contracts and gates](GO-APP-CONTROL.md).
