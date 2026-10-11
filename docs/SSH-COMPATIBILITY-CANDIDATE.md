# SSH compatibility candidate — not a deployed service

2026-10-11: built Dropbear 2026.94 from the signature-checked source recorded in SECURITY-LIVE-INVENTORY.md, using Bootlin armv5-eabi--musl--stable-2026.08-1. ARM EABI5 soft-float is intended to run on the ARMv7 drive; actual compatibility awaits device testing.

Bootlin toolchain archive SHA-256 (matched the vendor HTTPS checksum): `a7db571eaa0f1ba2eea9a3932e8ad64bfaf33bfb7e7b96dd09702fe3ecedcf1a`. Its README pins Buildroot tag `toolchains.bootlin.com-2026.08-1`. Matching musl recipe lists the iconv CVE-2026-6042 patch and three qsort CVE-2026-40200 patches. This is build-recipe evidence, not independent reproduction of libc. SDK relocation reported missing optional host-tool files; the cross compiler and build worked.

Configure: explicit x86_64 build / arm-buildroot-linux-musleabi host; zlib, syslog, lastlog, utmp/utmpx and wtmp/wtmpx disabled; CFLAGS `-Os -fstack-protector-strong`. `PROGRAMS="dropbear dropbearkey" MULTI=1`. Local options disable server password/PAM auth, all server TCP/stream/agent forwarding, X11 and SFTP; public-key auth remains enabled. Preprocessor checks with the Makefile's `LOCALOPTIONS_H_EXISTS` flag confirmed these settings.

Initial configure hardening combined `-pie` and `-static`, yielding an interpreter-dependent artifact: rejected, never uploaded. Final relink uses `-static -no-pie -Wl,-z,noexecstack,-z,relro,-z,now`. This trades away executable PIE/ASLR for a conventional static candidate; no claim of full hardening. ELF checks confirm ARM EABI5 EXEC, no INTERP, non-executable GNU_STACK. Stripped size: 370524 bytes. No emulator was available in PATH.

Source entropy path handles getrandom ENOSYS with fallback; boot-time entropy adequacy and all old-kernel runtime behavior still need validation. Help/version tests do not validate authentication, PTY, randomness or persistence. No private/client/host keys have been generated for this candidate.

Candidate SHA-256: `19a971e05c6fb7a5b8706669e9639f139a7f6d66885305c3d2003e362f0e2e08`.

Uploaded via stock file upload to an unused name, exact hash confirmed by HTTP readback:
`/mnt/storage/Scotti Upload/nimbus-dropbear-test-4fe692b9ac94.bin`.

Build/logs/source/local options are under `/tmp/opencode/nimbus-ssh-review/`. No candidate executed on the device by the agent. Proposed first test: checksum and copy to a newly created mode-0700 rootfs directory, verify copy, chmod 0700, then explicit `dropbearmulti dropbear -V` and `dropbearmulti dropbear -h` only. Do not invoke bare dropbear (which can start a listener). Media filesystem executable permissions must not be trusted for running this test.

Telnet remains running. No SSH listener, startup configuration, Wi-Fi, firewall, passwords or firmware changed. Full rollout requires unique host key and pinned client verification, key-only login in two sessions, reviewed rollback/recovery and reboot persistence before Telnet removal.

## Device version/help test

User supplied successful SHA-256 checks of both uploaded file and rootfs copy, followed by `Dropbear v2026.94` and the server help output. The binary runs far enough to parse these options on the actual device. No listener was started by these commands. Password-auth options are absent as expected for this build; full login, PTY, entropy and persistence remain untested.

## Interactive tests and interface-failure candidate

User generated a unique Ed25519 host key on the drive and pinned its public key on the management computer. Host fingerprint: `SHA256:H+oqmrKpKJmPZH8I9dSIOIXLQ5wz0TM3hCmhaIBnpKI`. Client fingerprint: `SHA256:YWIqzJaklCet4zj2p7cVkPMmSU2DeDhOmzttjkArOpk`. No private key contents collected. Two independent root SSH sessions worked on the temporary address-bound port 2222. User confirmed the requested password-only rejection test behaved as expected; supplied server logs show pre-auth exits, not detailed client rejection output.

Temporary port 2223 used `-l wlan1 -p 0.0.0.0:2223`; logs report binding to wlan1 and successful public-key authentication, without SO_BINDTODEVICE warnings. AP-side exclusion, address changes and reboot persistence still need testing. Existing rcS calls rc.local with start/stop after vendor services, including inetd and nimbus-service. No boot hook installed yet.

Upstream netio.c warns but continues on SO_BINDTODEVICE failure. Before persistence, built a minimal local patch that closes and skips that socket instead. Patch recorded in `device/ssh-interface-fail-closed.patch`; same source/toolchain/options as initial candidate, statically relinked and stripped. Linux build defines SO_BINDTODEVICE; this patch does not provide a portable guarantee for builds lacking that macro. Runtime negative/positive tests of the new binary are pending.

Revised candidate SHA-256: `1bebface41ff6ad832d0b1299ff49aca0698529399054901d860b50a1bb0213c`; 370524 bytes. Uploaded and hash-verified by HTTP readback at `/mnt/storage/Scotti Upload/nimbus-dropbear-bound-3e337b771230.bin`. Not executed by the agent; existing test binaries/listeners/keys and boot files are unchanged. Negative test should name a nonexistent interface and bind only loopback, expecting exit without a listener, then positive test the patched binary separately before startup installation.
