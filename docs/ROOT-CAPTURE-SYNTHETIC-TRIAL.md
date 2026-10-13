# Synthetic guardian disconnect trial — prepared, not deployed

Owner explicitly approved the exact synthetic staging/check, one fake-worker run,
loss of only that test SSH client, separate pinned inspection and retained logs.
Bundle hash reconfirmed locally. Device staging/check output is pending; no run
or interruption has been reported. All real-capture/service/mount/flash actions
remain outside this approval. Commands are delivered in phases, with check output
review before worker start.

Owner returned bundle checksum OK, archive extraction timestamp warnings,
guardian checksum OK and `SYNTHETIC-STAGE-CHECK=PASS no-worker-started`.
The archive deliberately has deterministic Unix-epoch timestamps; the native tar
warnings did not prevent extraction or the subsequent hash/pinned-stage check.
No need to alter timestamps, re-extract or retry. Native stage/check passed;
the approved one-shot synthetic run/interruption is next, not yet reported.

Owner ran the approved one-shot guardian command and returned exact
`SYNTHETIC-READY 1d3bba8de518c1b611d4fc1f70a1d3f04624e295179be8a08c866f9831ac8233 no-real-reader`.
Native synthetic worker readiness is observed. Test-client interruption and
retained cleanup records have not yet been returned; readiness alone is not a
disconnect/cleanup PASS. Do not launch a second worker.

## Owner-returned native invalidation/cleanup evidence

Separate strictly pinned 2225 inspection returned the exact session token in
GUARDIAN-INVALID, then:

```text
GUARDIAN-RESULT:
1d3bba8de518c1b611d4fc1f70a1d3f04624e295179be8a08c866f9831ac8233 invalidated=yes worker_exited=yes worker_status=256 restoration_certified=no
SYNTHETIC-RESULT:
1d3bba8de518c1b611d4fc1f70a1d3f04624e295179be8a08c866f9831ac8233 synthetic-only completed=no real_reader_started=no
```

Mount inspection returned `/dev/root` ext3 with the original exact
`rw,relatime,errors=continue,barrier=0,data=writeback` options (plus the normal
kernel rootfs view). Raw Linux wait status 256 corresponds to worker exit code 1,
the expected synthetic abort, not a successful capture or a signaled-exit status.

The limited native synthetic invalidation/cleanup checkpoint passed: matched
token, recorded invalidation, direct-worker exit, fake cleanup record and continued
pinned management/root-rw observation. Interruption timing/cause and SSH client
exit status were not independently recorded; these records do not distinguish
Ctrl+C/EOF/output loss/deadline or establish arbitrary descendant shutdown.
Retain all files; no second trial or cleanup is authorized. Immutable build
manifests keep their offline flags; this returned evidence is the separate native
record, not qualification of the real reader, continuous ro or hardware recovery.

## Proposed approval scope

Separate approval is required before executing the commands below:

1. Upload the **34188-byte** pinned synthetic bundle to a new root-owned 0700
   `/tmp/nimbus-guardian-synthetic-v1` stage; verify size/hash before extraction.
2. Extract only the reviewed seven regular files in that private tmpfs stage,
   and run the pinned guardian's **check-only fixture entry**.
3. Start the guardian once with its synthetic worker. After the fake readiness
   message, interrupt **only this SSH client** once with Ctrl+C, leaving the
   management listeners and other SSH sessions unchanged.
4. Use a separate pinned SSH session to inspect the retained invalidation,
   guardian and synthetic-worker records, plus root mount metadata.

No real capture worker, real streamer, device contents, service control, remount,
reboot, listener changes or firmware write is included. The dummy file named
`streamer` is a pinned, unused shell stub that immediately returns 64 if invoked;
it contains no capture code. The synthetic worker uses shell built-ins only,
emits fake readiness/ACK messages, waits for input and records its own cleanup.
The guardian may send one TERM only to its own unreaped synthetic worker.

Expected results after interruption: exact session token in GUARDIAN-INVALID,
GUARDIAN-RESULT with `invalidated=yes worker_exited=yes` and
`restoration_certified=no`, and SYNTHETIC-RESULT with
`completed=no real_reader_started=no`. No SYNTHETIC-DONE/real ROOT protocol success
is expected. An interrupted SSH client alone is **not** evidence of cleanup.
Retain all stages/logs, including the earlier inert probe. Do not rerun a failed
or completed stage, delete artifacts to retry, restart services or reboot.

This is a small native session/channel/cleanup test, not a continuous-ro,
real-reader/hasher descendant, resource-pressure or physical-recovery qualification.
Kernel stalls/SIGKILL/power loss are still outside userspace recovery guarantees.

## Artifact and provenance

`build/nimbus-guardian-synthetic-trial-v1/synthetic-trial.tar.gz`:

