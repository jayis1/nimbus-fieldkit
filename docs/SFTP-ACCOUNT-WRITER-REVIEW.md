# Account writer / transaction model checkpoint

Account installation is **still blocked**. This checkpoint supplies offline
writer evidence and a tested byte-selection model, not a device installer, a
working writer lock or permission to stop vendor services.

## Selected offline evidence

`scripts/audit-sftp-account-writers.py` reads only selected members of either the
reviewed stock archive or the pinned clean-derived beta5 archive. It emits hashes,
allowlisted tokens and allowlisted ELF dynamic symbols, never arbitrary strings
or account contents. Vendor binaries/scripts are not executed. Host `readelf` is
used only on bounded regular temporary copies. No live drive was contacted by
this checkpoint.

Completed input: beta5 `rootfs.tar`, SHA-256
`70aa4be20f2db812bb504b75e8f6ab6eb8bb9c800018ef3184ae7af68be08853`.
This is clean-derived **offline** provenance, not native identity verification.
Report: `build/nimbus-sftp-writer-review-v1/WRITER-AUDIT.json`.

| Selected component | Evidence / limit |
| --- | --- |
| `nimbus/nimbus` | `ResetAdmin` and `passwd` tokens; imports `fcntl`, `rename`, `system`; no selected `lckpwdf` import found. Not a complete handler/call-graph analysis. |
| `opt/qsi/bin/fw_server` | `passwd` token and `system` import. Client token absence does not exclude server-side writers. |
| `bin/busybox` | Account-path tokens and `fcntl`/`rename` imports; version marker `BusyBox v1.15.0`. Not proof of its exact build configuration or source patches. |
| `lib/libc-2.11.1.so` | Defines `lckpwdf`/`ulckpwdf`; `/etc/.pwd.lock` token. Lock availability does not establish caller participation. |
| `nimbus_resetpwn.sh` | Calls `ResetAdmin` through fw_server. Its history explicitly describes admin-password synchronization. It also changes Wi-Fi/services and must not be run for inspection. |
| `platform_functions` | Selected `/etc/passwd` occurrence is a read-only FTP-home lookup, not a proven writer. |

The adjacent retained `upstream-busybox-1.15.0/` holds `update_passwd.c`, GPL
license and URL/hash provenance. In this **upstream reference**, the writer:

- Opens the original account file before obtaining its `filename+` exclusive
  staging name, and creates a hardlinked `filename-` backup.
- Tries an inode `fcntl(F_SETLK)` write lock, but only warns if it fails.
- Unlocks before final flush/fsync/rename; does not call `lckpwdf`.

Therefore merely holding `/etc/.pwd.lock`, a Nimbus lock, or an advisory lock on
one inode cannot be claimed to exclude these possible paths. Preexisting open
descriptors and inode replacement also matter. The upstream source has **not**
been proved equivalent to the vendor binary; these are reasons to reject an
unsupported coordination claim, not native behavior qualification.

## Pure offline transaction model

`scripts/sftp-account-transaction-model.py` performs no filesystem, network,
service, mount, signal or account operation. It accepts private table bytes in
memory and uses the existing hash-pinned account planner to validate proposals.
Its returned bytes are private, never generic firmware inputs.

- Commit candidate requires exact current/baseline equality and the exact
  append-only reviewed proposal. Suggested order remains group→shadow→passwd.
- Rollback candidate removes only both exact proposed role lines per table,
  preserving every unrelated **current** byte, including later vendor password
  edits and new unrelated accounts. It never restores an entire old baseline.
- Changed role fields, one missing role, reused role IDs, new role group
  memberships, malformed tables or a changed root identity cause refusal.
- Only whole-table commit prefixes are recognized: none, group, group+shadow,
  or all three. Reverse order is passwd→shadow→group. Unexpected subsets require
  private review; they are not automatically repaired.

The model does not know who made an exact matching record, drain active sessions,
provide durable journaling, make three files atomic or ensure writer exclusion.
Its explicit installer/native/exclusion flags are false. A rollback candidate is
not authorization to execute rollback. Current shadow and shadow- mode0600 must
not be replaced by historic0744 metadata during any later operation.

Ten new fixture tests cover proposal/input mismatch, all whole-table prefixes,
preservation of later edits, ambiguous role changes/references and allowlisted
audit output. Fixture policy pins are synthetic test inputs, not native evidence.

## Next qualifying work

1. Establish actual native executable identities and the complete writer paths,
   including reset/startup handlers and spawned helpers. Do not run reset/password
   mutations merely to find them.
2. Review a coordination mechanism covering every writer and already-open
   descriptor, with bounded failure behavior and preserved pinned management.
   Service-script stop functions are not currently proven to do this. A fresh
   hash-before-rename is still insufficient.
3. Implement and qualify guarded staging, metadata preservation (private modes),
   durable journal/readback and crash/recovery behavior under that mechanism.
4. Revalidate current private inputs/collisions and obtain exact operation
   approval before any native role installation. Keep the completed private
   baseline/plan unchanged unless fresh planning is explicitly needed.

No new accounts, listeners, keys, service changes, reset, reboot or flash occurred.
Native SFTP authentication and recipient persistence/recovery remain separate
release gates.
