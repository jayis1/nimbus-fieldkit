# Nib — decorative desktop buddy

Original first-party floppy/robot character in the original dashboard's bottom-left corner. Bounded pupils follow mouse pointer position, coalesced through requestAnimationFrame; no timer-driven loop, AI service, external asset, telemetry, networking or mouse history. This is not Clippy artwork or a chat assistant. Coarse/touch pointers and reduced-motion settings keep the eyes still. Pointer leave, blur and hidden-tab transitions reset the gaze.

Shadow DOM keeps styling isolated. Artwork is decorative; the dismiss button has an accessible name/keyboard focus. Pointer events pass through except on that button. The mascot stays above the visible music bar and hides on narrow screens while the upload card is mounted. Theme changes follow the dashboard's light/dark attribute.

Dismissal persists only as a local `nimbus-mascot-hidden-v1` preference. **Show / hide buddy** in the existing global controls restores it. Dismissal removes listeners/observers and cancels the pending frame; reopening creates a fresh instance. Storage-unavailable browsers retain session functionality without claiming persistent preference. No uploads/music/Settings/device API handler is replaced.

## Guarded live UI candidate

`build/nimbus-mascot-ui-r1.tar` SHA-256: `fad576be49d97540f6d1d4949eb88e4279677e3abe070ce80550530d842c0efb`.

Prepared by `scripts/package-mascot-ui.py` from the exact retained upload-progress homepage, independently verified as currently served. The package guards homepage baseline `cef815fab959980289889a2fb99a0bb9619617d1052bdbd860850699f0491410`, installs additive `/nimbus/data/fieldkit-mascot-r1/mascot.js`, and inserts a single reference **after the existing bridge**. New homepage hash: `c5247236d5ed0a5b09076bf34523807cd39f4738a194f87cee8fc533103a4d9a`; mascot script: `67caede08756eb58afeb5c86d76ba354577590c40109746eef77dbe32e629d2f`.

Separate fresh root-owned 0700 private staging `/root/nimbus-mascot-r1`; verified homepage backup/atomic replacement and later-edit rollback refusal reuse the reviewed audio-package policy. No CSS, old adapters, services, keys, mount state, partition or firmware changes. Whole archive verification precedes extraction. Do not bypass guards or rerun partial staging. Older homepage rollbacks will intentionally refuse this later edit. The archive contains a vendor-derived homepage and stays local; publish only first-party source. Live installation/visual acceptance is pending.

## Validation and image lineage

150 tests run, 148 pass, 2 Node-dependent skips. The virtual-time Chromium regression uses deterministic frame scheduling because dump-dom does not guarantee compositor frames; checks cover gaze/reset, mobile upload hiding, music clearance, themes and persistent dismiss/restore alongside Music/upload/Settings regressions. A separate localhost-only Playwright/native Chromium run **with real requestAnimationFrame** passed gaze direction/bounds, theme/music clearance, dismissal across reload, restoration, reduced-motion static eyes and mobile upload hiding. Native Firefox/phone rendering remains pending. Installer fixtures test scope, install/rollback and later-edit refusal.

Full-suite host runs initially blocked in installer fixture `sync` calls, which flush unrelated host workloads. The successful full suite used a host-only PATH shim for fixture sync; production/device installers retain real sync. These fixtures do not certify device durability. No unrelated host data was deleted.

Future unified/image builds include `mascot.js` after the bridge and record its source hash. Fresh **beta2** generic/private images now include it; beta1 and all earlier image artifacts remain unchanged. See [beta test plan](BETA1-TEST-PLAN.md). No firmware boot, flash, recovery boot or service handover occurred.
