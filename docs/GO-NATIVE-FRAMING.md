# Native GO framing — inactive component

`device/wardrive-go-framing.h` implements the host contract's four-byte big-endian
length and bounded opaque-frame buffering in first-party C. It supplies no JSON
parser, authentication, request dispatch, enrollment, listener or radio operation.
**A correctly framed payload is not an authorized GO request.**

Limits:1–2048-byte bodies,2052-byte feed chunks,8 returned frames per feed and
4096 total frames per decoder lifetime. Fragmentation/coalescing is supported;
bad/zero lengths, chunk/batch/total overflow and truncated EOF latch failure.
An invalid feed clears its returned batch, so handlers must not dispatch failed
batches. Previous successful feeds are not rolled back. Private bodies are never
printed by the probe; clearing buffers is not a secure-erasure guarantee.

`device/wardrive-go-framing-probe.c` accepts only `--probe-frames` with inherited
pipe/socket stdin. It discards opaque payloads and prints only counts/fixed status
with `auth_verified=no native_go_verified=no`. It uses nonblocking reads/select,
a1-second monotonic read-loop deadline, bounded input and HUP/INT/TERM handling.
It never forks, executes a command, reads a supplied path, writes payload records,
binds a socket, scans, changes radio/settings, installs an account or updates
BusyBox. Deadline/signal behavior is not an absolute guarantee for stuck kernel
I/O. This is not a network accept loop or independent session guardian.

Eight host tests passed, including differential fragmented batch counts against
the host model, maximum/total/chunk/batch bounds, malformed/truncated input,
private opaque payload suppression, EOF/deadline/cancel and argument/input-type
refusal. Opaque NUL/non-JSON data can frame correctly by design; a later reviewed
JSON/auth handler must reject it before any operation.

Pinned builder: `scripts/build-go-framing.py`.
Retained inactive artifact: `build/nimbus-go-framing-v1/go-framing-probe.arm`,
37908 bytes, SHA-256
`e735030b476a5994f0add2c9b528f2f0694db7fcef3e4dcd183234ac6968c04a`.
Static ARM EABI5 ELF/non-executable stack/GNU_RELRO, emulated no-argument refusal
and one synthetic opaque frame passed. **No native framing probe was staged/run**;
earlier synthetic-supervisor approval is not permission for a new endpoint/trial.
Native JSON/state dispatch, transport authority, dedicated account/launch policy,
durable enrollment/revocation and vendor-writer coordination remain open.

Latest targeted regression:88 GO plus104 SFTP tests passed, no skips. Full suite
results and publication status are separate checkpoints, not firmware readiness.
The rootfs remains NOT FLASHABLE; private data/build outputs are not publication
inputs. WiGLE stays deferred.
