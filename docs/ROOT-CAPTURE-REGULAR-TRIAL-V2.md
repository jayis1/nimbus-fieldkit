# Corrected regular-file native trial v2 — prepared, not deployed

Owner confirmed the exact v2 upload/check, one positive run against the fake file
and retained output/log scope. Local bundle hash reconfirmed. Staging/check
output is pending; no v2 native execution has been reported. This does not
authorize touching failed v1, block reads, service stops, remounts or flashing.

Owner returned v2 bundle/guardian/all fixture inventory checksums OK and
`REGULAR-V2-STAGE-CHECK=PASS no-worker-started`, with nonfatal deterministic epoch
timestamp extraction warnings. Directory/free-space guards completed. The new
stage is checked, not executed; next is the approved one-shot positive run.

Owner subsequently invoked the approved one-shot v2 run and returned
`REGULAR-TRIAL=PASS reader-closed hasher-drained synthetic-only native_capture_qualified=no`.
The native positive worker reports success; independent drain/helper/guardian
records, predicted complete fake-wire size/hash and post-trial root mount
inspection are still pending. Do not rerun. This is not real host durability,
disconnect-under-reader-load or a raw-root/recovery qualification.

Owner's separate pinned inspection returned exact session-matched CHILD-DRAIN,
helper_status=0, guardian `invalidated=no worker_exited=yes worker_status=0
restoration_certified=no`, and complete fake wire size 262389/hash
`b0a542cfcd7752536d604cdb5916e78742e7f24bc480f8584e8b43ac99c8fddc`.
The synthetic data/drain checks match. However, the pasted real-root mount output
contains only `rootfs / rootfs rw 0 0`, **not** the previously expected ext3
`/dev/root /` line. Do not claim original root state unchanged or advance to more
native execution/capture. This may be incomplete pasted output or a changed mount
view; cause is unknown. Next step is complete read-only mount/mountinfo/uptime/USB
module metadata through the pinned connection. No remount, repair, reboot or retry.

Owner subsequently returned complete metadata through pinned 2225: uptime 2h45,
`/dev/root / ext3 rw,relatime,errors=continue,barrier=0,data=writeback`, and matching
mountinfo root identity 179:2 with VFS `rw,relatime` and superblock
`rw,errors=continue,barrier=0,data=writeback`. Readable full modules list has no
g_file_storage. Current root is reconfirmed; the cause of the earlier missing
line is not established, and no state change was made to obtain this result.
Internal media mounts rw and SD mounts ro as reported.

The limited native positive **synthetic** reader/hasher/drain/wire checkpoint
passes with this follow-up. This does not establish real continuous ro, host
durable ACK, cancellation under reader load, complete native descendants or
physical recovery. Retain all v1/v2 evidence; no further native run, cleanup,
service interruption, remount or real capture follows automatically.

The original v1 trial **failed**: `/bin/busybox sha256sum` has no such applet.
Its stage, partial wire and invalidation/drain records must remain untouched.
The owner resolved the working command as a standalone, non-symlink regular file:

- `/usr/bin/sha256sum`, 116878 bytes, root:root, mode 0755.
- SHA-256 `c8c1596d9bdf8d3bc66ee04615057bace07d51f01ede2f24b76900b585ae1ed2`.

V2 pins that executable's hash **and metadata**, and the tiny fixture wrapper
execs it directly, without BusyBox dispatch. The worker checks all fixture inputs
and the hasher before starting a reader. Host tests substitute the host hasher's
actual hash/metadata; they do not imply that the vendor binary ran on the PC.

## Proposed separate approval scope

Upload **78657 bytes** to a **new** private root-owned 0700
`/tmp/nimbus-reader-regular-v2`, requiring at least 1024 KiB tmpfs free before
creation. Verify and check the new pinned profile, return its output, then run
once against the same **262144 fake regular-file bytes** and retain all output.
No v1 overwrite, retry, repair or cleanup. The one positive run should finish
automatically: do not type an ACK or press Ctrl+C.

