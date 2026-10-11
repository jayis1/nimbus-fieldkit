# Upload/busy loader: CSS-only candidate

The user requested a better-looking upload loading wheel. The appended first-party styles in `device/unified/stock-dark.css` replace the compact vendor status card's GIF visually with a CSS ring, add a rounded theme-aware card, improve Cancel/focus styling, and position it within narrow viewports. Reduced-motion preference disables ring animation and button transitions. No external fonts, animation libraries or network assets are added.

The exact original stylesheet prefix is preserved; the patch only adds selectors scoped to `#div-short-block-msg` and its containing blockUI message. The original title (`#hTitle2`), Cancel button (`#btnMessageCancel2`) and vendor upload/cancel/completion handlers remain untouched. Hidden-state behavior is preserved: CSS does not force a display mode onto a hidden card. The same compact card may appear for other vendor busy operations with their own titles; it is not labelled unconditionally as an upload. The ring is **indeterminate**: the legacy uploader reports no reliable byte-progress percentage, so none is invented.

Prepared package: `build/nimbus-upload-loader-ui-r1.tar`, SHA-256 **`ac85292309d70599f91ea84584933536847c34c24a5732f0a07f32bcd0226b3f`**.

- Target: `/nimbus/data/fieldkit-v06/stock-dark.css` only.
- Expected live hash: `d1428615bd883030f5d11089aeb4a802eb0ca448c588e076baa9db53ac700164` (independently HTTP-verified before preparing the install).
- Patched hash: `232c5a167045871adb8282e59b097378d27589d60953c6b6daf4a9afb6068459`.
- Fresh private root stage: `/root/nimbus-upload-loader-r1`, root:root mode 0700.

`scripts/package-upload-loader.py` reuses the reviewed single-asset baseline/backup/atomic replace/guarded rollback policy from `scripts/package-flash-warning-fix.py`, specializing only the target, hashes and messages. It refuses a changed baseline, prior install attempt or later rollback edits. Original CSS is kept in the private stage's `backups/stock-dark.css`. Partial failures require review, not blind reruns. The package contains only first-party CSS/installer/metadata; no vendor homepage/controller, credentials or media.

Install is a separate explicit user-run rootfs CSS write, not flashing. It leaves the homepage, HTML5 Music adapter, patched Flash-warning controller, Settings bridge, services, SSH keys/listeners, mounts and upload transport unchanged. Do not perform the older Settings-CSS rollback over this later style update; its own later-edit guard should refuse that combination. No installation has yet occurred.

## Validation

**138 tests run: 136 pass, 2 Node-dependent skips.** Installer fixtures verify exact-prefix preservation, install/private backup/rollback and refusal to overwrite later styling. The local browser fixture exercises actual vendor blockUI methods with a simulated upload title and callback: it checks old-GIF hiding, CSS ring, Cancel callback and hidden-state restoration, light-theme ring color, normal completion/unblock, desktop and narrow viewport fit, and reduced-motion static ring. It performs no actual media upload or device request. Navigation, Settings and HTML5 Music regression checks pass in the same fixture.

Physical upload visuals and real success/failure/cancel transitions remain pending. A new unified/image build uses the updated stylesheet, but existing v4 images were not rebuilt. The previously installed audio and Flash-warning patches remain separate live UI changes; consistent capture/recovery gates are unchanged.

## r1 live overlap and r2 correction

The user reported that the bottom of the loader was behind the file-name/date/type/size header. Independent read-only HTTP verification confirmed that the served CSS was the exact r1 hash above, establishing that r1 is installed, not merely prepared. This is a visual failure, not successful full upload validation.

Vendor layout puts the busy message inside `#searchContainer .top` (`overflow:hidden`) and wraps `#searchContainer` in a separate fixed-position element. That outer element establishes its own stacking context; raising just the inner message/header does not escape it. r2 appends CSS scoped to the presence of the loader: it lifts that containing fixed layer, lifts the header/message, and makes the relevant header overflow visible. Normal stacking/clipping is restored when blockUI removes the message. No elements are reparented by the fix and no JavaScript/cancel handler is replaced.

Prepared correction: `build/nimbus-upload-loader-ui-r2.tar`, SHA-256 **`fde929480639cdab834de805adb937e92b82d6c8612ff3c45db5c5a76ac8ee22`**. Expected baseline is the installed r1 CSS `232c5a167045871adb8282e59b097378d27589d60953c6b6daf4a9afb6068459`; corrected CSS hash is **`8fda6af14c301ffae5146afa4be8f9bda1164598c00637e92c10afe7651abf98`**. `--from-r1` packaging enforces the exact r1 prefix and uses a separate private root stage `/root/nimbus-upload-loader-r2`, preserving r1 staging/backups. Whole-archive verification must precede extraction; installer verifies the live r1 hash before replacing only the stylesheet. Do not reuse the r1 stage or loosen a mismatch guard.

Validation: **139 tests run, 137 pass, 2 Node-dependent skips**. The browser regression overlays a file-header fixture at z-index 9999 over the lower part of the card. Hit-testing confirms the Cancel button and both lower card corners are unobscured, including in the narrow/reduced-motion run, and verifies both containing stacking levels return to their normal values after cancellation. The earlier inner-only fix failed this test; the outer-layer correction passes. Actual device r2 installation and visual confirmation remain pending. No service stop, remount or firmware flash occurred.

Subsequent read-only HTTP checks during [percentage preparation](UPLOAD-PERCENTAGE.md) confirmed that the exact r2 stylesheet is now served. User visual confirmation remains pending. The requested percentage requires a separate XHR transport adapter, not a fake percentage added to this indeterminate CSS ring; that guarded upgrade is prepared but not yet installed.
