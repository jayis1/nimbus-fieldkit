# Wireless Media Drive 64 GB — beta5 engineering checkpoint

**Not the requested complete installable firmware. NOT FLASHABLE.** The target
is the SanDisk Wireless **Media Drive** with advertised 64 GB internal storage,
not Wireless Stick/Flash Drive. Capacity is owner-specified build intent, not
measured recipient geometry or qualification of other 64 GB units/revisions.

## Implemented in this batch

- Native dashboard independently starts the read-only vendor battery query when
  homepage controls are absent. A shared singleton prevents duplicate polling.
  Explicit dashboard refresh also requests a bounded battery refresh.
- Native package ships `dashboard/battery.js`. The image keeps its existing
  unified-only homepage, whose battery asset is included separately. No second
  standalone dashboard entry point is installed in the image.
- Browser fixtures cover standalone and shadow-DOM Overview with missing
  snapshots, absent header controls and vendor `100/full` responses. Both show
  `100% / Full · device API`; snapshot availability is not battery availability.
- Invalid/refused/unavailable readings still become Unknown; old measurements
  are not invented or relabelled current. Raw shell snapshots remain sysfs-based;
  they can legitimately have null battery capacity while the browser API works.
- Builder has an explicit `--target sandisk-wireless-media-drive-64gb` profile.
  This does not resize the rootfs to 64 GB or write media/partition/boot regions.
- Release inventory now checks the battery source against archived contents.
  Historical beta4 tests compare its image to its immutable archive, not newer
  working-tree files; beta5 additionally compares the image to current sources.

## Native observation, not a new deployment

Fresh headless Chromium loaded the existing live homepage at
the drive's `#overview` page and rendered `Battery: 100% · Full`.
Evidence: `/tmp/opencode/dashboard-live-9qscu6_h/dom.html` and `stderr.log`.
The live toolkit host reported unavailable snapshot telemetry, with no integration
error element. This DOM dump proves the live header reading, not shadow-DOM
Overview contents or another user's browser/cache. The new standalone-source
fixes are included in beta5, **not installed on the drive**. Prior UI r1 remains
installed; no additional device staging, service, USB or mount action occurred.

## New retained offline candidate

Directory: `build/nimbus-custom-rootfs-64gb-beta5/`

- `rootfs.ext3.candidate`: 268435456 bytes (256 MiB).
- Image SHA-256:
  `fbe281697b37a1bc453e8f7fd45d10217083934793bce1440d0b6f923c5c6b5f`
- Archive SHA-256:
  `70aa4be20f2db812bb504b75e8f6ab6eb8bb9c800018ef3184ae7af68be08853`
- Clean vendor archive and management binary were hash-pinned before building.
  No private drive clone, personal keys/enrollment, Wi-Fi settings or media were
  imported. Vendor modules matched the clean input byte hashes. This selected
  privacy/policy audit is not an exhaustive vendor-account or licensing audit.
- Offline filesystem check, archive policy and image/archive feature-byte checks
  passed. Full integrity audit returned verified integrity but **production false,
  flash authorization false**, with eight unresolved gates.

Build invocation (historical; output already exists, do not rerun into it):

```bash
fakeroot python3 scripts/build-custom-image.py \
  --stock-rootfs /tmp/opencode/nimbus-release-build-f463izfi/rootfs_nimbus_v3.04.tar \
  --ssh-binary /tmp/opencode/nimbus-release-build-f463izfi/dropbearmulti \
  --target sandisk-wireless-media-drive-64gb \
  --output build/nimbus-custom-rootfs-64gb-beta5
```

## Work that cannot be labelled “all features ready”

Existing source has opt-in network health, bounded watchdog, storage warnings,
verified single-file copies, pre-encrypted archive storage, docs, and conditional
iperf/Git helpers. A saved ON flag is not a running feature or dependency install.
Absent media is not fixed by creating `/mnt/storage` or overriding USB ownership.

Remaining work includes recipient enrollment/entropy/Wi-Fi/reset semantics,
restricted non-root read-only SFTP native qualification, verified A/B integration,
consistent capture/recovery, a preservation-safe installation container, native
boot/storage/USB testing, legacy service/account review and redistribution rights.
Wardriving GO still needs session/location endpoints, phone permission handling,
radio capability/coexistence qualification and A→B dispatch; no GO session or
monitor-radio service is enabled by this image.

The eight readiness gates and SFTP/GO engineering are substantial separate work,
not cosmetic Unknown labels. No firmware flash, raw capture, provisioning or
publication is authorized merely by the model profile or this build.

## Tests

64 scoped tests passed, one skipped: 28 dashboard/battery/package, 22 firmware
inspection/inventory/target, five unified UI and nine historical custom-image
checks. One historical vendor comparison skipped because its old input path was
absent; beta5's builder independently verified its clean vendor-module hashes.
`git diff --check` passed. Full workspace regression was
not run; these tests do not establish hardware boot, power-loss safety, recipient
setup or implemented wardriving.

## Frozen-scope follow-up

The owner froze feature additions until existing scope is implemented and
confirmed: [frozen scope/acceptance ledger](FIRMWARE-FEATURE-FREEZE.md).
The previously skipped historical vendor-module comparison now accepts an
explicit `NIMBUS_TEST_STOCK_ROOTFS` path and verifies the pinned clean input hash
before comparing modules. Rerunning all ten custom-image tests against the
available reviewed archive passed with **zero skips**. Earlier counts above
remain the historical checkpoint, not an unrepeated full-suite pass.

Subsequent [media ownership fixes](MEDIA-OWNERSHIP-GUARD.md) are source-only and
not contained in this immutable beta5. Inventory now correctly reports rebuild
required. Image/archive checks continue to validate beta5's retained bytes rather
than pretending it contains new source changes.