- bytes: **34188**
- SHA-256: `df97a58cba389ded5a9e0b16e1f4fdefed84c0cbc3df546ab3b0c811626e7ec1`
- guardian ELF: 58240 bytes, SHA-256
  `9be5a9496cdfc6acab9245015aaf226a7147668bbc07a1cbd65a3d5a84fa2c60`
- guardian relay source is unchanged from pinned guardian-v2, compiled with a
  **separate synthetic fixture profile and synthetic input hashes**.
- synthetic worker: `device/root-capture-synthetic-worker.sh`.
- builder: `scripts/build-root-capture-synthetic-trial.py`, using the same verified
  local SDK; no deployment, network launch or device action during build.
- exact regular-file allowlist: guardian, worker.sh, identity.sh, streamer,
  SHA256SUMS, started, worker.log. No keys or personal data included.
- at this checkpoint only host trial tests and ARM no-argument refusal have run;
  full ARM/native disconnect behavior remains untested.

Validation: **99 capture/probe/trial tests passed**, including six new synthetic
profile tests. Log: `/tmp/opencode/nimbus-synthetic-trial-review-vnh1g3lz/capture.log`.
`git diff --check` passed. Full regression was not rerun at this checkpoint; its
last attempt's existing UI-performance timeout remains documented separately.

## Commands for owner review — not yet approved or run

From the project directory, stage and **check only**:

```bash
ssh -T -p 2225 -i ~/.ssh/nimbus-admin-ed25519 \
  -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=~/.ssh/nimbus-test-known-hosts \
  -o HostKeyAlias='[192.0.2.10]:2224' \
  root@192.0.2.10 '
    set -eu
    umask 077
    test "$(id -u)" = 0
    test -d /tmp && test ! -L /tmp
    grep -Fx "none /tmp tmpfs rw,relatime,size=4096k 0 0" /proc/mounts >/dev/null
    command -v tar >/dev/null
    stage=/tmp/nimbus-guardian-synthetic-v1
    mkdir "$stage"
    dd bs=1 count=34189 > "$stage/bundle.tar.gz" 2> "$stage/upload.log"
    test "$(stat -c %s "$stage/bundle.tar.gz")" = 34188
    printf "%s  %s\n" df97a58cba389ded5a9e0b16e1f4fdefed84c0cbc3df546ab3b0c811626e7ec1 "$stage/bundle.tar.gz" | sha256sum -c -
    tar -xzf "$stage/bundle.tar.gz" -C "$stage"
    printf "%s  %s\n" 9be5a9496cdfc6acab9245015aaf226a7147668bbc07a1cbd65a3d5a84fa2c60 "$stage/guardian" | sha256sum -c -
    "$stage/guardian" --fixture-check 1d3bba8de518c1b611d4fc1f70a1d3f04624e295179be8a08c866f9831ac8233 "$stage"
    printf "SYNTHETIC-STAGE-CHECK=PASS no-worker-started\n"
  ' < build/nimbus-guardian-synthetic-trial-v1/synthetic-trial.tar.gz
```

Return output before any worker start. If this fails, stop and retain the stage.

After reviewed successful staging/check-only output, in a **separate terminal**:

```bash
ssh -T -p 2225 -i ~/.ssh/nimbus-admin-ed25519 \
  -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=~/.ssh/nimbus-test-known-hosts \
  -o HostKeyAlias='[192.0.2.10]:2224' \
  root@192.0.2.10 \
  'exec /tmp/nimbus-guardian-synthetic-v1/guardian --fixture 1d3bba8de518c1b611d4fc1f70a1d3f04624e295179be8a08c866f9831ac8233 /tmp/nimbus-guardian-synthetic-v1'
```

Wait for `SYNTHETIC-READY ... no-real-reader`, then press **Ctrl+C once in this
terminal only**. Do not type an ACK, terminate other sessions or signal listeners.
If readiness is absent or an error appears, stop and inspect; never retry blindly.

Then from the original terminal, inspect through pinned management:

```bash
ssh -T -p 2225 -i ~/.ssh/nimbus-admin-ed25519 \
  -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=~/.ssh/nimbus-test-known-hosts \
  -o HostKeyAlias='[192.0.2.10]:2224' \
  root@192.0.2.10 '
    set -eu
    stage=/tmp/nimbus-guardian-synthetic-v1
    tries=0
    while test ! -f "$stage/GUARDIAN-RESULT" && test "$tries" -lt 10; do
      tries=$((tries+1)); sleep 1
    done
    for name in GUARDIAN-INVALID GUARDIAN-RESULT SYNTHETIC-RESULT; do
      test -f "$stage/$name" && test ! -L "$stage/$name"
      printf "%s:\n" "$name"
      cat "$stage/$name"
      printf "\n"
    done
    grep " / " /proc/mounts
  '
```

Return the readiness/interruption and inspection outputs together. Missing records
mean unknown cleanup, not permission to force a stop, retry or perform capture.
