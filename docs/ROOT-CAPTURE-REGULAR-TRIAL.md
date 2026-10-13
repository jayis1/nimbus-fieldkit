# Regular-file-only native reader/hasher trial — prepared, not deployed

**Historical v1 profile: failed, retained, do not rerun.** Its unsupported BusyBox
launcher has been replaced in a distinct **pending-approval** v2 profile; see
`ROOT-CAPTURE-REGULAR-TRIAL-V2.md`. Commands below document the original approved
attempt only, not permission to repeat it.

Owner explicitly approved the exact new-stage upload/check, one positive
regular-file-only run and retained synthetic output/logs. Local bundle hash
reconfirmed. Device staging/check output is pending; no reader execution has
been reported. Approval excludes block reads, service changes, remounts and flash.

Owner returned approved native staging: bundle hash OK, deterministic epoch-time
tar warnings, guardian hash OK, all checksum inventory inputs OK and final
`REGULAR-STAGE-CHECK=PASS no-worker-started`. The warnings did not block the
subsequent verified stage check. Free-space/directory guards completed. No reader
was started; next is the approved one-shot positive run, without Ctrl+C or ACK input.

Owner invoked that one-shot run and reported returning to the local prompt with
no trial PASS/output beyond the key passphrase prompt. SSH exit status was not
provided. Do not classify as success or rerun. Next is bounded metadata-only
inspection of guardian claim/invalid/result/stderr and reader drain/result/wire
presence, with missing files explicitly reported rather than aborting inspection.

## Returned failure — unsupported BusyBox hasher launcher

Owner returned session-matched claim/invalidation/guardian result with worker
exit status 256 (exit 1), and stderr:

```text
sha256sum: applet not found
Capture stream failed; coordinator must invalidate and observe cleanup.
```

CHILD-DRAIN reports the exact session with `reader-closed hasher-drained`.
REGULAR-RESULT reports `helper_status=1 synthetic-only host_readback_verified=no`.
SYNTHETIC-WIRE is truncated at 131171 bytes, SHA-256
`add1659bf3957a1a122d795a0db009e7af28f7f7fc16dd4d7c92b0fb973c39fc`.
Root remains at the exact original rw ext3 options and separate pinned 2225
inspection works. This is a **failed positive trial**, not usable image evidence.
Retain all original records/bytes; no retry, stage replacement or repair.

The pinned wrapper's `/bin/busybox sha256sum` invocation is unsupported on this
drive. Ordinary `sha256sum` commands already worked during checksum verification,
so resolve their actual executable/target/hash read-only before preparing any
correction. The production stream candidate also directly invokes this unsupported
BusyBox applet; it is blocked on this drive, not qualified by a cleanup report.
Any corrected trial must have new pins/build/stage and separate run approval;
do not edit or overwrite the failed stage or approve raw capture as a workaround.

## Proposed scope requiring separate approval

- Stage the **78625-byte** verified bundle in a newly created root-owned 0700
  `/tmp/nimbus-reader-regular-v1`. Require at least 1024 KiB tmpfs free first.
- Verify/extract the pinned regular files and private fixture directories, then
  run only the guardian's check entry. Return check output before execution.
- Run one **positive** fixture trial. Unlike the prior disconnect test, do not
  press Ctrl+C or type an ACK: this trial should finish by itself.
- The fixture-only ARM reader refuses block devices, reads **262144 known fake
  bytes** from `fixture/dev/mmcblk0p2` (an ordinary regular file), and passes those
  same bytes to its owned checksum child. Fake ro/geometry metadata is confined
  to the fixture directory; the real root remains rw and is never remounted.
- A pinned tiny wrapper execs the existing BusyBox sha256sum applet. The worker
  checks the BusyBox file hash first as an ordinary executable input. No real
  capture coordinator, service stop/restart, reboot, listener or block reader.
- A precomputed **synthetic ACK** exercises the reader's matching/exit path; it
  is not a real PC durable-readback acknowledgment. Fake output stays in a private
  tmpfs SYNTHETIC-WIRE file. Expected private CHILD-DRAIN reports reader closure
  and direct hasher reap; REGULAR-RESULT explicitly denies host readback proof.
- Inspect records and root mount metadata through a separate pinned SSH session.
  Retain every earlier/current stage and log. Do not retry or delete on failure.

This tests native executable/hash/pipe/child-drain compatibility in a small
positive fixture, not disconnect under real reader load, continuous ro, full
descendant tracking, real host durability, physical recovery or flash readiness.
The fake ROOT protocol frames are **not a root backup** or mount-state evidence.
Kernel IO stalls, SIGKILL and power loss remain outside recovery guarantees.

