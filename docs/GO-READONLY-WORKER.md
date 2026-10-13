# GO fixed read-only worker — source/artifact checkpoint

**Inactive, not a scan worker or complete sandbox.** This advances the executable
boundary from synthetic children to fixed read-only iw GET queries. No worker was
staged/run on the SanDisk in this batch; the earlier approved synthetic stage is
retained unchanged. Its approval does not extend to this new executable.

Source: `device/wardrive-go-iw-worker.c`, using compile-time worker hooks in
`device/wardrive-go-supervisor.c`. The default supervisor still accepts synthetic
probes only. The wrapper accepts only:

- `--query list` / `--query dev`.
- Controlled variants with the same fixed modes and STOP/EOF input semantics.

There is no scan/cache-dump command, interface/channel change, monitor action,
arbitrary executable/argument, shell, service helper, account operation or storage
writer. Output is discarded under the64 KiB bound; status contains only result,
byte count and own-child cleanup observations. This component is not a results
API and does not connect the host GPS/session model to an app.

## Execution policy

Production refuses root, mismatched real/effective UID/GID, root group or
supplementary groups. It needs a separately enrolled dedicated identity; do not
reuse the file-login role, vendor account, shared nobody identity or management
root key to bypass the missing setup. No account/UID was created or chosen here.

The only executable is `/usr/sbin/iw`, root-owned root-group0755, regular,
single-linked,160508 bytes and SHA-256
`468f4271f5af9eaa5380f30b9717a58462baec4596e87461ff23859dfe44321e`.
No-follow open, absent `security.capability` xattr, bounded descriptor hash and
metadata readback are required. Execution uses the **held descriptor**, not a
fresh pathname lookup. Unsupported xattr/descriptor-exec behavior refuses rather
than falling back to a shell or a different binary. Hashing is a prerequisite,
not a guaranteed bounded kernel-I/O operation.

Inside the owned child:

- Refuse any inherited effective/permitted/inheritable capability. A non-root UID
  by itself is insufficient because capabilities can bypass process limits.
- Apply hard/soft NPROC0, CORE0 and FSIZE0 limits. NPROC0 prevents ordinary
  unprivileged fork/clone, not an existing process's exec.
- Enumerate only its own proc fd metadata; close inherited descriptors except
  the held executable and bounded stdout pipe. Stdin/stderr are closed by the
  supervisor. Private inherited files/keys/control handles are not forwarded.
- Execute with only LC_ALL=C and a non-searchable PATH; no caller environment,
  agent socket, loader override, home or credential variables are passed.
- Retain the parent-death guard, monotonic worker deadline, TERM/KILL escalation,
  bounded output, nonblocking control/drain and direct-child reap from the core.

This is **not** a guarantee against a malicious executable invoking another
setuid/capable program or exploiting the kernel. Old-kernel no-new-privileges,
syscall sandboxing and stronger execution confinement are not qualified. Dynamic
iw dependencies, loader behavior, parent-death across exec and full descendant
containment still require review/native evidence. The status therefore keeps
`descendant_containment_verified=no` and `native_scan_verified=no`.

The shared-radio finding remains: wlan0 AP and wlan1 managed share phy0. Neither
is an independent survey radio. No active scan or driver abort/coexistence claim
is inferred from this worker's successful mock execution.

## Tests and inactive ARM artifact

Ten new tests passed with a compiled **host mock executable**, not vendor iw.
They cover actual descriptor execution, denied ordinary fork, stripped environment
and inherited private fd, timeout, STOP/EOF, fixed argument rejection, unsafe
mode/symlink/hash refusal, inherited-capability refusal and wrong-SDK refusal.

The harness retained capabilities despite a non-root UID; the fixture explicitly
drops them only in its own subprocess. The worker policy was not weakened. The
mock confirms its fork attempt gets EAGAIN. Diagnostic exit codes are fixture-only
and excluded from the production build. Host mock files/UID/hash overrides are
also compile-time fixtures, never production arguments/environment overrides.

Latest scoped regression: **58 GO tests and104 SFTP tests passed, no skips**.
Full workspace regression was not rerun; `git diff --check` passed.

Builder: `scripts/build-go-iw-worker.py`.
Retained output: `build/nimbus-go-iw-worker-v1/`.
Binary `go-iw-readonly-worker.arm`:78876 bytes, SHA-256
`fc9c8871d2fe751fcee0c75df81ff60e8997426a738ddf4632c4533f68811397`.
Pinned-SDK static ARM EABI5 EXEC, non-executable stack, GNU_RELRO and emulated
no-argument refusal passed. That does not exercise native descriptor execution,
non-root iw permissions, dynamic dependency compatibility or driver behavior.

## Next gates

Native use is blocked by dedicated non-root enrollment/provisioning, exact launch
policy and dependency/legacy-kernel review. The account writer coordination gate
is still unresolved; no role is installed as a shortcut. The original synthetic
v1/v2 artifacts/stage/receipts remain separate, immutable historical evidence.

Continue app-control identity/authenticated framing and clock exchange design,
then qualify native read-only execution under the intended dedicated identity.
Before any active scan, independently cover full worker confinement/controller
loss, private records, shared-radio safeguards, driver abort/restoration and exact
bounded-trial approval. BusyBox is unchanged; WiGLE remains deferred.
