# Shareable Nimbus replacement firmware — requested release scope

## Owner request

Build a complete replacement firmware for other owners of the **SanDisk Wireless
Media Drive**, incorporating the Nimbus additions from this project. This records
the requested deliverable, not a completed firmware build or permission to flash,
publish private artifacts, or treat unresolved vendor rights as established.

The owner subsequently reaffirmed accepting single-drive experimental risk and
requested checkpoints with the existing hardware. A spare is not a prerequisite
for preparing/testing within approved scope; see the
[single-drive evidence ledger and next read-only checkpoint](SINGLE-DRIVE-QUALIFICATION.md).
Exact firmware writes still require review, and failed-boot recovery is not promised.

Do not substitute a screenshot, source overlay, private drive clone, or renamed
rootfs image for the requested installable firmware.

## Current artifact and fresh audit

Latest follow-up: [64 GB-targeted beta5](FIRMWARE-64GB-BETA5.md) includes current
dashboard/battery sources and passed offline integrity/policy tests. It remains
rootfs-only, NOT FLASHABLE, not the complete installable firmware requested.
No redistribution, recovery or native feature gate was cleared by building it.

At the initial request checkpoint, the latest generic rootfs was
`build/nimbus-custom-rootfs-beta3/rootfs.ext3.candidate`: 256 MiB, recorded SHA-256
`d49d9d095f452c91297dfbaf4ad7f5cab4fbcc3ce761c51d89c9ee43b859da00`.
It is not a full disk or vendor update package and does not contain every later
source change. Retain it unchanged as historical evidence.

At this request's checkpoint, running
`python3 scripts/audit-image-readiness.py build/nimbus-custom-rootfs-beta3`
returned exit 2: **integrity verified, production false, flash authorization
false**. Reported blockers: per-device provisioning, native image boot, recovery,
deployment container, candidate SD/USB policy, GameHack pairing, vendor rights and
legacy-service/account/reset review. No device access or firmware write occurred.

Earlier public experimental distribution of generic beta3, recorded in
`BETA1-TEST-PLAN.md`, does not establish installation safety or redistribution
permission. A public download must not be promoted to a supported firmware release
on that basis.

## Release contents and boundaries

Rebuild from reviewed clean inputs and first-party sources, not a snapshot of the
owner's running drive. Maintain a per-feature source/hash and native-test manifest.

| Feature | Release treatment |
| --- | --- |
| Unified vendor/Nimbus homepage, themes, toolbox and Settings sign-in fix | Include current reviewed sources; retest in newly booted image |
| HTML5 music, upload progress/cancel, warning removal and layout fixes | Include; retain real backend response/error semantics |
| Nib desktop buddy and UI performance fixes | Include; validate narrow screens/reduced motion |
| FieldKit/native agent, snapshots and independent feature switches | Include reviewed runtime; no unauthenticated arbitrary-command API |
| Key-only Dropbear management | Include reviewed binary/startup, unique per-device identity and explicit enrollment; no shared admin key |
| SD diagnostics and companion-status | Include current read-only helpers; observations do not certify pairing or writable policy |
| Restricted SFTP for GameHack browsing | Release gate, not currently working firmware functionality; require native runtime/auth/jail/denial/USB-lifecycle qualification |
| GameHack SanDisk browser | Separate handheld application; handoff is in the GameHack project, not an ARM application installed on SanDisk |
| Persistent writable SD policy | Not implemented by temporary remount results; preserve safe ownership/lock behavior until separately qualified |
| Recovery/handover/restoration trial helpers | Development tooling, not default boot actions or user-facing automatic maintenance |
| Mobile companion, new radio roles and other planned features | Do not advertise as implemented |

The local OpenSSH runtime `build/nimbus-sftp-runtime-v1/` and inactive config-v2
are candidates only. Linux 2.6.35 requires the reviewed weaker rlimit/select
approach instead of modern seccomp; static binaries lack PIE/ASLR. Do not describe
the complete firmware as a modern security replacement for its legacy kernel.

## What “complete replacement” should mean

Deliver an installable, validated firmware package for an explicit hardware and
installed-bootloader compatibility matrix—not a whole-MMC clone of this drive.
Preserve the recipient's partition geometry, settings/calibration, bootloader,
rescue, Wi-Fi NVS and user media through a reviewed installation path. Retain
compatible kernel/modules unless a replacement receives its own qualification.
Do not presume different capacities/revisions or Wireless Stick/Flash Drive models
are compatible; presently this project's owner drive is the only native reference.