## Artifact

`build/nimbus-reader-regular-trial-v1/regular-trial.tar.gz`:

- bytes 78625; SHA-256
  `cd385bac9c0c9cd7283a38fdc6e9f31a2094c874d2a8a946650b5917a99ae985`
- separate pinned fixture guardian and fixture-only streamer, both ARM EABI5
  static non-PIE; same unchanged first-party C source as earlier candidates.
- explicit compile-time fixture define; no production block-reader binary or
  real remount/service worker included.
- fake data SHA-256
  `2312394bd99545d9de131c24efb781e765ac1aec243f2ed9347597a793a415e9`
- builder `scripts/build-root-capture-regular-trial.py`; worker template
  `device/root-capture-regular-worker.sh`.
- Estimated tmpfs files/output/log-cap/directories fit below the 1 MiB staging
  margin; this is not native peak RAM or allocation-pressure qualification.
- Only local compiled-code positive/refusal tests and ARM no-argument refusal
  have run. Hardware/capture/flash flags remain false. No native upload/execution.

Validation: **104 targeted capture/probe/trial tests passed**, including five new
regular-pipeline/profile tests. Log:
`/tmp/opencode/nimbus-regular-trial-review-f82zfe_6/capture.log`.
`git diff --check` passed. Full regression was not rerun; the earlier unrelated
UI-performance timeout is retained, not relabeled as a pass.

For this exact session, expected SYNTHETIC-WIRE is **262389 bytes**, SHA-256
`dec281280a23c0256766f77cfaf0e10cd21ff14c5f14ffe06f6f06eefc5bd4c7`.
This predicted fake wire is not evidence that any live capture occurred.

## Approved staging/check-only command — native result pending

Run from the project directory only after scope approval:

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
    stage=/tmp/nimbus-reader-regular-v1
    mkdir "$stage"
    dd bs=1 count=78626 > "$stage/bundle.tar.gz" 2> "$stage/upload.log"
    test "$(stat -c %s "$stage/bundle.tar.gz")" = 78625
    printf "%s  %s\n" cd385bac9c0c9cd7283a38fdc6e9f31a2094c874d2a8a946650b5917a99ae985 "$stage/bundle.tar.gz" | sha256sum -c -
    tar -xzf "$stage/bundle.tar.gz" -C "$stage"
    printf "%s  %s\n" cb53a61195e038ff11cba2a17dcc00548eeaccffed4d6056739203364c78cbe0 "$stage/guardian" | sha256sum -c -
    cd "$stage"
    sha256sum -c SHA256SUMS
    "$stage/guardian" --fixture-check dbfeda07e66c3e055fc7a1324c371ace3967a02a71322395f4b956a4d876b44c "$stage"
    printf "REGULAR-STAGE-CHECK=PASS no-worker-started\n"
  ' < build/nimbus-reader-regular-trial-v1/regular-trial.tar.gz
```

Return output before execution. Stop/retain on any error; no fixing inputs to pass.

## One-shot run, only after reviewed successful staging

```bash
ssh -T -p 2225 -i ~/.ssh/nimbus-admin-ed25519 \
  -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=~/.ssh/nimbus-test-known-hosts \
  -o HostKeyAlias='[192.0.2.10]:2224' \
  root@192.0.2.10 \
  'exec /tmp/nimbus-reader-regular-v1/guardian --fixture dbfeda07e66c3e055fc7a1324c371ace3967a02a71322395f4b956a4d876b44c /tmp/nimbus-reader-regular-v1'
```

Let it finish. Return output before considering any subsequent operation. On an
error retain the stage; do not rerun, interrupt other sessions, reboot or repair.

## Separate record/mount inspection

```bash
ssh -T -p 2225 -i ~/.ssh/nimbus-admin-ed25519 \
  -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=~/.ssh/nimbus-test-known-hosts \
  -o HostKeyAlias='[192.0.2.10]:2224' \
  root@192.0.2.10 '
    set -eu
    stage=/tmp/nimbus-reader-regular-v1
    for name in CHILD-DRAIN REGULAR-RESULT GUARDIAN-RESULT; do
      test -f "$stage/$name" && test ! -L "$stage/$name"
      printf "%s:\n" "$name"; cat "$stage/$name"; printf "\n"
    done
    stat -c %s "$stage/SYNTHETIC-WIRE"
    sha256sum "$stage/SYNTHETIC-WIRE"
    grep " / " /proc/mounts
  '
```

These are synthetic evidence checks, not a usable rollback image or continuous-ro
certificate. A precomputed ACK must never be substituted in a real capture.
