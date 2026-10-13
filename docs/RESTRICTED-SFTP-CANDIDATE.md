# Restricted SFTP candidate: offline ARM runtime built, native gates pending

Latest native follow-up: the owner-approved OpenSSH version/own-process rlimit
probes passed on the drive, including the selected poll fallback. No listener,
account/key, jail or bind view was created. See
[the exact process-probe evidence and limits](SFTP-LAYOUT-PREFLIGHT.md#completed-native-process-probe--2026-10-13).
Actual SFTP/privsep/confinement/USB qualification remains open; earlier statements
below that all native runtime execution is pending are historical.

[Account provisioning follow-up](SFTP-ACCOUNT-PROVISIONING.md) now pins the exact
lock-rule source/macros and supplies a private append-only account planner.
It creates no device accounts; native login, writer coordination and reset
semantics remain unqualified.

Latest checkpoint: the approved local runtime build completed and passed ARM-
emulated probes, version and effective-policy checks. Preserved candidate:
`build/nimbus-sftp-runtime-v1/`. Earlier configuration-only/unverified-source
statements below are historical preparation stages. No device deployment or
listener occurred; see the completed build evidence at the end of this document.

## Decision

Do not enable SFTP on the working root-management listener as a shortcut. Use a
separate maintained OpenSSH runtime with built-in `internal-sftp`, a dedicated
non-root `nimbus-files` account, distinct pinned enrollment and server-side jail.
Keep Dropbear management TCP 2224 and retained temporary management untouched.
First qualification is read-only media browsing/download, not backup uploads.

Offline review of the retained beta2 **local regular file**
`rootfs-tree/usr/libexec/sftp-server` found SHA-256
`0dd5b6154465551ec7c2c4d0f9f097ce3aaaeb4e27b9539d2ce1b68366f18189`.
`readelf` reports ARM ELF32 EABI5 EXEC, interpreter `/lib/ld-linux.so.3`, GNU_STACK
RWE, and dependencies on libcrypto.so.0.9.8, libutil, libz, libnsl, libcrypt,
libresolv and libc. This offline digest is not a fresh live-file match. Nothing
was executed. The old server is not selected for the new service.

The previously retained Dropbear source/toolchain workspace no longer exists at
its documented temporary location. No compatible ARM compiler or qemu-arm was
found in PATH. Reacquire and verify a current maintained source/toolchain with
reviewed libc fixes before building a runtime; old build notes cannot attest a
new binary. The stock vendor sshd must not be started with the new config.

## Prepared implementation

`scripts/prepare-sftp-candidate.py` creates an exclusive private **host-only**
candidate directory with `sshd_config`, `PLAN.json`, warnings and checksums.
Example proposed downstream address (must be freshly verified before use):

```sh
python3 scripts/prepare-sftp-candidate.py \
  --listen-address 192.168.11.1 \
  --output build/nimbus-restricted-sftp-config-v1
```

The inactive profile targets one explicit private IPv4 address on port 2226.
No wildcard, public or loopback fallback. It requires public-key authentication,
rejects root/password/PTY/user-rc/environment/forwarding, forces read-only
`internal-sftp`, and confines the account to a root-owned jail. No client input
can select an arbitrary server command. Separate host/auth paths cannot overwrite
existing management identities. Tests verify these config properties; they are
not proof that a server is built, policy is enforced natively or a jail exists.

## Native prerequisites—not actions performed

1. Pin a compatible maintained ARM sshd/runtime and its build dependencies. Review
   old-kernel entropy, sandbox and privilege-separation compatibility; do not
   silently disable protections to make startup work.
2. Verify the actual AP/interface/address and intended downstream management
   policy. This profile is not permission to open a new port or edit firewall rules.
3. Review/provision a dedicated non-root account and per-client key, unique pinned
   host identity, private authentication/log paths and narrow service lifecycle.
   Do not copy the admin private key to GameHack or phone.
4. A root-owned, non-user-writable jail must expose only explicit read-only views
   at `/internal` and `/sd`. Verify bind-view VFS read-only flags without changing
   internal/SD source mount policy. `internal-sftp -R` also denies protocol writes;
   a start directory alone is **not** confinement.
5. USB lifecycle is a critical blocker: a persistent bind view or SFTP open handle
   can keep media busy when the vendor exports it. Do not install persistent binds
   or leave a server running through USB handoff. Review session-stop/unmount and
   refusal behavior first. Module/mount snapshots alone cannot solve these races.
6. Scope the first bounded trial, retained independent management, evidence and
   exact stop/cleanup/rollback. Obtain explicit approval before any live account,
   keys, binds, listener or firewall change. No launcher/installer is supplied yet.
7. Native tests must reject root login, shell/PTY/forwarding, writes, traversal and
   symlink escapes; verify pinned non-root listing and selected-file size/hash.
   Neither read-only serving nor a jail makes legacy stock HTTP/FTP shares private.

GameHack pairing/UI activation follows native qualification, not config creation.
Writable versioned backups require another scoped no-overwrite/integrity design.
Pi networking, current browser functionality, root capture and firmware images
are unaffected. There is no working SFTP service claimed at this checkpoint.

## Runtime review and validation checkpoint

Upstream [release notes](https://www.openssh.com/releasenotes.html) identify
OpenSSH 10.6p1 (October 6, 2026) as the current portable release at this review.
The release-notes SHA-256 for its source tarball, converted from base64 to hex,
is `a9dc9565dffe8640f64d863cd29a32bc4a3dbdec0566a7fc44c5d6ee767d5f39`.
The [portable page](https://www.openssh.com/portable.html) publishes release signer
fingerprint `7168B983815A5EEF59A4ADFD2A3F414E736060BA`. No source archive/signature
was downloaded or verified in this checkpoint; these are upstream references,
not a completed source attestation or reproducible build.

An important compatibility boundary: since 10.4, failure to enable seccomp or
NO_NEW_PRIVS is fatal when the seccomp sandbox is selected. The drive's kernel
2.6.35 predates seccomp-BPF and NO_NEW_PRIVS. Therefore a default modern Linux
build cannot simply be copied onto this device. Review a supported alternative
sandbox configuration and its weaker protections explicitly, while retaining
privilege separation and chroot, before selecting any build. Do not use an old
OpenSSH version to hide this problem or silently configure sandboxing off.
No alternative sandbox has been selected or claimed equivalent here.

Nine candidate tests passed, including a real host `sshd -T` effective-policy
check with a disposable generated fixture key. It confirmed root/password denial,
read-only forced SFTP, forwarding prohibition, account and exact listen address.
This starts no listener and changes no host/device SSH service. Config-dump
directive names are normalized case-insensitively for newer OpenSSH releases.
The disposable key was not provisioned to any device. ARM/native enforcement
remains pending. The separate inactive configuration was generated locally at
`build/nimbus-restricted-sftp-config-v1/`; existing backups/bundles stay intact.

## Completed local ARM build

Local workspace: `/tmp/opencode/nimbus-sftp-build-nyitawo0/`. Source and SDK
downloads matched the pinned hashes. An isolated GPG keyring verified the OpenSSH
archive signature against the upstream-published signer fingerprint. Trust is
anchored to upstream HTTPS, not independent out-of-band signer verification.
Source/SDK extraction used bounded Python tar data filters; no vendor executable
or script was run.

The SDK README pins `bootlin/buildroot-toolchains` tag
`toolchains.bootlin.com-2026.08-1`. Its musl recipe and four security patches were
reviewed and preserved: CVE-2026-6042 iconv correction and CVE-2026-40200 qsort
corrections. Matching SDK checksum and recipe proximity support relevance, not
independently reproduced or patched-libc binary attestation.

First-party builder: `scripts/build-sftp-runtime.py`. It takes already downloaded
source/signature/key/SDK files, refuses changed inputs or an existing/symlink
output, and retains failed-build evidence. It performs no install, server launch,
download, root operation, mount or device action. Build tools execute only locally.
Target ssh-keygen runs under emulation for a disposable host-side policy fixture;
that key is removed with its private fixture directory, never provisioned/exported.

Selected **offline candidate** sandbox: upstream `rlimit`, retaining zero FSIZE,
NPROC and NOFILE limits, plus required privilege separation. This is materially
weaker than seccomp: no syscall allowlist. Native enforcement and pre/post-auth
unprivileged process behavior remain untested.

ARM emulation found libc select/pselect working with NOFILE=0 but libc poll failing.
The build explicitly selects upstream `openbsd-compat/bsd-poll.c` by configuring
libc poll/ppoll unavailable; it does not skip the descriptor limit. The actual
upstream fallback was compiled into a second probe and passed all select/pselect/
poll observations under emulation. Its limited event support and FD_SETSIZE bound
remain native session/load gates. The configure cross-only select assumption was
changed with a strict-layout checked transformation after emulated evidence passed.
Original/patched configure hashes and the **native-probe-required** warning are
retained. This is not native evidence.

Settings: ARM EABI5 soft-float, static EXEC, stack protector strong, non-executable
GNU_STACK and GNU_RELRO; no interpreter/dynamic library segment. Static linking
avoids vendor libraries but loses PIE/ASLR. No OpenSSL/zlib/PAM/libedit/Kerberos/
SELinux/security-key backend is linked; crypto algorithms are restricted. Dedicated
compile-time privsep account is `nimbus-sshd`, distinct from `nimbus-files`. Both
accounts remain uncreated.

Modern OpenSSH requires **three server binaries**, not just sshd:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| sshd | 673308 | `bc10f02c3d1803bcb643448326b9579cc7c08bb25d62f0bb0e43d6565d005355` |
| sshd-session | 1071012 | `63b3a7b59a105c47dd3e6d2baddac166bf18f261304fe4e08279b316721029c6` |
| sshd-auth | 1033924 | `037f55c692d5b206edc8b2119be84eb0ece85af94d7ad6a48b2cf11898e351d8` |
| ssh-keygen | 620060 | `358f9692434a80b347cf1ef13e8e7ca244ed59d459f8974021176644e949b61f` |
| raw libc rlimit probe | 60828 | `0374ac9c229b371433508dbe4b97709cdf3a6396646fe9c07b2419da1f94a520` |
| upstream select fallback probe | 60912 | `1274e41fa34f92f1e07d84a513ef9348663617460b8b5edf3f6bf6de325531d9` |

All six passed offline ELF metadata audits. Emulated `sshd -V` returned
`OpenSSH_10.6p1, without OpenSSL`; target ssh-keygen generated a disposable Ed25519
fixture; emulated `sshd -T` confirmed non-root/read-only/no-forwarding/jail policy
without a listener. Two separate builds produced identical hashes for the four
core binaries: limited same-host repeatability, not independent reproducible-build
certification.

Preserved private export: `build/nimbus-sftp-runtime-v1/`, 29 files, 3667098 bytes
of payload, plus export manifest. Includes runtime, licences/build recipe
references, probes and selected review logs; no credentials or vendor assets.
Directory is 0700, files 0600, not automatically executable. No installer, active
config or launch action is supplied. No production release/licensing review claim.

Twenty targeted candidate/runtime tests passed, including hash/signer/output/path
refusals, sandbox macro guards, ELF metadata refusals and a host probe showing its
limits do not alter the parent process. Full project suite was not run for this
build checkpoint. Native failure recovery remains unestablished.

## Next bounded native gate

Review an explicitly approved **version/probe-only** trial first: checksum-verified
copy of sshd and two probes into a new private stage, no replacement of the working
listener. Permit only `sshd -V` and no-argument probes. Probe limits affect only
the probe process, not management shells/services. Raw poll failure is expected;
selected fallback must pass. Do not start sshd, run target keygen, create accounts/
jails/bind views, edit startup/firewall or expose a port. New private staging files
are ordinary rootfs writes and require explicit approval. USB export must be
inactive; fresh power/space/pinned management checks are action-time prerequisites.
Kernel syscalls can stall; no hard recovery deadline is promised.

Only after native compatibility should confinement, pairing and USB lifecycle
tests proceed within separate scope. SFTP serving and native GameHack operation
remain **not qualified**.

Authorized-key-path review corrected another preparation issue: a non-root login
must be able to read its root-owned **public** authorized-key file during OpenSSH
authentication. The profile now uses
`/etc/nimbus-sftp-auth/nimbus-files/authorized_keys`, with a required traversable,
root-owned/non-user-writable hierarchy, rather than an unreadable private `/root`
stage. Host private keys and logs remain private; no admin private key is copied.
The generated config-v1 remains retained as historical preparation evidence;
generate a new config revision rather than overwriting it. No device auth file or
directory was created. Effective policy parsing is not a live account access test.

The corrected profile was generated separately at
`build/nimbus-restricted-sftp-config-v2/`. Host and ARM-emulated effective-policy
checks passed with the corrected authorized-key path. The supplementary ARM log
is retained at `/tmp/opencode/nimbus-sftp-build-nyitawo0/policy-v2-check/`.
The immutable runtime-v1 export still records its exact earlier builder revision;
later source-side policy-check improvements do not rewrite its provenance or
make its binaries native-qualified. Twenty targeted tests passed after this fix.

## Frozen-scope confinement/enrollment follow-up

Source now includes a strict confinement metadata validator, private offline
dedicated-public-key enrollment preparation and a listener/session/view shutdown
decision model. See [contracts and remaining native work](SFTP-CONFINEMENT-ENROLLMENT.md).
They do not implement a native collector, provision accounts/host identities,
start SFTP or qualify USB handoff. The retained ARM export's 29 files and six ELF
metadata audits passed a fresh read-only host check without executing binaries.
