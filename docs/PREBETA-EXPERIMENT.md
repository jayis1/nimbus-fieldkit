# prebeta experiment

Tag: `v0.1.0-prebeta-experiment.1`

**EXPERIMENTAL — SOURCE/OVERLAYS ONLY — NOT FLASHABLE.**

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
Local beta3 candidates passed filesystem/integrity checks, **not native boot or
recovery qualification**. Installed dashboard observations do not qualify a
candidate image or demonstrate higher upload/download throughput.

Consistent current rollback capture, independently verified recovery, safe
deployment container, native hardware tests and vendor licensing remain release
blockers. Persistent dual-writable-storage policy and companion roadmap features
are not delivered merely by this prerelease. See
[production readiness](PRODUCTION-READINESS.md),
[beta test plan](BETA1-TEST-PLAN.md) and [UI performance](UI-PERFORMANCE.md).