Updating OS contents does not require distributing another owner's boot regions,
settings or media. If the reviewed installation format needs additional firmware
components, obtain clean, licensed inputs and explicitly qualify those writes.
Normal USB media mode is not a proven system-flashing interface.

## Fresh owner setup and privacy

- No personal media, backups, captures, serial-specific configuration, logs,
  passwords, Wi-Fi secrets, host private keys or preauthorized owner clients.
- Never distribute `.private-backups/` or `.private-provisioning/` contents.
- Provide a reviewed first-use enrollment route before disabling all recovery
  access. Current generic SSH cannot start without provisioning while Telnet is
  disabled; this is a release-blocking usability/access problem, not a setup flow.
- Generate unique host identities per recipient with validated entropy and
  persistence. Design secure initial fingerprint delivery and dedicated client
  key enrollment; no shared factory management identity or password.
- Require recipient-selected Wi-Fi security and secrets. Check settings/account
  synchronization and factory reset behavior so reset cannot silently restore
  shared credentials or unexpectedly enable Telnet.
- Public file shares remain a distinct privacy boundary; SSH alone does not make
  retained HTTP/FTP services private. Document actual exposure and access policy.

## Ordered work before an installable build/release

1. **Freeze inputs/inventory:** identify the exact latest first-party sources,
   clean vendor rootfs/kernel dependencies and reviewed ARM binaries. Record
   licenses, hashes, ABI/runtime checks and installed-versus-staged feature status.
2. **Recovery and capture:** establish a consistent restoration input and verified
   recovery access for the test drive. Existing checksum-verified live raw backups
   are not by themselves consistent or restore-tested recovery images.
3. **Native file-service qualification:** complete the separately approved
   version/probe trial, then authenticated non-root read-only SFTP and USB-safe
   teardown. Do not enable experimental listeners or bind mounts merely by baking
   them into an image.
4. **First-use provisioning:** implement/test fresh identities, enrollment, Wi-Fi
   setup, persistence, resets and failed/interrupted setup without public secrets
   or a permanently inaccessible generic device.
5. **Safe installation design:** reject unchanged vendor programming/hooks. Review
   target validation, prior rescue side effects, failure reporting, power loss,
   settings/calibration preservation, write readback and actual recovery. Existing
   rescue can repartition before package hooks and ignores some hook/write failures;
   an added installer cannot retroactively veto these effects.
6. **Build a new offline candidate:** use a new output name, integrity/privacy/
   ownership/module audits, regression tests and conservative filesystem settings.
   Unresolved gates keep it explicitly NOT FLASHABLE; do not attach an updater
   wrapper merely because its CRCs parse.
7. **Approved native trials:** exact artifact/operation approval, stable power,
   known recovery limitations, boot/vendor-function/storage/USB tests and successful
   restoration. Include recipient-style first-use tests and GameHack browse/download
   against controlled fixtures; retain sanitized results.
8. **Redistribution and publication review:** establish applicable vendor binary
   rights, third-party notices/source obligations and an explicit tested hardware
   matrix. Publish only the generic qualified package with checksums, provenance,
   installation/recovery instructions and known limitations. Publication is a
   separate action, not automatic authorization from this release request.

Vendor redistribution remains unresolved. If a self-contained firmware cannot
legally be shared, offer a first-party local builder taking the recipient's lawful
vendor input; clearly identify that alternative as a builder, not the requested
ready-to-flash image. Do not bundle private or unlicensed inputs to work around it.

## Outcome of the initial scope checkpoint

Release scope recorded and existing beta3 integrity freshly audited. **No new
complete firmware image was generated**, no flash/updater invoked, no device
configuration changed and no asset published. The next engineering work is to
resolve recovery, native runtime and first-use provisioning—not relabel beta3.

## Follow-up: generic beta4 built offline

The owner's subsequent “continue” instruction led to a new clean-input rootfs
build, not an installation or publication. New artifact:

