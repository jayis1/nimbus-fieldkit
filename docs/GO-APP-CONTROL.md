# GO app-control boundary — host protocol checkpoint

`scripts/wardrive-go-control.py` is a host executable specification connecting
enrollment policy, bounded framing, session consent and clock exchange to the
existing GPS/session model. **It is not SSH/TLS, native authentication, a listener,
an app implementation or a running endpoint.** It creates no keys/accounts/files,
starts no worker and performs no radio/network/device operation. Python remains a
host test tool, not a new dependency installed on the SanDisk.

## Dedicated identity and transport authority

The in-memory registry accepts at most8 explicitly approved, structurally valid
public Ed25519 keys. It refuses management/file-browsing key reuse and duplicate
enrollment, including silently re-enrolling a revoked key. Public-key parsing is
reused from the reviewed confinement policy; parsing is **not proof of possession**.
No actual owner key, client private key or account table was read/prepared here.

One active channel per enrolled identity. A future trusted transport adapter must
supply verified client-key possession, pinned server identity and its connection
binding **out of band**. `TransportEvidence` is a typed fixture/adapter context,
not a cryptographic verifier. Client JSON cannot supply or override it. Native
verification remains a separate gate. IP/hostname/listener/username/session IDs
are not substitutes for authentication.

Each channel gets a fresh server-generated challenge and each enrolled identity
a private principal identifier. The host uses standard system-backed `secrets`;
native entropy/boot/reconnect replay handling is still unqualified. These IDs are
not credentials and their random generation does not authenticate the peer.

Revocation requires explicit owner approval and closes the model's channel,
clears pending framing/clock state and stops its modeled session immediately.
It rejects new channels for that key. Transport close/EOF, malformed/replayed/
cross-channel requests and a backwards server clock also fail closed. Actual
worker notification, drain and network disconnection are **not wired up** by
these in-memory operations. Registry persistence/reset and per-key rate limits
remain native implementation work.

## Versioned framing / request contract

- Four-byte unsigned big-endian body length,1–2048 bytes.
- Incremental parser with bounded buffer/chunk and at most8 returned frames per
  feed. Oversized/zero lengths, too many frames, bad JSON/UTF-8, duplicate/unknown
  fields, nonfinite numbers and truncated EOF are refused without echoing input.
- Envelope: exactly `schema`, `channel_id`, `request_id`, `operation`, `body`.
- Schema `nimbus-go-control/v1`; request ID increasing,1–4096 per channel.
- Allowed operations: start/status/stop/clock_begin/clock_reply/location. There
  is no shell/command/path/radio-setting/scan/relay/upload operation.
- Start body: duration_ms,consent,tier,location_mode. Only explicit consent,
  `pocket` tier and `foreground` sharing are accepted. Independent server-side
  capability gates still have to pass; wire data cannot turn them on.
- Location body contains exactly one `sample` using `nimbus-go-location/v1`.
  Existing session ID/sequence/acquisition replay, staleness/accuracy/permission
  rules apply. Public status returns no coordinates and always flags source-only,
  native unverified, radio not started and records not persisted.

No encryption/authentication is supplied by framing. JSON/body size bounds do
not provide an accept-loop/per-key CPU or connection rate limiter. Each frame is
processed in order; a later invalid frame can stop a modeled session begun by an
earlier frame. This is not an atomic request batch or a guarantee about delivery
to a native worker.

## One-use clock exchange

1. An active consented session requests `clock_begin`. Server records its own
   monotonic send time, generates a one-use nonce and invalidates the old fix/
   binding while exchange is pending.
2. The foreground app samples phone UTC **after receiving that nonce**, returning
   exactly nonce and phone_utc_ms through the same authenticated channel.
3. Server uses its monotonic reply-receive time; round-trip must be at most1900ms.
   Map phone UTC to the midpoint of that interval, with ceil(RTT/2)+50ms margin.
4. One-use nonce, increasing request ID and channel challenge prevent ordinary
   reply/frame replay. Across refreshes, phone UTC must stay consistent with the
   previous monotonic mapping within both uncertainty bounds and margin; a large
   wall-clock jump/frozen old timestamp refuses instead of retagging stale GPS.

The50ms margin and phone sampling/clock-drift assumptions need actual platform
qualification. An enrolled app can still lie about UTC, provider, permission,
accuracy or coordinates; this is not hardware-attested GPS. The measured interval
does not prove those claims or provide cryptography. Missing/rejected/stale fixes
remain unknown; no old point becomes fresh through a new challenge.

## Transport implementation direction / unresolved gates

A constrained channel using the maintained reviewed SSH runtime is a candidate
because device wall-clock synchronization must not be assumed. Do not reuse
root2224, its key, the SFTP file role, an unrestricted shell or the existing vault
upload API. No transport/listener/port/configuration is selected or installed by
this specification. Any GO endpoint needs distinct enrollment/revocation and a
strict server-selected handler: no PTY, environment overrides, agent/X11/port
forwarding, arbitrary original command or private key on the drive.

If SSH is selected, review its external forced-command **shell execution**
semantics: assigning `/bin/false` from the SFTP account plan is not automatically
a working safe GO shell/handler. Native auth/privsep, account writer coordination,
durable recipient provisioning/reset, dedicated launch identity/group policy,
clock framing implementation and app permission/hotspot tests remain required.
Do not create an account or add command access to an existing role to get a pass.

## Evidence

22 new fixtures passed for identity reuse/approval/capacity, transport evidence
separation, channel ownership/revocation, pocket/foreground consent/server gates,
request replay, framing bounds/fragmentation/truncation, malformed/auth-claim
messages, clock challenge/latency/continuity, private GPS flow and redacted status.
All authentication/capability contexts are synthetic; no device result is implied.

Latest scoped totals:80 GO tests plus104 SFTP tests, no skips. Full workspace
regression was not rerun. The new host model is not in immutable beta5 or the
earlier ARM worker/probe builds. No native trial, private provisioning or owner
credential change occurred in this batch. BusyBox is unchanged; WiGLE deferred.

A subsequent first-party C opaque-frame decoder/probe now matches bounded
framing with host differential tests; no JSON/auth dispatcher or endpoint is
supplied. Latest targeted GO total88 tests. See
[native framing component](GO-NATIVE-FRAMING.md). It was not run on the drive.
