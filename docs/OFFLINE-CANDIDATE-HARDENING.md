# Offline candidate v4 hardening — NOT FLASHABLE

Current generic output: `build/nimbus-custom-rootfs-candidate-v4/`.
Current private per-device output: `.private-provisioning/drive-a-rootfs-candidate-v4/`.

Both are 256 MiB ext3/rootfs-tar research candidates, not vendor update packages. The user has no spare drive; serial/UART recovery has not been established. Native boot, matching restoration and safe deployment remain blocked. No new live runtime, boot-hook, service, SD policy or firmware change was performed by this hardening work.

## Boot-time code/data separation

Earlier candidate startup executed the snapshot publisher from exported user media. That is an unsafe boot-time trust boundary: a media-resident script can be replaced independently of the rootfs. v4 invokes only `/opt/nimbus/native/nimbus-dashboard.sh`, which in turn uses its rootfs-resident settings helper and awk encoder.

`NIMBUS_DATA_DIR` selects the existing media directory for flags, vault inventory and published JSON. It does **not** select executable helpers. Data-directory symlinks and symlink path components are rejected. Snapshot output stays at the original unified-page URL, preserving the vendor homepage integration.

The startup publisher skips active USB export, wrong storage source, absent media and read-only storage. Existing toolkit files/settings are not overwritten. These are selected shell guards, not a proof that all races with the vendor USB state machine have been eliminated. Native boot/transition tests are still required. Rootfs-resident means root-controlled, not cryptographically immutable or a read-only root filesystem.

Manual execution of old media-resident tools remains a separate trust consideration; the agent has not updated the installed runtime or asserted that legacy HTTP/FTP is secure.

## Fail-closed SSH provisioning gate

- `/etc/nimbus` must be a non-symlink root-owned 0700 directory.
- Host key and authorized-key files must be nonempty, non-symlink regular files, root-owned 0600.
- The packaged Dropbear key utility must accept the host key before startup launches the wlan1-only key-auth listener.
- Wrong permissions are rejected, not silently repaired by root `chmod` through an untrusted path.
- Generic images still contain no SSH keys. Private images retain their separately generated per-device identity and must never be publicly redistributed.

File/host-key checks do not establish native login, entropy at generation, authorized-client reachability, reset safety or Wi-Fi provisioning. Existing legacy vendor accounts/services remain a separate release blocker.

## Archive and overlay boundaries

The builder rejects absolute/traversing/noncanonical names, duplicate normalized names, descendants under non-directory nodes, unsupported device/FIFO nodes and unsafe hardlink targets. Reading archive headers is bounded to 10,000 nodes, 32 MiB per node and 256 MiB total declared contents; policy-audit input is a regular file no larger than 512 MiB. These limits fit the reviewed vendor rootfs, not arbitrary third-party distributions.

Overlay writes independently validate contained canonical names. Digest inputs must be regular files, not symlinks/devices, and outputs under `/dev`, `/proc` or `/sys` are refused. Prior output directories are never overwritten. The stock rootfs and ARM SSH binary remain hash-pinned.

## Policy report and provenance

`scripts/rootfs-policy.py` reads tar contents without extracting or executing them. Selected checks cover Telnet retirement, locked root password, removed vendor SSH host keys, key distribution/modes, rootfs boot publisher, management binding, WPA2 default and unified Settings assets. It always reports production/flash authorization false; substring checks are not a complete semantic security audit.

The builder adds `ROOTFS-POLICY.json`, compares the entire regular-file module inventory/hashes with the reviewed vendor archive, and records exact overlay source hashes, previous UI lineage hash and artifact checksums in its manifest. Private-key content is never printed by these reports/tests. Mode checks are static metadata evidence; native login and filesystem behavior remain untested.

Example read-only checks:

```sh
python3 scripts/rootfs-policy.py build/nimbus-custom-rootfs-candidate-v4/rootfs.tar
python3 scripts/audit-image-readiness.py build/nimbus-custom-rootfs-candidate-v4
```

The readiness command exits 2 when integrity passes but release remains blocked. Use `--private` with the rootfs-policy checker only for private per-device archives. Do not upload the private archive, image, tree or provisioning bundle.

## SD policy decision

Live bounded writes, reboot readback and both normal/writable-SD USB cycles have passed on the installed firmware. Boot and USB return still restore SD ro. v4 deliberately preserves that vendor policy; it adds no forced block-write override, automatic rw remount, format or repair. A persistent writable policy remains separate work and must respect detected locks, exclusive ownership, startup/return transitions and capability gating.

## Recorded v4 artifacts

| Image | SHA-256 |
| --- | --- |
| Generic `rootfs.ext3.candidate` | `2039710a11a5882fdee7ddf89dee6ad21b4f2e68563aed25b5d85677898726de` |
| Private per-device `rootfs.ext3.candidate` | `49955af6d480c445cc94a4fb5920c16e93a152c90bc86cf44374b8ec462cf6b1` |

Both builds passed the offline policy checks, vendor module comparison and read-only e2fsck. Archive/image selected-file consistency is covered by local regression tests. Read-only image inode checks independently confirmed root ownership/modes for the boot script, SSH binary, publisher/settings helpers, encoder and provisioning directory/files. **106 local tests pass**, including hostile mutable-script fixtures, key-permission/host-key refusal, archive aliases/budgets and generic/private v4 image consistency. Generic/private builds and prior candidates stay local; no vendor update wrapper was generated or approved.

Earlier v1/v2 and intermediate v3 outputs are retained as research history, not current delivery candidates. In particular, do not deploy an earlier image to bypass the new boot-time code/data boundary. Existing public source-preview archives remain tied to their published earlier commits; they have not been silently replaced.
