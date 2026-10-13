# Inert native compatibility probe — prepared, not deployed

Owner approved the exact one-time temporary upload/hash-check/probe run and
retention scope on 2026-10-13. Host artifact hash was rechecked and matches below.
Execution is owner-operated with the encrypted SSH key; native output/exit status
has not yet been returned. No service interruption, remount, raw capture or flash
is authorized by this approval.

Owner's first approved attempt returned `Connection refused` on TCP 2225 before
authentication or remote-command execution. This attempt uploaded/ran nothing;
stage existence has not been inspected remotely. Do not retry the probe, reboot
or restart listeners/services automatically. Next check is strictly pinned,
metadata-only management on existing TCP 2224. Any listener re-establishment
requires separately reviewed scope/approval and fresh fallback verification.

Owner subsequently approved the temporary listener-only start and returned its
prerequisite/listening observation, then fresh strictly pinned 2225 authentication
(uid/gid 0, uptime 54 minutes). The probe's local hash was reconfirmed. The earlier
connection refusal did not consume a native execution; the already approved
one-time upload/run may now be attempted with the unchanged exclusive-stage
command below. Stop if the stage unexpectedly exists. Native results are pending.

## Owner-returned native result

The owner ran the approved exclusive-stage command through strictly pinned 2225
and returned the staged payload checksum `OK` followed by:

```text
monotonic=PASS
self_fd_enumeration=PASS
pipe_peer_loss_poll=PASS
detached_child_session=PASS
own_child_signal_and_select=PASS
own_child_reaped=PASS
PROBE=PASS native_capture_qualified=no
```

These establish the limited native probe's reported checks on the current drive,
not native guardian disconnect recovery, complete descendant/resource behavior,
continuous ro or physical recovery. SSH exit status was not separately supplied;
the reviewed remote command exits with the probe status after printing the log.
Retain `/tmp/nimbus-native-probe-v1` and its binary/upload/probe logs; no second
execution, cleanup, guardian launch, remount or raw read is authorized here.
Build manifests retain their original offline flags rather than being overwritten
to imply broader hardware qualification.

## Exact proposed scope

Separate owner approval is required for the commands below. Preparation/build
approval does not authorize upload/execution, service interruption or capture.

- Upload **only** the 33812-byte `native-probe.arm` to a newly created root-owned
  0700 `/tmp/nimbus-native-probe-v1` directory on the existing 4 MiB tmpfs.
- Verify exact size and SHA-256 before marking the staged binary executable.
- Run that probe once and preserve its small private output log and binary.
- Probe uses only its own pipes, one short-lived child and `/proc/self/fd` metadata.
  It tests monotonic time, select/poll, broken-pipe detection, setsid/session
  identity, SIGUSR1 to its own child and waitpid/reaping. On failure it may request
  TERM for that same unreaped child. There is no name/group/historic-PID signaling.
- No device/block reads, root/media writes, service stop/restart, remount, reboot,
  socket/listener, installer or capture invocation. No guardian/streamer is uploaded.
- Retain the stage on success or failure; never reuse it or automatically remove
  it to retry. Kernel stalls, signal interruption and power loss cannot be made
  safe by userspace timing. The probe child also has its own short timeout so
  loss of the probe parent need not leave it indefinitely waiting for a signal.

The probe is not a detached-guardian disconnect trial or a descendant-lifetime,
resource-pressure, filesystem-consistency or recovery qualification. Even all
PASS results do **not** permit a capture or firmware write.

## Local artifact and tests

`build/nimbus-root-capture-native-probe-v1/native-probe.arm`, mode 0600:

- bytes: **33812**
- SHA-256: `6c27fb1b08148f03500ed2ec46ec02ea0dc98b00235c7573d7b68b94c1d36540`
- source: `device/root-capture-native-probe.c`
- builder: `scripts/build-root-capture-native-probe.py`
- same hash-verified local SDK as the stream/guardian candidates; no downloads,
  deployment or device execution performed by the build.
- static ARM EABI5, non-executable stack, GNU_RELRO, stack protector; not PIE.
- host and ARM-emulated probe PASS, argument refusal, source capability check,
  bad-SDK refusal and artifact audit passed. Native result remains unknown.

Targeted capture/probe validation: **93 tests passed**. Log:
`/tmp/opencode/nimbus-native-probe-targeted-g_7vj6kk/capture.log`.
The full regression attempt timed out after 180 seconds in existing
`test_ui_performance_package.test_install_and_rollback_preserve_original_assets`;
it is not recorded as a full-suite pass. Retained log:
`/tmp/opencode/nimbus-native-probe-review-6yz7cdjg/regression.log`.
No remaining process with that run's private fixture-path prefix was observed.

## Owner-reviewed command, NOT run by the agent

Run from the project directory **only after approving the exact scope above**.
Your encrypted key passphrase remains local. No `sh -s` script upload is involved:
stdin contains only the bounded compiled probe payload.

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
    stage=/tmp/nimbus-native-probe-v1
    mkdir "$stage"
    dd bs=1 count=33813 > "$stage/probe" 2> "$stage/upload.log"
    test "$(stat -c %s "$stage/probe")" = 33812
    printf "%s  %s\n" \
      6c27fb1b08148f03500ed2ec46ec02ea0dc98b00235c7573d7b68b94c1d36540 \
      "$stage/probe" | sha256sum -c -
    chmod 700 "$stage/probe"
    rc=0
    "$stage/probe" --probe > "$stage/probe.log" 2>&1 || rc=$?
    cat "$stage/probe.log"
    exit "$rc"
  ' < build/nimbus-root-capture-native-probe-v1/native-probe.arm
```

Review the output and SSH exit status, not merely the presence of a PASS line.
An upload/hash/exec/probe error means stop and retain the stage; no retries,
remounts, service changes or cleanup are authorized by this command.
