# BusyBox update assessment

**Recommendation: evaluate a separate pinned modern runtime first; do not replace
the vendor `/bin/busybox` or its applet symlinks in place.** No BusyBox update was
built, installed or enabled by this assessment. WiGLE remains deferred and no
new feature is added to the freeze.

## Known baseline

Selected clean-derived vendor binary evidence identifies BusyBox v1.15.0;
`bin/busybox` is576540 bytes, SHA-256
`aad1bd291b7a23098b11a0ee6e9f0526a98ba82a84a1e4ae6a933fd74f5d153c`.
This is an offline baseline, not fresh verification of the live executable or an
exact vendor source/configuration match. Its age warrants security/compatibility
review, not an unsupported claim about a particular CVE or a current release.

Subsequent approved GO synthetic-probe follow-up verified that the live
`/bin/busybox` hash matches this baseline. No applet update/repointing occurred;
this still does not establish exact vendor source/configuration or replacement
compatibility. Native receipt is linked in the GO session checkpoint.

The rootfs relies on many BusyBox applets through symlinks. Changing that binary
can change boot/reset/recovery, mount/storage/USB, DHCP/network and shell behavior.
Option syntax, parsing, exit status, signal/trap handling, symlink and permission
semantics must be tested against real callers. A successful `--help`, ARM ELF
audit or emulated startup does not qualify that replacement.

The earlier account-writer review also found that upstream1.15.0's update helper
uses warning-only inode locking. Vendor equivalence is unverified. Updating
BusyBox alone does not coordinate proprietary Nimbus password/reset handlers,
make multi-table writes atomic or qualify recipient reset preservation.

## Lower-risk evaluation path

1. Inventory applet symlinks/callers in the hash-pinned clean vendor input as
   data; do not execute boot/reset/mount helpers to learn their behavior.
2. Select/review a supported release and its source/license/build configuration,
   security fixes, ARM/legacy-kernel/libc requirements and applet differences.
   Pin exact sources and artifacts; retain corresponding source/license notices.
3. Build a **separate** namespaced binary and call only individually qualified
   applets by absolute path. Do not prepend it globally to PATH, repoint vendor
   symlinks or silently enable login/account/network applets.
4. Run targeted host/emulator tests, then separately reviewed native compatibility
   trials preserving pinned management and vendor functionality. Replacement of
   `/bin/busybox` still requires independent boot/recovery/reset/storage acceptance.
5. Include it only in a newly named clean candidate after qualification; retain
   old beta5/other artifacts and keep firmware NOT FLASHABLE until release gates
   pass. No personal live-root clone becomes a build input.

For GO's immediate bounds/cancellation work, the first-party C synthetic
supervisor probe does not depend on adding BusyBox applets or their timeout
semantics. It is not a scan worker and does not remove native qualification gates.
Do not update BusyBox merely to assume `timeout` handles driver hangs or drains
descendants: those properties need direct evidence with the actual worker.