- `build/nimbus-custom-rootfs-beta4/rootfs.ext3.candidate`
- Size: **268435456 bytes (256 MiB)**.
- SHA-256: `69608cc1d1a4a1fc57d727e93bcb2e34078468b0acfa651fde7ea4f95553bef8`.
- Rootfs archive SHA-256:
  `dfebde7bc381c9ad6d5227aaa3e56dc7c3d6f0ed8de1b27794a5dbe65e00e952`.

This remains a **rootfs-only, NOT FLASHABLE** candidate, not the complete firmware
package requested. All earlier candidates and private provisioning remain intact.

### Inputs and actual additions

The unchanged local vendor `.img` was hash-verified before copying its filesystem
payload to a new local review workspace. Read-only host `debugfs dump` retrieved
the logical clean stock rootfs archive; its exact pinned hash matched the builder.
The management binary was read from beta3's archive and independently matched the
builder's pinned hash before reuse. Neither vendor scripts nor ARM binaries were
executed. No private device snapshot was used as the rootfs input.

The existing first-party builder ran under fakeroot. It included the latest
companion-status helper/documentation, companion-capable native agent and improved
SD diagnostic, alongside beta3's existing homepage/music/upload/Nib/performance
sources. Management startup and vendor SD read-only default remain unchanged.
Experimental SFTP runtime/configuration, accounts, enrollment and USB bind views
are **not installed or enabled** in beta4. The retained separate GameHack library
source bundle is an earlier staged bundle; it does not contain the newly requested
browser implementation, which remains a handoff rather than a working app.

No owner private keys, client enrollment, Wi-Fi settings or live media were
imported. Known key exclusions and rootfs selected-file policy passed; this is not
an exhaustive vendor credential/privacy audit or a fresh-owner setup solution.

### Repeatable inventory and validation

New tool: `scripts/inventory-firmware-release.py`. It checks bounded regular
candidate/source inputs without extraction or device access, compares allowlisted
source hashes with archived payloads and build provenance, and models the exact
v06 bridge path substitution. It rejects private manifests, known per-device
enrollment/host keys, unsafe archive paths and hash mismatches. Optional JSON
reports are exclusively created at mode 0600; no overwrite or firmware output.
It always retains false production/flash flags regardless of manifest claims.
It is a selected archive inventory, not a complete filesystem/secret/native audit.

Reports retained separately from immutable builds:
`build/nimbus-release-inventory-v1.json` (initial beta3 inspection) and
`build/nimbus-release-inventory-v2.json` (beta4). The initial beta3 report predates
modeling the bridge substitution; that difference was reviewed as expected, not
a missing UI patch. Beta4's 12 selected feature payloads and four build-source
records are current; `source_rebuild_required` is false **only for this checked
set**, not evidence that every planned feature is implemented.

```sh
python3 scripts/inventory-firmware-release.py --candidate build/nimbus-custom-rootfs-beta4
python3 scripts/audit-image-readiness.py build/nimbus-custom-rootfs-beta4
```

Both return **2** for a valid but release/flash-blocked candidate. Builder fsck,
module preservation and selected rootfs policy passed. Twelve new tests passed,
including all 12 feature files read directly from the ext3 image via read-only
debugfs and independent `e2fsck -f -n` (exit 0).

Full regression after fixing the native transfer server's exact allowlist for the
new companion bundle: **263 tests run, 259 passed, 4 skipped**. The new allowlist
accepts the complete reviewed file set, not arbitrary scripts or a partial bundle.
Skipped: two Node checks, unavailable trusted host Dropbear key utility, and an
older candidate-v1 vendor comparison tied to a removed temporary input path.
Beta4's builder independently verified clean vendor module hashes.

Initial ordinary `/tmp` fixture execution failed because some older tests rewrite
absolute paths sequentially, recursively replacing `/tmp` inside prior rewritten
paths. Using the workspace path as TMPDIR also failed because those fixtures do
not quote paths containing spaces. The successful full run used a temporary
private no-space path under the owner's cache directory, removed after the run. **No
production safety check was disabled to obtain the pass.** These fixture
portability defects remain follow-up test-infrastructure work; do not describe
plain default discovery as passing in this environment.

Build/review workspace: `/tmp/opencode/nimbus-release-build-f463izfi/`; selected
build and regression logs retained there. Generated image has its own manifest,
checksums and NOT-FLASHABLE warning. Nothing was flashed or published. Next work
remains consistent recovery, qualified file-service runtime and recipient setup,
followed by reviewed installation and license permissions.
