# prebeta experiment

Tag: `v0.1.0-prebeta-experiment.1`

**EXPERIMENTAL — NOT FLASHABLE.**

## Subsequent image-distribution authorization

After the initial source-only release, the owner explicitly authorized attaching
the generic beta3 rootfs candidate publicly. This changes distribution scope,
not technical readiness or vendor licensing status. The existing tag remains
unchanged; this follow-up is documented on `main` and in updated release notes.

Public image: `nimbus-beta3-generic-NOT-FLASHABLE.ext3.candidate`,
**268435456 bytes**, SHA-256
`d49d9d095f452c91297dfbaf4ad7f5cab4fbcc3ce761c51d89c9ee43b859da00`.
It contains vendor rootfs/components; their redistribution rights have **not**
been verified. It is not covered wholesale by the first-party source license.
The private provisioned image, vendor-derived UI update archives, live backups,
credentials and user media remain excluded.

The generic build imports no personal provisioning. Before attachment, complete
artifact integrity checks, another read-only filesystem check, an archive scan
of 3178 regular files for sensitive paths/PEM private-key markers, a raw-image
PEM-marker scan and selected ext3/archive comparisons passed. The actual ext3
provisioning directory contains the no-keys notice, not authorized/host keys.
These checks are not an exhaustive secret audit or a boot/security certification;
stock vendor accounts/legacy services still require review.

Key-only management requires separately reviewed unique provisioning; generic
SSH cannot start as-is and Telnet is disabled. No updater wrapper, deployment
command, guaranteed recovery, persistent dual-writable-SD policy or hardware
qualification is supplied. Do not flash this image.

The physical SanDisk image/features and companion access to a user's physical
drive are outside the Virtual Nimbus paywall. Only the companion's delivered
Virtual Nimbus toolkit uses its one-time unlock; this release changes no app or
billing code and does not turn roadmap features into delivered functionality.

## Original source-only release scope (historical)

This prerelease is for source review, offline fixtures and development. It is
not an installable SanDisk firmware update and does not authorize a live-device
trial. Do not feed source archives or locally generated ext3 candidates to the
vendor updater, rescue, `dd` or a USB flasher. Bricking/data-loss risks remain;
recovery is not guaranteed.

## Included

- First-party FieldKit source, optional integrations, build tools and tests.
- Original-homepage integration, HTML5 Music support and genuine upload progress.
- Nib stays visible during mobile uploads; cached geometry and fewer duplicate
  Settings/progress DOM writes reduce browser work.
- Guarded UI-update builder with exact-version checks and rollback that refuses
  later edits. Its generated vendor-homepage archive is **local-only**, not a
  public release asset.

## Excluded

No vendor firmware/rootfs, generated images, vendor-derived UI packages,
credentials, SSH keys, provisioning material, backups or user media are attached.
Generic and private beta3 images remain local. Key removal does not establish
vendor redistribution rights.

## Evidence and limits

The local development suite ran 204 tests: 202 passed, 2 skipped. This includes
local-only artifacts and later trial fixtures that are not all in this tag;
source-only archive testing can skip private-artifact/browser dependencies.
An independently extracted clean release-source snapshot ran **168 tests:
149 passed, 19 skipped**, with no failures. Skips cover unavailable private
artifacts and dependencies; they are not hardware qualification.
Local beta3 candidates passed filesystem/integrity checks, **not native boot or
recovery qualification**. Installed dashboard observations do not qualify a
candidate image or demonstrate higher upload/download throughput.

Consistent current rollback capture, independently verified recovery, safe
deployment container, native hardware tests and vendor licensing remain release
blockers. Persistent dual-writable-storage policy and companion roadmap features
are not delivered merely by this prerelease. See
[production readiness](PRODUCTION-READINESS.md),
[beta test plan](BETA1-TEST-PLAN.md) and [UI performance](UI-PERFORMANCE.md).