This still has synthetic ro metadata and a precomputed fake ACK, with output
confined to private tmpfs. It is **not** a real PC durable-readback protocol or
actual root backup. No block-device read, real capture coordinator, service stop,
remount, listener change, reboot or flashing. Ordinary-file reads of the pinned
hasher and fixture are included. Only owned reader/hasher cleanup is tested;
disconnect under reader load, complete descendants, memory pressure, continuous
ro and physical recovery remain unqualified. No v2 native upload/run has occurred.

## Inactive artifact

`build/nimbus-reader-regular-trial-v2/regular-trial.tar.gz`:

- 78657 bytes; SHA-256
  `58c0260d5816e12b52f27ca2e5c5b02a2003bbce82f8d896e16c6dc28ff7292e`.
- fixture guardian SHA-256
  `8cdfc037728b9c02ecc5083377e30b02a53e21e1f34e75b9b4f596c4e9b385a0`.
- compile-time fixture-only reader refuses block devices; no production reader
  or real service/remount worker included. Hardware/capture/flash flags false.
- prior stages and every previous build are retained, including failed v1.

Validation: **106 targeted tests passed**, including standalone-launcher
regression and wrong-hasher-hash/metadata refusal before reader start. Log:
`/tmp/opencode/nimbus-standalone-hasher-review-5rdbped6/capture.log`.
`git diff --check` passed. Full regression not rerun; the previous unrelated
UI-performance timeout is not relabeled as a pass.

Expected fake wire for this exact session: 262389 bytes, SHA-256
`b0a542cfcd7752536d604cdb5916e78742e7f24bc480f8584e8b43ac99c8fddc`.
These predicted fake bytes are not evidence that v2 has run on the drive.

## Approved staging/check command — native result pending

From the project directory, only after approval:

```bash
ssh -T -p 2225 -i ~/.ssh/nimbus-admin-ed25519 \
  -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=~/.ssh/nimbus-test-known-hosts \
  -o HostKeyAlias='[192.0.2.10]:2224' \
  root@192.0.2.10 '
    set -eu
    umask 077
    test "$(id -u)" = 0
    test -d /tmp
    test ! -L /tmp
    grep -Fx "none /tmp tmpfs rw,relatime,size=4096k 0 0" /proc/mounts >/dev/null
    command -v tar >/dev/null
    available=$(df -k /tmp | tail -n 1)
    set -- $available
    test "$#" = 6
    test "$1" = none
    test "$4" -ge 1024
    stage=/tmp/nimbus-reader-regular-v2
    mkdir "$stage"
    dd bs=1 count=78658 > "$stage/bundle.tar.gz" 2> "$stage/upload.log"
    test "$(stat -c %s "$stage/bundle.tar.gz")" = 78657
    printf "%s  %s\n" 58c0260d5816e12b52f27ca2e5c5b02a2003bbce82f8d896e16c6dc28ff7292e "$stage/bundle.tar.gz" | sha256sum -c -
    tar -xzf "$stage/bundle.tar.gz" -C "$stage"
    printf "%s  %s\n" 8cdfc037728b9c02ecc5083377e30b02a53e21e1f34e75b9b4f596c4e9b385a0 "$stage/guardian" | sha256sum -c -
    cd "$stage"
    sha256sum -c SHA256SUMS
    "$stage/guardian" --fixture-check d8250cbecf20f47e031319ef5644eff0966181a3ee9792dd92a54c7d900e14f1 "$stage"
    printf "REGULAR-V2-STAGE-CHECK=PASS no-worker-started\n"
  ' < build/nimbus-reader-regular-trial-v2/regular-trial.tar.gz
```

Return output before running anything else. Failure means retain stage and stop.

## Run once after reviewed successful staging/check

```bash
ssh -T -p 2225 -i ~/.ssh/nimbus-admin-ed25519 \
  -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=~/.ssh/nimbus-test-known-hosts \
  -o HostKeyAlias='[192.0.2.10]:2224' \
  root@192.0.2.10 \
  'exec /tmp/nimbus-reader-regular-v2/guardian --fixture d8250cbecf20f47e031319ef5644eff0966181a3ee9792dd92a54c7d900e14f1 /tmp/nimbus-reader-regular-v2'
```

Return output/exit status. No rerun on silent return or error. Inspection will
include drain/helper/guardian records, fake wire size/hash and root mount metadata.
Capture or repair never follows automatically from PASS.
